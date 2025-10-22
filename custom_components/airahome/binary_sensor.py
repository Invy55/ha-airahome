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
        AiraConnectionBinarySensor(coordinator, entry),
        AiraManualModeBinarySensor(coordinator, entry),
        AiraNightModeBinarySensor(coordinator, entry),
        AiraAwayModeBinarySensor(coordinator, entry),
        AiraInlineHeaterBinarySensor(coordinator, entry),
        AiraHotWaterHeatingBinarySensor(coordinator, entry),
        AiraDefrostingBinarySensor(coordinator, entry),
        AiraAlarmsBinarySensor(coordinator, entry),
    ]
    
    async_add_entities(binary_sensors)


class AiraBaseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Base class for Aira binary sensors."""

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_type: str,
        name: str,
        device_class: BinarySensorDeviceClass | None = None,
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._sensor_type = sensor_type
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_unique_id = f"{entry.entry_id}_{sensor_type}"
        self._attr_has_entity_name = True
        
        # Link to device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data.get(CONF_DEVICE_NAME, DEFAULT_SHORT_NAME),
            "manufacturer": "Aira",
            "model": "Heat Pump",
        }


class AiraConnectionBinarySensor(AiraBaseBinarySensor):
    """Binary sensor for BLE connection status."""

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialise connection binary sensor."""
        super().__init__(
            coordinator,
            entry,
            "connection",
            "Connection",
            BinarySensorDeviceClass.CONNECTIVITY,
        )

    @property
    def is_on(self) -> bool:
        """Return true if connected."""
        return self.coordinator.data.get("connected", False)


class AiraManualModeBinarySensor(AiraBaseBinarySensor):
    """Binary sensor for manual mode status."""

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialise manual mode binary sensor."""
        super().__init__(
            coordinator,
            entry,
            "manual_mode",
            "Manual Mode",
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if manual mode is enabled."""
        state = self.coordinator.data.get("state", {})
        return state.get("manual_mode_enabled")


class AiraNightModeBinarySensor(AiraBaseBinarySensor):
    """Binary sensor for night mode status."""

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialise night mode binary sensor."""
        super().__init__(
            coordinator,
            entry,
            "night_mode",
            "Night Mode",
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if night mode is enabled."""
        state = self.coordinator.data.get("state", {})
        return state.get("night_mode_enabled")


class AiraAwayModeBinarySensor(AiraBaseBinarySensor):
    """Binary sensor for away mode status."""

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialise away mode binary sensor."""
        super().__init__(
            coordinator,
            entry,
            "away_mode",
            "Away Mode",
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if away mode is enabled."""
        state = self.coordinator.data.get("state", {})
        return state.get("away_mode_enabled")


class AiraInlineHeaterBinarySensor(AiraBaseBinarySensor):
    """Binary sensor for inline heater status."""

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialise inline heater binary sensor."""
        super().__init__(
            coordinator,
            entry,
            "inline_heater",
            "Inline Heater",
            BinarySensorDeviceClass.HEAT,
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if inline heater is active."""
        state = self.coordinator.data.get("state", {})
        return state.get("inline_heater_active")


class AiraHotWaterHeatingBinarySensor(AiraBaseBinarySensor):
    """Binary sensor for hot water heating status."""

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialise hot water heating binary sensor."""
        super().__init__(
            coordinator,
            entry,
            "hot_water_heating",
            "Hot Water Heating",
            BinarySensorDeviceClass.HEAT,
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if hot water heating is enabled."""
        state = self.coordinator.data.get("state", {})
        hot_water = state.get("hot_water", {})
        return hot_water.get("heating_enabled")


class AiraDefrostingBinarySensor(AiraBaseBinarySensor):
    """Binary sensor for defrosting status."""

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialise defrosting binary sensor."""
        super().__init__(
            coordinator,
            entry,
            "defrosting",
            "Defrosting",
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if unit is defrosting."""
        system_check = self.coordinator.data.get("system_check", {})
        megmet_status = system_check.get("megmet_status", {})
        return megmet_status.get("outdoor_unit_defrosting")


class AiraAlarmsBinarySensor(AiraBaseBinarySensor):
    """Binary sensor for alarms status."""

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialise alarms binary sensor."""
        super().__init__(
            coordinator,
            entry,
            "alarms",
            "Alarms",
            BinarySensorDeviceClass.PROBLEM,
        )

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

