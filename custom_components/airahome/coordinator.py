"""Data update coordinator for Aira Heat Pump."""
from __future__ import annotations

import asyncio
import contextlib
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import logging
from time import perf_counter
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pyairahome import AiraHome

from .const import (
    BLE_COMMAND_SLEEP,
    BLE_CONNECT_TIMEOUT,
    BLE_RECONNECT_BACKOFF,
    CACHE_ERROR_PATTERNS,
    CONF_DEVICE_NAME,
    DEFAULT_DATA,
    DEFAULT_SHORT_NAME,
    ERROR_SOURCE_PREFIXES,
    STALE_DATA_THRESHOLD,
)


_LOGGER = logging.getLogger(__name__)


def _parse_error(error: dict[str, Any]) -> tuple[str, str, str, str, Any]:
    """Parse an error returned by the Aira protocol."""

    # default values
    source = "UNKNOWN"
    raw_code = "unknown"
    display_code = "Unknown"

    # Look for the first non-empty error source and code, ignoring unspecified codes
    for src, prefix in ERROR_SOURCE_PREFIXES.items():
        value = error.get(src, "")
        if value and not str(value).endswith("_UNSPECIFIED"):
            source = src.upper()
            raw_code = str(value)
            display_code = raw_code.removeprefix(prefix).replace("_", " ").title()
            break

    severity = (str(error.get("severity", "SEVERITY_UNSPECIFIED")).removeprefix("SEVERITY_").title())
    return source, display_code, raw_code, severity, error.get("occurred_at")


def _is_cache_error(err: Exception) -> bool:
    """Attempt to determine if the exception could be caused by a stale GATT cache."""
    error_message = str(err).lower()
    return any(pattern in error_message for pattern in CACHE_ERROR_PATTERNS)


class AiraDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Aira data from BLE."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        aira: AiraHome,
        update_interval: int = 30,
        mac_address: str | None = None,
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
        # The initial connection is established before the coordinator is created (in init).
        self._is_connected = True
        self._reconnect_task: asyncio.Task[None] | None = None
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        # perf_counter timestamp for the next allowed reconnect.
        self._next_reconnect_at = 0.0
        self._needs_cache_clear: bool = False

        # Map raw error codes to their severity and first-seen timestamp.
        self._active_errors: dict[str, tuple[str, str]] = {}

        # Timing and success tracking
        self._last_successful_data: dict[str, Any] | None = None
        self._last_successful_timestamp: float | None = None

        # Initialize coordinator data with empty but valid data structure to prevent sensor crashes
        self.data = deepcopy(DEFAULT_DATA)

    async def async_shutdown(self) -> None:
        """Cancel pending background tasks on integration shutdown/unload."""
        await super().async_shutdown()

        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError): # Suppress the CancelledError to avoid logging it as an error
                await self._reconnect_task
            _LOGGER.debug("Expectedly cancelled pending reconnect task on shutdown")

    def _calculate_scheduled_hot_water_temperature(self, state_dict: dict[str, Any]) -> float | None:
        """Calculate the scheduled hot water temperature from scheduler active actions."""
        try:
            scheduler = state_dict.get("scheduler", {})
            if not scheduler:
                return state_dict.get("target_hot_water_temperature")
            active_actions = scheduler.get("active_actions", [])
            if not active_actions:
                return state_dict.get("target_hot_water_temperature")
            for action in active_actions:
                if "set_dhw_setpoint" in action:
                    dhw_temp = action["set_dhw_setpoint"].get("temperature")
                    if dhw_temp is not None:
                        return float(dhw_temp)
            return state_dict.get("target_hot_water_temperature")
        except (KeyError, ValueError, TypeError):
            return None

    async def _fetch_all_data(self, start_time: float, rssi: int | None) -> dict[str, Any]:
        """Fetch all data from the Aira device via BLE."""
        state_data: dict[str, Any] | None = None
        system_check_state: dict[str, Any] | None = None

        try:
            state_data = await self.aira.ble._get_states()  # type: ignore[reportAssignmentType]
        except Exception as err:
            _LOGGER.warning("Failed to fetch state data: %s", err)
            if _is_cache_error(err):
                self._needs_cache_clear = True

        # Leave enough time between BLE commands for the device to respond reliably.
        await asyncio.sleep(BLE_COMMAND_SLEEP)

        try:
            system_check_state = (
                await self.aira.ble._get_system_check_state()  # type: ignore[reportAssignmentType]
            )
        except Exception as err:
            _LOGGER.warning("Failed to fetch system check state: %s", err)
            if _is_cache_error(err):
                self._needs_cache_clear = True

        if state_data is None and system_check_state is None:
            raise UpdateFailed("Both BLE data fetches failed")

        elapsed = perf_counter() - start_time
        _LOGGER.debug("BLE data fetch completed in %.1f seconds", elapsed)

        # Build result, merging with stale data if some fetches failed
        state_dict = state_data.get("state", {}) if state_data else {}
        system_dict = (
            system_check_state.get("system_check_state", {})
            if system_check_state
            else {}
        )

        successful = 2
        # If we have stale data and current fetch returned empty, use stale values
        if (
            self._last_successful_data
            and self._last_successful_timestamp is not None
            and perf_counter() - self._last_successful_timestamp
            < STALE_DATA_THRESHOLD
        ):
            # Handle empty result or aira errors
            if (
                not state_dict and self._last_successful_data.get("state")
            ) or state_data and (
                state_data.get("error") != "DATA_RESPONSE_ERROR_UNSPECIFIED"
            ):
                state_dict = self._last_successful_data["state"]
                successful -= 1
                _LOGGER.debug("Using stale state data due to empty fetch or error")

            if (
                not system_dict
                and self._last_successful_data.get("system_check_state")
            ) or system_check_state and (
                system_check_state.get("error") != "DATA_RESPONSE_ERROR_UNSPECIFIED"
            ):
                system_dict = self._last_successful_data["system_check_state"]
                successful -= 1
                _LOGGER.debug("Using stale system_check data due to empty fetch or error")

        state_dict["scheduled_hot_water_temperature"] = (
            self._calculate_scheduled_hot_water_temperature(state_dict)
        )

        result = {
            "state": state_dict,
            "system_check_state": system_dict,
            "connected": True,
            "rssi": rssi,
        }
        # Errors can be reported in either response. Deduplicate them by raw code.
        state_errors = state_dict.get("errors", [])
        if not isinstance(state_errors, list):
            state_errors = []
        system_errors = system_dict.get("errors", [])
        if not isinstance(system_errors, list):
            system_errors = []

        seen_codes: set[str] = set()
        all_errors: list[dict[str, Any]] = []
        for error in state_errors + system_errors:
            _, _, raw_code, _, _ = _parse_error(error)
            if raw_code != "unknown" and raw_code not in seen_codes:
                seen_codes.add(raw_code)
                all_errors.append(error)

        self._handle_error_changes(all_errors)

        # Only store as successful if we actually got some real data
        # Check if at least state data has content (it's the most important)
        if successful == 2:
            # Reset reconnect state only after both calls return complete data.
            self._reconnect_attempts = 0
            self._next_reconnect_at = 0.0
            self._last_successful_data = result
            # Record monotonic timestamp for age checks
            self._last_successful_timestamp = perf_counter()
            _LOGGER.debug("Data fetch successful, updated last_successful_data")
        else:
            _LOGGER.warning(
                "Data fetch returned empty state or error, leaving "
                "last_successful_data as is"
            )

        return result

    def _handle_error_changes(self, errors: list[dict[str, Any]]) -> None:
        """Log errors that appeared or cleared since the previous update."""
        device_name = self.config_entry.data.get(CONF_DEVICE_NAME, DEFAULT_SHORT_NAME)
        current_codes: set[str] = set()
        parsed: dict[str, tuple[str, str, str, Any]] = {}

        for error in errors:
            source, display_code, raw_code, severity, occurred_at = _parse_error(error)
            if raw_code != "unknown":
                current_codes.add(raw_code)
                parsed[raw_code] = (source, display_code, severity, occurred_at)

        for raw_code in current_codes - set(self._active_errors):
            source, display_code, severity, occurred_at = parsed[raw_code]
            if occurred_at:
                first_seen_at = (
                    occurred_at.isoformat()
                    if hasattr(occurred_at, "isoformat")
                    else str(occurred_at)
                )
            else:
                first_seen_at = datetime.now(timezone.utc).isoformat()
            self._active_errors[raw_code] = (severity, first_seen_at)

            if severity.lower() in {"critical", "error"}:
                _LOGGER.error(
                    "Aira alarm active on %s: [%s] %s (severity: %s, first_seen_at: %s)",
                    device_name, source, display_code, severity, first_seen_at,
                )
            else:
                previous_level = _LOGGER.level
                try:
                    _LOGGER.setLevel(logging.WARNING)
                    _LOGGER.warning(
                        "Aira warning active on %s: [%s] %s (severity: %s, first_seen_at: %s)",
                        device_name, source, display_code, severity, first_seen_at,
                    )
                finally:
                    _LOGGER.setLevel(previous_level)

        cleared = set(self._active_errors) - current_codes
        for raw_code in cleared:
            prefix = next((prefix for prefix in ERROR_SOURCE_PREFIXES.values() if raw_code.startswith(prefix)), "",)
            display_name = raw_code.removeprefix(prefix).replace("_", " ").title()
            severity, _ = self._active_errors.pop(raw_code)

            if severity.lower() in {"critical", "error"}:
                _LOGGER.error(
                    "Aira alarm cleared on %s: %s",
                    device_name, display_name,
                )
            else:
                previous_level = _LOGGER.level
                try:
                    _LOGGER.setLevel(logging.WARNING)
                    _LOGGER.warning(
                        "Aira warning cleared on %s: %s",
                        device_name, display_name,
                    )
                finally:
                    _LOGGER.setLevel(previous_level)

    async def _async_clear_gatt_cache(self) -> None:
        """Safely clear the BLE GATT cache for this device."""
        if not self.mac_address:
            return

        _LOGGER.info(
            "Clearing BLE GATT cache for %s due to suspected stale cache",
            self.mac_address,
        )
        try:
            await self.aira.ble._clear_cache(self.mac_address)
        except Exception as err:
            _LOGGER.warning("GATT cache clear raised: %s", err)
        finally:
            self._needs_cache_clear = False

    async def _async_reconnect(self) -> None:
        """Attempt to reconnect to the device in a background task scheduled by _schedule_reconnect."""
        aira = self.aira
        mac_address: str = self.mac_address  # type: ignore[assignment]

        try:
            if self._needs_cache_clear:
                await self._async_clear_gatt_cache()

            # Explicitly disconnect to clean up any stale connection state
            _LOGGER.debug("Disconnecting before reconnection attempt")
            try:
                await aira.ble._disconnect()
            except Exception as err:
                _LOGGER.debug("Disconnect during reconnect raised: %s (nothing to worry about)", err)

            # Small delay to let the BLE stack stabilize
            await asyncio.sleep(0.5)

            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, mac_address, connectable=True
            )
            if not ble_device:
                _LOGGER.error(
                    "Device %s not found in Home Assistant's bluetooth during reconnect attempt.",
                    mac_address,
                )
                return

            _LOGGER.info("Attempting reconnection to %s", ble_device.name)
            try:
                # Use standard connection (has built-in retry logic)
                success = await aira.ble._connect_device(
                    ble_device,
                    timeout=BLE_CONNECT_TIMEOUT,
                )
            except Exception as err:
                _LOGGER.error("Reconnection attempt raised exception: %s", err)
                if _is_cache_error(err):
                    self._needs_cache_clear = True
                    # Try purging the cache now so the next attempt starts cleanly.
                    await self._async_clear_gatt_cache()
                success = False
        except Exception as err:
            _LOGGER.error(
                "Unexpected error during reconnection attempt: %s",
                err,
                exc_info=True,
            )
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

        self._reconnect_task = self.hass.async_create_task(self._async_reconnect())

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Aira device via BLE."""
        start_time = perf_counter()

        mac_address: str = self.mac_address  # type: ignore[assignment]
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
                try:
                    async with asyncio.timeout(5):
                        rssi = await self.aira.ble._get_rssi()
                except TimeoutError:
                    _LOGGER.debug("Fallback RSSI fetch timed out")
                else:
                    _LOGGER.debug("Fallback RSSI fetch used")

            if not is_connected:
                _LOGGER.warning(
                    "Device not connected. Raising UpdateFailed to trigger reconnect logic."
                )
                raise UpdateFailed("Device not connected")

            # Fetch data
            try:
                # get data
                data = await self._fetch_all_data(start_time, rssi)
                _LOGGER.debug("Gathered data in %.1f seconds", perf_counter() - start_time)
                return data
            except Exception as data_err:
                _LOGGER.error("Error fetching data: %s", data_err)
                raise UpdateFailed from data_err

        except Exception as err:
            # Attempt to reconnect if not connected
            if is_connected:
                _LOGGER.error("Unexpected error during data update: %s. Considering disconnected", err, exc_info=True)
                self._is_connected = False
                is_connected = False

            # Device is not connected, return stale data if available and recent enough
            stale_result = None
            if self._last_successful_data and self._last_successful_timestamp:
                age = start_time - self._last_successful_timestamp
                if age < STALE_DATA_THRESHOLD:
                    _LOGGER.debug(
                        "Not connected, returning stale data (age: %.0f seconds)",
                        age,
                    )
                    stale_result = deepcopy(self._last_successful_data)
                    stale_result["connected"] = False
                    stale_result["rssi"] = rssi

            # Device is not connected, attempt reconnection with exponential backoff
            if self._reconnect_attempts < self._max_reconnect_attempts:
                now = perf_counter()
                if now >= self._next_reconnect_at:
                    _LOGGER.debug(
                        "Not connected, scheduling reconnect (attempt %d/%d)",
                        self._reconnect_attempts + 1,
                        self._max_reconnect_attempts,
                    )
                    self._schedule_reconnect()
                    delay = BLE_RECONNECT_BACKOFF[min(self._reconnect_attempts, len(BLE_RECONNECT_BACKOFF) - 1)]
                    self._next_reconnect_at = now + delay
                    self._reconnect_attempts += 1
                else:
                    _LOGGER.debug(
                        "Backoff active, next reconnect in %.0f seconds",
                        self._next_reconnect_at - now
                    )
            else:
                # Max attempts reached -> schedule a full entry reload so HA cleanly tears down BLE,
                # re-runs async_setup_entry and retries with native ConfigEntryNotReady backoff.
                # See https://github.com/Invy55/ha-airahome/wiki/Bluetooth-Issues
                _LOGGER.error(
                    "Max reconnect attempts (%d) reached, scheduling entry reload.",
                    self._max_reconnect_attempts
                )
                self._reconnect_attempts = 0
                self._next_reconnect_at = 0.0
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self.config_entry.entry_id)
                )

            if stale_result is not None:
                return stale_result
            raise UpdateFailed("Device not connected and no usable stale data") from err
