"""The Aira Heat Pump integration."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue, async_delete_issue
from homeassistant.helpers.translation import async_get_translations

from bleak.backends.device import BLEDevice
from pyairahome import AiraHome
from pyairahome.utils.exceptions import BLEConnectionError

from .const import (
    BLE_CONNECT_TIMEOUT,
    CONF_CERTIFICATE,
    CONF_DEVICE_UUID,
    CONF_INSTALLATION,
    CONF_MAC_ADDRESS,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import AiraDataUpdateCoordinator
from .services import async_setup_services


_LOGGER = logging.getLogger(__name__)


async def async_get_translation(hass: HomeAssistant, selector_name: str, key: str) -> str:
    """Return a translated selector option for the given name and key, falling back to the key itself."""
    translations = await async_get_translations(hass, hass.config.language, "selector", [DOMAIN])
    return translations.get(f"component.{DOMAIN}.selector.{selector_name}.options.{key}", key)

async def connect_with_cache_retry(aira: AiraHome, ble_device: BLEDevice, mac_address: str, timeout: int = BLE_CONNECT_TIMEOUT) -> bool:
    """Connect to BLE device, retrying once with cache clear on failure."""
    try:
        if await aira.ble._connect_device(ble_device, timeout=timeout):
            _LOGGER.info("Successfully connected to Aira device via BLE")
            return True
        raise BLEConnectionError("Initial BLE connection failed")
    except Exception as conn_err:
        _LOGGER.warning("Initial BLE connection attempt failed: %s. Attempting cache clear and retry.", conn_err)
        await aira.ble._clear_cache(mac_address)
        await asyncio.sleep(0.5)
        if await aira.ble._connect_device(ble_device, timeout=timeout):
            _LOGGER.info("Successfully connected to Aira device via BLE after CLEARING CACHE.")
            return True
        raise BLEConnectionError("BLE connection retry failed after clearing cache")


PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.WATER_HEATER, Platform.CLIMATE]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Reject config entries created with an older version of the integration."""
    _LOGGER.warning(
        "Config entry was created with an unsupported version (%s). Please reconfigure the integration.",
        config_entry.version
    )
    async_delete_issue(hass, DOMAIN, "migration_required")
    async_create_issue(
        hass,
        DOMAIN,
        "migration_required",
        is_fixable=True,
        severity=IssueSeverity.ERROR,
        translation_key="migration_required",
        data={"entry_id": config_entry.entry_id},
    )
    return False


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Aira Heat Pump component."""
    hass.data.setdefault(DOMAIN, {})
    await async_setup_services(hass)
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


    device_type = entry.data.get(CONF_INSTALLATION, {}).get("type", "unknown") # unused for now, will be used to support solar
    
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
        await connect_with_cache_retry(aira, ble_device, mac_address)
    except Exception as conn_err:
        _LOGGER.error("Initial BLE connection attempt failed: %s", conn_err)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="initial_ble_connection_failed",
        ) from conn_err
    
    # Get scan interval from options or use default
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    _LOGGER.debug("Using set scan interval of %d seconds", scan_interval)

    # Create data update coordinator
    coordinator = AiraDataUpdateCoordinator(hass, entry, aira, scan_interval, mac_address)
        
    try:
        async with asyncio.timeout(120):
            await coordinator.async_config_entry_first_refresh()
    except TimeoutError as err:
        raise ConfigEntryNotReady("Timed out waiting for first data refresh") from err

    # Store the coordinator and AiraHome instance for the platforms to use
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "aira": aira
    }
    entry.async_on_unload(coordinator.async_shutdown)
    
    # Forward the setup to the platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Aira Heat Pump integration")
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    # Get the stored data before cleanup
    aira = hass.data[DOMAIN].get(entry.entry_id, {}).get("aira")

    # Coordinator is stopped by homeassistant
    
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