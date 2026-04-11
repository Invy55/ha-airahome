"""Water heater platform for Aira Heat Pump."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.water_heater import WaterHeaterEntity, WaterHeaterEntityFeature
from homeassistant.components.water_heater.const import STATE_ELECTRIC, STATE_HEAT_PUMP, STATE_PERFORMANCE
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pyairahome import AiraHome
from pyairahome.commands import SetTargetHotWaterTemperature

from .const import CONF_DEVICE_NAME, CONF_DEVICE_UUID, CONF_INSTALLATION, CONF_MAC_ADDRESS, DEFAULT_SHORT_NAME, DOMAIN
from .coordinator import AiraDataUpdateCoordinator


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aira water heater platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    aira = hass.data[DOMAIN][entry.entry_id]["aira"]
    
    water_heaters: list[WaterHeaterEntity] = [
        AiraWaterHeater(coordinator, entry, aira)
    ]
    
    async_add_entities(water_heaters, True)


# ============================================================================
# WATER HEATER
# ============================================================================

class AiraWaterHeater(CoordinatorEntity, WaterHeaterEntity): # type: ignore
    """Representation of an Aira Heat Pump DHW (Domestic Hot Water) system."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
    )
    _attr_operation_list = [
        STATE_OFF,
        STATE_PERFORMANCE,
        STATE_HEAT_PUMP,
        STATE_ELECTRIC,
    ]
    _attr_max_temp = 65
    _attr_min_temp = 15 # min to 15 because schedule can take it to 15, but we don't allow the user to set it
    _attr_target_temperature_step = 0.1
    
    _allowed_temperatures = [50, 55, 65]  # default; overridden based on tank size in __init__

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        aira: AiraHome
    ) -> None:
        """Initialize the water heater."""
        super().__init__(coordinator)
        self._device_uuid = entry.data[CONF_DEVICE_UUID]
        tank_size = entry.data.get(CONF_INSTALLATION, {}).get("tank_size", "")
        if "100" in tank_size: # since 100 liters is very small aira allows different setpoints
            self._allowed_temperatures = [55, 60, 65]
        unique_id_suffix = "water_heater"
        self._attr_unique_id = f"{self._device_uuid}_{unique_id_suffix}"
        self._attr_translation_key = unique_id_suffix
        self.aira = aira

        self._attr_device_info = DeviceInfo(**{
            "identifiers": {(DOMAIN, self._device_uuid)},
            "connections": {(dr.CONNECTION_BLUETOOTH, entry.data.get(CONF_MAC_ADDRESS))},
            "name": entry.data.get(CONF_DEVICE_NAME, DEFAULT_SHORT_NAME),
            "manufacturer": "Aira",
            "model": "Heat Pump",
        })

    @property
    def current_temperature(self): # type: ignore
        """Return the current temperature."""
        if not self.coordinator.data:
            return None
        
        try:
            return round(float(self.coordinator.data["state"]["current_hot_water_temperature"]), 2)
        except (KeyError, ValueError, TypeError):
            return None
    
    @property
    def target_temperature(self): # type: ignore
        """Return the setpoint temperature considering scheduled temperatures."""
        try:
            value = self.coordinator.data.get("state", {}).get("scheduled_hot_water_temperature")
            return round(float(value), 2) if value is not None else None
        except (KeyError, ValueError, TypeError):
            return None
    
    async def _set_temperature(self, temperature: float) -> bool | list[dict]:
        """Set the water heater temperature to the specified value."""
        _LOGGER.debug("Setting water heater temperature to %s°C", temperature)
        command_in = SetTargetHotWaterTemperature(temperature=temperature)
            
        try:
            updates = [x async for x in await self.aira.ble._run_command(command_in=command_in)] # type: ignore
            if "succeeded" in updates[-1]:
                return True
            elif "error" in updates[-1]:
                _LOGGER.error("Failed to set water heater temperature: %s", updates[-1]["error"])
                return False
        except RuntimeError as e:
            _LOGGER.error("Error setting water heater temperature: %s", str(e))
        
        return False

    async def _fake_temperature_set(self, temperature: float) -> None:
        """Fake setting the water heater temperature (for propagating change to the entire integration asap)."""
        _LOGGER.debug("Faking setting water heater temperature to %s°C", temperature)
        try:
            self.coordinator.data['state']['target_hot_water_temperature'] = temperature
            self._attr_target_temperature = temperature
            self.coordinator.async_update_listeners() # force every entity subscribed to the coordinator to update
        except (KeyError, TypeError):
            pass

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        using_scheduler = False
        states = self.coordinator.data.get('state', {})
        scheduler = states.get('scheduler', {})
        for action in scheduler.get('active_actions', []):
            if 'set_dhw_setpoint' in action:
                using_scheduler = True
                break

        previous_temp = self.target_temperature
        if not previous_temp:
            return

        if using_scheduler:
            _LOGGER.warning("Cannot set temperature manually while scheduler is active.")
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="scheduler_active"
            )

        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="temperature_not_provided"
            )

        temp = float(temperature)
        
        if self._attr_target_temperature_step and previous_temp is not None and abs(int(temp*10 - previous_temp*10)) == self._attr_target_temperature_step*10:
            # used + - buttons, calculate closest allowed temperature
            if temp < previous_temp: # pressed -
                # If we're already at the minimum allowed temperature, stay there
                if previous_temp == min(self._allowed_temperatures):
                    closest_temp = previous_temp
                else:
                    # Find the next lower temperature in allowed values
                    lower_temps = [t for t in self._allowed_temperatures if t < previous_temp]
                    closest_temp = max(lower_temps) if lower_temps else previous_temp
            else: # pressed +
                # If we're already at the maximum allowed temperature, stay there
                if previous_temp == max(self._allowed_temperatures):
                    closest_temp = previous_temp
                else:
                    # Find the next higher temperature in allowed values
                    higher_temps = [t for t in self._allowed_temperatures if t > previous_temp]
                    closest_temp = min(higher_temps) if higher_temps else previous_temp

            if closest_temp and closest_temp != previous_temp:
                _LOGGER.debug("Closest temperature found. Setting water heater temperature to %s°C", closest_temp)   
                if await self._set_temperature(closest_temp):
                    await self._fake_temperature_set(closest_temp)
                    return
        else:
            # Check if the temperature is in the allowed list
            if temp not in self._allowed_temperatures:
                allowed_temps_str = ", ".join(map(str, self._allowed_temperatures))
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_temperature",
                    translation_placeholders={
                        "allowed_temperatures": allowed_temps_str,
                        "temperature": temperature
                    },
                )
            if await self._set_temperature(temp):
                _LOGGER.debug("Selected temperature allowed. Setting water heater temperature to %s°C", temp)
                await self._fake_temperature_set(temp)
                return

        if previous_temp:
            await self._fake_temperature_set(previous_temp)  # Ensure state is consistent

    @property
    def current_operation(self): # type: ignore
        """Return current operation status."""
        status = None
        if not self.coordinator.data:
            return status
        
        if not self.coordinator.data.get("state", {}).get("hot_water", {}).get("heating_enabled"):
            status = STATE_OFF
        else:
            heatpump = False
            inline_heater = False

            pump_active_state = self.coordinator.data.get("state", {}).get("pump_active_state", False)
            if pump_active_state == "PUMP_ACTIVE_STATE_DHW":
                heatpump = True
            inline_heater_state = self.coordinator.data.get("state", {}).get("inline_heater_active", False)
            
            if inline_heater_state:
                inline_heater = True
            if heatpump and inline_heater:
                status = STATE_PERFORMANCE
            elif heatpump:
                status = STATE_HEAT_PUMP
            elif inline_heater:
                status = STATE_ELECTRIC
            else:
                status = STATE_OFF

        return status