"""Sensor platform for Aira Heat Pump."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
    SensorEntityDescription
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_NAME, CONF_DEVICE_UUID, CONF_MAC_ADDRESS, CONF_NUM_PHASES, DEFAULT_SHORT_NAME, DOMAIN,CONF_NUM_ZONES, DEFAULT_NUM_ZONES
from .coordinator import AiraDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aira sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    sensors: list[SensorEntity] = [
        # === TEMPERATURE SENSORS ===
        AiraTemperatureSensor(coordinator, entry,
            unique_id_suffix="hot_water_temp",
            data_path=("state", "current_hot_water_temperature"),
            icon="mdi:water-thermometer"
        ),
        AiraTemperatureSensor(coordinator, entry,
            unique_id_suffix="target_hot_water_temp",
            data_path=("state", "target_hot_water_temperature"),
            icon="mdi:water-thermometer-outline"
        ),
        AiraScheduledTemperatureSensor(coordinator, entry),
        AiraTemperatureSensor(coordinator, entry,
            unique_id_suffix="outdoor_temp",
            data_path=("system_check_state", "sensor_values", "outdoor_unit_ambient_temperature"),
            icon="mdi:thermometer"
        ),
        AiraTemperatureSensor(coordinator, entry,
            unique_id_suffix="indoor_supply_temp",
            data_path=("system_check_state", "sensor_values", "indoor_unit_supply_temperature"),
            icon="mdi:thermometer-water"
        ),
        AiraTemperatureSensor(coordinator, entry,
            unique_id_suffix="calculated_supply_temp",
            data_path=("system_check_state", "calculated_setpoints", "supply"),
            icon="mdi:thermometer-water",
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        # === OUTDOOR UNIT SENSORS ===
        # Temperatures
        AiraTemperatureSensor(coordinator, entry,
            unique_id_suffix="ou_supply_temp",
            data_path=("system_check_state", "sensor_values", "outdoor_unit_supply_temperature"),
            icon="mdi:thermometer-water"
        ),
        AiraTemperatureSensor(coordinator, entry,
            unique_id_suffix="ou_return_temp",
            data_path=("system_check_state", "sensor_values", "outdoor_unit_return_temperature"),
            icon="mdi:thermometer-water"
        ),
        AiraTemperatureSensor(coordinator, entry,
            unique_id_suffix="evaporator_coil_temp",
            data_path=("system_check_state", "megmet_status", "evaporator_coil_temperature"),
            icon="mdi:thermometer-lines",
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        AiraTemperatureSensor(coordinator, entry,
            unique_id_suffix="gas_discharge_temp",
            data_path=("system_check_state", "megmet_status", "gas_discharge_temperature"),
            icon="mdi:thermometer-lines",
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        AiraTemperatureSensor(coordinator, entry,
            unique_id_suffix="gas_return_temp",
            data_path=("system_check_state", "megmet_status", "gas_return_temperature"),
            icon="mdi:thermometer-lines",
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        AiraTemperatureSensor(coordinator, entry,
            unique_id_suffix="condensing_temp",
            data_path=("system_check_state", "megmet_status", "condensing_temperature"),
            icon="mdi:thermometer-lines",
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        AiraTemperatureSensor(coordinator, entry,
            unique_id_suffix="evaporating_temp",
            data_path=("system_check_state", "megmet_status", "evaporating_temperature"),
            icon="mdi:thermometer-lines",
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        AiraTemperatureSensor(coordinator, entry,
            unique_id_suffix="inner_coil_temp",
            data_path=("system_check_state", "megmet_status", "inner_coil_temperature"),
            icon="mdi:thermometer-lines",
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        # Electrical
        AiraVoltageSensor(coordinator, entry,
            unique_id_suffix="ou_voltage",
            data_path=("system_check_state", "megmet_status", "ac_input_voltage"),
            icon="mdi:flash",
        ),
        AiraCurrentSensor(coordinator, entry,
            unique_id_suffix="ou_current",
            data_path=("system_check_state", "megmet_status", "ac_input_current"),
            icon="mdi:current-ac",
        ),
        # Pressures
        AiraPressureSensor(coordinator, entry,
            unique_id_suffix="ou_evaporator_pressure",
            data_path=("system_check_state", "megmet_status", "evaporator_pressure"),
            icon="mdi:thermometer-lines",
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        AiraPressureSensor(coordinator, entry,
            unique_id_suffix="ou_condenser_pressure",
            data_path=("system_check_state", "megmet_status", "condenser_pressure"),
            icon="mdi:thermometer-lines",
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        # Fans
        AiraRotationSpeedSensor(coordinator, entry,
            unique_id_suffix="ou_fan_1_speed",
            data_path=("system_check_state", "megmet_status", "dc_fan1_running_speed"),
            icon="mdi:fan",
        ),
        AiraRotationSpeedSensor(coordinator, entry,
            unique_id_suffix="ou_fan_2_speed",
            data_path=("system_check_state", "megmet_status", "dc_fan1_running_speed"),
            icon="mdi:fan",
        ),
        # Compressor
        AiraFrequencySensor(coordinator, entry,
            unique_id_suffix="ou_compressor_speed",
            data_path=("system_check_state", "megmet_status", "compressor_running_speed"),
            icon="mdi:engine",
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        AiraFrequencySensor(coordinator, entry,
            unique_id_suffix="ou_compressor_freq_limit",
            data_path=("system_check_state", "megmet_status", "compressor_frequency_limit"),
            icon="mdi:engine",
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        AiraPercentageSensor(coordinator, entry,
            unique_id_suffix="ou_compressor_need",
            data_path=("system_check_state", "megmet_status", "compressor_need_percent_calculated"),
            icon="mdi:engine",
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        AiraPercentageSensor(coordinator, entry,
            unique_id_suffix="ou_compressor_limit",
            data_path=("system_check_state", "megmet_status", "compressor_limit_percent_calculated"),
            icon="mdi:engine",
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        # Electronic Expansion Valve
        AiraEEVStepSensor(coordinator, entry),
        # === POWER SENSORS ===
        AiraPowerSensor(coordinator, entry,
            unique_id_suffix="instant_power_kw",
            data_path=("system_check_state", "energy_calculation", "current_electrical_power_w"),
            unit_of_measurement=UnitOfPower.KILO_WATT,
            original_unit=UnitOfPower.WATT,
            icon="mdi:lightning-bolt"
        ),
        AiraPowerSensor(coordinator, entry,
            unique_id_suffix="instant_power_w",
            data_path=("system_check_state", "energy_calculation", "current_electrical_power_w"),
            unit_of_measurement=UnitOfPower.WATT,
            original_unit=UnitOfPower.WATT,
            icon="mdi:lightning-bolt",
            enabled_by_default=False
        ),
        AiraPowerSensor(coordinator, entry,
            unique_id_suffix="dhw_instant_power_kw",
            data_path=("system_check_state", "energy_calculation", "current_electrical_power_w"),
            unit_of_measurement=UnitOfPower.KILO_WATT,
            original_unit=UnitOfPower.WATT,
            icon="mdi:lightning-bolt",
            allowed_status=["PUMP_ACTIVE_STATE_DHW", "PUMP_ACTIVE_STATE_ANTI_LEGIONELLA"]
        ),
        AiraPowerSensor(coordinator, entry,
            unique_id_suffix="dhw_instant_power_w",
            data_path=("system_check_state", "energy_calculation", "current_electrical_power_w"),
            unit_of_measurement=UnitOfPower.WATT,
            original_unit=UnitOfPower.WATT,
            icon="mdi:lightning-bolt",
            allowed_status=["PUMP_ACTIVE_STATE_DHW", "PUMP_ACTIVE_STATE_ANTI_LEGIONELLA"],
            enabled_by_default=False
        ),
        AiraPowerSensor(coordinator, entry,
            unique_id_suffix="hc_instant_power_kw",
            data_path=("system_check_state", "energy_calculation", "current_electrical_power_w"),
            unit_of_measurement=UnitOfPower.KILO_WATT,
            original_unit=UnitOfPower.WATT,
            icon="mdi:lightning-bolt",
            allowed_status=["PUMP_ACTIVE_STATE_HEATING", "PUMP_ACTIVE_STATE_COOLING", "PUMP_ACTIVE_STATE_DEFROSTING"]
        ),
        AiraPowerSensor(coordinator, entry,
            unique_id_suffix="hc_instant_power_w",
            data_path=("system_check_state", "energy_calculation", "current_electrical_power_w"),
            unit_of_measurement=UnitOfPower.WATT,
            original_unit=UnitOfPower.WATT,
            icon="mdi:lightning-bolt",
            allowed_status=["PUMP_ACTIVE_STATE_HEATING", "PUMP_ACTIVE_STATE_COOLING", "PUMP_ACTIVE_STATE_DEFROSTING"],
            enabled_by_default=False
        ),
        AiraInstantHeatSensor(coordinator, entry,
            unit_of_measurement=UnitOfPower.KILO_WATT
        ),
        AiraInstantHeatSensor(coordinator, entry,
            unit_of_measurement=UnitOfPower.WATT,
            enabled_by_default=False
        ),
        # === ENERGY SENSORS ===
        AiraEnergySensor(coordinator, entry,
            unique_id_suffix="electricity_kwh",
            data_path=("system_check_state", "energy_calculation", "electrical_energy_cum_wh"),
            icon="mdi:transmission-tower",
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            original_unit=UnitOfEnergy.WATT_HOUR,
        ),
        AiraEnergySensor(coordinator, entry,
            unique_id_suffix="electricity_wh",
            data_path=("system_check_state", "energy_calculation", "electrical_energy_cum_wh"),
            icon="mdi:transmission-tower",
            unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            original_unit=UnitOfEnergy.WATT_HOUR,
            enabled_by_default=False
        ),
        AiraEnergySensor(coordinator, entry,
            unique_id_suffix="heat_kwh",
            data_path=("system_check_state", "energy_calculation", "water_energy_cum_wh"),
            icon="mdi:fire",
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            original_unit=UnitOfEnergy.WATT_HOUR,
            state_class=SensorStateClass.TOTAL
        ),
        AiraEnergySensor(coordinator, entry,
            unique_id_suffix="heat_wh",
            data_path=("system_check_state", "energy_calculation", "water_energy_cum_wh"),
            icon="mdi:fire",
            unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            original_unit=UnitOfEnergy.WATT_HOUR,
            enabled_by_default=False,
            state_class=SensorStateClass.TOTAL
        ),
        AiraEnergyBalanceSensor(coordinator, entry),
        # === COP SENSORS ===
        AiraInstantCOPSensor(coordinator, entry),
        AiraCumulativeCOPSensor(coordinator, entry),
        AiraDeviceCOPSensor(coordinator, entry),
        # === FLOW SENSORS ===
        AiraFlowRateSensor(coordinator, entry,
            unique_id_suffix="flow_meter_1",
            data_path=("system_check_state", "sensor_values", "flow_meter_1"),
        ),
        AiraFlowRateSensor(coordinator, entry,
            unique_id_suffix="flow_meter_2",
            data_path=("system_check_state", "sensor_values", "flow_meter_2"),
        ),
        # === SYSTEM STATUS SENSORS ===
        AiraEnumSensor(coordinator, entry,
            unique_id_suffix="operating_status",
            data_path=("state", "operating_status"),
            replace="OPERATING_STATUS_",
            icon="mdi:information-outline"
        ),
        AiraEnumSensor(coordinator, entry,
            unique_id_suffix="active_state",
            data_path=("state", "pump_active_state"),
            replace="PUMP_ACTIVE_STATE_",
            icon="mdi:heat-pump-outline"
        ),        
        AiraLEDPatternSensor(coordinator, entry),
        # === CONNECTION SENSORS ===
        AiraSignalStrengthSensor(coordinator, entry,
            unique_id_suffix="system_rssi",
            data_path=("rssi", )
        ),
        # === VERSION SENSORS ===
        AiraStringSensor(coordinator, entry,
            unique_id_suffix="software_version",
            data_path=("state", "versions", "connectivity_manager"),
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        AiraStringSensor(coordinator, entry,
            unique_id_suffix="ou_software_version",
            data_path=("state", "versions", "outdoor_unit_application"),
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        AiraStringSensor(coordinator, entry,
            unique_id_suffix="platform_version",
            data_path=("state", "versions", "linux_build_id"),
            entity_category=EntityCategory.DIAGNOSTIC
        )
    ]

    # PER ZONE LOOP
    num_zones = entry.options.get(CONF_NUM_ZONES, DEFAULT_NUM_ZONES)
    _LOGGER.debug("Setting up sensors for %d zones based on config entry options", num_zones)

    for i in range(1, num_zones + 1):  # zone loop
        sensors.extend([
        AiraTemperatureSensor(coordinator, entry,
            unique_id_suffix=f"zone_{i}_supply_temp",
            data_path=("system_check_state", "sensor_values", f"indoor_unit_supply_temperature_zone_{i}"),
            icon="mdi:thermometer-water"
        ),
        AiraTemperatureSensor(coordinator, entry,
            unique_id_suffix=f"zone_{i}_temp",
            data_path=("state", "thermostats", "last_update", "actual_temperature"),
            icon="mdi:thermometer",
            index=f"ZONE_{i}",
            divide_by_10=True
        ),
        AiraHumiditySensor(coordinator, entry,
            unique_id_suffix=f"zone_{i}_humidity",
            data_path=("state", "thermostats", "last_update", "humidity"),
            icon="mdi:water-percent",
            index=f"ZONE_{i}",
            divide_by_10=True
        ),
        AiraSignalStrengthSensor(coordinator, entry,
            unique_id_suffix=f"zone_{i}_rssi",
            data_path=("state", "thermostats", "rssi"),
            index=f"ZONE_{i}"
        ),
        AiraEnumSensor(coordinator, entry,
            unique_id_suffix=f"zone_{i}_active_state",
            data_path=("state", "current_pump_mode_state", f"zone_{i}"),
            replace="PUMP_MODE_STATE_",
            icon="mdi:heat-pump-outline"
        ),
        AiraPercentageSensor(coordinator, entry,
            unique_id_suffix=f"zone_{i}_valve_position",
            data_path=("system_check_state", "valve_status", f"mixing_valve{i}_calculated_position"),
            icon="mdi:valve",
            entity_category=EntityCategory.DIAGNOSTIC
        ),
        AiraTemperatureSensor(coordinator, entry,
            unique_id_suffix=f"zone_{i}_calculated_supply_temp",
            data_path=("system_check_state", "calculated_setpoints", f"supply_ zone_{i}"),
            icon="mdi:thermometer-water",
            entity_category=EntityCategory.DIAGNOSTIC
        )
        ])

        # check configured modes on the heatpump to enable heating/cooling targets accordingly
        allowed_pump_mode_state = coordinator.data.get("state", {}).get("allowed_pump_mode_state", "PUMP_MODE_STATE_HEATING_COOLING").lower()
        if "heating" in allowed_pump_mode_state:
            sensors.extend([
            AiraTemperatureSensor(coordinator, entry,
                unique_id_suffix=f"zone_{i}_heat_target",
                data_path=("state", "zone_setpoints_heating", f" zone_{i}"),
                icon="mdi:sun-thermometer",
            ),
            AiraCurveSensor(coordinator, entry,
                zone=i,
                heating=True        
            )
            ])
        if "cooling" in allowed_pump_mode_state:
            sensors.extend([
            AiraTemperatureSensor(coordinator, entry,
                unique_id_suffix=f"zone_{i}_cool_target",
                data_path=("state", "zone_setpoints_cooling", f" zone_{i}"),
                icon="mdi:snowflake-thermometer",
            ),
            AiraCurveSensor(coordinator, entry,
                zone=i,
                heating=False        
            )
            ])

    # PER PHASE LOOP
    num_phases = entry.options.get(CONF_NUM_PHASES, 0)
    _LOGGER.debug("Setting up sensors for %d phases based on config entry options", num_phases)
    if num_phases < 0:
        _LOGGER.warning("To enable voltage and current sensors configure the number of phases in the integration configuration.", num_phases)
        num_phases = 0

    for i in range(num_phases):
        sensors.extend([
            AiraVoltageSensor(coordinator, entry,
                unique_id_suffix=f"voltage_phase_{i}",
                data_path=("system_check_state", "energy_calculation", f"voltage_phase_{i}"),
                icon="mdi:flash",
            ),
            AiraCurrentSensor(coordinator, entry,
                unique_id_suffix=f"current_phase_{i}",
                data_path=("system_check_state", "energy_calculation", f"current_phase_{i}"),
                icon="mdi:current-ac",
            ),
        ])
   
    # Debug: Log the current data structure to help diagnose sensor issues
    if coordinator.data:
        _LOGGER.debug("Current coordinator data structure:")
        # _LOGGER.debug("  state keys: %s", coordinator.data.get("state", {}))
        # _LOGGER.debug("  flow_data keys: %s", coordinator.data.get("flow_data", {}))
        # _LOGGER.debug("  system_check_state keys: %s", coordinator.data.get("system_check_state", {}))
        _LOGGER.debug("  state keys: %s", list(coordinator.data.get("state", {}).keys()))
        # _LOGGER.debug("  flow_data keys: %s", list(coordinator.data.get("flow_data", {}).keys()))
        _LOGGER.debug("  system_check_state_state keys: %s", list(coordinator.data.get("system_check_state_state", {}).keys()))
    else:
        _LOGGER.warning("Coordinator data is empty - this will cause sensor issues")
    
    async_add_entities(sensors, True)

# ============================================================================
# BASE SENSOR CLASS
# ============================================================================

class AiraSensorBase(CoordinatorEntity, SensorEntity): # type: ignore
    """Base class for Aira sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        unique_id_suffix: str,
        icon: str | None = None,
        entity_category: EntityCategory | None = None,
        enabled_by_default: bool = True
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._device_uuid = entry.data[CONF_DEVICE_UUID]
        self._attr_unique_id = f"{self._device_uuid}_{unique_id_suffix}"

        if icon:
            self._attr_icon = icon

        if entity_category:
            self._attr_entity_category = entity_category

        self._attr_entity_registry_enabled_default = enabled_by_default

        #self.entity_description = SensorEntityDescription(
        #    key=unique_id_suffix,
        #    translation_key=unique_id_suffix
        #)

        self._attr_translation_key = unique_id_suffix

        self._attr_device_info = DeviceInfo(**{
            "identifiers": {(DOMAIN, self._device_uuid)},
            "connections": {(dr.CONNECTION_BLUETOOTH, entry.data.get(CONF_MAC_ADDRESS))},
            "name": entry.data.get(CONF_DEVICE_NAME, DEFAULT_SHORT_NAME),
            "manufacturer": "Aira",
            "model": "Heat Pump",
        })

# ============================================================================
# TEMPERATURE SENSORS
# ============================================================================

class AiraTemperatureSensor(AiraSensorBase):
    """Base class for all temperature sensors."""
    
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:thermometer",
        entity_category: EntityCategory | None = None,
        enabled_by_default: bool = True,
        divide_by_10: bool = False,
        index: int | str | None = None
    ) -> None:
        super().__init__(coordinator, entry, unique_id_suffix, icon, entity_category, enabled_by_default)
        self._data_path = data_path
        self._divide_by_10 = divide_by_10

        # if string: ZONE_1 or ZONE_2
        # if int: 1 or 2
        self._index = index

    @property
    def native_value(self) -> float | None: # type: ignore
        if not self.coordinator.data:
            return None

        if self._data_path:
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path] # type: ignore # Ignore since the try catch will handle any issues with missing keys or wrong types
                    if self._index is not None and isinstance(value, list):
                        for element in value:
                            # caso in cui l'elemento ha un campo zone:
                            if isinstance(self._index, str) and element.get("zone") == self._index:
                                value = element
                                break
                        if isinstance(self._index, int) and len(value) >= self._index:
                            value = value[self._index - 1]  # Adjust for 0-based index

                if self._divide_by_10:
                    # Round to 1 decimal place
                    return round(float(value) / 10, 2) # type: ignore
                # Round to 1 decimal place
                return round(float(value), 2) # type: ignore
            except (KeyError, ValueError, TypeError):
                return None
        return None

class AiraScheduledTemperatureSensor(AiraSensorBase):
    """Schedule temperature sensor. Varies based on current schedule/target temperature."""

    _attr_name = "DHW Scheduled Temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        unique_id_suffix = "scheduled_temp"
        super().__init__(coordinator, entry, unique_id_suffix, "mdi:thermometer-water")

    @property
    def native_value(self) -> float | None: # type: ignore # TODO add night cooldown calculation
        try:
            value = None
            states = self.coordinator.data.get('state', {})
            scheduler = states.get('scheduler', {})
            if not scheduler:
                value = states.get("target_hot_water_temperature", None) # If no scheduler, return current target temperature
                return round(float(value), 2) if value is not None else None
            active_actions = scheduler.get('active_actions', [])
            if not active_actions:
                value = states.get("target_hot_water_temperature", None) # If no scheduler, return current target temperature
                return round(float(value), 2) if value is not None else None
            
            # Look for dhw (domestic hot water) setpoint in active actions
            for action in active_actions:
                if 'set_dhw_setpoint' in action:
                    dhw_temp = action['set_dhw_setpoint'].get('temperature')
                    if dhw_temp is not None:
                        value = dhw_temp
                    return round(float(value), 2) if value is not None else None
                
            value = states.get("target_hot_water_temperature", None) # Fallback to current target temperature
            return round(float(value), 2) if value is not None else None
        except (KeyError, ValueError, TypeError):
            return None

# ============================================================================
# HUMIDITY SENSORS
# ============================================================================

class AiraHumiditySensor(AiraSensorBase):
    """Base class for all temperature sensors."""
    
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:water-percent",
        entity_category: EntityCategory | None = None,
        enabled_by_default: bool = True,
        divide_by_10: bool = False,
        index: int | str | None = None
    ) -> None:
        super().__init__(coordinator, entry, unique_id_suffix, icon, entity_category, enabled_by_default)
        self._data_path = data_path
        self._divide_by_10 = divide_by_10
        # if string: ZONE_1 or ZONE_2
        # if int: 1 or 2
        self._index = index

    @property
    def native_value(self) -> float | None: # type: ignore
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
                                value = element
                                break
                        if isinstance(self._index, int) and len(value) >= self._index:
                            value = value[self._index - 1]  # Adjust for 0-based index

                if self._divide_by_10:
                    # Round to 1 decimal place
                    return round(float(value) / 10, 1) # type: ignore
                # Round to 1 decimal place
                return round(float(value), 1) # type: ignore
            except (KeyError, ValueError, TypeError):
                return None
        return None

# ============================================================================
# SIGNAL STRENGTH SENSORS
# ============================================================================

class AiraSignalStrengthSensor(AiraSensorBase):
    """Base class for all signal strength sensors."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        entity_category: EntityCategory | None = None,
        enabled_by_default: bool = True,
        index: int | str | None = None
    ) -> None:
        super().__init__(coordinator, entry, unique_id_suffix, None, entity_category, enabled_by_default)
        self._data_path = data_path

        # if string: ZONE_1 or ZONE_2
        # if int: 1 or 2
        self._index = index

    @property
    def native_value(self) -> int | None: # type: ignore
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
                                value = element
                                break
                        if isinstance(self._index, int) and len(value) >= self._index:
                            value = value[self._index - 1]  # Adjust for 0-based index

                return int(value) # type: ignore
            except (KeyError, ValueError, TypeError):
                return None
        return None
    
    @property
    def icon(self) -> str: # type: ignore
        """Return the icon based on signal strength."""
        value = self.native_value
        if value is None:
            return "mdi:bluetooth-off"
        elif value >= -60:
            return "mdi:signal-cellular-3"
        elif -70 <= value < -60:
            return "mdi:signal-cellular-2"
        elif -80 <= value < -70:
            return "mdi:signal-cellular-1"
        else:
            return "mdi:signal-cellular-outline"

# ============================================================================
# ELECTRICAL SENSORS
# ===========================================================================

class AiraVoltageSensor(AiraSensorBase):
    """Base class for all voltage sensors."""

    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:flash",
        entity_category: EntityCategory | None = None,
        enabled_by_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry, unique_id_suffix, icon, entity_category, enabled_by_default)
        self._data_path = data_path

    @property
    def native_value(self) -> float | None: # type: ignore
        if not self.coordinator.data:
            return None

        if self._data_path:
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path]
                # Round to 1 decimal place
                return round(float(value), 2) # type: ignore
            except (KeyError, ValueError, TypeError):
                return None
        return None

class AiraCurrentSensor(AiraSensorBase):
    """Base class for all current sensors."""

    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:current-ac",
        entity_category: EntityCategory | None = None,
        enabled_by_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry, unique_id_suffix, icon, entity_category, enabled_by_default)
        self._data_path = data_path

    @property
    def native_value(self) -> float | None: # type: ignore
        if not self.coordinator.data:
            return None

        if self._data_path:
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path]
                # Round to 1 decimal place
                return round(float(value), 2) # type: ignore
            except (KeyError, ValueError, TypeError):
                return None
        return None

# ============================================================================
# POWER SENSORS
# ===========================================================================

class AiraPowerSensor(AiraSensorBase):
    """Base class for all power sensors."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 3

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:lightning-bolt",
        entity_category: EntityCategory | None = None,
        unit_of_measurement: str = UnitOfPower.KILO_WATT,
        original_unit: str = UnitOfPower.WATT,
        enabled_by_default: bool = True,
        allowed_status: list[str] | None = None
    ) -> None:
        super().__init__(coordinator, entry, unique_id_suffix, icon, entity_category, enabled_by_default)
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._original_unit = original_unit
        self._data_path = data_path
        self._allowed_status = allowed_status

    @property
    def native_value(self) -> float | None: # type: ignore
        if not self.coordinator.data:
            return None

        if self._data_path:
            if self._allowed_status and self.coordinator.data.get("state", {}).get("pump_active_state") not in self._allowed_status:
                return 0.0  # Return 0 if not in allowed operating status
            
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path]

                if self._original_unit == UnitOfPower.WATT and self._attr_native_unit_of_measurement == UnitOfPower.KILO_WATT:
                    # Convert W to kW
                    return round(float(value) / 1000, 3) # type: ignore
                elif self._original_unit == UnitOfPower.KILO_WATT and self._attr_native_unit_of_measurement == UnitOfPower.WATT:
                    # Convert kW to W
                    return round(float(value) * 1000, 3) # type: ignore
                else:
                    return round(float(value), 3) # type: ignore
            except (KeyError, ValueError, TypeError):
                return None
        return None

# ============================================================================
# ENERGY SENSORS
# ============================================================================

class AiraEnergySensor(AiraSensorBase):
    """Base class for all energy sensors."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_suggested_display_precision = 3

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:transmission-tower",
        entity_category: EntityCategory | None = None,
        unit_of_measurement: str = UnitOfEnergy.KILO_WATT_HOUR,
        original_unit: str = UnitOfEnergy.WATT_HOUR,
        enabled_by_default: bool = True,
        state_class=SensorStateClass.TOTAL_INCREASING
    ) -> None:
        super().__init__(coordinator, entry, unique_id_suffix, icon, entity_category, enabled_by_default)
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._original_unit = original_unit
        self._data_path = data_path
        self._attr_state_class = state_class

    @property
    def native_value(self) -> float | None: # type: ignore
        if not self.coordinator.data:
            return None

        if self._data_path:
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path]
                # Convert to kWh if original unit is Wh
                if self._original_unit == UnitOfEnergy.WATT_HOUR and self._attr_native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR:
                    # Convert Wh to kWh
                    return round(float(value) / 1000, 3) # type: ignore
                elif self._original_unit == UnitOfEnergy.KILO_WATT_HOUR and self._attr_native_unit_of_measurement == UnitOfEnergy.WATT_HOUR:
                    # Convert kWh to Wh
                    return round(float(value) * 1000, 3) # type: ignore
                else:
                    return round(float(value), 3) # type: ignore
            except (KeyError, ValueError, TypeError):
                return None
        return None

# ============================================================================
# INSTANT HEAT SENSORS
# ============================================================================

class AiraInstantHeatSensor(AiraSensorBase):
    """Thermal power output sensor. Calculated using https://docs.openenergymonitor.org/heatpumps/basics.html#mass-flow-rate-heat-transfer"""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_suggested_display_precision = 3

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry, unit_of_measurement: str = UnitOfPower.WATT,
        enabled_by_default: bool = True,
    ) -> None:
        unique_id_suffix = f"instant_heat_{unit_of_measurement.lower()}"        
        super().__init__(coordinator, entry, unique_id_suffix, "mdi:fire", None, enabled_by_default)
        self._attr_native_unit_of_measurement = unit_of_measurement

    @property
    def native_value(self) -> float | None: # type: ignore
        """Return the state."""
        # heat output (W) = specific heat (J/kg.K) x flow rate (kg/s) x DT (K)
        # heat output (W) = 4200 J/kg.K x 0.25 kg/s x 5K = 5250 W
        try:
            flow = float(self.coordinator.data["system_check_state"]["sensor_values"]["flow_meter_1"]) / 60.0  # in L/min -> kg/s
            specific_heat = 4186  # J/kg.K
            dt = float(self.coordinator.data["system_check_state"]["sensor_values"]["outdoor_unit_supply_temperature"]) - float(self.coordinator.data["system_check_state"]["sensor_values"]["outdoor_unit_return_temperature"])  # delta T in K
            heat_output_w = specific_heat * flow * dt  # in Watts
            if self._attr_native_unit_of_measurement == UnitOfPower.KILO_WATT:
                return round(heat_output_w / 1000, 3)  # Convert to kW
            return round(heat_output_w, 3)
        except (KeyError, ValueError, TypeError):
            return None

# ============================================================================
# PRESSURE SENSORS
# ============================================================================

class AiraPressureSensor(AiraSensorBase):
    """Base class for all pressure sensors."""

    _attr_device_class = SensorDeviceClass.PRESSURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPressure.BAR
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:thermometer-lines",
        entity_category: EntityCategory | None = None,
        enabled_by_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry, unique_id_suffix, icon, entity_category, enabled_by_default)
        self._data_path = data_path

    @property
    def native_value(self) -> float | None: # type: ignore
        if not self.coordinator.data:
            return None

        if self._data_path:
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path]
                # Round to 1 decimal places
                return round(float(value), 2) # type: ignore
            except (KeyError, ValueError, TypeError):
                return None
        return None

# ============================================================================
# FAN SENSORS
# ============================================================================

class AiraRotationSpeedSensor(AiraSensorBase):
    """Base class for all pressure sensors."""

    #_attr_device_class = SensorDeviceClass.?
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = REVOLUTIONS_PER_MINUTE

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:rotate-right",
        entity_category: EntityCategory | None = None,
        enabled_by_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry, unique_id_suffix, icon, entity_category, enabled_by_default)
        self._data_path = data_path

    @property
    def native_value(self) -> int | None: # type: ignore
        if not self.coordinator.data:
            return None

        if self._data_path:
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path]

                return int(value) # type: ignore
            except (KeyError, ValueError, TypeError):
                return None
        return None

# ============================================================================
# ENERGY BALANCE SENSOR
# ============================================================================

class AiraEnergyBalanceSensor(AiraSensorBase):
    """Energy balance sensor."""

    _attr_name = "Energy Balance"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        unique_id_suffix = "energy_balance"
        super().__init__(coordinator, entry, unique_id_suffix, "mdi:scale-balance")

    @property
    def native_value(self) -> int | None: # type: ignore
        """Return the state."""
        try:
            energy_balance = self.coordinator.data["system_check_state"].get("energy_balance", {})
            return energy_balance.get("energy_balance")
        except (KeyError, ValueError, TypeError):
                return None

# ============================================================================
# FLOW SENSORS
# ============================================================================

class AiraFlowRateSensor(AiraSensorBase):
    """Water flow rate sensor."""

    _attr_device_class = SensorDeviceClass.VOLUME_FLOW_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfVolumeFlowRate.LITERS_PER_MINUTE
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        entity_category: EntityCategory | None = None,
        enabled_by_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry, unique_id_suffix, None, entity_category, enabled_by_default)
        self._data_path = data_path

    @property
    def native_value(self) -> float | None: # type: ignore
        if not self.coordinator.data:
            return None

        if self._data_path:
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path]
                # Round to 1 decimal places
                return round(float(value), 2) # type: ignore
            except (KeyError, ValueError, TypeError):
                return 0
        return None

    @property
    def icon(self) -> str: # type: ignore
        """Return the icon based on flow rate."""
        value = self.native_value
        if value is None or value == 0:
            return "mdi:water-off"
        else:
            return "mdi:water"

# ============================================================================
# FREQUENCY SENSORS
# ============================================================================

class AiraFrequencySensor(AiraSensorBase):
    """General frequency sensor."""
    
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfFrequency.HERTZ

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:sine-wave",
        entity_category: EntityCategory | None = None,
        enabled_by_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry, unique_id_suffix, icon, entity_category, enabled_by_default)
        self._data_path = data_path

    @property
    def native_value(self) -> int | None: # type: ignore
        if not self.coordinator.data:
            return None

        if self._data_path:
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path]

                return int(value) # type: ignore
            except (KeyError, ValueError, TypeError):
                return None
        return None

# ============================================================================
# PERCENTAGE SENSOR
# ============================================================================

class AiraPercentageSensor(AiraSensorBase):
    """Base class for all percentage sensors."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:percent",
        entity_category: EntityCategory | None = None,
        enabled_by_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry, unique_id_suffix, icon, entity_category, enabled_by_default)
        self._data_path = data_path
    
    @property
    def native_value(self) -> int | None: # type: ignore
        if not self.coordinator.data:
            return None

        if self._data_path:
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path]

                return int(value) # type: ignore
            except (KeyError, ValueError, TypeError):
                return None
        return None

# ============================================================================
# EXPANSION VALVE SENSOR
# ============================================================================

class AiraEEVStepSensor(AiraSensorBase):
    """Electronic Expansion Valve step sensor."""

    _attr_name = "Electronic Expansion Valve Step"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        unique_id_suffix = "eev_step"
        super().__init__(coordinator, entry, unique_id_suffix, "mdi:valve", None, False)

    @property
    def native_value(self) -> int | None: # type: ignore
        """Return the state."""
        outdoor_unit = self.coordinator.data["system_check_state"].get("megmet_status", {})
        return outdoor_unit.get("eev_step", None)

# ============================================================================
# ENUM / STRING SENSORS
# ============================================================================

class AiraEnumSensor(AiraSensorBase):
    """Base class for all enum sensors."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_state_class = None

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        replace: str,
        icon: str = "mdi:information-outline",
        entity_category: EntityCategory | None = None,
        enabled_by_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry, unique_id_suffix, icon, entity_category, enabled_by_default)
        self._data_path = data_path
        self._replace = replace
    
    @property
    def native_value(self) -> str | None: # type: ignore
        if not self.coordinator.data:
            return None

        if self._data_path:
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path]

                return str(value).replace(self._replace, "").replace("_", " ").title()
            except (KeyError, ValueError, TypeError):
                return None
        return None

class AiraStringSensor(AiraSensorBase):
    """Base class for all string sensors."""

    _attr_device_class = None
    _attr_state_class = None

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:information-outline",
        entity_category: EntityCategory | None = None,
        enabled_by_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry, unique_id_suffix, icon, entity_category, enabled_by_default)
        self._data_path = data_path
    
    @property
    def native_value(self) -> str | None: # type: ignore
        if not self.coordinator.data:
            return None

        if self._data_path:
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path]

                return value # type: ignore
            except (KeyError, ValueError, TypeError):
                return None
        return None

# ============================================================================
# LED STATUS SENSORS
# ============================================================================

class AiraLEDPatternSensor(AiraSensorBase):
    """LED pattern sensor."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_state_class = None

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        unique_id_suffix = "led_pattern"
        super().__init__(coordinator, entry, unique_id_suffix, None, None, False)

    @property
    def native_value(self) -> str | None: # type: ignore
        """Return the state."""
        try:
            pattern = self.coordinator.data["state"].get("led_pattern", "")
            return pattern.replace("LED_PATTERN_", "").replace("_", " ").title()
        except (KeyError, ValueError, TypeError):
                return None

    @property
    def icon(self) -> str: # type: ignore
        """Return the icon based on LED pattern."""
        if not self.native_value:
            _LOGGER.debug("LED pattern sensor native_value is None")
            return "mdi:lightbulb-question"
        
        pattern = self.native_value.upper()
        if pattern is None:
            return "mdi:lightbulb-off"
        elif pattern == "UNSPECIFIED":
            return "mdi:lightbulb-off"
        elif pattern == "NORMAL":
            return "mdi:lightbulb-on"
        elif pattern == "COMMISSIONING":
            return "mdi:lightbulb-auto"
        elif pattern == "PROCESSING":
            return "mdi:lightbulb-auto"
        elif pattern == "ATTENTION":
            return "mdi:lightbulb-alert"
        elif pattern == "AWAY MODE":
            return "mdi:lightbulb-night"
        elif pattern == "ERROR UNACKNOWLEDGED":
            return "mdi:lightbulb-alert"
        elif pattern == "ERROR ACKNOWLEDGED":
            return "mdi:lightbulb-alert-outline"
        elif pattern == "CONFIRM":
            return "mdi:lightbulb-check"
        elif pattern == "BLACK":
            return "mdi:lightbulb-off"
        elif pattern == "BOOSTING":
            return "mdi:lightbulb-auto"
        elif pattern == "COOLING":
            return "mdi:lightbulb-auto"
        else:
            return "mdi:lightbulb-question"

# ============================================================================
# COP SENSORS
# ============================================================================

class AiraInstantCOPSensor(AiraSensorBase):
    """Instant COP sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = None
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        unique_id_suffix = "instant_cop"
        super().__init__(coordinator, entry, unique_id_suffix, "mdi:gauge", None)

    @property
    def native_value(self) -> float | None: # type: ignore
        """Return the state."""
        try:
            flow = float(self.coordinator.data["system_check_state"]["sensor_values"]["flow_meter_1"]) / 60.0  # in L/min -> kg/s
            specific_heat = 4186  # J/kg.K
            dt = float(self.coordinator.data["system_check_state"]["sensor_values"]["outdoor_unit_supply_temperature"]) - float(self.coordinator.data["system_check_state"]["sensor_values"]["outdoor_unit_return_temperature"])  # delta T in K
            heat_output_w = specific_heat * flow * dt  # in Watts
            energy_calc = self.coordinator.data["system_check_state"].get("energy_calculation", {})
            elec_power = energy_calc.get("current_electrical_power_w")
            
            if elec_power and heat_output_w and elec_power > 0:
                return round(heat_output_w / elec_power, 2)
            return None
        except (KeyError, ValueError, TypeError):
            return None

class AiraCumulativeCOPSensor(AiraSensorBase):
    """Cumulative COP sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = None
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        unique_id_suffix = "cumulative_cop"
        super().__init__(coordinator, entry, unique_id_suffix, "mdi:gauge", None)

    @property
    def native_value(self) -> float | None: # type: ignore
        """Return the state."""
        try:
            energy_calc = self.coordinator.data["system_check_state"]["energy_calculation"]
            elec_kwh = energy_calc["electrical_energy_cum_kwh"]
            thermal_kwh = energy_calc["water_energy_cum_kwh"]

            if elec_kwh and thermal_kwh and elec_kwh > 0:
                return round(thermal_kwh / elec_kwh, 2)
            return None
        except (KeyError, ValueError, TypeError):
            return None

class AiraDeviceCOPSensor(AiraSensorBase):
    """Device-reported COP sensor (real-time from heat pump)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = None
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        unique_id_suffix = "reported_cop"
        super().__init__(coordinator, entry, unique_id_suffix, "mdi:gauge", None)

    @property
    def native_value(self) -> float | None: # type: ignore
        """Return the state."""
        try:
            energy_calc = self.coordinator.data["system_check_state"].get("energy_calculation", {})
            cop_now = energy_calc.get("cop_now")
            # Only return non-zero values (0 means pump is idle/not operating)
            # Filter out edge case values > 8 as they are artifacts according to emoncms.org
            if cop_now and cop_now > 0 and cop_now <= 8: 
                return round(cop_now, 2)
            return None
        except (KeyError, ValueError, TypeError):
                return None

# ============================================================================
# CURVE SENSOR
# ============================================================================

class AiraCurveSensor(AiraSensorBase):
    """Heating/Cooling Curve sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        zone: int,
        heating: bool = True
    ) -> None:
        unique_id_suffix = f"zone_{zone}_{'heating' if heating else 'cooling'}_curve"
        super().__init__(coordinator, entry, unique_id_suffix, "mdi:chart-line", None)
        #self._attr_name = f"Zone {zone} {'Heating' if heating else 'Cooling'} Curve"
        self._zone = zone
        self._heating = heating

        if self._heating:
            self._curve_key = f"heat_curves"
        else:
            self._curve_key = f"cool_curves"

    @property
    def native_value(self) -> float | None: # type: ignore
        """Return the state."""
        if not self.coordinator.data:
            return None
        
        try:
            outdoor_temp = float(self.coordinator.data["system_check_state"]["sensor_values"]["outdoor_unit_ambient_temperature"])

            # get the heat curve points
            ambient = self.extra_state_attributes["ambient"]
            supply = self.extra_state_attributes["supply"]

            try:
                # if temperature is lower than lowest ambient, clamp to lowest supply
                if outdoor_temp <= ambient[0]:
                    return supply[0]
                
                # if temperature is higher than highest ambient, clamp to highest supply
                if outdoor_temp >= ambient[-1]:
                    return supply[-1]
        
                # interpolate the supply temperature based on outdoor temperature
                for i in range(len(ambient) - 1):
                    if ambient[i] <= outdoor_temp < ambient[i + 1]:
                        u = (outdoor_temp - ambient[i]) / (ambient[i + 1] - ambient[i])
                        return round(supply[i] + u * (supply[i + 1] - supply[i]), 2)
            except Exception:
                return None
        except (KeyError, ValueError, TypeError):
            return None
        
    @property
    def extra_state_attributes(self) -> dict[str, Any]: # type: ignore
        """Return the state attributes."""
        if not self.coordinator.data:
            return {"ambient": [], "supply": []}
    
        try:
            curves = self.coordinator.data["state"][self._curve_key][f" zone_{self._zone}"]
            output = {
                "ambient": [],
                "supply": []
            }
            for p in curves.keys():
                for t in ["ambient", "supply"]:
                    output[t].append(curves[p][t])

            return output
        except (KeyError, ValueError, TypeError):
            return {"ambient": [], "supply": []}
