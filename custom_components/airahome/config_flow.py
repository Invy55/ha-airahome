"""Config flow for Aira Heat Pump integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from functools import partial

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, OptionsFlowWithReload, ConfigFlowResult, ConfigEntry
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.translation import async_get_translations
from homeassistant.helpers import config_validation as cv

from pyairahome import AiraHome
from pyairahome.utils.exceptions import AuthenticationError
from pyairahome.enums import DeviceType
from grpc._channel import _InactiveRpcError
from grpc import RpcError, StatusCode

from .const import (
    CONF_CERTIFICATE,
    CONF_CLOUD_EMAIL,
    CONF_CLOUD_PASSWORD,
    CONF_DEVICE_NAME,
    CONF_DEVICE_UUID,
    CONF_INSTALLATION,
    CONF_MAC_ADDRESS,
    CONF_NUM_PHASES,
    CONF_SCAN_INTERVAL,
    CONF_NUM_ZONES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_NAME,
    DOMAIN,
    SUPPORTED_DEVICE_TYPES
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAC_ADDRESS): str,
    }
)

async def get_translated_device_type(device_type_key: str, hass: HomeAssistant) -> str:
    """Get translated device type string."""
    translations = await async_get_translations(
        hass,
        hass.config.language,
        "device_type",
        [DOMAIN],
    )

    return translations.get(f"component.{DOMAIN}.device_type.{device_type_key}", device_type_key)

async def get_translated_zone(num_zones: int, hass: HomeAssistant) -> str:
    """Get translated zone string."""
    translations = await async_get_translations(
        hass,
        hass.config.language,
        "zones",
        [DOMAIN],
    )

    return translations.get(f"component.{DOMAIN}.zones.{num_zones}", str(num_zones))

async def get_translated_phase(num_phases: int, hass: HomeAssistant) -> str:
    """Get translated phase string."""
    translations = await async_get_translations(
        hass,
        hass.config.language,
        "phases",
        [DOMAIN],
    )

    return translations.get(f"component.{DOMAIN}.phases.{num_phases}", str(num_phases))


class AiraHomeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aira Heat Pump."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, str] = {}
        self._uuid: str | None = None
        self._tested: bool = False
        self._service_info: BluetoothServiceInfoBleak | None = None
        self._mac_address: str | None = None
        self._name: str | None = None
        self._cloud_devices: list[dict] = []
        self._aira: AiraHome | None = None
        self._certificate: str | None = None
        self._installation = {} # store useful data like tank size, etc.

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowWithReload:
        """Get the options flow for this handler."""
        return AiraHomeOptionsFlowHandler()

    # Manual setup by the user
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step. Obtain cloud credentials and use them to fetch available devices."""
        errors: dict[str, str] = {}
        
        data_schema = vol.Schema(
            {
                vol.Required(CONF_CLOUD_EMAIL): cv.string,
                vol.Required(CONF_CLOUD_PASSWORD): cv.string,
            }
        )

        if user_input is not None:
            # Inserted credentials
            username = user_input[CONF_CLOUD_EMAIL]
            password = user_input[CONF_CLOUD_PASSWORD]

            # Try to authenticate and get devices
            try:
                # Ensure credentials are not None
                if not username or not password:
                    errors["base"] = "invalid_auth"
                    raise AuthenticationError("Empty username or password")
                
                _LOGGER.debug("Initializing AiraHome instance")
                aira = AiraHome(ext_loop=self.hass.loop)
                self._aira = aira # Store for later

                _LOGGER.debug("Logging in to Aira Cloud")
                await self.hass.async_add_executor_job(
                    partial(
                        aira.cloud.login_with_credentials,
                        username=username,
                        password=password
                    )
                )
                
                # Get devices from the cloud api
                devices: dict[str, list] = await self.hass.async_add_executor_job(
                    partial(
                        aira.cloud.get_devices, raw=False
                    )
                ) #type: ignore
                
                if devices and "devices" in devices.keys() and devices["devices"]:
                    # Store devices for the next step
                    self._cloud_devices = devices["devices"]
                    _LOGGER.info("Found %d device(s) in the cloud account", len(self._cloud_devices))
                    return await self.async_step_select_device()
                else:
                    _LOGGER.error("No devices found in the cloud account")
                    errors["base"] = "no_devices_found"
                    
            except AuthenticationError as exc:
                _LOGGER.error("Cloud authentication failed: %s", exc)
                errors["base"] = "invalid_auth"
            except _InactiveRpcError as exc:
                if exc.code() == StatusCode.DEADLINE_EXCEEDED:
                    _LOGGER.error("Cloud service timeout: %s", exc)
                    errors["base"] = "cloud_timeout"
                elif exc.code() == StatusCode.UNAVAILABLE:
                    _LOGGER.error("Cloud service unavailable: %s", exc)
                    errors["base"] = "cloud_unavailable"
                else:
                    # fallback for other gRPC errors
                    _LOGGER.error("gRPC error during cloud login: %s", exc)
                    errors["base"] = "cloud_error"

            except Exception as exc:
                if len(errors) == 0:
                    _LOGGER.error("Unexpected error during cloud login: %s", exc)
                    errors["base"] = "unknown"
        
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_select_device(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Second step - let the user select the heat pump to configure."""

        if user_input is not None or self._uuid:
            if self._uuid:
                selected_uuid = self._uuid
            elif user_input:
                selected_uuid = user_input["device"]
            else:
                return self.async_abort(reason="unknown")
            
            # Find the selected device
            selected_device = None
            for device in self._cloud_devices:
                device_uuid = device.get("id", {}).get("value")
                if device_uuid == selected_uuid:
                    selected_device = device
                    break
            
            if not selected_device:
                return self.async_abort(reason="device_not_found")
            
            # Check if already configured
            await self.async_set_unique_id(selected_uuid)
            self._abort_if_unique_id_configured()

            device_type = selected_device.get("device_id", {}).get("type", "DEVICE_TYPE_UNSPECIFIED").lower().replace("device_type_", "")
            if device_type not in SUPPORTED_DEVICE_TYPES:
                _LOGGER.error("Selected device is not a heat pump: %s", device_type)
                return self.async_abort(reason="unsupported_device")

            aira = self._aira
            if not aira:
                return self.async_abort(reason="unknown")

            if device_type == "heat_pump":
                _LOGGER.info("Configuring Aira Heat Pump. Device type: %s")
                details: dict[str, dict] = await self.hass.async_add_executor_job(
                        partial(
                            aira.cloud.get_heatpump_details,
                            household_id=selected_device.get("device_id", {}).get("household_id", {}).get("value", ""),
                            _type=DeviceType.DEVICE_TYPE_HEAT_PUMP, # type: ignore
                            local_id=selected_device.get("device_id", {}).get("local_id", {})
                        )
                    )
                # Retrieve certificate now for later usage, this way we can avoid storing credentials
                self._certificate = details.get("heat_pump", {}).get("certificate", None)
                if tank_size := details.get("heat_pump", {}).get("tank_size", None):
                    if "NONE" not in tank_size and "UNSPECIFIED" not in tank_size:
                        self._installation["tank_size"] = tank_size # store tank size if available
                
                states: dict[str, dict] = await self.hass.async_add_executor_job( # type: ignore
                        partial(
                            aira.cloud.get_states,
                            device_ids=selected_uuid
                        )
                    )
                _LOGGER.debug("Retrieved device states: %s", states)
                self._installation[CONF_NUM_ZONES] = states.get("heat_pump_states", [{}])[0].get(CONF_NUM_ZONES, 1) # default to 1 zone if not provided
                #self._installation["num_phases"] = unknown, there is no way to know before connecting...


            # Move to last configuration step
            self._uuid = selected_uuid
            return await self.async_step_configure()

        _LOGGER.debug(self._async_current_entries())

        # Build device selection list
        already_configured = [e.unique_id for e in self._async_current_entries()]
        device_options = {}
        for device in self._cloud_devices:
            device_uuid = device.get("id", {}).get("value")
            if not device_uuid:
                continue # skip invalid entries without an id
            if device_uuid in already_configured:
                continue # skip already configured devices
            device_type = device.get("device_id", {}).get("type", "DEVICE_TYPE_UNSPECIFIED").lower().replace("device_type_", "")
            translated_device_type = await get_translated_device_type(device_type, self.hass)
            online_status = device.get("online", {}).get("online", False)
            status_str = "🟢" if online_status else "🔴"
            display_name = f"{status_str} {translated_device_type} [{device_uuid}]"
            device_options[device_uuid] = display_name
        
        if not device_options:
            _LOGGER.error("No unconfigured devices available in the cloud account")
            return self.async_abort(reason="no_devices_found")

        data_schema = vol.Schema(
            {
                vol.Required("device"): vol.In(device_options),
            }
        )
        
        return self.async_show_form(
            step_id="select_device",
            data_schema=data_schema,
            description_placeholders={
                "device_count": str(len(self._cloud_devices) - len(already_configured))
            }
        )

    async def async_step_configure(self,
        user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Third Step - configure polling interval and finalize setup."""
        if user_input is not None:
            # Get the UUID from stored context if not passed
            if not self._uuid:
                return self.async_abort(reason="unknown")

            
            # Now discover BLE device with this UUID
            _LOGGER.info("Looking for BLE device with UUID: %s", self._uuid)
            service_info = self._service_info
            mac_address = self._mac_address
            name = self._name
            
            if not mac_address:
                _LOGGER.error("BLE device not found for UUID: %s", self._uuid)
                return self.async_abort(reason="ble_device_not_found")
            
            installation = self._installation.copy()
            installation.pop(CONF_NUM_PHASES, None) # remove num_phases from installation data to avoid redundancy
            installation.pop(CONF_NUM_ZONES, None) # remove num_zones from installation data to avoid redundancy

            # Create entry with all necessary data
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data={
                    CONF_MAC_ADDRESS: mac_address,
                    CONF_DEVICE_UUID: self._uuid,
                    CONF_DEVICE_NAME: name,
                    CONF_CERTIFICATE: self._certificate
                },
                options={
                    CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    CONF_NUM_ZONES: user_input.get(CONF_NUM_ZONES, self._installation.get(CONF_NUM_ZONES, 1)),
                    CONF_NUM_PHASES: user_input.get(CONF_NUM_PHASES, self._installation.get(CONF_NUM_PHASES, 0)),
                    CONF_INSTALLATION: self._installation
                }
            )
        
        if not self._tested and self._uuid:
            # Test BLE connection to get installation details
            service_info = await self._find_ble_device_by_uuid(self._uuid)
            mac_address = service_info.address if service_info else None
            
            if not mac_address:
                _LOGGER.error("BLE device not found for UUID: %s", self._uuid)
                return self.async_abort(reason="ble_device_not_found")
            
            success, installation = await self._ble_connect_test(mac_address)
            if not success:
                _LOGGER.error("Cannot connect to BLE device at %s", mac_address)
                return self.async_abort(reason=installation.get("error", "cannot_connect"))
            
            # Store installation details
            self._installation.update(installation)
            self._tested = True
            self._service_info = service_info
            self._mac_address = mac_address
            self._name = service_info.name if service_info else DEFAULT_NAME or DEFAULT_NAME

        # Show configuration form
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=DEFAULT_SCAN_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=20, max=300)),
                vol.Required(
                    CONF_NUM_ZONES,
                    default=self._installation.get(CONF_NUM_ZONES, 1)
                ): vol.In({
                    1: await get_translated_zone(1, self.hass),
                    2: await get_translated_zone(2, self.hass)
                }),
                vol.Required(
                    CONF_NUM_PHASES,
                    default=self._installation.get(CONF_NUM_PHASES, 0)
                ): vol.In({
                    0: await get_translated_phase(0, self.hass), # unknown
                    1: await get_translated_phase(1, self.hass),
                    3: await get_translated_phase(3, self.hass)
                }),
            }
        )
        
        return self.async_show_form(
            step_id="configure",
            data_schema=data_schema,
            description_placeholders={
                "default_interval": str(DEFAULT_SCAN_INTERVAL)
            },
        )

    # Helper methods
    async def _find_ble_device_by_uuid(self, target_uuid: str) -> BluetoothServiceInfoBleak | None:
        """Find BLE device MAC address by matching UUID in manufacturer data."""
        from uuid import UUID
        try:
            bluetooth_devices = bluetooth.async_discovered_service_info(self.hass)
            
            for service_info in bluetooth_devices:
                if service_info.manufacturer_data:
                    for company_id, data_bytes in service_info.manufacturer_data.items():
                        if company_id == 0xFFFF:
                            try:
                                # Extract UUID from manufacturer data
                                device_uuid = str(UUID(data_bytes.hex()))
                                if device_uuid == target_uuid:
                                    _LOGGER.debug(
                                        "Found matching BLE device at %s",
                                        service_info.address
                                    )
                                    return service_info
                            except Exception:
                                pass
            
            _LOGGER.debug("No BLE device found with UUID %s", target_uuid)
            return None
            
        except Exception as err:
            _LOGGER.error("Error searching for BLE device: %s", err)
            return None

    async def _ble_connect_test(self, mac_address: str) -> tuple[bool, dict]:
        """Test connection to the BLE device."""
        ble_device = bluetooth.async_ble_device_from_address(
                    self.hass, mac_address, connectable=True
                )
        if not self._aira or not ble_device:
            return False, {"error": "ble_device_not_found"}
        
        try:
            await self._aira.ble._connect_device(ble_device)
            installation = {}

            # get configuration to get the number of phases
            configuration: dict[str, dict] = await self._aira.ble._get_configuration() # type: ignore
            electricity_meter = configuration.get("config", {}).get("electricity_meter", {}).get("type", "ELECTRICITY_METER_TYPE_UNSPECIFIED")
            if electricity_meter == "ELECTRICITY_METER_TYPE_ET340":
                installation[CONF_NUM_PHASES] = 3
            elif electricity_meter == "ELECTRICITY_METER_TYPE_ET112":
                installation[CONF_NUM_PHASES] = 1
            else:
                installation[CONF_NUM_PHASES] = 0 # unknown / not detected do not provide data in ha

            if outdoor_unit_size := configuration.get("config", {}).get("outdoor_unit_size", None):
                if "NONE" not in outdoor_unit_size and "UNSPECIFIED" not in outdoor_unit_size:
                    installation["outdoor_unit_size"] = outdoor_unit_size # store outdoor unit infos if available
            # Cleanup in a task to avoid blocking the flow
            self.hass.async_create_task(self._aira.ble._cleanup())

            return True, installation
        except Exception as err:
            _LOGGER.error("BLE connection test failed: %s", err)
            return False, {"error": "cannot_connect"}

    # Ha auto discovery via bluetooth
    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak) -> ConfigFlowResult:
        """Handle Bluetooth discovery by Home Assistant."""
        _LOGGER.debug("Bluetooth discovery: %s", discovery_info)
        
        # First extract the UUID from manufacturer data
        from uuid import UUID
        device_uuid = None
        if discovery_info.manufacturer_data:
            for company_id, data_bytes in discovery_info.manufacturer_data.items():
                if company_id == 0xFFFF:
                    try:
                        device_uuid = str(UUID(data_bytes.hex()))
                        break
                    except Exception:
                        pass
        
        device_name = discovery_info.name or DEFAULT_NAME

        # Ignore devices without UUID
        if not device_uuid or not device_name.startswith("AH") or not device_uuid.startswith(device_name.split("-")[1]):
            # Silently abort the flow for non-Aira devices (no UUID means surely not an Aira device)
            return self.async_abort(reason="not_aira_device")
        
        # Check if already configured using the UUID
        await self.async_set_unique_id(device_uuid)
        self._abort_if_unique_id_configured()

        self._uuid = device_uuid
        self._mac_address = discovery_info.address
        self._name = discovery_info.name or DEFAULT_NAME

        self.context["title_placeholders"] = {
            "name": self._name,
            "address": self._mac_address,
            "uuid": self._uuid,
        }

        return await self.async_step_user()

class AiraHomeOptionsFlowHandler(OptionsFlowWithReload):
    """Handle options flow for Aira integration."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # Keep existing options and update only what was changed
            options = dict(self.config_entry.options)
            options.update(user_input)
            return self.async_create_entry(
                title=self.config_entry.title,
                data=options
            )

        current_scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        current_num_zones = self.config_entry.options.get(
            CONF_NUM_ZONES, 1
        )

        current_num_phases = self.config_entry.options.get(
            CONF_NUM_PHASES, 0
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=current_scan_interval
                ): vol.All(vol.Coerce(int), vol.Range(min=20, max=300)),
                vol.Required(
                    CONF_NUM_ZONES,
                    default=current_num_zones
                ): vol.In({
                    1: await get_translated_zone(1, self.hass),
                    2: await get_translated_zone(2, self.hass)
                }),
                vol.Required(
                    CONF_NUM_PHASES,
                    default=current_num_phases
                ): vol.In({
                    0: await get_translated_phase(0, self.hass), # unknown
                    1: await get_translated_phase(1, self.hass),
                    3: await get_translated_phase(3, self.hass)
                }),
            }
        ),
            description_placeholders={
                "default_interval": str(DEFAULT_SCAN_INTERVAL)
            },
        )