"""Services for the Aira Home integration."""
from __future__ import annotations

import datetime
from functools import partial
import logging

from google.protobuf.duration_pb2 import Duration
from google.protobuf.timestamp_pb2 import Timestamp
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr, entity_registry as er
from pyairahome.commands import ActivateHotWaterBoosting, DeactivateHotWaterBoosting, SetAwayMode
from pyairahome.utils.exceptions import BLEConnectionError
import voluptuous as vol

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)

SERVICE_ACTIVATE_DHW_BOOST = "activate_dhw_boost"
SERVICE_DEACTIVATE_DHW_BOOST = "deactivate_dhw_boost"
SERVICE_SET_AWAY_MODE = "set_away_mode"

DHW_BOOST_VALID_HOURS = [1, 2, 3, 4, 6, 8, 12, 24]
AWAY_MODE_MIN_DAYS = 3

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

SET_AWAY_MODE_SCHEMA = vol.Schema({
    **_TARGET_SCHEMA,
    vol.Required("start_date"): cv.date,
    vol.Required("end_date"): cv.date,
})

SERVICES = [SERVICE_ACTIVATE_DHW_BOOST, SERVICE_DEACTIVATE_DHW_BOOST, SERVICE_SET_AWAY_MODE]


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
                continue
            error = updates[-1].get("error", "no confirmation received from device")
        except (BLEConnectionError, TimeoutError) as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="dhw_boost_activate_failed",
                translation_placeholders={"hours": str(hours), "error": str(e)},
            ) from e

        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="dhw_boost_activate_failed",
            translation_placeholders={"hours": str(hours), "error": str(error)},
        )


def _date_to_timestamp(d: datetime.date) -> Timestamp:
    # Aira uses timestamps with time set to 00.00.00 for dates
    dt = datetime.datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=datetime.timezone.utc)
    ts = Timestamp()
    ts.FromDatetime(dt)
    return ts


async def _handle_set_away_mode(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the set_away_mode service call."""
    start_date: datetime.date = call.data["start_date"]
    end_date: datetime.date = call.data["end_date"]

    if start_date < datetime.date.today():
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="away_mode_start_in_past",
        )

    if (end_date - start_date).days < AWAY_MODE_MIN_DAYS:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="away_mode_dates_too_close",
            translation_placeholders={"min_days": str(AWAY_MODE_MIN_DAYS)},
        )

    for aira in _get_aira_instances_from_target(hass, call):
        _LOGGER.debug("Setting away mode from %s to %s", start_date, end_date)
        command_in = SetAwayMode(
            current_time=_date_to_timestamp(start_date),
            end_time=_date_to_timestamp(end_date),
            target_room_temperature=0.0, # apparently normal app behavior is to set target temp to 0 when activating away mode, the user can't do anything about it officially
        )
        placeholders = {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}
        try:
            updates = [x async for x in await aira.ble._run_command(command_in=command_in)]  # type: ignore
            if "succeeded" in updates[-1]:
                _LOGGER.debug("Away mode set from %s to %s", start_date, end_date)
                continue
            error = updates[-1].get("error", "no confirmation received from device")
        except (BLEConnectionError, TimeoutError) as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="away_mode_set_failed",
                translation_placeholders={**placeholders, "error": str(e)},
            ) from e

        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="away_mode_set_failed",
            translation_placeholders={**placeholders, "error": str(error)},
        )


async def _handle_deactivate_dhw_boost(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the deactivate_dhw_boost service call."""
    for aira in _get_aira_instances_from_target(hass, call):
        _LOGGER.debug("Deactivating DHW boost")
        command_in = DeactivateHotWaterBoosting()
        try:
            updates = [x async for x in await aira.ble._run_command(command_in=command_in)]  # type: ignore
            if "succeeded" in updates[-1]:
                _LOGGER.debug("DHW boost deactivated")
                continue
            error = updates[-1].get("error", "no confirmation received from device")
        except (BLEConnectionError, TimeoutError) as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="dhw_boost_deactivate_failed",
                translation_placeholders={"error": str(e)},
            ) from e

        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="dhw_boost_deactivate_failed",
            translation_placeholders={"error": str(error)},
        )


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
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_AWAY_MODE,
        partial(_handle_set_away_mode, hass),
        schema=SET_AWAY_MODE_SCHEMA,
    )