"""Climate platform for Aira Heat Pump."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
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
from pyairahome.utils.exceptions import BLEConnectionError

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
                configured_pump_modes=configured_pump_modes
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
        configured_pump_modes: str,
    ) -> None:
        """Initialise the zone climate entity."""
        unique_id_suffix = f"zone_{zone}_climate"
        super().__init__(coordinator, entry, aira, unique_id_suffix)

        self._zone = zone

        # Determine which HVAC modes the device configuration supports
        self._supports_heating = "heating" in configured_pump_modes
        self._supports_cooling = "cooling" in configured_pump_modes

        hvac_modes: list[HVACMode] = [HVACMode.OFF]
        if self._supports_heating:
            hvac_modes.append(HVACMode.HEAT)
        if self._supports_cooling:
            hvac_modes.append(HVACMode.COOL)
        if self._supports_heating and self._supports_cooling:
            hvac_modes.append(HVACMode.HEAT_COOL)
        _LOGGER.debug("Zone %d configured pump modes: %s, supports heating: %s, supports cooling: %s, resulting HVAC modes: %s",
            zone, configured_pump_modes, self._supports_heating, self._supports_cooling, hvac_modes
        )
        self._attr_hvac_modes = hvac_modes

        self._attr_supported_features = (
            ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TARGET_TEMPERATURE
        )
        _LOGGER.debug("Zone %d supported features: %d", zone, self._attr_supported_features)


    # Internal helpers
    def _get_thermostat_field(self, field: str) -> Any:
        """Read a field from this zone's thermostat last_update list entry."""
        try:
            updates = self.coordinator.data["state"]["thermostats"]
            if isinstance(updates, list):
                for element in updates:
                    if element.get("zone") == f"ZONE_{self._zone}":
                        if element.get("rssi") == 0:
                            return None
                        return element.get(field)
        except (KeyError, TypeError):
            pass
        return None
    
    async def _set_setpoints(self, heating: float | None, cooling: float | None) -> None:
        """Send a command to set the heating/cooling setpoints for this zone."""
        # Plain ValueError, not HomeAssistantError: this is a bug in our own calling code, not a device/BLE failure. Should never happen.
        if heating is not None and cooling is not None:
            raise ValueError(f"Can't set both heating and cooling setpoints at the same time due to device limitations. Received heating: {heating}, cooling: {cooling}")
        if heating is None and cooling is None:
            raise ValueError(f"No setpoint provided to set_setpoints. Received heating: {heating}, cooling: {cooling}")

        mode = "heating" if heating is not None else "cooling"
        temperature = heating if heating is not None else cooling

        zone = f"zone_{self._zone}"
        command_in = SetZoneSetpoints(
            zone_setpoints=ZoneTemperatures(
                **{zone: temperature}
            ),
            # NB: Aira uses the heating setpoint for both cooling and heating
            # Kind.KIND_HEATING if heating is not None else Kind.KIND_COOLING
            kind=Kind.KIND_HEATING
        )

        placeholders = {
            "zone": str(self._zone),
            "mode": mode,
            "temperature": str(temperature),
        }
        try:
            updates = [x async for x in await self.aira.ble._run_command(command_in=command_in)] # type: ignore
            if "succeeded" in updates[-1]:
                return
            error = updates[-1].get("error", "no confirmation received from device")
        except (BLEConnectionError, TimeoutError) as e:
            _LOGGER.error("Error setting %s setpoint to %s temperature: %s", mode, temperature, str(e))
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_setpoint_failed",
                translation_placeholders={**placeholders, "error": str(e)},
            ) from e

        _LOGGER.error("Failed to set zone %d %s setpoint to %s temperature: %s", self._zone, mode, temperature, error)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="set_setpoint_failed",
            translation_placeholders={**placeholders, "error": str(error)},
        )

    async def _fake_setpoint_set(self, heating: float | None, cooling: float | None) -> None:
        """Fake setting the zone heating/cooling setpoints (for propagating change to the entire integration asap)."""
        _LOGGER.debug("Faking setting zone %d setpoints to heating=%s°C cooling=%s°C", self._zone, heating, cooling)
        try:
            zone_key = f"zone_{self._zone}"
            state = self.coordinator.data["state"]
            if heating is not None:
                state["zone_setpoints_heating"][zone_key] = heating
            if cooling is not None:
                state["zone_setpoints_heating"][zone_key] = cooling
            
            self.coordinator.async_update_listeners() # force every entity subscribed to the coordinator to update
        except (KeyError, TypeError):
            pass

    async def _set_mode_on_off(self, heating: bool | None, cooling: bool | None) -> None:
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

        for command_in, mode, action in commands:
            placeholders = {"zone": str(self._zone), "mode": mode, "action": action}
            try:
                updates = [x async for x in await self.aira.ble._run_command(command_in=command_in)] # type: ignore
                if "succeeded" in updates[-1]:
                    # Fake-write this command's effect immediately, so a later command in this same
                    # batch failing doesn't leave an already-applied change unreflected until the next coordinator update.
                    self._fake_mode_set(
                        heating if mode == "heating" else None,
                        cooling if mode == "cooling" else None,
                    )
                    continue
                error = updates[-1].get("error", "no confirmation received from device")
            except (BLEConnectionError, TimeoutError) as e:
                _LOGGER.error("Error setting %s mode to %s: %s", mode, action, str(e))
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="hvac_mode_failed",
                    translation_placeholders={**placeholders, "error": str(e)},
                ) from e

            _LOGGER.error("Failed to set %s mode to %s: %s", mode, action, error)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="hvac_mode_failed",
                translation_placeholders={**placeholders, "error": str(error)},
            )

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
        except (ValueError, TypeError, AttributeError):
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
        except (ValueError, TypeError, AttributeError):
            pass
        return None
    
    @property
    def target_temperature(self) -> float | None:  # type: ignore
        """Return the target temperature (always the heating setpoint)."""
        if not self.coordinator.data:
            return None
        try:
            value = self.coordinator.data.get("state", {}).get("zone_setpoints_heating", {}).get(f"zone_{self._zone}")
            return round(float(value), 2) if value is not None else None
        except (KeyError, ValueError, TypeError):
            return None

    @property
    def hvac_mode(self) -> HVACMode:  # type: ignore
        """Return the current HVAC mode derived from the zone pump mode state."""
        if not self.coordinator.data:
            return HVACMode.OFF
        try:
            zone_state = self.coordinator.data.get("state", {}).get("allowed_pump_mode_state", "").lower().replace("pump_mode_state_", "")
            if not zone_state:
                return HVACMode.OFF
            state = zone_state
            # Apparently aira shows heating/cooling active even if the user can't use cooling for example...
            has_heat = "heating" in state and self._supports_heating
            has_cool = "cooling" in state and self._supports_cooling
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
            if active == "PUMP_ACTIVE_STATE_COOLING":  # device should never report this for heating-only units, but if it does the action will be wrong
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
        """Set the zone target temperature (always the heating setpoint)."""
        if not self.coordinator.data:
            return

        setpoint = kwargs.get(ATTR_TEMPERATURE)
        if setpoint is None:
            return

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

        _LOGGER.debug("Received set_temperature call with kwargs: %s", kwargs)

        await self._set_setpoints(setpoint, None)
        await self._fake_setpoint_set(setpoint, None)

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

        # Fake-write moved into _set_mode_on_off, so state updates for each command instead of only on full success.
        await self._set_mode_on_off(heating, cooling)

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