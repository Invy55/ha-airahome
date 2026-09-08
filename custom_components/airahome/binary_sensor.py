"""Binary sensor platform for Aira Heat Pump."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_NAME, CONF_DEVICE_UUID, CONF_MAC_ADDRESS, CONF_NUM_ZONES, DEFAULT_NUM_ZONES, DEFAULT_SHORT_NAME, DOMAIN
from .coordinator import AiraDataUpdateCoordinator, _parse_error


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aira binary sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    binary_sensors: list[BinarySensorEntity] = [
        AiraBinarySensor(coordinator, entry,
            unique_id_suffix="connection",
            data_path=("connected", ),
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            icon=("mdi:bluetooth-off", "mdi:bluetooth-connect"),
        ),
        AiraBinarySensor(coordinator, entry,
            unique_id_suffix="manual_mode",
            data_path=("state", "manual_mode_enabled"),
            device_class=None,
            icon=("mdi:hand-back-right-off-outline", "mdi:hand-back-right-outline"),
        ),
        AiraBinarySensor(coordinator, entry,
            unique_id_suffix="night_mode",
            data_path=("state", "night_mode_enabled"),
            device_class=None,
            icon=("mdi:sleep-off", "mdi:sleep"),
        ),
        AiraBinarySensor(coordinator, entry,
            unique_id_suffix="away_mode",
            data_path=("state", "away_mode_enabled"),
            device_class=None,
            icon=("mdi:home-outline", "mdi:home-export-outline"),
        ),
        AiraBinarySensor(coordinator, entry,
            unique_id_suffix="inline_heater",
            data_path=("state", "inline_heater_active"),
            device_class=BinarySensorDeviceClass.HEAT,
            icon=("mdi:power-plug-off-outline", "mdi:resistor"),
        ),
        AiraBinarySensor(coordinator, entry,
            unique_id_suffix="dhw_heating",
            data_path=("state", "hot_water", "heating_enabled"),
            device_class=BinarySensorDeviceClass.HEAT,
            icon=("mdi:water-boiler-off", "mdi:water-boiler"),
        ),
        AiraBinarySensor(coordinator, entry,
            unique_id_suffix="defrosting",
            data_path=("system_check_state", "megmet_status", "outdoor_unit_defrosting"),
            icon=("mdi:sun-snowflake-variant", "mdi:snowflake-melt"),
        ),
        AiraBinarySensor(coordinator, entry,
            unique_id_suffix="ou_pump",
            data_path=("system_check_state", "circulation_pump_status", "pump_0_active"),
            icon=("mdi:pump-off", "mdi:pump"),
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        AiraProblemBinarySensor(
            coordinator,
            entry,
            unique_id_suffix="alarms",
            severities=("critical", "error"),
            include_stopping_flags=True,
        ),
        AiraProblemBinarySensor(
            coordinator,
            entry,
            unique_id_suffix="warnings",
            severities=("warning", "unspecified"),
            include_stopping_flags=False,
        ),
    ]
    
    # PER ZONE LOOP
    num_zones = entry.options.get(CONF_NUM_ZONES, DEFAULT_NUM_ZONES)
    _LOGGER.debug("Setting up binary_sensors for %d zones based on config entry options", num_zones)

    for i in range(1, num_zones+1):  # zone loop
        binary_sensors.extend([
        AiraBinarySensor(coordinator, entry,
            unique_id_suffix=f"zone_{i}_circulator",
            data_path=("system_check_state", "circulation_pump_status", f"pump_{i}_active"),
            icon=("mdi:pump-off", "mdi:pump")
        ),
        AiraBinarySensor(coordinator, entry,
            unique_id_suffix=f"thermostat_{i}_low_battery",
            data_path=("state", "thermostats", "last_update", "warning_low_battery_level"),
            device_class=BinarySensorDeviceClass.BATTERY,
            icon=("mdi:battery", "mdi:battery-alert-variant-outline"),
            index=f"ZONE_{i}"
        )
        ])

    async_add_entities(binary_sensors, True)

# ============================================================================
# BINARY SENSORS
# ===========================================================================

class AiraBaseBinarySensor(CoordinatorEntity, BinarySensorEntity): # type: ignore
    """Base class for Aira binary sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        unique_id_suffix: str,
        icon: str | tuple[str, str] | None = None,
        entity_category: EntityCategory | None = None,
        enabled_by_default: bool = True
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator)
        self._device_uuid = entry.data[CONF_DEVICE_UUID]
        self._attr_unique_id = f"{self._device_uuid}_{unique_id_suffix}"
        
        self._icon = icon

        if entity_category:
            self._attr_entity_category = entity_category

        self._attr_entity_registry_enabled_default = enabled_by_default

        self._attr_translation_key = unique_id_suffix

        self._attr_device_info = DeviceInfo(**{
            "identifiers": {(DOMAIN, self._device_uuid)},
            "connections": {(dr.CONNECTION_BLUETOOTH, entry.data.get(CONF_MAC_ADDRESS))},
            "name": entry.data.get(CONF_DEVICE_NAME, DEFAULT_SHORT_NAME),
            "manufacturer": "Aira",
            "model": "Heat Pump",
        })

    @property
    def icon(self) -> str: # type: ignore
        """Return the icon to use for the binary sensor."""
        if not self._icon:
            return # type: ignore
        if isinstance(self._icon, tuple):
            return self._icon[1] if self.is_on else self._icon[0]
        return self._icon

class AiraBinarySensor(AiraBaseBinarySensor):
    """Generic binary sensor for Aira."""

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        device_class: BinarySensorDeviceClass | None = None,
        icon: str | tuple[str, str] = ("mdi:toggle-switch-off-outline", "mdi:toggle-switch-outline"),
        entity_category: EntityCategory | None = None,
        enabled_by_default: bool = True,
        index: int | str | None = None
    ) -> None:
        """Initialise generic binary sensor."""
        super().__init__(coordinator, entry, unique_id_suffix, icon, entity_category, enabled_by_default)
        self._attr_device_class = device_class
        self._data_path = data_path
        self._index = index

    @property
    def is_on(self) -> bool | None: # type: ignore
        """Return true if the sensor is on."""
        if not self.coordinator.data:
            return None

        if self._data_path:
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path] # type: ignore
                    if self._index is not None and isinstance(value, list):
                        for element in value:
                            # caso in cui l'elemento ha un campo zone:
                            if isinstance(self._index, str) and element.get("zone") == self._index:
                                if element.get("rssi") == 0:
                                    return None
                                value = element
                                break
                        if isinstance(self._index, int) and len(value) >= self._index:
                            value = value[self._index - 1]  # Adjust for 0-based index

                return bool(value)
            except (KeyError, ValueError, TypeError):
                return None
        return None

# ============================================================================
# PROBLEM (ALARMS / WARNINGS) SENSOR
# ============================================================================

class AiraProblemBinarySensor(AiraBaseBinarySensor):
    """Problem binary sensor that filters alarms or warnings by severity."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        unique_id_suffix: str,
        severities: tuple[str, ...],
        include_stopping_flags: bool = False,
    ) -> None:
        """Initialise problem binary sensor."""
        super().__init__(coordinator, entry, unique_id_suffix, None)
        self._severities = tuple(s.lower() for s in severities)
        self._include_stopping_flags = include_stopping_flags
        self._prefix_label = "error" if any(s in self._severities for s in ("critical", "error")) else "warning"

    def _get_matching_errors(self) -> list[tuple[str, str, str, str, Any]]:
        """Return parsed error tuples matching this sensor's severity filter, deduplicated by raw_code."""
        if not self.coordinator.data:
            return []

        # Get both error lists since some errors appear in only one of them
        state_list = self.coordinator.data.get("state", {}).get("errors", [])
        system_list = self.coordinator.data.get("system_check_state", {}).get("errors", [])

        seen_raw_codes: set[str] = set()
        matching: list[tuple[str, str, str, str, Any]] = []

        for err in state_list + system_list:
            source, display_code, raw_code, severity, occurred_at = _parse_error(err)
            if raw_code != "unknown" and raw_code not in seen_raw_codes:
                seen_raw_codes.add(raw_code)
                if severity.lower() in self._severities:
                    matching.append((source, display_code, raw_code, severity, occurred_at))

        return matching

    @property
    def is_on(self) -> bool:
        """Return true if any matching problems are active."""
        if not self.coordinator.data:
            return False

        if self._include_stopping_flags:
            state = self.coordinator.data.get("state", {})
            error_meta = state.get("error_metadata", {})
            if (
                error_meta.get("hp_has_stopping_alarms")
                or error_meta.get("hp_has_acknowledgeable_alarms")
                or error_meta.get("compressor_has_stopping_alarm")
            ):
                return True

        return len(self._get_matching_errors()) > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attributes: dict[str, Any] = {}

        if self._include_stopping_flags:
            state = self.coordinator.data.get("state", {})
            error_meta = state.get("error_metadata", {})
            attributes["stopping_alarms"] = "🚨" if error_meta.get("hp_has_stopping_alarms", False) else "🟢"
            attributes["acknowledgeable_alarms"] = "🚨" if error_meta.get("hp_has_acknowledgeable_alarms", False) else "🟢"
            attributes["compressor_alarms"] = "🚨" if error_meta.get("compressor_has_stopping_alarm", False) else "🟢"

        matching = self._get_matching_errors()
        attributes[f"{self._prefix_label}_count"] = len(matching)

        for i, (source, display_code, raw_code, severity, occurred_at) in enumerate(matching[:5], 1):
            attributes[f"{self._prefix_label}_{i}_source"] = source
            attributes[f"{self._prefix_label}_{i}_code"] = display_code
            attributes[f"{self._prefix_label}_{i}_severity"] = severity
            if occurred_at:
                attributes[f"{self._prefix_label}_{i}_occurred_at"] = (
                    occurred_at.isoformat() if hasattr(occurred_at, "isoformat") else str(occurred_at)
                )
            else:
                first_seen = self.coordinator._active_errors.get(raw_code)
                if first_seen:
                    attributes[f"{self._prefix_label}_{i}_first_seen_at"] = (
                        first_seen[1] if isinstance(first_seen, tuple) else first_seen
                    )

        return attributes