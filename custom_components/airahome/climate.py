"""Climate platform for Aira Heat Pump."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pyairahome import AiraHome
from pyairahome.commands import (
    DisableCoolingFunction,
    DisableHeatingFunction,
    EnableCoolingFunction,
    EnableHeatingFunction,
    SetZoneSetpoints,
)
from pyairahome.device.heat_pump.command.v1.set_zone_setpoints_pb2 import SetZoneSetpoints as _SetZoneSetpointsPb2, ZoneTemperatures  # type: ignore

from . import async_get_translation
from .const import (
    CONF_DEVICE_NAME,
    CONF_DEVICE_UUID,
    CONF_MAC_ADDRESS,
    CONF_NUM_ZONES,
    DEFAULT_NUM_ZONES,
    DEFAULT_SHORT_NAME,
    DOMAIN,
)
from .coordinator import AiraDataUpdateCoordinator

Kind = _SetZoneSetpointsPb2.Kind


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aira climate platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    aira = hass.data[DOMAIN][entry.entry_id]["aira"]

    num_zones = entry.options.get(CONF_NUM_ZONES, DEFAULT_NUM_ZONES)
    _LOGGER.debug("Setting up climate entities for %d zones based on config entry options", num_zones)

    # Use configured pump modes instead of current pump mode state to determine supported HVAC modes, since the user could have disabled cooling but we want ha to allow it to be enabled back
    configured_pump_modes = coordinator.data.get("state", {}).get("configured_pump_modes", "PUMP_MODE_STATE_HEATING_COOLING").lower()

    entities: list[ClimateEntity] = []
    for i in range(1, num_zones + 1):
        entities.append(
            AiraZoneClimate(
                coordinator, entry, aira,
                zone=i,
                allowed_pump_mode_state=configured_pump_modes
            )
        )

    async_add_entities(entities, True)


# ============================================================================
# BASE CLIMATE CLASS
# ============================================================================

class AiraClimateBase(CoordinatorEntity, ClimateEntity):  # type: ignore
    """Base class for Aira climate entities."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        aira: AiraHome,
        unique_id_suffix: str,
    ) -> None:
        """Initialise the climate entity."""
        super().__init__(coordinator)
        self._device_uuid = entry.data[CONF_DEVICE_UUID]
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

    def _fake_write_coordinator(self, path: tuple, value: Any) -> None:
        """Fake setting a value in the coordinator data to reflect a successful command, then write state."""
        _LOGGER.debug("Fake writing to coordinator data at path %s with value %s", path, value)
        try:
            data = self.coordinator.data
            for key in path[:-1]:
                data = data[key]
            data[path[-1]] = value
            self.async_write_ha_state()
        except (KeyError, TypeError):
            pass

# ============================================================================
# ZONE CLIMATE ENTITY
# ============================================================================

class AiraZoneClimate(AiraClimateBase):
    """Climate entity representing a single Aira heating/cooling zone."""

    _attr_target_temperature_step = 0.5
    _attr_min_temp = 10.0
    _attr_max_temp = 30.0
    _attr_precision = 0.1

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        aira: AiraHome,
        zone: int,
        allowed_pump_mode_state: str,
    ) -> None:
        """Initialise the zone climate entity."""
        unique_id_suffix = f"zone_{zone}_climate"
        super().__init__(coordinator, entry, aira, unique_id_suffix)

        self._zone = zone

        # Determine which HVAC modes the device configuration supports
        self._supports_heating = "heating" in allowed_pump_mode_state
        self._supports_cooling = "cooling" in allowed_pump_mode_state

        hvac_modes: list[HVACMode] = [HVACMode.OFF]
        if self._supports_heating:
            hvac_modes.append(HVACMode.HEAT)
        if self._supports_cooling:
            hvac_modes.append(HVACMode.COOL)
        if self._supports_heating and self._supports_cooling:
            hvac_modes.append(HVACMode.HEAT_COOL)
        _LOGGER.debug("Zone %d allowed pump mode state: %s, supports heating: %s, supports cooling: %s, resulting HVAC modes: %s",
            zone, allowed_pump_mode_state, self._supports_heating, self._supports_cooling, hvac_modes
        )
        self._attr_hvac_modes = hvac_modes

        features = (
            ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TARGET_TEMPERATURE
        )
        if self._supports_heating and self._supports_cooling:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        self._attr_supported_features = features
        _LOGGER.debug("Zone %d supported features: %d", zone, features)


    # Internal helpers
    def _get_thermostat_field(self, field: str) -> Any:
        """Read a field from this zone's thermostat last_update list entry."""
        try:
            updates = self.coordinator.data["state"]["thermostats"]
            if isinstance(updates, list):
                for element in updates:
                    if element.get("zone") == f"ZONE_{self._zone}":
                        return element.get(field)
        except (KeyError, TypeError):
            pass
        return None
    
    async def _set_setpoints(self, heating: float | None, cooling: float | None) -> bool:
        """Send a command to set the heating/cooling setpoints for this zone."""
        if heating is not None and cooling is not None:
            _LOGGER.warning("Can't set both heating and cooling setpoints at the same time due to device limitations. Received heating: %s, cooling: %s", heating, cooling)
            return False
        if heating is None and cooling is None:
            _LOGGER.warning("No setpoint provided to set_setpoints. Received heating: %s, cooling: %s", heating, cooling)
            return False
        
        zone = f"zone_{self._zone}"
        command_in = SetZoneSetpoints(
            zone_setpoints=ZoneTemperatures(
                **{zone: heating if heating is not None else cooling}
            ),
            kind=Kind.KIND_HEATING if heating is not None else Kind.KIND_COOLING
        )
            
        try:
            updates = [x async for x in await self.aira.ble._run_command(command_in=command_in)] # type: ignore
            if "succeeded" in updates[-1]:
                return True
            elif "error" in updates[-1]:
                _LOGGER.error("Failed to set zone %d %s setpoint to %s temperature: %s", self._zone, "heating" if heating is not None else "cooling", str(heating) if heating is not None else str(cooling), updates[-1]["error"])
                return False
        except RuntimeError as e:
            _LOGGER.error("Error setting %s setpoint to %s temperature: %s", "heating" if heating is not None else "cooling", str(heating) if heating is not None else str(cooling), str(e))
        
        return False

    async def _fake_setpoint_set(self, heating: float | None, cooling: float | None) -> None:
        """Fake setting the zone heating/cooling setpoints (for propagating change to the entire integration asap)."""
        _LOGGER.debug("Faking setting zone %d setpoints to heating=%s°C cooling=%s°C", self._zone, heating, cooling)
        try:
            zone_key = f"zone_{self._zone}"
            state = self.coordinator.data["state"]
            if heating is not None:
                state["zone_setpoints_heating"][zone_key] = heating
            if cooling is not None:
                state["zone_setpoints_cooling"][zone_key] = cooling
            
            self.coordinator.async_update_listeners() # force every entity subscribed to the coordinator to update
        except (KeyError, TypeError):
            pass

    async def _set_mode_on_off(self, heating: bool | None, cooling: bool | None) -> bool:
        """Helper for setting HVAC mode by toggling heating/cooling functions."""
        commands = []
        if heating is not None:
            if heating:
                commands.append((EnableHeatingFunction(), "heating", "enabled"))
            else:
                commands.append((DisableHeatingFunction(), "heating", "disabled"))
        if cooling is not None:
            if cooling:
                commands.append((EnableCoolingFunction(), "cooling", "enabled"))
            else:
                commands.append((DisableCoolingFunction(), "cooling", "disabled"))
        
        results = []
        for command in commands:
            command_in, mode, action = command
            try:
                updates = [x async for x in await self.aira.ble._run_command(command_in=command_in)] # type: ignore
                if "succeeded" in updates[-1]:
                    results.append(True)
                elif "error" in updates[-1]:
                    _LOGGER.error("Failed to set %s mode to %s: %s", mode, action, updates[-1]["error"])
                    results.append(False) # TODO: test this append
            except RuntimeError as e:
                _LOGGER.error("Error setting %s mode to %s: %s", mode, action, str(e))
                results.append(False)
        
        return all(results)

    def _fake_mode_set(self, heating: bool | None, cooling: bool | None) -> None:
        """Fake setting the allowed pump mode state (for propagating change to the entire integration asap)."""
        try:
            state = self.coordinator.data["state"]
            current = state.get("allowed_pump_mode_state", "").lower().replace("pump_mode_state_", "")
            has_heat = "heating" in current if heating is None else heating
            has_cool = "cooling" in current if cooling is None else cooling

            if has_heat and has_cool:
                new_state = "PUMP_MODE_STATE_HEATING_COOLING"
            elif has_heat:
                new_state = "PUMP_MODE_STATE_HEATING"
            elif has_cool:
                new_state = "PUMP_MODE_STATE_COOLING"
            else:
                new_state = ""

            state["allowed_pump_mode_state"] = new_state
            _LOGGER.debug("Faking allowed_pump_mode_state to %s", new_state)
            self.coordinator.async_update_listeners()
        except (KeyError, TypeError):
            pass

    # State properties
    @property
    def current_temperature(self) -> float | None:  # type: ignore
        """Return the current temperature from the zone thermostat."""
        if not self.coordinator.data:
            return None
        try:
            raw = self._get_thermostat_field("last_update").get("actual_temperature")
            if raw is not None:
                return round(float(raw) / 10, 2)
        except (ValueError, TypeError):
            pass
        return None

    @property
    def current_humidity(self) -> float | None:  # type: ignore
        """Return the current humidity from the zone thermostat."""
        if not self.coordinator.data:
            return None
        try:
            raw = self._get_thermostat_field("last_update").get("humidity")
            if raw is not None:
                return round(float(raw) / 10, 1)
        except (ValueError, TypeError):
            pass
        return None
    
    @property
    def target_temperature(self) -> float | None:  # type: ignore
        """Return the target temperature for the current HVAC mode"""
        if not self.coordinator.data:
            return None
        try:
            state = self.coordinator.data.get("state", {})
            mode = self.hvac_mode
            if mode == HVACMode.HEAT_COOL:
                return None
            if mode == HVACMode.HEAT:
                value = state.get("zone_setpoints_heating", {}).get(f"zone_{self._zone}")
            elif mode == HVACMode.COOL:
                value = state.get("zone_setpoints_cooling", {}).get(f"zone_{self._zone}")
            else:
                return None
            return round(float(value), 2) if value is not None else None
        except (KeyError, ValueError, TypeError):
            return None
        
    @property
    def target_temperature_high(self) -> float | None:  # type: ignore
        """Return the cooling setpoint (upper bound in HEAT_COOL range mode)."""
        if not self._supports_cooling or not self.coordinator.data:
            return None
        try:
            value = self.coordinator.data.get("state", {}).get(
                "zone_setpoints_cooling", {}
            ).get(f"zone_{self._zone}")
            return round(float(value), 2) if value is not None else None
        except (KeyError, ValueError, TypeError):
            return None

    @property
    def target_temperature_low(self) -> float | None:  # type: ignore
        """Return the heating setpoint (lower bound in HEAT_COOL range mode)."""
        if not self._supports_heating or not self.coordinator.data:
            return None
        try:
            value = self.coordinator.data.get("state", {}).get(
                "zone_setpoints_heating", {}
            ).get(f"zone_{self._zone}")
            return round(float(value), 2) if value is not None else None
        except (KeyError, ValueError, TypeError):
            return None

    @property
    def hvac_mode(self) -> HVACMode:  # type: ignore
        """Return the current HVAC mode derived from the zone pump mode state."""
        if not self.coordinator.data:
            return HVACMode.OFF
        try:
            zone_state = self.coordinator.data.get("state", {}).get("allowed_pump_mode_state", "").lower()
            if not zone_state:
                return HVACMode.OFF
            state = zone_state.lower().replace("pump_mode_state_", "")
            has_heat = "heating" in state
            has_cool = "cooling" in state
            if has_heat and has_cool:
                return HVACMode.HEAT_COOL
            if has_heat:
                return HVACMode.HEAT
            if has_cool:
                return HVACMode.COOL
        except (KeyError, TypeError):
            pass
        return HVACMode.OFF
    
    @property
    def hvac_action(self) -> HVACAction | None:  # type: ignore
        """Return what the heat pump is currently doing (global active state)."""
        if not self.coordinator.data:
            return None
        try:
            active = self.coordinator.data.get("state", {}).get("pump_active_state", "")
            if active == "PUMP_ACTIVE_STATE_HEATING":
                return HVACAction.HEATING
            if active == "PUMP_ACTIVE_STATE_COOLING":
                return HVACAction.COOLING
            if active == "PUMP_ACTIVE_STATE_DEFROSTING":
                return HVACAction.DEFROSTING
            if self.hvac_mode == HVACMode.OFF:
                return HVACAction.OFF
        except (KeyError, TypeError):
            pass
        return HVACAction.IDLE
    
    # Service calls
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the zone target temperature (heating, cooling, or both in range mode)."""
        if not self.coordinator.data:
            return

        temp_single = kwargs.get(ATTR_TEMPERATURE)
        temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)

        current_pump_mode_state = self.coordinator.data.get("state", {}).get("current_pump_mode_state", {}).get(f"zone_{self._zone}", "").lower().replace("pump_mode_state_", "")

        setpoint_heating = None
        setpoint_cooling = None

        # if the user is in a single mode and it corresponds to the allowed mode we allow the setpoint update
        if self.hvac_mode == HVACMode.HEAT and current_pump_mode_state == "heating":
            setpoint_heating = temp_single
        elif self.hvac_mode == HVACMode.COOL and current_pump_mode_state == "cooling":
            setpoint_cooling = temp_single
        # if the user is in heat_cool mode we allow updating only the setpoint corresponding to the current active mode, since aira doesn't allow setting both at the same time
        # ha always sends both temp_low and temp_high, so we infer which one the user actually changed by comparing with current stored values
        elif self.hvac_mode == HVACMode.HEAT_COOL:
            heating_changed = temp_low is not None and temp_low != self.target_temperature_low
            cooling_changed = temp_high is not None and temp_high != self.target_temperature_high
            if current_pump_mode_state == "heating":
                if cooling_changed and not heating_changed:
                    _LOGGER.warning("Can't set temperature for cooling when pump is in heating mode")
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="unsupported_set_temp",
                        translation_placeholders={
                            "hvac_mode": await async_get_translation(self.hass, "pump_mode_state", "cooling"),
                            "pump_mode_state": await async_get_translation(self.hass, "pump_mode_state", current_pump_mode_state),
                        }
                    )
                setpoint_heating = temp_low
            elif current_pump_mode_state == "cooling":
                if heating_changed and not cooling_changed:
                    _LOGGER.warning("Can't set temperature for heating when pump is in cooling mode")
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="unsupported_set_temp",
                        translation_placeholders={
                            "hvac_mode": await async_get_translation(self.hass, "pump_mode_state", "heating"),
                            "pump_mode_state": await async_get_translation(self.hass, "pump_mode_state", current_pump_mode_state),
                        }
                    )
                setpoint_cooling = temp_high
        else:
            _LOGGER.warning("Can't set temperature with unsupported HVAC mode %s and pump mode state %s", self.hvac_mode, current_pump_mode_state)
            disallowed_mode = "heating" if self.hvac_mode == HVACMode.COOL else "cooling"

            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unsupported_set_temp",
                translation_placeholders={
                    "hvac_mode": await async_get_translation(self.hass, "pump_mode_state", disallowed_mode),
                    "pump_mode_state": await async_get_translation(self.hass, "pump_mode_state", current_pump_mode_state),
                }
            )

        _LOGGER.debug("Received set_temperature call with kwargs: %s. Current pump mode state: %s", kwargs, current_pump_mode_state)

        for setpoint in [setpoint_heating, setpoint_cooling]:
            if setpoint is None:
                continue
            if not (self._attr_min_temp <= setpoint <= self._attr_max_temp):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="temperature_out_of_range",
                    translation_placeholders={
                        "temperature": str(setpoint),
                        "min_temp": str(self._attr_min_temp),
                        "max_temp": str(self._attr_max_temp),
                    }
                )

        if await self._set_setpoints(setpoint_heating, setpoint_cooling):
            await self._fake_setpoint_set(setpoint_heating, setpoint_cooling)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode by toggling the global heating / cooling functions."""
        _LOGGER.debug("Zone %d: setting HVAC mode to %s", self._zone, hvac_mode)

        heating: bool | None = None
        cooling: bool | None = None

        if hvac_mode == HVACMode.HEAT:
            heating = True if self._supports_heating else None
            cooling = False if self._supports_cooling else None
        elif hvac_mode == HVACMode.COOL:
            heating = False if self._supports_heating else None
            cooling = True if self._supports_cooling else None
        elif hvac_mode == HVACMode.HEAT_COOL:
            heating = True if self._supports_heating else None
            cooling = True if self._supports_cooling else None
        elif hvac_mode == HVACMode.OFF:
            heating = False if self._supports_heating else None
            cooling = False if self._supports_cooling else None

        if await self._set_mode_on_off(heating, cooling):
            self._fake_mode_set(heating, cooling)

    async def async_turn_on(self) -> None:
        """Turn the zone on (restores the most capable supported mode)."""
        if self._supports_heating and self._supports_cooling:
            await self.async_set_hvac_mode(HVACMode.HEAT_COOL)
        elif self._supports_heating:
            await self.async_set_hvac_mode(HVACMode.HEAT)
        elif self._supports_cooling:
            await self.async_set_hvac_mode(HVACMode.COOL)

    async def async_turn_off(self) -> None:
        """Turn the zone off."""
        await self.async_set_hvac_mode(HVACMode.OFF)