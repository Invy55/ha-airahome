"""Sensor platform for Aira Heat Pump."""
from __future__ import annotations

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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_NAME, CONF_DEVICE_UUID, DEFAULT_SHORT_NAME, DOMAIN
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
        AiraScheduledTemperatureSensor(coordinator, entry),
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
        AiraPressureSensor(coordinator, entry,
            name="OU Evaporator Pressure",
            unique_id_suffix="ou_evaporator_pressure",
            data_path=("system_check", "megmet_status", "evaporator_pressure"),
            icon="mdi:thermometer-lines",
            enabled_by_default=False
        ),
        AiraPressureSensor(coordinator, entry,
            name="OU Condenser Pressure",
            unique_id_suffix="ou_condenser_pressure",
            data_path=("system_check", "megmet_status", "condenser_pressure"),
            icon="mdi:thermometer-lines",
            enabled_by_default=False
        ),
        # Fans
        AiraRotationSpeedSensor(coordinator, entry,
            name="OU Fan 1 Speed",
            unique_id_suffix="ou_fan_1_speed",
            data_path=("system_check", "megmet_status", "dc_fan1_running_speed"),
            icon="mdi:fan",
            enabled_by_default=False
        ),
        AiraRotationSpeedSensor(coordinator, entry,
            name="OU Fan 2 Speed",
            unique_id_suffix="ou_fan_2_speed",
            data_path=("system_check", "megmet_status", "dc_fan1_running_speed"),
            icon="mdi:fan",
            enabled_by_default=False
        ),
        # Compressor
        AiraRotationSpeedSensor(coordinator, entry,
            name="OU Compressor Speed",
            unique_id_suffix="ou_compressor_speed",
            data_path=("system_check", "megmet_status", "compressor_running_speed"),
            icon="mdi:engine",
            enabled_by_default=False
        ),
        AiraFrequencySensor(coordinator, entry,
            name="OU Compressor Frequency Limit",
            unique_id_suffix="ou_compressor_freq_limit",
            data_path=("system_check", "megmet_status", "compressor_frequency_limit"),
            icon="mdi:engine",
            enabled_by_default=False
        ),
        AiraPercentageSensor(coordinator, entry,
            name="OU Compressor Need Percent",
            unique_id_suffix="ou_compressor_need",
            data_path=("system_check", "megmet_status", "compressor_need_percent_calculated"),
            icon="mdi:engine",
            enabled_by_default=False
        ),
        AiraPercentageSensor(coordinator, entry,
            name="OU Compressor Limit Percent",
            unique_id_suffix="ou_compressor_limit",
            data_path=("system_check", "megmet_status", "compressor_limit_percent_calculated"),
            icon="mdi:engine",
            enabled_by_default=False
        ),
        # Electronic Expansion Valve
        AiraEEVStepSensor(coordinator, entry),
        # === POWER SENSORS ===
        AiraPowerSensor(coordinator, entry,
            name="Instant Power Consumption (kW)",
            unique_id_suffix="instant_power_kw",
            data_path=("system_check", "energy_calculation", "current_electrical_power_w"),
            unit_of_measurement=UnitOfPower.KILO_WATT,
            original_unit=UnitOfPower.WATT,
            icon="mdi:lightning-bolt"
        ),
        AiraPowerSensor(coordinator, entry,
            name="Instant Power Consumption (W)",
            unique_id_suffix="instant_power_w",
            data_path=("system_check", "energy_calculation", "current_electrical_power_w"),
            unit_of_measurement=UnitOfPower.WATT,
            original_unit=UnitOfPower.WATT,
            icon="mdi:lightning-bolt",
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
            name="Total Electricity Consumption (kWh)",
            unique_id_suffix="electricity_kwh",
            data_path=("system_check", "energy_calculation", "electrical_energy_cum_wh"),
            icon="mdi:transmission-tower",
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            original_unit=UnitOfEnergy.WATT_HOUR,
        ),
        AiraEnergySensor(coordinator, entry,
            name="Total Electricity Consumption (Wh)",
            unique_id_suffix="electricity_wh",
            data_path=("system_check", "energy_calculation", "electrical_energy_cum_wh"),
            icon="mdi:transmission-tower",
            unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            original_unit=UnitOfEnergy.WATT_HOUR,
            enabled_by_default=False
        ),
        AiraEnergySensor(coordinator, entry,
            name="Total Heat Produced (kWh)",
            unique_id_suffix="heat_kwh",
            data_path=("system_check", "energy_calculation", "water_energy_cum_wh"),
            icon="mdi:fire",
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            original_unit=UnitOfEnergy.WATT_HOUR,
        ),
        AiraEnergySensor(coordinator, entry,
            name="Total Heat Produced (Wh)",
            unique_id_suffix="heat_wh",
            data_path=("system_check", "energy_calculation", "water_energy_cum_wh"),
            icon="mdi:fire",
            unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            original_unit=UnitOfEnergy.WATT_HOUR,
            enabled_by_default=False
        ),
        AiraEnergyBalanceSensor(coordinator, entry),
        # === COP SENSORS ===
        AiraInstantCOPSensor(coordinator, entry),
        AiraCumulativeCOPSensor(coordinator, entry),
        AiraDeviceCOPSensor(coordinator, entry),
        # === FLOW SENSORS ===
        AiraFlowRateSensor(coordinator, entry,
            name="Primary Circuit Flow",
            unique_id_suffix="flow_meter_1",
            data_path=("system_check", "sensor_values", "flow_meter1"),
        ),
        AiraFlowRateSensor(coordinator, entry,
            name="DHW Tank Inlet Flow",
            unique_id_suffix="flow_meter_2",
            data_path=("system_check", "sensor_values", "flow_meter2"),
        ),
        # === SYSTEM STATUS SENSORS ===
        AiraEnumSensor(coordinator, entry,
            name="Operating Status",
            unique_id_suffix="operating_status",
            data_path=("state", "operating_status"),
            replace="OPERATING_STATUS_",
            icon="mdi:information-outline"
        ),
        AiraEnumSensor(coordinator, entry,
            name="HP Active State",
            unique_id_suffix="active_state",
            data_path=("state", "pump_active_state"),
            replace="PUMP_ACTIVE_STATE_",
            icon="mdi:heat-pump-outline"
        ),        
        AiraLEDPatternSensor(coordinator, entry),
        # === CONNECTION SENSORS ===
        AiraSignalStrengthSensor(coordinator, entry,
            name="BLE Signal Strength",
            unique_id_suffix="system_rssi",
            data_path=("rssi", )
        ),
    ]

    # PER ZONE LOOP
    for i in range(1, coordinator.data.get("state", {}).get("number_of_zones", 2) + 1):  # Zones 1 and 2, falls back to 2
        sensors.extend([
        AiraTemperatureSensor(coordinator, entry,
            name=f"Zone {i} Supply Temperature",
            unique_id_suffix=f"zone_{i}_supply_temp",
            data_path=("system_check", "sensor_values", "indoor_unit_supply_temperature"),
            icon="mdi:thermometer-water"
        ),
        AiraTemperatureSensor(coordinator, entry,
            name=f"Zone {i} Temperature",
            unique_id_suffix=f"zone_{i}_temp",
            data_path=("state", "thermostats", "last_update", "actual_temperature"),
            icon="mdi:thermometer",
            index=f"ZONE_{i}",
            divide_by_10=True
        ),
        AiraHumiditySensor(coordinator, entry,
            name=f"Zone {i} Humidity",
            unique_id_suffix=f"zone_{i}_humidity",
            data_path=("state", "thermostats", "last_update", "humidity"),
            icon="mdi:water-percent",
            index=f"ZONE_{i}",
            divide_by_10=True
        ),
        AiraSignalStrengthSensor(coordinator, entry,
            name=f"Zone {i} Signal Strength",
            unique_id_suffix=f"zone_{i}_rssi",
            data_path=("state", "thermostats", "rssi"),
            index=f"ZONE_{i}"
        ),
        AiraEnumSensor(coordinator, entry,
            name=f"HP Zone {i} State",
            unique_id_suffix=f"zone_{i}_active_state",
            data_path=("state", "current_pump_mode_state", f"zone{i}"),
            replace="PUMP_MODE_STATE_",
            icon="mdi:heat-pump-outline"
        )
        # TODO ADD SETPOINTS

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
            )
            ])
        if "cooling" in allowed_pump_mode_state:
            sensors.extend([
            AiraTemperatureSensor(coordinator, entry,
                name=f"Zone {i} Cooling Target",
                unique_id_suffix=f"zone_{i}_cool_target",
                data_path=("state", "zone_setpoints_cooling", f"zone{i}"),
                icon="mdi:snowflake-thermometer",
            )
            ])

    # PER PHASE LOOP
    current_phase_2 = coordinator.data.get("system_check", {}).get("energy_calculation", {}).get("current_phase2", 0)
    current_phase_3 = coordinator.data.get("system_check", {}).get("energy_calculation", {}).get("current_phase3", 0)
    num_phases = 3
    if current_phase_2 == 0 and current_phase_3 == 0:
        num_phases = 1
    for i in range(num_phases):
        sensors.extend([
            AiraVoltageSensor(coordinator, entry,
                name=f"Voltage Phase {i}",
                unique_id_suffix=f"voltage_phase_{i}",
                data_path=("system_check", "energy_calculation", f"voltage_phase{i}"),
                icon="mdi:flash",
                enabled_by_default=True
            ),
            AiraCurrentSensor(coordinator, entry,
                name=f"Current Phase {i}",
                unique_id_suffix=f"current_phase_{i}",
                data_path=("system_check", "energy_calculation", f"current_phase{i}"),
                icon="mdi:current-ac",
                enabled_by_default=True
            ),
        ])
   
    # Debug: Log the current data structure to help diagnose sensor issues
    if coordinator.data:
        _LOGGER.debug("Current coordinator data structure:")
        # _LOGGER.debug("  state keys: %s", coordinator.data.get("state", {}))
        # _LOGGER.debug("  flow_data keys: %s", coordinator.data.get("flow_data", {}))
        # _LOGGER.debug("  system_check keys: %s", coordinator.data.get("system_check", {}))
        _LOGGER.debug("  state keys: %s", list(coordinator.data.get("state", {}).keys()))
        # _LOGGER.debug("  flow_data keys: %s", list(coordinator.data.get("flow_data", {}).keys()))
        _LOGGER.debug("  system_check keys: %s", list(coordinator.data.get("system_check", {}).keys()))
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
        self._device_uuid = entry.data[CONF_DEVICE_UUID]
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._device_uuid)},
            "name": entry.data.get(CONF_DEVICE_NAME, DEFAULT_SHORT_NAME),
            "manufacturer": "Aira",
            "model": "Heat Pump",
        }

    # TODO check if AVAIABLE property is needed

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
        name: str,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:thermometer",
        enabled_by_default: bool = True,
        divide_by_10: bool = False,
        index: int | str | None = None
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{self._device_uuid}_{unique_id_suffix}"
        self._data_path = data_path
        self._divide_by_10 = divide_by_10
        # if string: ZONE_1 or ZONE_2
        # if int: 1 or 2
        self._index = index
        self._attr_entity_registry_enabled_default = enabled_by_default

    @property
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

                if self._divide_by_10:
                    return round(float(value) / 10, 2) # Round to 1 decimal place
                return round(float(value), 2) # Round to 1 decimal place
            except (KeyError, ValueError, TypeError):
                return None
        return None

class AiraScheduledTemperatureSensor(AiraSensorBase):
    """Schedule temperature sensor. Varies based on current schedule/target temperature."""

    _attr_name = "DHW Scheduled Temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = "mdi:thermometer-water"
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_uuid}_scheduled_temp"
        
    @property
    def native_value(self) -> float | None:
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
        name: str,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:water-percent",
        enabled_by_default: bool = True,
        divide_by_10: bool = False,
        index: int | str | None = None
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{self._device_uuid}_{unique_id_suffix}"
        self._data_path = data_path
        self._divide_by_10 = divide_by_10
        # if string: ZONE_1 or ZONE_2
        # if int: 1 or 2
        self._index = index
        self._attr_entity_registry_enabled_default = enabled_by_default

    @property
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

                if self._divide_by_10:
                    return round(float(value) / 10, 1) # Round to 1 decimal place
                return round(float(value), 1) # Round to 1 decimal place
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
        name: str,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        enabled_by_default: bool = True,
        index: int | str | None = None
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = name
        self._attr_unique_id = f"{self._device_uuid}_{unique_id_suffix}"
        self._data_path = data_path

        # if string: ZONE_1 or ZONE_2
        # if int: 1 or 2
        self._index = index
        self._attr_entity_registry_enabled_default = enabled_by_default

    @property
    def native_value(self) -> int | None:
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

                return int(value)
            except (KeyError, ValueError, TypeError):
                return None
        return None
    
    @property
    def icon(self) -> str:
        """Return the icon based on signal strength."""
        value = self.native_value
        if value is None:
            return "mdi:signal-off"
        elif value >= -67:
            return "mdi:signal-cellular-4"
        elif -70 <= value < -67:
            return "mdi:signal-cellular-3"
        elif -80 <= value < -70:
            return "mdi:signal-cellular-2"
        elif -90 <= value < -80:
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
        name: str,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:flash",
        enabled_by_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{self._device_uuid}_{unique_id_suffix}"
        self._data_path = data_path
        self._attr_entity_registry_enabled_default = enabled_by_default

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None

        if self._data_path:
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path]

                return round(float(value), 2) # Round to 1 decimal place
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
        name: str,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:current-ac",
        enabled_by_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{self._device_uuid}_{unique_id_suffix}"
        self._data_path = data_path
        self._attr_entity_registry_enabled_default = enabled_by_default

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None

        if self._data_path:
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path]

                return round(float(value), 2) # Round to 1 decimal place
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
        name: str,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:lightning-bolt",
        unit_of_measurement: str = UnitOfPower.KILO_WATT,
        original_unit: str = UnitOfPower.WATT,
        enabled_by_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._original_unit = original_unit
        self._attr_unique_id = f"{self._device_uuid}_{unique_id_suffix}"
        self._data_path = data_path
        self._attr_entity_registry_enabled_default = enabled_by_default

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None

        if self._data_path:
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path]

                if self._original_unit == UnitOfPower.WATT and self._attr_native_unit_of_measurement == UnitOfPower.KILO_WATT:
                    return round(float(value) / 1000, 3)  # Convert W to kW
                elif self._original_unit == UnitOfPower.KILO_WATT and self._attr_native_unit_of_measurement == UnitOfPower.WATT:
                    return round(float(value) * 1000, 3)  # Convert kW to W
                else:
                    return round(float(value), 3)
            except (KeyError, ValueError, TypeError):
                return None
        return None

# ============================================================================
# ENERGY SENSORS
# ============================================================================

class AiraEnergySensor(AiraSensorBase):
    """Base class for all energy sensors."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 3

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        name: str,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:transmission-tower",
        unit_of_measurement: str = UnitOfEnergy.KILO_WATT_HOUR,
        original_unit: str = UnitOfEnergy.WATT_HOUR,
        enabled_by_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._original_unit = original_unit
        self._attr_unique_id = f"{self._device_uuid}_{unique_id_suffix}"
        self._data_path = data_path
        self._attr_entity_registry_enabled_default = enabled_by_default

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None

        if self._data_path:
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path]
                # Convert to kWh if original unit is Wh
                if self._original_unit == UnitOfEnergy.WATT_HOUR and self._attr_native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR:
                    return round(float(value) / 1000, 3)  # Convert Wh to kWh
                elif self._original_unit == UnitOfEnergy.KILO_WATT_HOUR and self._attr_native_unit_of_measurement == UnitOfEnergy.WATT_HOUR:
                    return round(float(value) * 1000, 3)  # Convert kWh to Wh
                else:
                    return round(float(value), 3)
            except (KeyError, ValueError, TypeError):
                return None
        return None

# ============================================================================
# INSTANT HEAT SENSORS
# ============================================================================

class AiraInstantHeatSensor(AiraSensorBase):
    """Thermal power output sensor. Calculated using https://docs.openenergymonitor.org/heatpumps/basics.html#mass-flow-rate-heat-transfer"""

    _attr_name = "Instant Heat Production"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_icon = "mdi:fire"
    _attr_suggested_display_precision = 3

    def __init__(
            self,
            coordinator: AiraDataUpdateCoordinator,
            entry: ConfigEntry, unit_of_measurement: str = UnitOfPower.WATT,
            enabled_by_default: bool = True,
            ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_uuid}_instant_heat_{unit_of_measurement.lower()}"
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._attr_entity_registry_enabled_default = enabled_by_default

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        # heat output (W) = specific heat (J/kg.K) x flow rate (kg/s) x DT (K)
        # heat output (W) = 4200 J/kg.K x 0.25 kg/s x 5K = 5250 W
        try:
            flow = float(self.coordinator.data["system_check"]["sensor_values"]["flow_meter1"]) / 60.0  # in L/min -> kg/s
            specific_heat = 4200  # J/kg.K
            dt = float(self.coordinator.data["system_check"]["sensor_values"]["outdoor_unit_supply_temperature"]) - float(self.coordinator.data["system_check"]["sensor_values"]["outdoor_unit_return_temperature"])  # delta T in K
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
        name: str,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:thermometer-lines",
        enabled_by_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{self._device_uuid}_{unique_id_suffix}"
        self._data_path = data_path
        self._attr_entity_registry_enabled_default = enabled_by_default

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None

        if self._data_path:
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path]

                return round(float(value), 2) # Round to 1 decimal places
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
        name: str,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:rotate-right",
        enabled_by_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{self._device_uuid}_{unique_id_suffix}"
        self._data_path = data_path
        self._attr_entity_registry_enabled_default = enabled_by_default

    @property
    def native_value(self) -> int | None:
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

# ============================================================================
# ENERGY BALANCE SENSOR
# ============================================================================

class AiraEnergyBalanceSensor(AiraSensorBase):
    """Energy balance sensor."""

    _attr_name = "Energy Balance"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:scale-balance"

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_uuid}_energy_balance"

    @property
    def native_value(self) -> int | None:
        """Return the state."""
        energy_balance = self.coordinator.data["system_check"].get("energy_balance", {})
        return energy_balance.get("energy_balance")

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
        name: str,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        enabled_by_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = name
        self._attr_unique_id = f"{self._device_uuid}_{unique_id_suffix}"
        self._data_path = data_path
        self._attr_entity_registry_enabled_default = enabled_by_default

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None

        if self._data_path:
            value = self.coordinator.data
            try:
                for path in self._data_path:
                    value = value[path]

                return round(float(value), 2) # Round to 1 decimal places
            except (KeyError, ValueError, TypeError):
                return 0
        return None

    @property
    def icon(self) -> str:
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
        name: str,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        icon: str = "mdi:sine-wave",
        enabled_by_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{self._device_uuid}_{unique_id_suffix}"
        self._data_path = data_path
        self._attr_entity_registry_enabled_default = enabled_by_default

    @property
    def native_value(self) -> int | None:
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
            name: str,
            unique_id_suffix: str,
            data_path: tuple[str, ...],
            icon: str = "mdi:percent",
            enabled_by_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = name
        self._attr_unique_id = f"{self._device_uuid}_{unique_id_suffix}"
        self._data_path = data_path
        self._attr_icon = icon
        self._attr_entity_registry_enabled_default = enabled_by_default
    
    @property
    def native_value(self) -> int | None:
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

# ============================================================================
# EXPANSION VALVE SENSOR
# ============================================================================

class AiraEEVStepSensor(AiraSensorBase):
    """Electronic Expansion Valve step sensor."""

    _attr_name = "Electronic Expansion Valve Step"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:valve"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_uuid}_eev_step"

    @property
    def native_value(self) -> int | None:
        """Return the state."""
        outdoor_unit = self.coordinator.data["system_check"].get("megmet_status", {})
        return outdoor_unit.get("eev_step")

# ============================================================================
# ENUM SENSORS
# ============================================================================

class AiraEnumSensor(AiraSensorBase):
    """Base class for all enum sensors."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_state_class = None

    def __init__(
        self,
        coordinator: AiraDataUpdateCoordinator,
        entry: ConfigEntry,
        name: str,
        unique_id_suffix: str,
        data_path: tuple[str, ...],
        replace: str,
        icon: str = "mdi:information-outline",
        enabled_by_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{self._device_uuid}_{unique_id_suffix}"
        self._data_path = data_path
        self._replace = replace
        self._attr_entity_registry_enabled_default = enabled_by_default
    
    @property
    def native_value(self) -> str | None:
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

# ============================================================================
# LED STATUS SENSORS
# ============================================================================

class AiraLEDPatternSensor(AiraSensorBase):
    """LED pattern sensor."""

    _attr_name = "LED Pattern"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_state_class = None
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_uuid}_led_pattern"

    @property
    def native_value(self) -> str | None:
        """Return the state."""
        pattern = self.coordinator.data["state"].get("led_pattern", "")
        return pattern.replace("LED_PATTERN_", "").replace("_", " ").title()

    @property
    def icon(self) -> str:
        """Return the icon based on LED pattern."""
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

    _attr_name = "Instant COP"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = None
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_uuid}_instant_cop"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        try:
            flow = float(self.coordinator.data["system_check"]["sensor_values"]["flow_meter1"]) / 60.0  # in L/min -> kg/s
            specific_heat = 4200  # J/kg.K
            dt = float(self.coordinator.data["system_check"]["sensor_values"]["outdoor_unit_supply_temperature"]) - float(self.coordinator.data["system_check"]["sensor_values"]["outdoor_unit_return_temperature"])  # delta T in K
            heat_output_w = specific_heat * flow * dt  # in Watts
            energy_calc = self.coordinator.data["system_check"].get("energy_calculation", {})
            elec_power = energy_calc.get("current_electrical_power_w")
            
            if elec_power and heat_output_w and elec_power > 0:
                return round(heat_output_w / elec_power, 2)
            return None
        except (KeyError, ValueError, TypeError):
            return None

class AiraCumulativeCOPSensor(AiraSensorBase):
    """Cumulative COP sensor."""

    _attr_name = "Cumulative COP"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = None
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_uuid}_cumulative_cop"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        try:
            energy_calc = self.coordinator.data["system_check"]["energy_calculation"]
            elec_kwh = energy_calc["electrical_energy_cum_kwh"]
            thermal_kwh = energy_calc["water_energy_cum_kwh"]

            if elec_kwh and thermal_kwh and elec_kwh > 0:
                return round(thermal_kwh / elec_kwh, 2)
            return None
        except (KeyError, ValueError, TypeError):
            return None

class AiraDeviceCOPSensor(AiraSensorBase):
    """Device-reported COP sensor (real-time from heat pump)."""

    _attr_name = "Heatpump Reported COP"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = None
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: AiraDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._device_uuid}_reported_cop"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        energy_calc = self.coordinator.data["system_check"].get("energy_calculation", {})
        cop_now = energy_calc.get("cop_now")
        # Only return non-zero values (0 means pump is idle/not operating)
        # Filter out edge case values > 8 as they are artifacts according to emoncms.org
        if cop_now and cop_now > 0 and cop_now <= 8: 
            return round(cop_now, 2)
        return None