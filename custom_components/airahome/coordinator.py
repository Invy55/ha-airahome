"""Data update coordinator for Aira Heat Pump."""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from functools import partial
from datetime import timedelta
from time import perf_counter

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from pyairahome import AiraHome

from .const import CONF_DEVICE_NAME, CONF_MAC_ADDRESS, DEFAULT_SHORT_NAME, DOMAIN, STALE_DATA_THRESHOLD, DEFAULT_DATA, BLE_CONNECT_TIMEOUT, BLE_COMMAND_SLEEP

_LOGGER = logging.getLogger(__name__)

class AiraDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Aira data from BLE."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        aira: AiraHome,
        update_interval: int = 30,
        mac_address: str | None = None
    ) -> None:
        """Initialise coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=entry.data.get(CONF_DEVICE_NAME, DEFAULT_SHORT_NAME),
            update_interval=timedelta(seconds=update_interval),
        )
        self.config_entry = entry
        self.aira = aira
        self.mac_address = mac_address
        self._is_connected = True # start with connected true since we connected in the init
        self._reconnect_task: asyncio.Task | None = None
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._update_interval_seconds: float = update_interval # type: ignore

        # Timing and success tracking
        self._last_update_time = None
        self._last_successful_data = None
        self._last_successful_timestamp = None
        
        # Initialize coordinator data with empty but valid data structure to prevent sensor crashes
        self.data = DEFAULT_DATA.copy()

    async def _fetch_all_data(self, start_time: float, rssi: int | None) -> dict[str, Any]:
        """Fetch all data from the Aira device via BLE."""
        start_time = perf_counter()
        state_data: dict = await self.aira.ble._get_states() # type: ignore

        await asyncio.sleep(BLE_COMMAND_SLEEP) # ensure BLE_COMMAND_SLEEP between calls

        system_check_state: dict = await self.aira.ble._get_system_check_state() # type: ignore

        # Reset reconnect attempts on successful data fetch
        self._reconnect_attempts = 0
        
        elapsed = perf_counter() - start_time
        _LOGGER.debug("BLE data fetch completed in %.1f seconds", elapsed)
                        
        # Build result, merging with stale data if some fetches failed
        state_dict = state_data.get("state", {}) if state_data else {}
        system_dict = system_check_state.get("system_check_state", {}) if system_check_state else {}

        successful = True
        # If we have stale data and current fetch returned empty, use stale values
        if self._last_successful_data and perf_counter() - self._last_successful_timestamp < STALE_DATA_THRESHOLD: # type: ignore
            if not state_dict and self._last_successful_data.get("state"):
                state_dict = self._last_successful_data["state"]
                successful = False
                _LOGGER.debug("Using stale state data due to empty fetch")

            if not system_dict and self._last_successful_data.get("system_check_state"):
                system_dict = self._last_successful_data["system_check_state"]
                _LOGGER.debug("Using stale system_check data due to empty fetch")

        # Record completion time for next cycle (monotonic)
        self._last_update_time = perf_counter()

        result = {
            "state": state_dict,
            "system_check": system_dict,
            "connected": True,
            "rssi": rssi,
        }
        
        # Only store as successful if we actually got some real data
        # Check if at least state data has content (it's the most important)
        if successful:
            self._last_successful_data = result
            # Record monotonic timestamp for age checks
            self._last_successful_timestamp = perf_counter()
            _LOGGER.info("Data fetch successful, updated last_successful_data")
        else:
            _LOGGER.warning("Data fetch returned empty state, not updating last_successful_data")
        
        return result

    async def _async_reconnect(self) -> None:
        """Attempt to reconnect to the device. This runs in a background task scheduled by _schedule_reconnect."""
        aira = self.aira
        mac_address: str = self.mac_address # type: ignore # This is already checked in init

        try:
            # First, explicitly disconnect to clean up any stale connection state
            _LOGGER.debug("Disconnecting before reconnection attempt")
            try:
                await aira.ble._disconnect()
            except Exception as disc_err:
                _LOGGER.debug("Disconnect during reconnect raised: %s (nothing to worry about)", disc_err)
            
            # Small delay to let the BLE stack stabilize
            await asyncio.sleep(0.5)
            
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, mac_address, connectable=True
            )
            if not ble_device:
                _LOGGER.error(
                    "Device %s not found in Home Assistant's bluetooth during reconnect attempt.",
                    mac_address
                )
                return
             
            _LOGGER.info("Attempting reconnection to %s", ble_device.name)
            try:
                # Use standard connection (has built-in retry logic)
                success = await aira.ble._connect_device(
                    ble_device,
                    timeout=BLE_CONNECT_TIMEOUT
                )
            except Exception as conn_err:
                _LOGGER.error("Reconnection attempt raised exception: %s", conn_err)
                success = False
        except Exception as err:
            _LOGGER.error("Unexpected error during reconnection attempt: %s", err, exc_info=True)
            success = False

        if success:
            _LOGGER.info("Reconnected to Aira device via BLE successfully")
            self._is_connected = True
        else:
            _LOGGER.warning("Reconnection attempt to Aira device via BLE failed")
            self._is_connected = False        

    def _schedule_reconnect(self) -> None:
        """Schedule a reconnect attempt in a background task."""
        if self._reconnect_task and not self._reconnect_task.done():
            return  # already scheduled

        self._reconnect_task = self.hass.async_create_task(
            self._async_reconnect()
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Aira device via BLE."""
        start_time = perf_counter()

        mac_address: str = self.mac_address # type: ignore # This is already checked in init
        is_connected = self._is_connected

        rssi = None

        try:
            # Get RSSI from Home Assistant's bluetooth integration
            try:
                # Get service info which contains RSSI
                service_info = bluetooth.async_last_service_info(
                    self.hass, mac_address, connectable=True
                )
                if service_info and service_info.rssi is not None:
                    rssi = service_info.rssi
            except Exception:
                # Fallback: try getting from device
                rssi = await self.hass.async_add_executor_job(
                    self.aira.ble.get_rssi
                )
                _LOGGER.debug("Fallback RSSI fetch used")

            if not is_connected:
                _LOGGER.warning("Device not connected. Raising UpdateFailed to trigger reconnect logic.")
                raise UpdateFailed("Device not connected")

            # Fetch data
            try:
                # get all data and return it
                data =  await self._fetch_all_data(start_time, rssi)
                _LOGGER.debug("Gathered data in %.1f seconds", perf_counter() - start_time)
                return data
            except Exception as data_err:
                _LOGGER.error("Error fetching data: %s", data_err)
                raise UpdateFailed from data_err
            
        except Exception as err:
            # Attempt to reconnect if not connected
            if is_connected: # for the future: check if this is the best approach or we should check specific exceptions
                _LOGGER.error("Unexpected error during data update: %s. Considering disconnected", err, exc_info=True)
                self._is_connected = False
                is_connected = False

            # Device is not connected, return stale data if available
            stale_result = DEFAULT_DATA.copy()
            if self._last_successful_data and self._last_successful_timestamp:
                age = start_time - self._last_successful_timestamp
                if age < STALE_DATA_THRESHOLD:
                    _LOGGER.debug(
                        "Not connected, returning stale data (age: %.0f seconds)",
                        age
                    )
                    # Return last good data but mark as disconnected
                    stale_result = self._last_successful_data.copy()
                    stale_result["connected"] = False
                    stale_result["rssi"] = rssi  # Update RSSI even if using stale data
                    #return stale_result # TODO MOVED BELOW AFTER SCHEDULING RECONNECT ATTEMPT


            # Device is not connected, attempt reconnection
            if self._reconnect_attempts < self._max_reconnect_attempts:
                _LOGGER.debug(
                    "Not connected, scheduling reconnect (attempt %d/%d)",
                    self._reconnect_attempts + 1,
                    self._max_reconnect_attempts
                )
                self._schedule_reconnect()
                self._reconnect_attempts += 1
            else:
                # If we reach this point something is seriously wrong, the best thing is asking the user to
                # manually intervene. The most common issue in my experience is the bluetooth cache being
                # stale because aira seems to not send Service Changed indications properly. Forcing unpairing
                # is the only way to recover from this since it should reset the cache. For more infos check
                # https://github.com/Invy55/ha-airahome/wiki/Bluetooth-Issues
                _LOGGER.error(
                    "Max reconnect attempts (%d) reached, skipping update and resetting attempts.",
                    self._max_reconnect_attempts
                )

                raise ConfigEntryError(
                    "Bluetooth connection failed after multiple attempts. "
                    "This often means the host's Bluetooth cache is stale — removing/unpairing the device (or rebooting the host / replugging the adapter) and re-pairing may help. "
                    "Another solution could be using esphome proxies for connecting to the device, since we can disable caching there. "
                    "See https://github.com/Invy55/ha-airahome/wiki/Bluetooth-Issues for more details."
                )
            
            return stale_result