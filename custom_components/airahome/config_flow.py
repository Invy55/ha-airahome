"""Config flow for Aira Heat Pump integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from functools import partial

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_CLOUD_EMAIL,
    CONF_CLOUD_PASSWORD,
    CONF_DEVICE_NAME,
    CONF_DEVICE_UUID,
    CONF_MAC_ADDRESS,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_NAME,
    DOMAIN
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAC_ADDRESS): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aira Heat Pump."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, str] = {}
        self._cloud_email: str | None = None
        self._cloud_password: str | None = None
        self._cloud_devices: list[dict] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step. Obtain cloud credentials and use them to fetch available devices."""
        errors: dict[str, str] = {}
        
        data_schema = vol.Schema(
            {
                vol.Required("email"): str,
                vol.Required("password"): str,
            }
        )

        if user_input is not None:
            # Store credentials temporarily and move to device selection
            self._cloud_email = user_input["email"]
            self._cloud_password = user_input["password"]
            
            # Try to authenticate and get devices
            try:
                # Ensure credentials are not None
                if not self._cloud_email or not self._cloud_password:
                    errors["base"] = "invalid_auth"
                    return self.async_show_form(
                        step_id="user",
                        data_schema=data_schema,
                        errors=errors,
                    )
                
                def import_and_init(hass):
                    """Import AiraHome and initialize instance."""
                    from pyairahome import AiraHome
                    return AiraHome(ext_loop=hass.loop)
                
                _LOGGER.debug("Initializing AiraHome instance")
                aira = await self.hass.async_add_executor_job(import_and_init, self.hass)

                await self.hass.async_add_executor_job(
                    aira.cloud.login_with_credentials,
                    self._cloud_email,
                    self._cloud_password
                )
                
                # Get devices from cloud
                devices = await self.hass.async_add_executor_job(
                    partial(aira.cloud.get_devices, raw=False)
                ) # type: dict
                
                if devices and "devices" in devices.keys() and devices["devices"]:
                    self._cloud_devices = devices["devices"]
                    _LOGGER.info("Found %d device(s) in the cloud account", len(self._cloud_devices))
                    return await self.async_step_select_device()
                else:
                    errors["base"] = "no_devices_found"
                    
            except Exception as exc:
                _LOGGER.error("Cloud authentication failed: %s", exc)
                errors["base"] = "invalid_auth"
        
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_select_device(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Second step - let the user select the heat pump to configure."""
        if user_input is not None:
            selected_uuid = user_input["device"]
            
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
            
            # Move to configuration step
            return await self.async_step_configure(
                selected_uuid=selected_uuid,
                selected_device=selected_device
            )
        
        # Build device selection list
        device_options = {}
        for device in self._cloud_devices:
            device_uuid = device.get("id", {}).get("value")
            online_status = device.get("online", {}).get("online", False)
            status_str = "🟢" if online_status else "🔴"
            display_name = f"{status_str} {device_uuid}"
            device_options[device_uuid] = display_name
        
        data_schema = vol.Schema(
            {
                vol.Required("device"): vol.In(device_options),
            }
        )
        
        return self.async_show_form(
            step_id="select_device",
            data_schema=data_schema,
            description_placeholders={
                "device_count": str(len(self._cloud_devices))
            },
        )
    
    async def async_step_configure(self, user_input: dict[str, Any] | None = None,
        selected_uuid: str | None = None,
        selected_device: dict | None = None
    ) -> FlowResult:
        """Third Step - configure polling interval and finalize setup."""
        if user_input is not None:
            # Get the UUID from stored context if not passed
            if not selected_uuid:
                selected_uuid = self.context.get("selected_uuid")
            
            scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            
            # Now discover BLE device with this UUID
            _LOGGER.info("Looking for BLE device with UUID: %s", selected_uuid)
            
            # Scan for BLE devices with matching UUID
            service_info = await self._find_ble_device_by_uuid(selected_uuid)
            mac_address = service_info.address if service_info else None
            name = service_info.name if service_info else DEFAULT_NAME or DEFAULT_NAME
            
            if not mac_address:
                _LOGGER.error("BLE device not found for UUID: %s", selected_uuid)
                return self.async_abort(reason="ble_device_not_found")
            
            # Maybe we should try to connect to the heatpump here to validate?

            # Create entry with all necessary data
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data={
                    CONF_MAC_ADDRESS: mac_address,
                    CONF_DEVICE_UUID: selected_uuid,
                    CONF_CLOUD_EMAIL: self._cloud_email,
                    CONF_CLOUD_PASSWORD: self._cloud_password,
                    CONF_DEVICE_NAME: name
                },
                options={
                    CONF_SCAN_INTERVAL: scan_interval,
                },
            )
        
        # Store UUID for later if provided
        if selected_uuid:
            self.context["selected_uuid"] = selected_uuid
        
        # Show configuration form
        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL, 
                    default=DEFAULT_SCAN_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=20, max=300)),
            }
        )
        
        return self.async_show_form(
            step_id="configure",
            data_schema=data_schema,
            description_placeholders={
                "default_interval": str(DEFAULT_SCAN_INTERVAL)
            },
        )
    
    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

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

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak) -> FlowResult:
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
        
        # Ignore devices without UUID
        if not device_uuid:
            # Silently abort the flow for non-Aira devices (no UUID means surely not an Aira device)
            return self.async_abort(reason="not_aira_device")
        
        # Check if already configured using the UUID
        await self.async_set_unique_id(device_uuid)
        self._abort_if_unique_id_configured()
        
        # Store discovery info for confirmation
        self.context["title_placeholders"] = {
            "name": discovery_info.name or DEFAULT_NAME,
            "address": discovery_info.address,
            "uuid": device_uuid,
        }
        
        return await self.async_step_bluetooth_confirm()
    
    async def async_step_bluetooth_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Confirm Bluetooth discovery."""
        if user_input is not None:
            device_uuid = self.unique_id  # previously set unique ID
            mac_address = self.context["title_placeholders"]["address"]
            name = self.context["title_placeholders"]["name"]
            
            # Maybe we should try to connect to the heatpump here to validate?

            return self.async_create_entry(
                title=DEFAULT_NAME,
                data={
                    CONF_MAC_ADDRESS: mac_address,
                    CONF_DEVICE_UUID: device_uuid,
                    CONF_DEVICE_NAME: name
                },
            )
        
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=self.context["title_placeholders"],
        )

class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Aira integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
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

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=current_scan_interval,
                    ): vol.All(vol.Coerce(int), vol.Range(min=20, max=300)),
                }
            ),
            description_placeholders={
                "default_interval": str(DEFAULT_SCAN_INTERVAL)
            },
        )

def _is_valid_mac(mac: str) -> bool:
    """Validate MAC address format."""
    import re
    # Match MAC address with various separators (: - .) or no separators
    return bool(re.match(r'^([0-9A-Fa-f]{2}[:-.]?){5}[0-9A-Fa-f]{2}$', mac))