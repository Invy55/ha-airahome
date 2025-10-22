"""Climate platform for Aira Heat Pump."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DEVICE_NAME, DEFAULT_SHORT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aira climate platform."""
    device_data = hass.data[DOMAIN][entry.entry_id]
    
    async_add_entities([AiraClimate(device_data, entry)], True)


class AiraClimate(ClimateEntity):
    """Representation of an Aira Heat Pump climate device."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO]

    def __init__(self, device_data: dict[str, Any], entry: ConfigEntry) -> None:
        """Initialise the climate device."""
        self._device = device_data["device"]
        self._mac_address = device_data["mac_address"]
        self._attr_unique_id = f"{entry.entry_id}_climate"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data.get(CONF_DEVICE_NAME, DEFAULT_SHORT_NAME),
            "manufacturer": "Aira",
            "model": "Heat Pump",
        }
        
        self._attr_current_temperature = None
        self._attr_target_temperature = None
        self._attr_hvac_mode = HVACMode.OFF

    async def async_update(self) -> None:
        """Fetch new state data for the climate device.
        
        This is the only method that should fetch new data for Home Assistant.
        """
        try:
            # TODO: Implement actual data fetching from the device
            # For now, this is a placeholder for the first iteration
            _LOGGER.debug("Updating Aira climate device: %s", self._mac_address)
            
            # Example of how you might fetch data:
            # data = await self.hass.async_add_executor_job(self._device.get_status)
            # self._attr_current_temperature = data.get("current_temp")
            # self._attr_target_temperature = data.get("target_temp")
            
        except Exception as err:
            _LOGGER.error("Error updating Aira device: %s", err)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        
        _LOGGER.debug("Setting temperature to %s", temperature)
        
        try:
            # TODO: Implement actual temperature setting
            # await self.hass.async_add_executor_job(
            #     self._device.set_temperature, temperature
            # )
            self._attr_target_temperature = temperature
            await self.async_update_ha_state()
        except Exception as err:
            _LOGGER.error("Error setting temperature: %s", err)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target HVAC mode."""
        _LOGGER.debug("Setting HVAC mode to %s", hvac_mode)
        
        try:
            # TODO: Implement actual HVAC mode setting
            # await self.hass.async_add_executor_job(
            #     self._device.set_mode, hvac_mode
            # )
            self._attr_hvac_mode = hvac_mode
            await self.async_update_ha_state()
        except Exception as err:
            _LOGGER.error("Error setting HVAC mode: %s", err)

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.async_set_hvac_mode(HVACMode.AUTO)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

