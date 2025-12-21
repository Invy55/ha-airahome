"""The Aira Heat Pump integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from functools import partial
from pyairahome import AiraHome

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryError

from .const import (
    BLE_CONNECT_TIMEOUT,
    CONF_CERTIFICATE,
    CONF_DEVICE_UUID,
    CONF_INSTALLATION,
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
    device_uuid = entry.data.get(CONF_DEVICE_UUID)
    certificate = entry.data.get(CONF_CERTIFICATE)
    if not device_uuid:
        _LOGGER.error("No device UUID found in config entry data")
        raise ConfigEntryError("Device UUID missing from config entry. Please reconfigure the integration")
    if not mac_address:
        _LOGGER.error("No MAC address found in config entry data, BLE connection will not be possible")
        raise ConfigEntryError("MAC address missing from config entry. Please reconfigure the integration")


    device_type = entry.data.get(CONF_INSTALLATION, {}).get("type", "unknown") # unused for now
    
    _LOGGER.info("Setting up Aira Heat Pump integration for device at %s", mac_address)
    
    aira = AiraHome(ext_loop=hass.loop)
    aira.uuid = device_uuid
    if certificate:
        aira.ble.add_certificate(certificate)
    else:
        _LOGGER.warning("No certificate found in config entry, some BLE operations will fail")
    
    # Connect library logger to Home Assistant's logging system
    # This ensures pyairahome logs use HA's log level
    lib_logger = logging.getLogger("pyairahome")
    lib_logger.setLevel(_LOGGER.level)

    # Get BLE device from Home Assistant's bluetooth integration
    _LOGGER.debug("Getting BLE device from HA bluetooth integration")
    ble_device = bluetooth.async_ble_device_from_address(
        hass, mac_address, connectable=True
    )
    if not ble_device:
        _LOGGER.error(
            "Device %s not found in Home Assistant's bluetooth. "
            "Make sure the device is powered on and within range.",
            mac_address
        )
        raise ConfigEntryNotReady("Device not found in Home Assistant's bluetooth. Please ensure the device is powered on and within range.")
    
    # Connect aira instance to the device
    try:
        connected = await aira.ble._connect_device(ble_device, timeout=BLE_CONNECT_TIMEOUT)

        if connected:
            _LOGGER.info("Successfully connected to Aira device via BLE")
        else:
            raise ValueError("BLE connection failed, connection returned False/None")
    except Exception as err:
        _LOGGER.error("Initial BLE connection attempt failed.")
        raise ConfigEntryNotReady("Initial BLE connection failed. Please ensure the device is powered on and within range.") from err
    
    # Get scan interval from options or use default
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    _LOGGER.debug("Using set scan interval of %d seconds", scan_interval)

    # Create data update coordinator
    coordinator = AiraDataUpdateCoordinator(hass, entry, aira, scan_interval, mac_address)
    
    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator and AiraHome instance for the platforms to use
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "aira": aira,
        "device_uuid": device_uuid  # TODO CHECK IF NEEDED
    }
    
    # Forward the setup to the platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Aira Heat Pump integration")
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    # Get the stored data before cleanup
    aira = hass.data[DOMAIN].get(entry.entry_id).get("aira")
    coordinator = hass.data[DOMAIN].get(entry.entry_id).get("coordinator")

    # Stop the coordinator
    if coordinator:
        _LOGGER.debug("Data update coordinator stopped")
        # nothing particular to do here as coordinator is stopped by ha
    
    # Clean up BLE connection and resources
    if aira and aira.ble:
        try:
            _LOGGER.debug("Cleaning up BLE resources")
            # Use a timeout to prevent hanging during cleanup
            async with asyncio.timeout(10):
                await aira.ble._cleanup()
            _LOGGER.debug("BLE resources cleaned up")
        except asyncio.TimeoutError:
            _LOGGER.warning("BLE cleanup timed out")
        except asyncio.CancelledError:
            raise
        except Exception as err:
            _LOGGER.warning("Error during BLE cleanup: %s", err)

    if unload_ok:
        # Clean up stored data
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("Aira integration unloaded successfully")
    else:
        _LOGGER.warning("Failed to unload some platforms")
    
    return unload_ok