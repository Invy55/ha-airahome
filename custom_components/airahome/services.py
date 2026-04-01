"""Services for the Aira Home integration."""
from __future__ import annotations

import logging
from functools import partial

import voluptuous as vol
from google.protobuf.duration_pb2 import Duration
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr, entity_registry as er
from pyairahome.commands import ActivateHotWaterBoosting, DeactivateHotWaterBoosting

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_ACTIVATE_DHW_BOOST = "activate_dhw_boost"
SERVICE_DEACTIVATE_DHW_BOOST = "deactivate_dhw_boost"

DHW_BOOST_VALID_HOURS = [1, 2, 3, 4, 6, 8, 12, 24]

_TARGET_SCHEMA = {
    vol.Optional("entity_id"): vol.Any(cv.string, [cv.string]),
    vol.Optional("device_id"): vol.Any(cv.string, [cv.string]),
    vol.Optional("area_id"): vol.Any(cv.string, [cv.string]),
}

ACTIVATE_DHW_BOOST_SCHEMA = vol.Schema(
    {
        **_TARGET_SCHEMA,
        vol.Required("hours"): vol.All(vol.Coerce(int), vol.In(DHW_BOOST_VALID_HOURS)),
    }
)

DEACTIVATE_DHW_BOOST_SCHEMA = vol.Schema(_TARGET_SCHEMA)

SERVICES = [SERVICE_ACTIVATE_DHW_BOOST, SERVICE_DEACTIVATE_DHW_BOOST]


def _get_aira_instances_from_target(hass: HomeAssistant, call: ServiceCall) -> list:
    """Resolve service call target (entity_id and/or device_id) to the AiraHome instances associated with those entities/devices. Remove duplicates if multiple entities/devices belong to the same config entry."""
    
    domain_data: dict = hass.data.get(DOMAIN, {})
    seen_entry_ids: set[str] = set()
    aira_instances = []

    entity_ids = call.data.get("entity_id", [])
    if isinstance(entity_ids, str):
        entity_ids = [entity_ids]
    for entity_id in entity_ids:
        entity = er.async_get(hass).async_get(entity_id)
        if not entity or not entity.config_entry_id:
            _LOGGER.error("Entity %s not found or has no config entry", entity_id)
            continue
        entry_id = entity.config_entry_id
        if entry_id in seen_entry_ids or entry_id not in domain_data:
            continue
        seen_entry_ids.add(entry_id)
        aira_instances.append(domain_data[entry_id]["aira"])

    device_ids = call.data.get("device_id", [])
    if isinstance(device_ids, str):
        device_ids = [device_ids]
    for device_id in device_ids:
        device = dr.async_get(hass).async_get(device_id)
        if not device:
            _LOGGER.error("Device %s not found", device_id)
            continue
        entry_id = next(
            (eid for eid in device.config_entries if eid in domain_data), None
        )
        if not entry_id or entry_id in seen_entry_ids:
            continue
        seen_entry_ids.add(entry_id)
        aira_instances.append(domain_data[entry_id]["aira"])

    return aira_instances


async def _handle_activate_dhw_boost(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the activate_dhw_boost service call."""
    hours: int = call.data["hours"]

    for aira in _get_aira_instances_from_target(hass, call):
        _LOGGER.debug("Activating DHW boost for %d hour(s)", hours)
        command_in = ActivateHotWaterBoosting(
            hot_water_boost_duration=Duration(seconds=hours * 3600)
        )
        try:
            updates = [x async for x in await aira.ble._run_command(command_in=command_in)]  # type: ignore
            if "succeeded" in updates[-1]:
                _LOGGER.debug("DHW boost activated for %d hour(s)", hours)
            elif "error" in updates[-1]:
                raise HomeAssistantError(f"Failed to activate DHW boost: {updates[-1]['error']}")
        except RuntimeError as e:
            raise HomeAssistantError(f"Error activating DHW boost: {e}") from e


async def _handle_deactivate_dhw_boost(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the deactivate_dhw_boost service call."""
    for aira in _get_aira_instances_from_target(hass, call):
        _LOGGER.debug("Deactivating DHW boost")
        command_in = DeactivateHotWaterBoosting()
        try:
            updates = [x async for x in await aira.ble._run_command(command_in=command_in)]  # type: ignore
            if "succeeded" in updates[-1]:
                _LOGGER.debug("DHW boost deactivated")
            elif "error" in updates[-1]:
                raise HomeAssistantError(f"Failed to deactivate DHW boost: {updates[-1]['error']}")
        except RuntimeError as e:
            raise HomeAssistantError(f"Error deactivating DHW boost: {e}") from e


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register airahome services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_ACTIVATE_DHW_BOOST,
        partial(_handle_activate_dhw_boost, hass),
        schema=ACTIVATE_DHW_BOOST_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DEACTIVATE_DHW_BOOST,
        partial(_handle_deactivate_dhw_boost, hass),
        schema=DEACTIVATE_DHW_BOOST_SCHEMA,
    )


def async_unload_services(hass: HomeAssistant) -> None:
    """Remove airahome services."""
    for service in SERVICES:
        hass.services.async_remove(DOMAIN, service)