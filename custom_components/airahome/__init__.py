"""The Aira Heat Pump integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from functools import partial

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    BLE_CONNECT_TIMEOUT,
    CONF_CLOUD_EMAIL,
    CONF_CLOUD_PASSWORD,
    CONF_CERTIFICATE,
    CONF_DEVICE_UUID,
    CONF_MAC_ADDRESS,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN
)

from .coordinator import AiraDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.WATER_HEATER] # TODO  Platform.CLIMATE


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Aira Heat Pump component."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aira Heat Pump from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Get stored data
    mac_address = entry.data.get(CONF_MAC_ADDRESS)
    
    _LOGGER.info("Setting up Aira Heat Pump integration for device at %s", mac_address)
    
    # Import the library in executor to avoid blocking the event loop
    # (protobuf imports are heavy and trigger blocking import warnings)
    try:
        def import_and_init(hass):
            """Import AiraHome and initialize instance."""
            from pyairahome import AiraHome
            return AiraHome(ext_loop=hass.loop)
        
        _LOGGER.debug("Initializing AiraHome instance")
        aira = await hass.async_add_executor_job(import_and_init, hass)

    except ImportError as e:
        _LOGGER.error("Failed to import pyairahome library: %s", e)
        raise ConfigEntryNotReady("pyairahome library not available") from e

    # Connect library logger to Home Assistant's logging system
    # This ensures pyairahome logs use HA's log level
    lib_logger = logging.getLogger("pyairahome")
    lib_logger.setLevel(_LOGGER.level)

    # Setup cloud authentication and BLE connection
    try:
        # Check if we have cloud credentials in config entry
        # These would be stored during initial setup
        cloud_email = entry.data.get(CONF_CLOUD_EMAIL)
        cloud_password = entry.data.get(CONF_CLOUD_PASSWORD)
        certificate = entry.data.get(CONF_CERTIFICATE)
        device_uuid = entry.data.get(CONF_DEVICE_UUID)

        if not device_uuid:
            _LOGGER.error("No device UUID found in config entry data")
            raise ConfigEntryNotReady("Device UUID missing from config entry. Please reconfigure the integration")

        # If we don't have certificate/UUID, we need cloud authentication
        # This happens only once during first setup. Perhaps we should move this to config flow setup
        if not certificate:
            if cloud_email and cloud_password:
                _LOGGER.info("Authenticating with cloud to get device certificate")
                await hass.async_add_executor_job(
                    partial(aira.cloud.login_with_credentials, username=cloud_email, password=cloud_password)
                )
            
                _LOGGER.debug("Fetching device certificate from cloud")
                device_details = await hass.async_add_executor_job(
                    partial(aira.cloud.get_device_details, device_id=device_uuid, raw=False)
                ) # type: dict
                
                certificate = device_details["heat_pump"]["certificate"]["certificate_pem"]
                _LOGGER.debug("Saved certificate obtained from cloud")
                
                # Update data in AiraHome instance
                aira.uuid = device_uuid
                # Parse and store certificate using add_certificate (handles both certificate and _cert)
                aira.ble.add_certificate(certificate)
                
                # Store for future use
                hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        "certificate": certificate,
                    }
                )
                _LOGGER.info("Device certificate stored for advanced BLE communication")
            else:
                _LOGGER.warning("No certificate found - BLE features will be limited")
        else:
            # Use stored certificate and UUID
            _LOGGER.debug("Using stored certificate for BLE")
            # Update data in AiraHome instance
            aira.uuid = device_uuid
            aira.ble.add_certificate(certificate)
        
        # Attempt BLE connection using Home Assistant's Bluetooth integration
        # Don't block setup if bluetooth is having issues
        _LOGGER.info("Looking for the device at %s over BLE", mac_address)
        if mac_address:
            try:
                _LOGGER.debug("Getting BLE device from HA bluetooth integration")
                ble_device = bluetooth.async_ble_device_from_address(
                    hass, mac_address, connectable=True
                )
                _LOGGER.debug("ble_device result: %s", ble_device)
                
                if ble_device:
                    _LOGGER.info("Found BLE device: %s (%s), attempting connection", ble_device.name, ble_device.address)
                    
                    # Use standard connection with improved error handling
                    connected = await hass.async_add_executor_job(
                        aira.ble.connect_device,
                        ble_device,
                        BLE_CONNECT_TIMEOUT
                    )
                    if connected:
                        _LOGGER.info("Successfully connected to Aira device via BLE")
                    else:
                        _LOGGER.warning("BLE connection failed, will retry later")
                else:
                    _LOGGER.warning(
                        "Device %s not found in Home Assistant's bluetooth. "
                        "Make sure the device is powered on and within range.",
                        mac_address
                    )
            except asyncio.CancelledError:
                _LOGGER.warning("BLE setup was cancelled, will retry later")

            except Exception as err:
                _LOGGER.error("BLE connection attempt failed: %s. Will retry later.", err, exc_info=True)
        
        else:
            _LOGGER.warning("No MAC address available, BLE connection not attempted")
        
        # Get scan interval from options or use default
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        _LOGGER.debug("Using set scan interval of %d seconds", scan_interval)
        
        # Create reconnect callback for the coordinator
        async def reconnect_device() -> bool:
            """Reconnect to the BLE device using bleak-retry-connector for reliability."""
            try:
                if mac_address:
                    # First, explicitly disconnect to clean up any stale connection state
                    _LOGGER.debug("Disconnecting before reconnection attempt")
                    try:
                        await hass.async_add_executor_job(aira.ble.disconnect)
                    except Exception as disc_err:
                        _LOGGER.debug("Disconnect during reconnect raised: %s (nothing to worry about)", disc_err)
                    
                    # Small delay to let the BLE stack stabilize
                    await asyncio.sleep(0.5)
                    
                    ble_device = bluetooth.async_ble_device_from_address(
                        hass, mac_address, connectable=True
                    )
                    if ble_device:
                        _LOGGER.info("Attempting reconnection to %s", ble_device.name)
                        
                        # Use standard connection (has built-in retry logic)
                        success = await hass.async_add_executor_job(
                            aira.ble.connect_device,
                            ble_device,
                            BLE_CONNECT_TIMEOUT
                        )
                        if success:
                            _LOGGER.info("Reconnected to Aira device via BLE successfully")

                        return success
            except asyncio.TimeoutError:
                _LOGGER.warning("Reconnect timed out")
            except Exception as err:
                _LOGGER.warning("Reconnect failed: %s", err)
            return False
        

        # Create data update coordinator
        coordinator = AiraDataUpdateCoordinator(
            hass, entry, aira, scan_interval, reconnect_callback=reconnect_device
        )
        
        # Fetch initial data - allow failure for poor BLE connectivity
        # The coordinator will keep retrying in the background
        try:
            await coordinator.async_config_entry_first_refresh()

            # Check if we actually got data
            if coordinator.data and coordinator.data.get("state"):
                _LOGGER.info("Initial data fetch successful")
            else:
                _LOGGER.warning("Initial data fetch returned empty data, will retry in background")
        except asyncio.CancelledError:
            _LOGGER.warning("Initial data fetch was cancelled (system issue), will retry in background")

        except Exception as err:
            _LOGGER.warning(
                "Initial data fetch failed: %s. Integration will start anyway and retry in background.",
                err
            )
        
        # Store the coordinator and AiraHome instance for the platforms to use
        hass.data[DOMAIN][entry.entry_id] = {
            "coordinator": coordinator,
            "aira": aira,
            "mac_address": mac_address,
            "device_uuid": device_uuid,
        }
        
        _LOGGER.info("Aira Heat Pump integration initialized successfully")
        
    except Exception as err:
        _LOGGER.error("Failed to initialize Aira integration: %s", err, exc_info=True)
        raise ConfigEntryNotReady(f"Unable to initialize device: {err}") from err
    
    # Forward the setup to the platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Set up options update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Aira Heat Pump integration")
    
    # Get the stored data before cleanup
    entry_data = hass.data[DOMAIN].get(entry.entry_id, {})
    coordinator = entry_data.get("coordinator")
    aira = entry_data.get("aira")
    
    # Clean up BLE connection and resources
    if aira and aira.ble:
        try:
            _LOGGER.debug("Cleaning up BLE resources")
            # Use a timeout to prevent hanging during cleanup
            await asyncio.wait_for(
                hass.async_add_executor_job(aira.ble.cleanup),
                timeout=10.0  # 10 second timeout for cleanup
            )
            _LOGGER.debug("BLE resources cleaned up")
        except asyncio.TimeoutError:
            _LOGGER.warning("BLE cleanup timed out")
        except Exception as err:
            _LOGGER.warning("Error during BLE cleanup: %s", err)
    
    # Stop the coordinator
    if coordinator:
        _LOGGER.debug("Stopping coordinator updates")
        # DataUpdateCoordinator cleanup is handled by async_unload_platforms
        # No explicit shutdown method needed
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Clean up stored data
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("Aira integration unloaded successfully")
    else:
        _LOGGER.warning("Failed to unload some platforms")
    
    return unload_ok