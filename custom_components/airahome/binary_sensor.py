"""Binary sensor platform for Aira Heat Pump."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_NAME, DEFAULT_SHORT_NAME, DOMAIN
from .coordinator import AiraDataUpdateCoordinator

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
            name="Connection",
            unique_id_suffix="connection",
            data_path=("connected", ),
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            icon=("mdi:bluetooth-off", "mdi:bluetooth-connect"),
        ),
        AiraBinarySensor(coordinator, entry,
            name="Manual Mode",
            unique_id_suffix="manual_mode",
            data_path=("state", "manual_mode_enabled"),
            device_class=None,
            icon=("mdi:hand-back-right-off-outline", "mdi:hand-back-right-outline"),
        ),
        AiraBinarySensor(coordinator, entry,
            name="Night Mode",
            unique_id_suffix="night_mode",
            data_path=("state", "night_mode_enabled"),
            device_class=None,
            icon=("mdi:sleep-off", "mdi:sleep"),
        ),
        AiraBinarySensor(coordinator, entry,
            name="Away Mode",
            unique_id_suffix="away_mode",
            data_path=("state", "away_mode_enabled"),
            device_class=None,
            icon=("mdi:home-outline", "mdi:home-export-outline"),
        ),
        AiraBinarySensor(coordinator, entry,
            name="Inline Heater",
            unique_id_suffix="inline_heater",
            data_path=("state", "inline_heater_active"),
            device_class=BinarySensorDeviceClass.HEAT,
            icon=("mdi:power-plug-off-outline", "mdi:resistor"),
        ),
        AiraBinarySensor(coordinator, entry,
            name="DHW Heating",
            unique_id_suffix="dhw_heating",
            data_path=("state", "hot_water", "heating_enabled"),
            device_class=BinarySensorDeviceClass.HEAT,
            icon=("mdi:water-boiler-off", "mdi:water-boiler"),
        ),
        AiraBinarySensor(coordinator, entry,
            name="Defrosting",
            unique_id_suffix="defrosting",
            data_path=("system_check", "megmet_status", "outdoor_unit_defrosting"),
            icon=("mdi:sun-snowflake-variant", "mdi:snowflake-melt"),
        ),
        AiraAlarmsBinarySensor(coordinator, entry),
    ]
    
    async_add_entities(binary_sensors)

# ============================================================================
# BINARY SENSORS
# ===========================================================================

class AiraBaseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Base class for Aira binary sensors."""

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator)
        self._entry_id = entry.entry_id
        
        # Link to device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data.get(CONF_DEVICE_NAME, DEFAULT_SHORT_NAME),
            "manufacturer": "Aira",
            "model": "Heat Pump",
        }

class AiraBinarySensor(AiraBaseBinarySensor):
    """Generic binary sensor for Aira."""

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        name: str,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        device_class: BinarySensorDeviceClass | None = None,
        icon: str | tuple[str, str] = ("toggle-switch-off-outline", "toggle-switch-outline"),
    ) -> None:
        """Initialise generic binary sensor."""
        super().__init__(coordinator, entry)
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{unique_id_suffix}"
        self._attr_device_class = device_class
        self._data_path = data_path
        self._icon = icon

    @property
    def is_on(self) -> bool | None:
        """Return true if the sensor is on."""
        if not self.coordinator.data:
            return None

        if self._data_path:
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path]

                return bool(value)
            except (KeyError, ValueError, TypeError):
                return None
        return None

    @property
    def icon(self) -> str:
        """Return the icon to use for the binary sensor."""
        if isinstance(self._icon, tuple):
            return self._icon[1] if self.is_on else self._icon[0]
        return self._icon

# ============================================================================
# ALARM SENSOR
# ===========================================================================

class AiraAlarmsBinarySensor(AiraBaseBinarySensor):
    """Binary sensor for alarms status."""

    _attr_name = "Alarms"
    _attr_unique_id = "alarms"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialise alarms binary sensor."""
        super().__init__(coordinator, entry)

    @property
    def is_on(self) -> bool:
        """Return true if there are active alarms."""
        state = self.coordinator.data.get("state", {})
        error_meta = state.get("error_metadata", {})
        return bool(
            error_meta.get("hp_has_stopping_alarms")
            or error_meta.get("hp_has_acknowledgeable_alarms")
            or error_meta.get("compressor_has_stopping_alarm")
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        state = self.coordinator.data.get("state", {})
        error_meta = state.get("error_metadata", {})
        errors = state.get("errors", [])
        
        attributes = {
            "stopping_alarms": error_meta.get("hp_has_stopping_alarms", False),
            "acknowledgeable_alarms": error_meta.get("hp_has_acknowledgeable_alarms", False),
            "compressor_alarms": error_meta.get("compressor_has_stopping_alarm", False),
            "error_count": len(errors),
        }
        
        # Add first few errors
        if errors:
            for i, error in enumerate(errors[:3], 1):
                attributes[f"error_{i}_code"] = error.get("code", "Unknown")
                attributes[f"error_{i}_message"] = error.get("message", "Unknown")
        
        return attributes