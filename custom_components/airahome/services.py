"""Service handlers for the AiraHome integration."""
from __future__ import annotations

import logging
from datetime import datetime, time, timedelta, timezone
from functools import partial
from typing import Any
from zoneinfo import ZoneInfo

import voluptuous as vol
from google.protobuf.duration_pb2 import Duration
from google.protobuf.timestamp_pb2 import Timestamp
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_CLOUD_EMAIL,
    CONF_CLOUD_PASSWORD,
    CONF_DEVICE_ID,
    CONF_DEVICE_UUID,
    CONF_DURATION_HOURS,
    CONF_END_DATETIME,
    CONF_ENTRY_ID,
    CONF_INTERVAL_WEEKS,
    CONF_OFFSET,
    CONF_PLAN_NAME,
    CONF_START_DATETIME,
    CONF_STRATEGY,
    CONF_TEMPERATURE,
    CONF_WEEKDAYS,
    DOMAIN,
    SERVICE_ACTIVATE_HOT_WATER_BOOST,
    SERVICE_ADD_HOT_WATER_TIME_PLAN,
    SERVICE_DEACTIVATE_HOT_WATER_BOOST,
    SERVICE_REMOVE_HOT_WATER_TIME_PLAN,
    SERVICE_SET_ROOM_OFFSET,
    STRATEGY_ROOM_TEMP_DELTA,
    STRATEGY_ZONE_SETPOINTS,
)

_LOGGER = logging.getLogger(__name__)
_DEFAULT_DHW_TEMPERATURE = 15.0

_WEEKDAY_ENUM_NAMES = {
    "mon": "WEEKDAY_MONDAY",
    "tue": "WEEKDAY_TUESDAY",
    "wed": "WEEKDAY_WEDNESDAY",
    "thu": "WEEKDAY_THURSDAY",
    "fri": "WEEKDAY_FRIDAY",
    "sat": "WEEKDAY_SATURDAY",
    "sun": "WEEKDAY_SUNDAY",
}


def _validate_weekdays(value: Any) -> list[str]:
    if value in (None, "", []):
        return []

    if isinstance(value, str):
        weekday_values = [item.strip().lower() for item in value.split(",") if item.strip()]
    else:
        weekday_values = [cv.string(item).strip().lower() for item in cv.ensure_list(value)]

    normalized: list[str] = []
    for weekday in weekday_values:
        if weekday not in _WEEKDAY_ENUM_NAMES:
            raise vol.Invalid(
                "Weekdays must be a comma-separated list of mon,tue,wed,thu,fri,sat,sun."
            )
        if weekday not in normalized:
            normalized.append(weekday)

    return normalized


HOT_WATER_BOOST_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ENTRY_ID): cv.string,
        vol.Optional(CONF_DEVICE_UUID): cv.string,
        vol.Optional(CONF_DEVICE_ID): vol.Any(cv.string, [cv.string]),
        vol.Required(CONF_DURATION_HOURS): vol.All(vol.Coerce(float), vol.Range(min=0.05, max=24)),
    }
)

HOT_WATER_BOOST_STOP_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ENTRY_ID): cv.string,
        vol.Optional(CONF_DEVICE_UUID): cv.string,
        vol.Optional(CONF_DEVICE_ID): vol.Any(cv.string, [cv.string]),
    }
)

HOT_WATER_TIME_PLAN_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ENTRY_ID): cv.string,
        vol.Optional(CONF_DEVICE_UUID): cv.string,
        vol.Optional(CONF_DEVICE_ID): vol.Any(cv.string, [cv.string]),
        vol.Required(CONF_START_DATETIME): cv.datetime,
        vol.Required(CONF_END_DATETIME): cv.datetime,
        vol.Required(CONF_TEMPERATURE): vol.All(vol.Coerce(float), vol.Range(min=15, max=65)),
        vol.Optional(CONF_PLAN_NAME, default=""): cv.string,
        vol.Optional(CONF_WEEKDAYS, default=[]): _validate_weekdays,
        vol.Optional(CONF_INTERVAL_WEEKS, default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=52)),
    }
)

ROOM_OFFSET_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ENTRY_ID): cv.string,
        vol.Optional(CONF_DEVICE_UUID): cv.string,
        vol.Optional(CONF_DEVICE_ID): vol.Any(cv.string, [cv.string]),
        vol.Required(CONF_OFFSET): vol.All(vol.Coerce(float), vol.Range(min=-5, max=5)),
        vol.Optional(CONF_STRATEGY, default=STRATEGY_ZONE_SETPOINTS): vol.In(
            [STRATEGY_ZONE_SETPOINTS, STRATEGY_ROOM_TEMP_DELTA]
        ),
        vol.Optional(CONF_DURATION_HOURS, default=0.5): vol.All(
            vol.Coerce(float), vol.Range(min=0.05, max=24)
        ),
    }
)


def _registered(hass: HomeAssistant) -> bool:
    return hass.data.setdefault(DOMAIN, {}).get("_services_registered", False)


def _mark_registered(hass: HomeAssistant, value: bool) -> None:
    hass.data.setdefault(DOMAIN, {})["_services_registered"] = value


def _extract_device_ids(call: ServiceCall) -> list[str]:
    device_ids: list[str] = []

    requested_device_id = call.data.get(CONF_DEVICE_ID)
    if isinstance(requested_device_id, str):
        device_ids.append(requested_device_id)
    elif isinstance(requested_device_id, list):
        device_ids.extend(requested_device_id)

    target = getattr(call, "target", None)
    target_get = getattr(target, "get", None)
    if callable(target_get):
        target_device_id = target_get(CONF_DEVICE_ID)
        if isinstance(target_device_id, str):
            device_ids.append(target_device_id)
        elif isinstance(target_device_id, list):
            device_ids.extend(target_device_id)

    normalized: list[str] = []
    for device_id in device_ids:
        if device_id not in normalized:
            normalized.append(device_id)
    return normalized


def _select_entry_data(hass: HomeAssistant, call: ServiceCall) -> dict[str, Any]:
    domain_data = hass.data.get(DOMAIN, {})
    entries = {
        entry_id: data
        for entry_id, data in domain_data.items()
        if isinstance(data, dict) and "aira" in data
    }

    if not entries:
        raise ServiceValidationError("No configured AiraHome entries are loaded.")

    requested_entry_id = call.data.get(CONF_ENTRY_ID)
    requested_device_uuid = call.data.get(CONF_DEVICE_UUID)
    requested_device_ids = _extract_device_ids(call)

    if requested_entry_id:
        if requested_entry_id not in entries:
            raise ServiceValidationError(f"Unknown entry_id: {requested_entry_id}")
        return entries[requested_entry_id]

    if requested_device_uuid:
        for entry_data in entries.values():
            if entry_data.get("device_uuid") == requested_device_uuid:
                return entry_data
        raise ServiceValidationError(f"Unknown device_uuid: {requested_device_uuid}")

    if requested_device_ids:
        if len(requested_device_ids) != 1:
            raise ServiceValidationError("Select exactly one Home Assistant device.")

        device_registry = dr.async_get(hass)
        device_entry = device_registry.async_get(requested_device_ids[0])
        if device_entry is None:
            raise ServiceValidationError(f"Unknown device_id: {requested_device_ids[0]}")

        primary_config_entry = getattr(device_entry, "primary_config_entry", None)
        if primary_config_entry and primary_config_entry in entries:
            return entries[primary_config_entry]

        for identifier_domain, identifier in device_entry.identifiers:
            if identifier_domain != DOMAIN:
                continue

            for entry_data in entries.values():
                if entry_data.get("device_uuid") == identifier:
                    return entry_data

        raise ServiceValidationError(
            f"Home Assistant device {requested_device_ids[0]} is not linked to a loaded AiraHome entry."
        )

    if len(entries) > 1:
        raise ServiceValidationError(
            "Multiple AiraHome entries are loaded. Provide entry_id, device_uuid, or target a device."
        )

    return next(iter(entries.values()))


async def _ensure_cloud_login(hass: HomeAssistant, entry_data: dict[str, Any]) -> None:
    coordinator = entry_data["coordinator"]
    entry = coordinator.config_entry
    aira = entry_data["aira"]

    email = entry.data.get(CONF_CLOUD_EMAIL)
    password = entry.data.get(CONF_CLOUD_PASSWORD)
    if not email or not password:
        raise ServiceValidationError("Cloud credentials are missing for this entry.")

    await hass.async_add_executor_job(
        partial(aira.cloud.login_with_credentials, username=email, password=password)
    )


async def _ensure_ble_connection(hass: HomeAssistant, entry_data: dict[str, Any]) -> None:
    aira = entry_data["aira"]
    coordinator = entry_data["coordinator"]

    is_connected = await hass.async_add_executor_job(aira.ble.is_connected)
    if is_connected:
        return

    if coordinator.reconnect_callback:
        reconnected = await coordinator.reconnect_callback()
        if reconnected:
            return

    raise HomeAssistantError("BLE device is not connected.")


def _command_progress(update: dict[str, Any]) -> dict[str, Any]:
    return update.get("command_progress", update)


def _extract_error(updates: list[dict[str, Any]]) -> str | None:
    for update in updates:
        progress = _command_progress(update)
        error = progress.get("error")
        if error:
            return error.get("message") or str(error)
    return None


def _ensure_success(updates: list[dict[str, Any]]) -> None:
    error = _extract_error(updates)
    if error:
        raise HomeAssistantError(error)

    if not updates:
        raise HomeAssistantError("The command returned no progress updates.")

    last_progress = _command_progress(updates[-1])
    if "succeeded" not in last_progress:
        raise HomeAssistantError("The command did not report success.")


def _build_room_temp_delta_command(offset: float, duration_hours: float) -> Any:
    from pyairahome.commands import SetRoomTempSetpointDelta
    from pyairahome.device.heat_pump.command.v1.set_room_temp_setpoint_delta_pb2 import (
        RoomTempSetpointDelta,
        SetRoomTempSetpointDelta as _RawSetRoomTempSetpointDelta,
    )

    payload = _RawSetRoomTempSetpointDelta()
    delta = RoomTempSetpointDelta()
    delta.kind = RoomTempSetpointDelta.Kind.KIND_HEATING
    delta.duration.CopyFrom(Duration(seconds=int(duration_hours * 3600)))
    delta.delta_zone_1 = offset
    payload.room_temp_setpoint_deltas.append(delta)
    return SetRoomTempSetpointDelta(payload.room_temp_setpoint_deltas)


def _build_zone_setpoints_command(offset: float) -> Any:
    from pyairahome.commands import SetZoneSetpoints
    from pyairahome.device.heat_pump.command.v1.set_zone_setpoints_pb2 import (
        SetZoneSetpoints as _RawSetZoneSetpoints,
        ZoneTemperatures,
    )

    zone_setpoints = ZoneTemperatures(zone_1=offset)
    return SetZoneSetpoints(
        zone_setpoints=zone_setpoints,
        kind=_RawSetZoneSetpoints.Kind.KIND_HEATING,
    )


def _as_utc(hass: HomeAssistant, value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo(str(hass.config.time_zone)))
    return value.astimezone(timezone.utc)


def _as_local(hass: HomeAssistant, value: datetime) -> datetime:
    tzinfo = ZoneInfo(str(hass.config.time_zone))
    if value.tzinfo is None:
        return value.replace(tzinfo=tzinfo)
    return value.astimezone(tzinfo)


def _timestamp_from_local(value: datetime) -> Timestamp:
    timestamp = Timestamp()
    timestamp.FromDatetime(value.astimezone(timezone.utc))
    return timestamp


def _schedule_dt(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S")


def _weekday_values(weekdays: list[str]) -> list[int]:
    from pyairahome.schedule.v1 import rrule_pb2

    return [getattr(rrule_pb2, _WEEKDAY_ENUM_NAMES[weekday]) for weekday in weekdays]


def _build_weekday_rrule(weekdays: list[str]) -> Any:
    from pyairahome.schedule.v1 import rrule_pb2

    rrule = rrule_pb2.RRule(
        frequency=rrule_pb2.FREQUENCY_DAILY,
        interval=1,
    )
    rrule.by_weekday.extend(
        rrule_pb2.ByWeekday(every=rrule_pb2.Every(weekday=weekday_value))
        for weekday_value in _weekday_values(weekdays)
    )
    return rrule


def _build_dhw_setpoint_event(
    *,
    local_datetime: datetime,
    temperature: float,
    weekdays: list[str] | None = None,
    name: str = "",
) -> Any:
    from pyairahome.schedule.v1.action_pb2 import Action, SetDhwSetpoint
    from pyairahome.schedule.v1.event_pb2 import Event

    event = Event(
        action=Action(set_dhw_setpoint=SetDhwSetpoint(temperature=temperature)),
        event_start=_timestamp_from_local(local_datetime),
        event_start_dt=_schedule_dt(local_datetime),
        name=name,
    )
    if weekdays:
        event.rrule.CopyFrom(_build_weekday_rrule(weekdays))
    return event


def _parse_state_datetime(hass: HomeAssistant, value: Any) -> datetime:
    if isinstance(value, datetime):
        return _as_local(hass, value)

    if isinstance(value, str):
        return _as_local(hass, datetime.fromisoformat(value.replace(" ", "T")))

    raise ServiceValidationError(f"Unsupported scheduler datetime value: {value!r}")


def _event_from_scheduler_dict(hass: HomeAssistant, event_data: dict[str, Any]) -> Any | None:
    from pyairahome.schedule.v1.action_pb2 import Action, SetDhwSetpoint
    from pyairahome.schedule.v1.event_pb2 import Event

    action_data = event_data.get("action", {})
    set_dhw = action_data.get("set_dhw_setpoint")
    if not isinstance(set_dhw, dict) or "temperature" not in set_dhw:
        return None

    start_dt_value = event_data.get("event_start_dt") or event_data.get("event_start")
    if not start_dt_value:
        return None

    start_local = _parse_state_datetime(hass, start_dt_value)

    event = Event(
        action=Action(
            set_dhw_setpoint=SetDhwSetpoint(temperature=float(set_dhw["temperature"]))
        ),
        event_start=_timestamp_from_local(start_local),
        event_start_dt=_schedule_dt(start_local),
        name=str(event_data.get("name", "")),
    )

    end_dt_value = event_data.get("event_end_dt") or event_data.get("event_end")
    if end_dt_value:
        end_local = _parse_state_datetime(hass, end_dt_value)
        event.event_end.CopyFrom(_timestamp_from_local(end_local))
        event.event_end_dt = _schedule_dt(end_local)

    rrule_data = event_data.get("rrule")
    if isinstance(rrule_data, dict):
        from pyairahome.schedule.v1 import rrule_pb2

        frequency_name = str(rrule_data.get("frequency", "FREQUENCY_UNSPECIFIED"))
        interval = int(rrule_data.get("interval", 0))
        rrule = rrule_pb2.RRule(
            frequency=getattr(rrule_pb2, frequency_name, rrule_pb2.FREQUENCY_UNSPECIFIED),
            interval=interval,
        )
        for by_weekday in rrule_data.get("by_weekday", []):
            every = by_weekday.get("every")
            if not isinstance(every, dict):
                continue
            weekday_name = str(every.get("weekday", "WEEKDAY_UNSPECIFIED"))
            rrule.by_weekday.append(
                rrule_pb2.ByWeekday(
                    every=rrule_pb2.Every(
                        weekday=getattr(rrule_pb2, weekday_name, rrule_pb2.WEEKDAY_UNSPECIFIED)
                    )
                )
            )
        event.rrule.CopyFrom(rrule)

    return event


def _current_hot_water_events(
    hass: HomeAssistant, entry_data: dict[str, Any]
) -> list[Any]:
    scheduler = entry_data.get("coordinator").data.get("state", {}).get("scheduler", {})
    events: list[Any] = []
    for schedule in scheduler.get("schedules", []):
        customer_dhw = schedule.get("customer_dhw_temp")
        if not isinstance(customer_dhw, dict):
            continue
        for event_data in customer_dhw.get("events", []):
            event = _event_from_scheduler_dict(hass, event_data)
            if event is not None:
                events.append(event)
    return events


def _event_weekday_codes(event: Any) -> set[str]:
    from pyairahome.schedule.v1 import rrule_pb2

    reverse = {getattr(rrule_pb2, enum_name): code for code, enum_name in _WEEKDAY_ENUM_NAMES.items()}
    weekdays: set[str] = set()
    for by_weekday in event.rrule.by_weekday:
        if by_weekday.HasField("every"):
            code = reverse.get(by_weekday.every.weekday)
            if code:
                weekdays.add(code)
    return weekdays


def _remove_overlapping_recurring_events(events: list[Any], weekdays: list[str]) -> list[Any]:
    requested = set(weekdays)
    kept: list[Any] = []
    for event in events:
        if event.HasField("rrule") and _event_weekday_codes(event) & requested:
            continue
        kept.append(event)
    return kept


def _clear_hot_water_schedule() -> Any:
    from pyairahome.schedule.v1.event_pb2 import Events
    from pyairahome.schedule.v1.schedule_pb2 import Schedule

    schedule = Schedule()
    schedule.customer_dhw_temp.CopyFrom(Events())
    return schedule


def _schedule_with_events(events: list[Any]) -> Any:
    from pyairahome.schedule.v1.schedule_pb2 import Schedule

    schedule = Schedule()
    schedule.customer_dhw_temp.events.extend(events)
    return schedule


def _build_hot_water_time_plan(
    hass: HomeAssistant,
    *,
    start_datetime: datetime,
    end_datetime: datetime,
    temperature: float,
    plan_name: str,
    weekdays: list[str],
    interval_weeks: int,
) -> Any:
    from pyairahome.schedule.v1.action_pb2 import Action, SetDhwSetpoint
    from pyairahome.schedule.v1.event_pb2 import Event
    from pyairahome.schedule.v1.schedule_pb2 import Schedule

    start_local = _as_local(hass, start_datetime)
    end_local = _as_local(hass, end_datetime)
    if end_local <= start_local:
        raise ServiceValidationError("end_datetime must be after start_datetime.")

    if weekdays:
        if interval_weeks != 1:
            raise ServiceValidationError("Recurring hot water time plans only support interval_weeks=1.")
        same_day = start_local.date() == end_local.date()
        all_day_next_midnight = (
            end_local.date() == start_local.date() + timedelta(days=1)
            and end_local.timetz().replace(tzinfo=None) == time(0, 0)
        )
        if not same_day and not all_day_next_midnight:
            raise ServiceValidationError(
                "Recurring hot water time plans must end on the same local day or at 00:00 the next day."
            )

        events = [
            _build_dhw_setpoint_event(
                local_datetime=start_local,
                temperature=temperature,
                weekdays=weekdays,
            )
        ]
        if not all_day_next_midnight:
            events.append(
                _build_dhw_setpoint_event(
                    local_datetime=end_local,
                    temperature=_DEFAULT_DHW_TEMPERATURE,
                    weekdays=weekdays,
                )
            )

        schedule = Schedule()
        schedule.customer_dhw_temp.events.extend(events)
        return schedule

    event = Event(
        action=Action(set_dhw_setpoint=SetDhwSetpoint(temperature=temperature)),
        name=plan_name,
    )
    start_timestamp = Timestamp()
    start_timestamp.FromDatetime(start_local.astimezone(timezone.utc))
    event.event_start.CopyFrom(start_timestamp)

    end_timestamp = Timestamp()
    end_timestamp.FromDatetime(end_local.astimezone(timezone.utc))
    event.event_end.CopyFrom(end_timestamp)

    schedule = Schedule()
    schedule.customer_dhw_temp.events.append(event)
    return schedule


async def _refresh_coordinator(entry_data: dict[str, Any]) -> None:
    coordinator = entry_data["coordinator"]
    await coordinator.async_request_refresh()


def _queue_refresh(hass: HomeAssistant, entry_data: dict[str, Any]) -> None:
    hass.async_create_task(_refresh_coordinator(entry_data))


async def _run_cloud_command(
    hass: HomeAssistant, entry_data: dict[str, Any], command: Any
) -> list[dict[str, Any]]:
    aira = entry_data["aira"]
    device_uuid = entry_data["device_uuid"]
    return await hass.async_add_executor_job(
        lambda: list(aira.cloud.run_command(device_uuid, command, raw=False))
    )


async def _handle_activate_hot_water_boost(hass: HomeAssistant, call: ServiceCall) -> None:
    from pyairahome.commands import ActivateHotWaterBoosting

    entry_data = _select_entry_data(hass, call)
    hours = float(call.data[CONF_DURATION_HOURS])

    await _ensure_cloud_login(hass, entry_data)

    command = ActivateHotWaterBoosting(
        hot_water_boost_duration=Duration(seconds=int(hours * 3600))
    )
    updates = await _run_cloud_command(hass, entry_data, command)
    _ensure_success(updates)
    _queue_refresh(hass, entry_data)


async def _handle_deactivate_hot_water_boost(hass: HomeAssistant, call: ServiceCall) -> None:
    from pyairahome.commands import DeactivateHotWaterBoosting

    entry_data = _select_entry_data(hass, call)

    await _ensure_cloud_login(hass, entry_data)

    updates = await _run_cloud_command(hass, entry_data, DeactivateHotWaterBoosting())
    _ensure_success(updates)
    _queue_refresh(hass, entry_data)


async def _handle_add_hot_water_time_plan(hass: HomeAssistant, call: ServiceCall) -> None:
    from pyairahome.commands import AddSchedule, RemoveSchedule

    entry_data = _select_entry_data(hass, call)

    await _ensure_cloud_login(hass, entry_data)

    schedule = _build_hot_water_time_plan(
        hass,
        start_datetime=call.data[CONF_START_DATETIME],
        end_datetime=call.data[CONF_END_DATETIME],
        temperature=float(call.data[CONF_TEMPERATURE]),
        plan_name=call.data[CONF_PLAN_NAME],
        weekdays=call.data[CONF_WEEKDAYS],
        interval_weeks=int(call.data[CONF_INTERVAL_WEEKS]),
    )
    if call.data[CONF_WEEKDAYS]:
        merged_events = _remove_overlapping_recurring_events(
            _current_hot_water_events(hass, entry_data),
            call.data[CONF_WEEKDAYS],
        )
        merged_events.extend(schedule.customer_dhw_temp.events)

        updates = await _run_cloud_command(
            hass, entry_data, RemoveSchedule(_clear_hot_water_schedule())
        )
        _ensure_success(updates)
        updates = await _run_cloud_command(
            hass, entry_data, AddSchedule(_schedule_with_events(merged_events))
        )
    else:
        updates = await _run_cloud_command(hass, entry_data, AddSchedule(schedule))
    _ensure_success(updates)
    _queue_refresh(hass, entry_data)


async def _handle_remove_hot_water_time_plan(hass: HomeAssistant, call: ServiceCall) -> None:
    from pyairahome.commands import RemoveSchedule

    entry_data = _select_entry_data(hass, call)

    await _ensure_cloud_login(hass, entry_data)

    schedule = _build_hot_water_time_plan(
        hass,
        start_datetime=call.data[CONF_START_DATETIME],
        end_datetime=call.data[CONF_END_DATETIME],
        temperature=float(call.data[CONF_TEMPERATURE]),
        plan_name=call.data[CONF_PLAN_NAME],
        weekdays=call.data[CONF_WEEKDAYS],
        interval_weeks=int(call.data[CONF_INTERVAL_WEEKS]),
    )
    if call.data[CONF_WEEKDAYS]:
        remaining_events = _remove_overlapping_recurring_events(
            _current_hot_water_events(hass, entry_data),
            call.data[CONF_WEEKDAYS],
        )
        updates = await _run_cloud_command(
            hass, entry_data, RemoveSchedule(_clear_hot_water_schedule())
        )
        _ensure_success(updates)
        if remaining_events:
            updates = await _run_cloud_command(
                hass, entry_data, AddSchedule(_schedule_with_events(remaining_events))
            )
    else:
        updates = await _run_cloud_command(hass, entry_data, RemoveSchedule(schedule))
    _ensure_success(updates)
    _queue_refresh(hass, entry_data)


async def _handle_set_room_offset(hass: HomeAssistant, call: ServiceCall) -> None:
    entry_data = _select_entry_data(hass, call)
    aira = entry_data["aira"]
    offset = float(call.data[CONF_OFFSET])
    strategy = call.data[CONF_STRATEGY]
    duration_hours = float(call.data[CONF_DURATION_HOURS])

    await _ensure_ble_connection(hass, entry_data)

    if strategy == STRATEGY_ROOM_TEMP_DELTA:
        from pyairahome.commands import ClearRoomTempSetpointDelta

        command = (
            ClearRoomTempSetpointDelta()
            if offset == 0
            else _build_room_temp_delta_command(offset, duration_hours)
        )
    else:
        command = _build_zone_setpoints_command(offset)

    updates = await hass.async_add_executor_job(
        lambda: list(aira.ble.run_command(command, raw=False))
    )
    _ensure_success(updates)
    _queue_refresh(hass, entry_data)


async def async_register_services(hass: HomeAssistant) -> None:
    """Register integration services once."""
    if _registered(hass):
        return

    hass.services.async_register(
        DOMAIN,
        SERVICE_ACTIVATE_HOT_WATER_BOOST,
        partial(_handle_activate_hot_water_boost, hass),
        schema=HOT_WATER_BOOST_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DEACTIVATE_HOT_WATER_BOOST,
        partial(_handle_deactivate_hot_water_boost, hass),
        schema=HOT_WATER_BOOST_STOP_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_HOT_WATER_TIME_PLAN,
        partial(_handle_add_hot_water_time_plan, hass),
        schema=HOT_WATER_TIME_PLAN_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_HOT_WATER_TIME_PLAN,
        partial(_handle_remove_hot_water_time_plan, hass),
        schema=HOT_WATER_TIME_PLAN_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ROOM_OFFSET,
        partial(_handle_set_room_offset, hass),
        schema=ROOM_OFFSET_SCHEMA,
    )

    _mark_registered(hass, True)
    _LOGGER.debug("AiraHome services registered")


async def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister integration services when no entries remain."""
    if not _registered(hass):
        return

    for service_name in (
        SERVICE_ACTIVATE_HOT_WATER_BOOST,
        SERVICE_DEACTIVATE_HOT_WATER_BOOST,
        SERVICE_ADD_HOT_WATER_TIME_PLAN,
        SERVICE_REMOVE_HOT_WATER_TIME_PLAN,
        SERVICE_SET_ROOM_OFFSET,
    ):
        if hass.services.has_service(DOMAIN, service_name):
            hass.services.async_remove(DOMAIN, service_name)

    _mark_registered(hass, False)
    _LOGGER.debug("AiraHome services unregistered")
