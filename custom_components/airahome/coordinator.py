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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import CONF_DEVICE_NAME, CONF_MAC_ADDRESS, DEFAULT_SHORT_NAME, DOMAIN, STALE_DATA_THRESHOLD

_LOGGER = logging.getLogger(__name__)


class AiraDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Aira data from BLE."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        aira: Any,
        update_interval: int = 10,
        reconnect_callback: Any | None = None,
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
        self.reconnect_callback = reconnect_callback
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 3
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3  # Reconnect after 3 consecutive failures
        self._update_interval_seconds = update_interval
        # Use monotonic perf_counter for timing to avoid system clock jumps
        self._last_update_time = None
        self._last_successful_data = None
        self._last_successful_timestamp = None
        
        # Initialize with empty but valid data structure to prevent sensor crashes
        self.data = {
            "state": {},
            # "flow_data": {},
            "system_check": {},
            "connected": False,
            "rssi": None,
        }

    async def _fetch_all_data(self, start_time: float, rssi: int | None) -> dict[str, Any]:
        state_data = await self.hass.async_add_executor_job(
            partial(self.aira.ble.get_states, raw=False)
        )

        #await asyncio.sleep(0.5)  # Small delay to avoid overwhelming the device
        #flow_data = await self.hass.async_add_executor_job(
        #    partial(self.aira.ble.get_flow_data, raw=False)
        #)

        await asyncio.sleep(1.0)  # Small delay to avoid overwhelming the device
        system_check = await self.hass.async_add_executor_job(
            partial(self.aira.ble.get_system_check_state, raw=False)
        )
        
        # Reset reconnect attempts and failure counter on successful data fetch
        self._reconnect_attempts = 0
        self._consecutive_failures = 0
        
        elapsed = perf_counter() - start_time
        _LOGGER.debug("BLE data fetch completed in %.1f seconds", elapsed)
        
        # Calculate wait time to ensure next update starts interval seconds after completion
        # If last update finished at T=35 and interval is 10, next should start at T=45
        if self._last_update_time is not None:
            time_since_last = perf_counter() - self._last_update_time
            if time_since_last < self._update_interval_seconds:
                wait_time = self._update_interval_seconds - time_since_last
                _LOGGER.debug(
                    "Waiting %.1f seconds before allowing next update (interval from completion)",
                    wait_time
                )
                await asyncio.sleep(wait_time)
                        
        # Build result, merging with stale data if some fetches failed
        state_dict = state_data.get("state", {}) if state_data else {}
        #flow_dict = flow_data.get("main_pump_flow", {}) if flow_data else {}
        system_dict = system_check.get("system_check_state", {}) if system_check else {}

        successful = True
        # If we have stale data and current fetch returned empty, use stale values
        if self._last_successful_data and perf_counter() - self._last_successful_timestamp < STALE_DATA_THRESHOLD:
            if not state_dict and self._last_successful_data.get("state"):
                state_dict = self._last_successful_data["state"]
                successful = False
                _LOGGER.debug("Using stale state data due to empty fetch")
            #if not flow_dict and self._last_successful_data.get("flow_data"):
            #    flow_dict = self._last_successful_data["flow_data"]
            #    _LOGGER.debug("Using stale flow data due to empty fetch")
            if not system_dict and self._last_successful_data.get("system_check"):
                system_dict = self._last_successful_data["system_check"]
                _LOGGER.debug("Using stale system_check data due to empty fetch")

        # Record completion time for next cycle (monotonic)
        self._last_update_time = perf_counter()

        result = {
            "state": state_dict,
            #"flow_data": flow_dict,
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

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Aira device via BLE."""
        start_time = perf_counter()
        
        try:
            # Check connection
            is_connected = await self.hass.async_add_executor_job(
                self.aira.ble.is_connected
            )
            
            # Get RSSI from Home Assistant's bluetooth integration
            rssi = None
            try:
                mac_address = self.hass.data[DOMAIN][self.config_entry.entry_id].get(CONF_MAC_ADDRESS)
            except (KeyError, AttributeError):
                # Entry not yet in hass.data during first setup
                mac_address = self.config_entry.data.get(CONF_MAC_ADDRESS)
            if mac_address:
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
                if self._reconnect_attempts < self._max_reconnect_attempts:
                    _LOGGER.debug(
                        "Not connected, attempting reconnect (attempt %d/%d)",
                        self._reconnect_attempts + 1,
                        self._max_reconnect_attempts
                    )
                    if self.reconnect_callback:
                        is_connected = await self.reconnect_callback()
                        if is_connected:
                            _LOGGER.info("Successfully reconnected to device")
                            # Reset counters on successful reconnect
                            self._reconnect_attempts = 0
                            self._consecutive_failures = 0
                        else:
                            self._reconnect_attempts += 1
                            _LOGGER.warning("Reconnect attempt failed")
                    else:
                        _LOGGER.warning("No reconnect callback available")
                else:
                    _LOGGER.error(
                        "Max reconnect attempts (%d) reached, skipping update",
                        self._max_reconnect_attempts
                    )
                    # Reset counter for next update cycle
                    self._reconnect_attempts = 0
            
            # If not connected, check if we have recent stale data to return
                if self._last_successful_data and self._last_successful_timestamp:
                    age = perf_counter() - self._last_successful_timestamp
                    if age < STALE_DATA_THRESHOLD:
                        _LOGGER.debug(
                            "Not connected, returning stale data (age: %.0f seconds)",
                            age
                        )
                        # Return last good data but mark as disconnected
                        stale_result = self._last_successful_data.copy()
                        stale_result["connected"] = False
                        stale_result["rssi"] = rssi  # Update RSSI even if using stale data
                        return stale_result
                
                # Not connected and no fresh stale data - keep existing coordinator state
                _LOGGER.warning("Not connected and no stale data available - maintaining last coordinator state")
                if self.data and len(self.data.keys()) > 0:
                    # Return existing coordinator data but mark as disconnected
                    result = self.data.copy()
                    result["connected"] = False
                    result["rssi"] = rssi if rssi else None
                    return result
                
                # Only raise UpdateFailed on very first connection when we have no data at all
                _LOGGER.error("Initial connection failed with no data available")
                raise UpdateFailed("Device disconnected and no initial data available")
                        
            # Fetch all data types with timeout handling
            try:
                # get all data and return it
                return await self._fetch_all_data(start_time, rssi)
            except (EOFError, BrokenPipeError, ConnectionError, TimeoutError) as conn_err:
                # BLE connection is dead or timed out - attempt reconnection immediately
                error_type = "timeout" if isinstance(conn_err, TimeoutError) else "connection error"
                _LOGGER.error("BLE %s: %s", error_type, conn_err)
                
                # Try to reconnect and retry the fetch
                if self.reconnect_callback:
                    _LOGGER.info("Attempting immediate reconnection...")
                    try:
                        reconnected = await self.reconnect_callback()
                        if reconnected:
                            _LOGGER.info("Reconnected successfully, retrying data fetch...")
                            # Reset failure counter and try again
                            self._consecutive_failures = 0
                            # Retry the data fetch
                            try:
                                # get all data and return it
                                return await self._fetch_all_data(start_time, rssi)
                            except Exception as retry_err:
                                _LOGGER.warning("Retry after reconnection failed: %s", retry_err)
                    except Exception as reconn_err:
                        _LOGGER.error("Reconnection attempt failed: %s", reconn_err)
                
                # Reconnection failed or retry failed - fall back to stale data
                if self._last_successful_data and self._last_successful_timestamp:
                    age = perf_counter() - self._last_successful_timestamp
                    if age < STALE_DATA_THRESHOLD:
                        _LOGGER.info(
                            "Connection lost and retry failed, returning stale data (age: %.0f seconds)",
                            age
                        )
                        stale_result = self._last_successful_data.copy()
                        stale_result["connected"] = False
                        stale_result["rssi"] = rssi if rssi else None
                        return stale_result
                
                # No fresh stale data - keep existing coordinator state to prevent sensors going unavailable
                _LOGGER.warning("Connection lost, retry failed, and no stale data available - maintaining last coordinator state")
                if self.data and self.data.get("state"):
                    # Return existing coordinator data but mark as disconnected
                    result = self.data.copy()
                    result["connected"] = False
                    result["rssi"] = None
                    return result
                
                # Only raise UpdateFailed on very first update when we have no data at all
                _LOGGER.error("First update failed with no initial data available")
                raise UpdateFailed(f"Initial connection failed: {conn_err}")
                
            except Exception as data_err:
                # Check if this is a Bleak DBus error (stale connection)
                error_type = type(data_err).__name__
                error_str = str(data_err)
                error_module = type(data_err).__module__
                
                # Detect BleakDBusError, GATT errors, or event loop conflicts
                is_connection_error = (
                    "BleakDBusError" in error_type or
                    "bleak.exc" in error_module or
                    "org.bluez.GattCharacteristic" in error_str or
                    "org.freedesktop.DBus.Error.UnknownObject" in error_str or
                    ("RuntimeError" in error_type and "different loop" in error_str) or
                    "Out of memory" in error_str
                )
                
                # Log at WARNING level so we can see what's happening
                _LOGGER.warning(
                    "Error detection - Type: %s, Module: %s, IsConnectionError: %s, Message: %s", 
                    error_type, error_module, is_connection_error, error_str
                )
                
                if is_connection_error:
                    # GATT characteristic doesn't exist - connection is stale, attempt reconnection
                    _LOGGER.error("BLE GATT error (stale connection): %s", data_err)
                    
                    # Try to reconnect and retry the fetch
                    if self.reconnect_callback:
                        _LOGGER.info("Attempting immediate reconnection after GATT error...")
                        try:
                            reconnected = await self.reconnect_callback()
                            if reconnected:
                                _LOGGER.info("Reconnected successfully, retrying data fetch...")
                                self._consecutive_failures = 0
                                # Retry the data fetch
                                try:
                                    # get all data and return it
                                    return await self._fetch_all_data(start_time, rssi)
                                except Exception as retry_err:
                                    _LOGGER.warning("Retry after GATT error reconnection failed: %s", retry_err)
                        except Exception as reconn_err:
                            _LOGGER.error("Reconnection after GATT error failed: %s", reconn_err)
                    
                    # Reconnection failed or retry failed - fall back to stale data
                    if self._last_successful_data and self._last_successful_timestamp:
                        age = perf_counter() - self._last_successful_timestamp
                        if age < STALE_DATA_THRESHOLD:
                            _LOGGER.info(
                                "GATT error and retry failed, returning stale data (age: %.0f seconds)",
                                age
                            )
                            stale_result = self._last_successful_data.copy()
                            stale_result["connected"] = False
                            stale_result["rssi"] = rssi if rssi else None
                            return stale_result
                    
                    # No fresh stale data - keep existing coordinator state to prevent sensors going unavailable
                    _LOGGER.warning("GATT error, retry failed, and no stale data available - maintaining last coordinator state")
                    if self.data and self.data.get("state"):
                        # Return existing coordinator data but mark as disconnected
                        result = self.data.copy()
                        result["connected"] = False
                        result["rssi"] = None
                        return result
                    
                    # Only raise UpdateFailed on very first update when we have no data at all
                    _LOGGER.error("First update failed with GATT error and no initial data available")
                    raise UpdateFailed(f"Initial GATT error: {data_err}")
                
                # Regular timeout/error - increment failure counter
                _LOGGER.warning("Failed to fetch data from device: %s", data_err, exc_info=True)
                self._consecutive_failures += 1
                _LOGGER.debug("Consecutive failures: %d/%d", self._consecutive_failures, self._max_consecutive_failures)
                
                # Check if we have recent stale data to return
                if self._last_successful_data and self._last_successful_timestamp:
                    age = perf_counter() - self._last_successful_timestamp
                    if age < STALE_DATA_THRESHOLD:
                        _LOGGER.info(
                            "Data fetch error, returning stale data (age: %.0f seconds)",
                            age
                        )
                        stale_result = self._last_successful_data.copy()
                        stale_result["connected"] = False
                        stale_result["rssi"] = rssi if rssi else None
                        return stale_result
                
                # No fresh stale data - keep existing coordinator state to prevent sensors going unavailable
                _LOGGER.warning("Data fetch failed and no stale data available - maintaining last coordinator state")
                if self.data and self.data.get("state"):
                    # Return existing coordinator data but mark as disconnected
                    result = self.data.copy()
                    result["connected"] = False
                    result["rssi"] = None
                    return result
                
                # Only raise UpdateFailed on very first update when we have no data at all
                _LOGGER.error("First update failed with no initial data available")
                raise UpdateFailed(f"Initial data fetch failed: {data_err}")
            
        except Exception as err:
            _LOGGER.error("Error in coordinator update: %s", err, exc_info=True)
            
            # Increment consecutive failure counter
            self._consecutive_failures += 1
            _LOGGER.debug("Consecutive failures: %d/%d", self._consecutive_failures, self._max_consecutive_failures)
            
            # Check if we have recent stale data to return
            if self._last_successful_data and self._last_successful_timestamp:
                age = perf_counter() - self._last_successful_timestamp
                if age < STALE_DATA_THRESHOLD:
                    _LOGGER.info(
                        "Coordinator error, returning stale data (age: %.0f seconds)",
                        age
                    )
                    stale_result = self._last_successful_data.copy()
                    stale_result["connected"] = False
                    stale_result["rssi"] = None
                    return stale_result
            
            # No fresh stale data - keep existing coordinator state to prevent sensors going unavailable
            _LOGGER.warning("Coordinator error and no stale data available - maintaining last coordinator state")
            if self.data and self.data.get("state"):
                # Return existing coordinator data but mark as disconnected
                result = self.data.copy()
                result["connected"] = False
                result["rssi"] = None
                return result
            
            # Only raise UpdateFailed on very first update when we have no data at all
            _LOGGER.error("First coordinator update failed with no initial data available")
            raise UpdateFailed(f"Initial coordinator error: {err}")