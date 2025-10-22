"""Sensor platform for Aira Heat Pump."""
from __future__ import annotations

from functools import cached_property
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    PERCENTAGE,
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
from homeassistant.helpers import entity_registry as er
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
    """Set up Aira sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    sensors: list[SensorEntity] = [
        # === TEMPERATURE SENSORS ===
        AiraTemperatureSensor(coordinator, entry,
            name="DHW Temperature",
            unique_id_suffix="hot_water_temp",
            data_path=("state", "current_hot_water_temperature"),
            icon="mdi:water-thermometer"
        ),
        AiraTemperatureSensor(coordinator, entry,
            name="Target DHW Temperature",
            unique_id_suffix="target_hot_water_temp",
            data_path=("state", "target_hot_water_temperature"),
            icon="mdi:water-thermometer-outline"
        ),
        # TODO ADD SCHEDULED TARGET TEMPERATURE
        AiraTemperatureSensor(coordinator, entry,
            name="Outdoor Temperature",
            unique_id_suffix="outdoor_temp",
            data_path=("state", "current_outdoor_temperature"),
            icon="mdi:thermometer"
        ),
        AiraTemperatureSensor(coordinator, entry,
            name="Indoor Unit Supply Temperature",
            unique_id_suffix="indoor_supply_temp",
            data_path=("system_check", "sensor_values", "indoor_unit_supply_temperature"),
            icon="mdi:thermometer-water"
        ),
        
        # === OUTDOOR UNIT SENSORS ===
        # Temperatures
        AiraTemperatureSensor(coordinator, entry,
            name="OU Evaporator Coil Temperature",
            unique_id_suffix="evaporator_coil_temp",
            data_path=("system_check", "megmet_status", "evaporator_coil_temperature"),
            icon="mdi:thermometer-lines",
            enabled_by_default=False
        ),
        AiraTemperatureSensor(coordinator, entry,
            name="OU Gas Discharge Temperature",
            unique_id_suffix="gas_discharge_temp",
            data_path=("system_check", "megmet_status", "gas_discharge_temperature"),
            icon="mdi:thermometer-lines",
            enabled_by_default=False
        ),
        AiraTemperatureSensor(coordinator, entry,
            name="OU Gas Return Temperature",
            unique_id_suffix="gas_return_temp",
            data_path=("system_check", "megmet_status", "gas_return_temperature"),
            icon="mdi:thermometer-lines",
            enabled_by_default=False
        ),
        AiraTemperatureSensor(coordinator, entry,
            name="OU Condensing Temperature",
            unique_id_suffix="condensing_temp",
            data_path=("system_check", "megmet_status", "condensing_temperature"),
            icon="mdi:thermometer-lines",
            enabled_by_default=False
        ),
        AiraTemperatureSensor(coordinator, entry,
            name="OU Evaporating Temperature",
            unique_id_suffix="evaporating_temp",
            data_path=("system_check", "megmet_status", "evaporating_temperature"),
            icon="mdi:thermometer-lines",
            enabled_by_default=False
        ),
        AiraTemperatureSensor(coordinator, entry,
            name="OU Inner Coil Temperature",
            unique_id_suffix="inner_coil_temp",
            data_path=("system_check", "megmet_status", "inner_coil_temperature"),
            icon="mdi:thermometer-lines",
            enabled_by_default=False
        ),
        # Electrical
        AiraVoltageSensor(coordinator, entry,
            name="OU Voltage",
            unique_id_suffix="ou_voltage",
            data_path=("system_check", "megmet_status", "ac_input_voltage"),
            icon="mdi:flash",
            enabled_by_default=False
        ),
        AiraCurrentSensor(coordinator, entry,
            name="OU Current",
            unique_id_suffix="ou_current",
            data_path=("system_check", "megmet_status", "ac_input_current"),
            icon="mdi:current-ac",
            enabled_by_default=False
        ),



        # Pressures
        AiraEvaporatorPressureSensor(coordinator, entry),
        AiraCondenserPressureSensor(coordinator, entry),
        # Compressor
        AiraCompressorSpeedSensor(coordinator, entry),
        AiraCompressorFrequencyLimitSensor(coordinator, entry),
        AiraCompressorLimitPercentSensor(coordinator, entry),
        # Fans
        AiraDCFan1SpeedSensor(coordinator, entry),
        AiraDCFan2SpeedSensor(coordinator, entry),
        
        # Electronic Expansion Valve
        AiraEEVStepSensor(coordinator, entry),

        # === POWER SENSORS ===
        AiraElectricalPowerSensor(coordinator, entry,
            name="Electrical Power",
            unique_id_suffix="electrical_power",
            data_path=("system_check", "energy_calculation", "current_electrical_power_w"),
            icon="mdi:lightning-bolt"
        ),
        
        AiraThermalPowerSensor(coordinator, entry),


        # todo add calculated setpoint from systemcheck state, probably are the supply target temperatures
        
        # === PER_ZONE SENSORS ===
        # Create sensors for each thermostat dynamically. Indexes are 1, 2
        *[
            sensor_class(coordinator, entry, thermostat_index.get("zone"))
            for thermostat_index in coordinator.data.get("state", {}).get("thermostats", [{"zone": 1}, {"zone": 2}])  # thermostat 1 and 2
            for sensor_class in [
                # Thermostat Sensors
                AiraThermostatTemperatureSensor,
                AiraThermostatHumiditySensor,
                AiraThermostatSignalSensor,
            ]
        ],

        # === ENERGY SENSORS ===
        AiraElectricalEnergySensor(coordinator, entry),
        AiraThermalEnergySensor(coordinator, entry),
        AiraElectricalEnergyWhSensor(coordinator, entry),
        AiraHeatEnergyWhSensor(coordinator, entry),
        AiraEnergyBalanceSensor(coordinator, entry),
        

        
        # === COP SENSORS ===
        AiraInstantaneousCOPSensor(coordinator, entry),
        AiraCumulativeCOPSensor(coordinator, entry),
        AiraDeviceCOPSensor(coordinator, entry),
        
        # === FLOW SENSORS ===
        AiraFlowRateSensor(coordinator, entry),
        AiraFlowMeter1Sensor(coordinator, entry),
        AiraFlowMeter2Sensor(coordinator, entry),
        
        # === SYSTEM STATUS SENSORS ===
        AiraOperatingStatusSensor(coordinator, entry),
        AiraPumpActiveStateSensor(coordinator, entry),
        AiraPumpModeZone1Sensor(coordinator, entry),
        AiraLEDPatternSensor(coordinator, entry),
        
        # === CONNECTION SENSORS ===
        AiraBLERSSISensor(coordinator, entry),
    ]

    # PER ZONE LOOP
    for i in range(1, coordinator.data.get("state", {}).get("number_of_zones", 2) + 1):  # Zones 1 and 2, falls back to 2
        sensors.extend([
        AiraTemperatureSensor(coordinator, entry,
            name=f"Zone {i} Supply Temperature",
            unique_id_suffix=f"zone_{i}_supply_temp",
            data_path=("system_check", "sensor_values", "indoor_unit_supply_temperature_"),
            icon="mdi:thermometer-water"
        ),
        AiraTemperatureSensor(coordinator, entry,
            name=f"Zone {i} Temperature",
            unique_id_suffix=f"zone_{i}_temp",
            data_path=("state", "thermostats", "last_update", "actual_temperature"),
            icon="mdi:sun-thermometer",
            index=f"ZONE_{i}"
        ),

        ])

        # check configured modes on the heatpump to enable heating/cooling targets accordingly
        allowed_pump_mode_state = coordinator.data.get("state", {}).get("allowed_pump_mode_state", "PUMP_MODE_STATE_HEATING_COOLING").lower()
        if "heating" in allowed_pump_mode_state:
            sensors.extend([
            AiraTemperatureSensor(coordinator, entry,
                name=f"Zone {i} Heating Target",
                unique_id_suffix=f"zone_{i}_heat_target",
                data_path=("state", "zone_setpoints_heating", f"zone{i}"),
                icon="mdi:sun-thermometer",
            ),

            ])
        if "cooling" in allowed_pump_mode_state:
            sensors.extend([
            AiraTemperatureSensor(coordinator, entry,
                name=f"Zone {i} Cooling Target",
                unique_id_suffix=f"zone_{i}_cool_target",
                data_path=("state", "zone_setpoints_cooling", f"zone{i}"),
                icon="mdi:snowflake-thermometer",
            ),
            ])

    # PER PHASE LOOP
    current_phase_2 = coordinator.data.get("system_check", {}).get("energy_calculation", {}).get("current_phase_2", 0)
    current_phase_3 = coordinator.data.get("system_check", {}).get("energy_calculation", {}).get("current_phase_3", 0)
    num_phases = 3
    if current_phase_2 == 0 and current_phase_3 == 0:
        num_phases = 1
    for i in range(1, num_phases + 1):
        sensors.extend([
            AiraVoltageSensor(coordinator, entry,
                name=f"Voltage Phase {i}",
                unique_id_suffix=f"voltage_phase_{i}",
                data_path=("system_check", "energy_calculation", f"voltage_phase_{i}"),
                icon="mdi:flash",
                enabled_by_default=True
            ),
            AiraCurrentSensor(coordinator, entry,
                name=f"Current Phase {i}",
                unique_id_suffix=f"current_phase_{i}",
                data_path=("system_check", "energy_calculation", f"current_phase_{i}"),
                icon="mdi:current-ac",
                enabled_by_default=True
            ),
        ])

    # Check entity registry and enable any disabled entities
    entity_reg = er.async_get(hass)
    for sensor in sensors:
        if hasattr(sensor, "unique_id") and sensor.unique_id:
            entity_id = entity_reg.async_get_entity_id("sensor", DOMAIN, sensor.unique_id)
            if entity_id:
                # Entity exists in registry, check if it's disabled
                entity_entry = entity_reg.async_get(entity_id)
                if entity_entry and entity_entry.disabled:
                    _LOGGER.info(
                        "Enabling disabled sensor: %s (unique_id: %s)",
                        entity_id,
                        sensor.unique_id,
                    )
                    entity_reg.async_update_entity(
                        entity_id,
                        disabled_by=None,
                    )
    
    # Debug: Log the current data structure to help diagnose sensor issues
    if coordinator.data:
        _LOGGER.debug("Current coordinator data structure:")
        _LOGGER.debug("  state keys: %s", list(coordinator.data.get("state", {}).keys()))
        _LOGGER.debug("  flow_data keys: %s", list(coordinator.data.get("flow_data", {}).keys()))
        _LOGGER.debug("  system_check keys: %s", list(coordinator.data.get("system_check", {}).keys()))
        
        # Check specific keys for failing sensors
        # system_check = coordinator.data.get("system_check", {})
        # if "energy_calculation" in system_check:
        #     _LOGGER.info("  energy_calculation keys: %s", list(system_check["energy_calculation"].keys()))
        # if "sensor_values" in system_check:
        #     _LOGGER.info("  sensor_values keys: %s", list(system_check["sensor_values"].keys()))
        # if "energy_balance" in system_check:
        #     _LOGGER.info("  energy_balance keys: %s", list(system_check["energy_balance"].keys()))
    else:
        _LOGGER.warning("Coordinator data is empty - this will cause sensor issues")
    
    
    async_add_entities(sensors, False)

# ============================================================================
# BASE SENSOR CLASS
# ============================================================================

class AiraSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for Aira sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._entry_id = entry.entry_id
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data.get(CONF_DEVICE_NAME, DEFAULT_SHORT_NAME),
            "manufacturer": "Aira",
            "model": "Heat Pump",
        }

# ============================================================================
# TEMPERATURE SENSORS
# ============================================================================

class AiraTemperatureSensor(AiraSensorBase):
    """Base class for all temperature sensors."""
    
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        name: str,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:thermometer",
        enabled_by_default: bool = True,
        index: int | str | None = None
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{unique_id_suffix}"
        self._data_path = data_path

        # if string: ZONE_1 or ZONE_2
        # if int: 1 or 2
        self._index = index
        self._attr_entity_registry_enabled_default = enabled_by_default

    @cached_property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None

        if self._data_path:
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path]
                    if self._index is not None and isinstance(value, list):
                        for element in value:
                            # caso in cui l'elemento ha un campo zone:
                            if isinstance(self._index, str) and element.get("zone") == self._index:
                                value = element
                                break
                        if isinstance(self._index, int) and len(value) >= self._index:
                            value = value[self._index - 1]  # Adjust for 0-based index

                return round(float(value), 1) # Round to 1 decimal place
            except (KeyError, ValueError, TypeError):
                return None
        return None

# ============================================================================
# ELECTRICAL SENSORS
# ===========================================================================
class AiraVoltageSensor(AiraSensorBase):
    """Base class for all voltage sensors."""

    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        name: str,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:flash",
        enabled_by_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{unique_id_suffix}"
        self._data_path = data_path
        self._attr_entity_registry_enabled_default = enabled_by_default

    @cached_property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None

        if self._data_path:
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path]

                return round(float(value), 1) # Round to 1 decimal place
            except (KeyError, ValueError, TypeError):
                return None
        return None

class AiraCurrentSensor(AiraSensorBase):
    """Base class for all current sensors."""

    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        name: str,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:current-ac",
        enabled_by_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{unique_id_suffix}"
        self._data_path = data_path
        self._attr_entity_registry_enabled_default = enabled_by_default

    @cached_property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None

        if self._data_path:
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path]

                return round(float(value), 1) # Round to 1 decimal place
            except (KeyError, ValueError, TypeError):
                return None
        return None

# ============================================================================
# POWER SENSORS
# ============================================================================

class AiraElectricalPowerSensor(AiraSensorBase):
    """Base class for all electrical power sensors."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        name: str,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:lightning-bolt",
        enabled_by_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{unique_id_suffix}"
        self._data_path = data_path
        self._attr_entity_registry_enabled_default = enabled_by_default

    @cached_property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None

        if self._data_path:
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path]

                return int(value)
            except (KeyError, ValueError, TypeError):
                return None
        return None

# TODO
class AiraThermalPowerSensor(AiraSensorBase):
    """Thermal power output sensor."""

    _attr_name = "Thermal Power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_thermal_power"

    @cached_property
    def native_value(self) -> float | None:
        """Return the state."""
        return self.coordinator.data["flow_data"].get("power_kilowatts")

# ============================================================================
# ENERGY SENSORS
# ============================================================================

class AiraElectricalEnergySensor(AiraSensorBase):
    """Electrical energy consumption sensor."""

    _attr_name = "Electrical Energy"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:lightning-bolt"

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_electrical_energy"

    @cached_property
    def native_value(self) -> float | None:
        """Return the state."""
        energy_calc = self.coordinator.data["system_check"].get("energy_calculation", {})
        kwh = energy_calc.get("electrical_energy_cum_kwh")
        if kwh is not None:
            return kwh
        wh = energy_calc.get("electrical_energy_cum_wh")
        return wh / 1000 if wh is not None else None


class AiraThermalEnergySensor(AiraSensorBase):
    """Thermal energy output sensor."""

    _attr_name = "Thermal Energy"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_thermal_energy"

    @cached_property
    def native_value(self) -> float | None:
        """Return the state."""
        energy_calc = self.coordinator.data["system_check"].get("energy_calculation", {})
        kwh = energy_calc.get("water_energy_cum_kwh")
        if kwh is not None:
            return kwh
        wh = energy_calc.get("water_energy_cum_wh")
        return wh / 1000 if wh is not None else None


class AiraElectricalEnergyWhSensor(AiraSensorBase):
    """Electrical energy consumption sensor (Wh)."""

    _attr_name = "Electrical Energy, Wh"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_icon = "mdi:lightning-bolt"

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_electrical_energy_wh"

    @cached_property
    def native_value(self) -> int | None:
        """Return the state."""
        energy_calc = self.coordinator.data["system_check"].get("energy_calculation", {})
        return energy_calc.get("electrical_energy_cum_wh")


class AiraHeatEnergyWhSensor(AiraSensorBase):
    """Heat energy output sensor (Wh)."""

    _attr_name = "Heat Energy, Wh"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_heat_energy_wh"

    @cached_property
    def native_value(self) -> int | None:
        """Return the state."""
        energy_calc = self.coordinator.data["system_check"].get("energy_calculation", {})
        return energy_calc.get("water_energy_cum_wh")


class AiraEnergyBalanceSensor(AiraSensorBase):
    """Energy balance sensor."""

    _attr_name = "Energy Balance"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:scale-balance"

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_energy_balance"

    @cached_property
    def native_value(self) -> int | None:
        """Return the state."""
        energy_balance = self.coordinator.data["system_check"].get("energy_balance", {})
        return energy_balance.get("energy_balance")





# ============================================================================
# COP SENSORS
# ============================================================================

class AiraInstantaneousCOPSensor(AiraSensorBase):
    """Instantaneous COP sensor."""

    _attr_name = "Instantaneous COP"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = None

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_instantaneous_cop"

    @cached_property
    def native_value(self) -> float | None:
        """Return the state."""
        energy_calc = self.coordinator.data["system_check"].get("energy_calculation", {})
        elec_power = energy_calc.get("current_electrical_power_w")
        thermal_power_kw = self.coordinator.data["flow_data"].get("power_kilowatts")
        
        if elec_power and thermal_power_kw and elec_power > 0:
            return round((thermal_power_kw * 1000) / elec_power, 2)
        return None


class AiraCumulativeCOPSensor(AiraSensorBase):
    """Cumulative COP sensor."""

    _attr_name = "Cumulative COP"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = None

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_cumulative_cop"

    @cached_property
    def native_value(self) -> float | None:
        """Return the state."""
        energy_calc = self.coordinator.data["system_check"].get("energy_calculation", {})
        elec_kwh = energy_calc.get("electrical_energy_cum_kwh")
        thermal_kwh = energy_calc.get("water_energy_cum_kwh")
        
        if elec_kwh and thermal_kwh and elec_kwh > 0:
            return round(thermal_kwh / elec_kwh, 2)
        return None


class AiraDeviceCOPSensor(AiraSensorBase):
    """Device-reported COP sensor (real-time from heat pump)."""

    _attr_name = "Device COP"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = None

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_device_cop"

    @cached_property
    def native_value(self) -> float | None:
        """Return the state."""
        energy_calc = self.coordinator.data["system_check"].get("energy_calculation", {})
        cop_now = energy_calc.get("cop_now")
        # Only return non-zero values (0 means pump is idle/not operating)
        # Filter out edge case values > 20 as they are artifacts
        if cop_now and cop_now > 0 and cop_now <= 20:
            return round(cop_now, 2)
        return None


# ============================================================================
# FLOW SENSORS
# ============================================================================

class AiraFlowRateSensor(AiraSensorBase):
    """Water flow rate sensor."""

    _attr_name = "Water Flow Rate"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfVolumeFlowRate.LITERS_PER_MINUTE
    _attr_icon = "mdi:water"

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_flow_rate"

    @cached_property
    def native_value(self) -> float | None:
        """Return the state - last flow measurement."""
        flow_measurements = self.coordinator.data["flow_data"].get("flow_data", [])
        if flow_measurements:
            return flow_measurements[-1].get("flow")
        return None


class AiraFlowMeter1Sensor(AiraSensorBase):
    """Flow meter 1 sensor."""

    _attr_name = "Flow Meter 1"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfVolumeFlowRate.LITERS_PER_MINUTE
    _attr_icon = "mdi:water-pump"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_flow_meter1"

    @cached_property
    def native_value(self) -> float | None:
        """Return the state."""
        sensor_values = self.coordinator.data["system_check"].get("sensor_values", {})
        return sensor_values.get("flow_meter1")


class AiraFlowMeter2Sensor(AiraSensorBase):
    """Flow meter 2 sensor."""

    _attr_name = "Flow Meter 2"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfVolumeFlowRate.LITERS_PER_MINUTE
    _attr_icon = "mdi:water-pump"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_flow_meter2"

    @cached_property
    def native_value(self) -> float | None:
        """Return the state."""
        sensor_values = self.coordinator.data["system_check"].get("sensor_values", {})
        return sensor_values.get("flow_meter2")

# ============================================================================
# PRESSURE SENSORS
# ============================================================================

class AiraEvaporatorPressureSensor(AiraSensorBase):
    """Evaporator pressure sensor."""

    _attr_name = "Evaporator Pressure"
    _attr_device_class = SensorDeviceClass.PRESSURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPressure.BAR
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_evaporator_pressure"

    @cached_property
    def native_value(self) -> float | None:
        """Return the state."""
        outdoor_unit = self.coordinator.data["system_check"].get("megmet_status", {})
        return outdoor_unit.get("evaporator_pressure")


class AiraCondenserPressureSensor(AiraSensorBase):
    """Condenser pressure sensor."""

    _attr_name = "Condenser Pressure"
    _attr_device_class = SensorDeviceClass.PRESSURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPressure.BAR
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_condenser_pressure"

    @cached_property
    def native_value(self) -> float | None:
        """Return the state."""
        outdoor_unit = self.coordinator.data["system_check"].get("megmet_status", {})
        return outdoor_unit.get("condenser_pressure")


# ============================================================================
# COMPRESSOR SENSORS
# ============================================================================

class AiraCompressorSpeedSensor(AiraSensorBase):
    """Compressor running speed sensor."""

    _attr_name = "Compressor Speed"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "RPM"
    _attr_icon = "mdi:engine"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_compressor_speed"

    @cached_property
    def native_value(self) -> int | None:
        """Return the state."""
        outdoor_unit = self.coordinator.data["system_check"].get("megmet_status", {})
        return outdoor_unit.get("compressor_running_speed")


class AiraCompressorFrequencyLimitSensor(AiraSensorBase):
    """Compressor frequency limit sensor."""

    _attr_name = "Compressor Frequency Limit"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfFrequency.HERTZ
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_compressor_freq_limit"

    @cached_property
    def native_value(self) -> int | None:
        """Return the state."""
        outdoor_unit = self.coordinator.data["system_check"].get("megmet_status", {})
        return outdoor_unit.get("compressor_frequency_limit")


class AiraCompressorLimitPercentSensor(AiraSensorBase):
    """Compressor limit percentage sensor."""

    _attr_name = "Compressor Limit"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_compressor_limit_percent"

    @cached_property
    def native_value(self) -> int | None:
        """Return the state."""
        outdoor_unit = self.coordinator.data["system_check"].get("megmet_status", {})
        return outdoor_unit.get("compressor_limit_percent_calculated")


# ============================================================================
# FAN SENSORS
# ============================================================================

class AiraDCFan1SpeedSensor(AiraSensorBase):
    """DC Fan 1 speed sensor."""

    _attr_name = "DC Fan 1 Speed"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "RPM"
    _attr_icon = "mdi:fan"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_dc_fan1_speed"

    @cached_property
    def native_value(self) -> int | None:
        """Return the state."""
        outdoor_unit = self.coordinator.data["system_check"].get("megmet_status", {})
        return outdoor_unit.get("dc_fan1_running_speed")


class AiraDCFan2SpeedSensor(AiraSensorBase):
    """DC Fan 2 speed sensor."""

    _attr_name = "DC Fan 2 Speed"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "RPM"
    _attr_icon = "mdi:fan"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_dc_fan2_speed"

    @cached_property
    def native_value(self) -> int | None:
        """Return the state."""
        outdoor_unit = self.coordinator.data["system_check"].get("megmet_status", {})
        return outdoor_unit.get("dc_fan2_running_speed")


# ============================================================================
# ELECTRICAL SENSORS
# ============================================================================


class AiraACInputCurrentSensor(AiraSensorBase):
    """AC input current sensor."""

    _attr_name = "AC Input Current"
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_ac_input_current"

    @cached_property
    def native_value(self) -> int | None:
        """Return the state."""
        outdoor_unit = self.coordinator.data["system_check"].get("megmet_status", {})
        return outdoor_unit.get("ac_input_current")


# ============================================================================
# EXPANSION VALVE SENSOR
# ============================================================================

class AiraEEVStepSensor(AiraSensorBase):
    """Electronic Expansion Valve step sensor."""

    _attr_name = "EEV Step"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:valve"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_eev_step"

    @cached_property
    def native_value(self) -> int | None:
        """Return the state."""
        outdoor_unit = self.coordinator.data["system_check"].get("megmet_status", {})
        return outdoor_unit.get("eev_step")


# ============================================================================
# THERMOSTAT SENSORS
# ============================================================================

class AiraThermostatTemperatureSensor(AiraSensorBase):
    """Thermostat temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        thermostat_index: int = 0,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._thermostat_index = thermostat_index
        self._attr_name = f"Thermostat {self._thermostat_index} Temperature"
        self._attr_unique_id = f"{entry.entry_id}_thermostat{self._thermostat_index}_temp"

    @cached_property
    def native_value(self) -> float | None:
        """Return the state."""
        thermostats = self.coordinator.data["state"].get("thermostats", [])
        if len(thermostats) >= self._thermostat_index:
            found = False
            for thermostat in thermostats:
                if thermostat.get("zone") == self._thermostat_index:
                    found = True
                    break
            if not found:
                return None
            last_update = thermostat.get("last_update", {})
            temp_raw = last_update.get("actual_temperature")
            if temp_raw is not None:
                return round(temp_raw * 0.1, 1)
        return None

class AiraThermostatHumiditySensor(AiraSensorBase):
    """Thermostat humidity sensor."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        thermostat_index: int = 0,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._thermostat_index = thermostat_index
        self._attr_name = f"Thermostat {self._thermostat_index} Humidity"
        self._attr_unique_id = f"{entry.entry_id}_thermostat{self._thermostat_index}_humidity"

    @cached_property
    def native_value(self) -> float | None:
        """Return the state."""
        thermostats = self.coordinator.data["state"].get("thermostats", [])
        if len(thermostats) >= self._thermostat_index:
            found = False
            for thermostat in thermostats:
                if thermostat.get("zone") == self._thermostat_index:
                    found = True
                    break
            if not found:
                return None
            last_update = thermostat.get("last_update", {})
            temp_raw = last_update.get("humidity")
            if temp_raw is not None:
                return round(temp_raw * 0.1, 1)
        return None


class AiraThermostatSignalSensor(AiraSensorBase):
    """Thermostat signal strength sensor."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        thermostat_index: int = 0,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._thermostat_index = thermostat_index
        thermostat_num = thermostat_index + 1
        self._attr_name = f"Thermostat {thermostat_num} Signal"
        self._attr_unique_id = f"{entry.entry_id}_thermostat{thermostat_num}_signal"

    @cached_property
    def native_value(self) -> int | None:
        """Return the state."""
        thermostats = self.coordinator.data["state"].get("thermostats", [])
        if len(thermostats) > self._thermostat_index:
            return thermostats[self._thermostat_index].get("rssi")
        return None


# ============================================================================
# SYSTEM STATUS SENSORS
# ============================================================================

class AiraOperatingStatusSensor(AiraSensorBase):
    """Operating status sensor."""

    _attr_name = "Operating Status"
    _attr_icon = "mdi:information"

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_operating_status"

    @cached_property
    def native_value(self) -> str | None:
        """Return the state."""
        status = self.coordinator.data["state"].get("operating_status", "")
        return status.replace("OPERATING_STATUS_", "").replace("_", " ").title()


class AiraPumpActiveStateSensor(AiraSensorBase):
    """Pump active state sensor."""

    _attr_name = "Pump Active State"
    _attr_icon = "mdi:pump"

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_pump_active_state"

    @cached_property
    def native_value(self) -> str | None:
        """Return the state."""
        state = self.coordinator.data["state"].get("pump_active_state", "")
        return state.replace("PUMP_ACTIVE_STATE_", "").replace("_", " ").title()


class AiraPumpModeZone1Sensor(AiraSensorBase):
    """Pump mode zone 1 sensor."""

    _attr_name = "Pump Mode Zone 1"
    _attr_icon = "mdi:radiator"

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_pump_mode_zone1"

    @cached_property
    def native_value(self) -> str | None:
        """Return the state."""
        pump_mode = self.coordinator.data["state"].get("current_pump_mode_state", {})
        mode = pump_mode.get("zone1", "")
        return mode.replace("PUMP_MODE_STATE_", "").replace("_", " ").title()


class AiraLEDPatternSensor(AiraSensorBase):
    """LED pattern sensor."""

    _attr_name = "LED Pattern"
    _attr_icon = "mdi:led-on"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_led_pattern"

    @cached_property
    def native_value(self) -> str | None:
        """Return the state."""
        pattern = self.coordinator.data["state"].get("led_pattern", "")
        return pattern.replace("LED_PATTERN_", "").replace("_", " ").title()


# ============================================================================
# CONNECTION SENSORS
# ============================================================================

class AiraBLERSSISensor(AiraSensorBase):
    """BLE signal strength (RSSI) sensor."""

    _attr_name = "BLE Signal Strength"
    _attr_icon = "mdi:bluetooth"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_ble_rssi"

    @cached_property
    def native_value(self) -> int | None:
        """Return the RSSI value."""
        return self.coordinator.data.get("rssi")
    
    @cached_property
    def icon(self) -> str:
        """Return icon based on signal strength."""
        rssi = self.coordinator.data.get("rssi")
        if rssi is None:
            return "mdi:bluetooth-off"
        elif rssi >= -60:
            return "mdi:bluetooth"  # Excellent
        elif rssi >= -75:
            return "mdi:bluetooth-connect"  # Good
        else:
            return "mdi:bluetooth-off"  # Poor
