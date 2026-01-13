import copy
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from logging import Logger
from typing import List

from f3_data_models.models import (
    Day_Of_Week,
    Event,
    Event_Cadence,
    EventInstance,
    EventTag_x_Event,
    EventTag_x_EventInstance,
    EventType,
    EventType_x_Event,
    EventType_x_EventInstance,
    Location,
    Org,
    Org_Type,
)
from f3_data_models.utils import DbManager
from flask import Request, Response
from slack_sdk.web import WebClient
from sqlalchemy import or_

from utilities import constants
from utilities.builders import add_loading_form
from utilities.database.orm import SlackSettings
from utilities.helper_functions import (
    _parse_view_private_metadata,
    current_date_cst,
    get_location_display_name,
    safe_convert,
    safe_get,
    trigger_map_revalidation,
)
from utilities.slack import actions, orm

META_DO_NOT_SEND_AUTO_PREBLASTS = "do_not_send_auto_preblasts"
META_EXCLUDE_FROM_PAX_VAULT = "exclude_from_pax_vault"


def manage_series(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    action = safe_get(body, "actions", 0, "selected_option", "value")

    if action == "add":
        build_series_add_form(body, client, logger, context, region_record, loading_form=True)
    elif action == "edit":
        build_series_list_form(body, client, logger, context, region_record, loading_form=True)


def build_series_add_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
    edit_event: Event | None = None,
    new_preblast: bool = False,
    loading_form: bool = False,
):
    metadata = _parse_view_private_metadata(body)
    if safe_get(metadata, "series_id"):
        edit_event: Event = DbManager.get(
            Event, metadata["series_id"], joinedloads=[Event.event_types, Event.event_tags]
        )
        parent_metadata = metadata
    else:
        parent_metadata = {"series_id": edit_event.id} if edit_event else {}

    if loading_form:
        update_view_id = add_loading_form(body, client, new_or_add="add")
    else:
        update_view_id = None

    if edit_event:
        title_text = "Edit a Series"
    else:
        title_text = "Add a Series"
    form = copy.deepcopy(SERIES_FORM)
    parent_metadata.update({"is_series": "True"})

    aos: List[Org] = DbManager.find_records(
        Org, [Org.parent_id == region_record.org_id, Org.is_active, Org.org_type == Org_Type.ao]
    )
    region_org_record: Org = DbManager.get(
        Org, region_record.org_id, joinedloads=[Org.locations, Org.event_types, Org.event_tags]
    )
    locations = [location for location in region_org_record.locations if location.is_active]
    location_records2 = DbManager.find_join_records2(
        Location,
        Org,
        [Location.org_id == Org.id, Org.parent_id == region_record.org_id],
    )
    locations.extend(record[0] for record in location_records2)

    form.set_options(
        {
            actions.CALENDAR_ADD_SERIES_AO: orm.as_selector_options(
                names=[ao.name for ao in aos],
                values=[str(ao.id) for ao in aos],
            ),
            actions.CALENDAR_ADD_EVENT_AO: orm.as_selector_options(
                names=[ao.name for ao in aos],
                values=[str(ao.id) for ao in aos],
            ),
            actions.CALENDAR_ADD_SERIES_LOCATION: orm.as_selector_options(
                names=[get_location_display_name(location) for location in locations],
                values=[str(location.id) for location in locations],
            ),
            actions.CALENDAR_ADD_SERIES_TYPE: orm.as_selector_options(
                names=[event_type.name for event_type in region_org_record.event_types],
                values=[str(event_type.id) for event_type in region_org_record.event_types],
            ),
            actions.CALENDAR_ADD_SERIES_TAG: orm.as_selector_options(
                names=[tag.name for tag in region_org_record.event_tags],
                values=[str(tag.id) for tag in region_org_record.event_tags],
            ),
        }
    )

    if edit_event:
        form.delete_block(actions.CALENDAR_ADD_SERIES_DOW)
        form.delete_block(actions.CALENDAR_ADD_SERIES_FREQUENCY)
        form.delete_block(actions.CALENDAR_ADD_SERIES_INTERVAL)
        form.delete_block(actions.CALENDAR_ADD_SERIES_INDEX)
        form.delete_block(actions.CALENDAR_ADD_SERIES_START_DATE)
        form.delete_block(actions.CALENDAR_ADD_SERIES_END_DATE)
        initial_values = {
            actions.CALENDAR_ADD_SERIES_NAME: edit_event.name,
            actions.CALENDAR_ADD_SERIES_DESCRIPTION: edit_event.description,
            actions.CALENDAR_ADD_SERIES_AO: str(edit_event.org_id),
            actions.CALENDAR_ADD_EVENT_AO: str(edit_event.org_id),
            actions.CALENDAR_ADD_SERIES_LOCATION: safe_convert(edit_event.location_id, str),
            actions.CALENDAR_ADD_SERIES_TYPE: str(edit_event.event_types[0].id),  # TODO: handle multiple event types
            actions.CALENDAR_ADD_SERIES_START_DATE: safe_convert(
                edit_event.start_date, datetime.strftime, ["%Y-%m-%d"]
            ),
            actions.CALENDAR_ADD_SERIES_END_DATE: safe_convert(edit_event.end_date, datetime.strftime, ["%Y-%m-%d"]),
            actions.CALENDAR_ADD_SERIES_START_TIME: safe_convert(edit_event.start_time, lambda t: t[:2] + ":" + t[2:]),
            actions.CALENDAR_ADD_SERIES_END_TIME: safe_convert(edit_event.end_time, lambda t: t[:2] + ":" + t[2:]),
        }

        options = []
        if safe_get(edit_event, "is_private"):
            options.append("private")
        if safe_get(edit_event, "meta") and safe_get(edit_event.meta, META_EXCLUDE_FROM_PAX_VAULT):
            options.append("exclude_from_pax_vault")
        if safe_get(edit_event, "meta") and safe_get(edit_event.meta, META_DO_NOT_SEND_AUTO_PREBLASTS):
            options.append("no_auto_preblasts")
        if safe_get(edit_event, "highlight"):
            options.append("highlight")
        if options:
            initial_values[actions.CALENDAR_ADD_SERIES_OPTIONS] = options

        if edit_event.event_tags:
            initial_values[actions.CALENDAR_ADD_SERIES_TAG] = [
                str(edit_event.event_tags[0].id)
            ]  # TODO: handle multiple event tags
    else:
        initial_values = {
            actions.CALENDAR_ADD_SERIES_START_DATE: datetime.now().strftime("%Y-%m-%d"),
            actions.CALENDAR_ADD_SERIES_FREQUENCY: Event_Cadence.weekly.name,
            actions.CALENDAR_ADD_SERIES_INTERVAL: "1",
            actions.CALENDAR_ADD_SERIES_INDEX: 1,
        }

    # This is triggered when the AO is selected, defaults are loaded for the location
    # TODO: is there a better way to update the modal without having to rebuild everything?
    action_id = safe_get(body, "actions", 0, "action_id")
    if action_id in (actions.CALENDAR_ADD_SERIES_AO, actions.CALENDAR_ADD_EVENT_AO):
        form_data = SERIES_FORM.get_selected_values(body)
        ao: Org = DbManager.get(Org, safe_convert(safe_get(form_data, action_id), int))
        if ao:
            if ao.default_location_id:
                initial_values[actions.CALENDAR_ADD_SERIES_LOCATION] = str(ao.default_location_id)

        form.set_initial_values(initial_values)
        form.update_modal(
            client=client,
            view_id=safe_get(body, "view", "id"),
            callback_id=actions.ADD_SERIES_CALLBACK_ID,
            title_text=title_text,
            parent_metadata=parent_metadata,
        )
    elif update_view_id:
        form.set_initial_values(initial_values)
        form.update_modal(
            client=client,
            view_id=update_view_id,
            callback_id=actions.ADD_SERIES_CALLBACK_ID,
            title_text=title_text,
            parent_metadata=parent_metadata,
        )
    else:
        form.set_initial_values(initial_values)
        form.post_modal(
            client=client,
            trigger_id=safe_get(body, "trigger_id"),
            title_text=title_text,
            callback_id=actions.ADD_SERIES_CALLBACK_ID,
            new_or_add="add",
            parent_metadata=parent_metadata,
        )


def handle_series_add(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    metadata = _parse_view_private_metadata(body)
    form_data = SERIES_FORM.get_selected_values(body)

    end_date = safe_convert(safe_get(form_data, actions.CALENDAR_ADD_SERIES_END_DATE), datetime.strptime, ["%Y-%m-%d"])

    if safe_get(form_data, actions.CALENDAR_ADD_SERIES_END_TIME):
        end_time: str = safe_get(form_data, actions.CALENDAR_ADD_SERIES_END_TIME).replace(":", "")
    else:
        end_time = (
            datetime.strptime(safe_get(form_data, actions.CALENDAR_ADD_SERIES_START_TIME), "%H:%M") + timedelta(hours=1)
        ).strftime("%H%M")

    # Slack won't return the selection for location and event type after being defaulted, so we need to get the initial value # noqa
    view_blocks = safe_get(body, "view", "blocks")
    location_block = [block for block in view_blocks if block["block_id"] == actions.CALENDAR_ADD_SERIES_LOCATION][0]
    location_initial_value = safe_get(location_block, "element", "initial_option", "value")
    location_id = form_data.get(actions.CALENDAR_ADD_SERIES_LOCATION) or location_initial_value
    event_type_block = [block for block in view_blocks if block["block_id"] == actions.CALENDAR_ADD_SERIES_TYPE][0]
    event_type_initial_value = safe_get(event_type_block, "element", "initial_option", "value")
    event_type_id = form_data.get(actions.CALENDAR_ADD_SERIES_TYPE) or event_type_initial_value

    # Apply int conversion to all values if not null
    location_id = safe_convert(location_id, int)
    event_type_id = safe_convert(event_type_id, int)
    org_id = safe_convert(
        safe_get(form_data, actions.CALENDAR_ADD_SERIES_AO) or safe_get(form_data, actions.CALENDAR_ADD_EVENT_AO), int
    )
    event_tag_id = safe_convert(safe_get(form_data, actions.CALENDAR_ADD_SERIES_TAG, 0), int)
    recurrence_interval = safe_convert(safe_get(form_data, actions.CALENDAR_ADD_SERIES_INTERVAL), int)
    index_within_interval = safe_convert(safe_get(form_data, actions.CALENDAR_ADD_SERIES_INDEX), int)

    selected_options = safe_get(form_data, actions.CALENDAR_ADD_SERIES_OPTIONS) or []
    is_private = "private" in selected_options
    exclude_from_pax_vault = "exclude_from_pax_vault" in selected_options
    do_not_send_auto_preblasts = "no_auto_preblasts" in selected_options
    highlight = "highlight" in selected_options

    if safe_get(form_data, actions.CALENDAR_ADD_SERIES_NAME):
        series_name = safe_get(form_data, actions.CALENDAR_ADD_SERIES_NAME)
    else:
        org: Org = DbManager.get(Org, org_id)
        event_type: EventType = DbManager.get(EventType, event_type_id)
        series_name = f"{org.name} {event_type.name if event_type else ''}"

    day_of_weeks = safe_get(form_data, actions.CALENDAR_ADD_SERIES_DOW)

    if safe_get(metadata, "series_id"):
        existing_series: Event = DbManager.get(
            Event, metadata["series_id"], joinedloads=[Event.event_types, Event.event_tags]
        )
        merged_meta = dict(safe_get(existing_series, "meta") or {})
        if exclude_from_pax_vault:
            merged_meta[META_EXCLUDE_FROM_PAX_VAULT] = True
        else:
            merged_meta.pop(META_EXCLUDE_FROM_PAX_VAULT, None)
        if do_not_send_auto_preblasts:
            merged_meta[META_DO_NOT_SEND_AUTO_PREBLASTS] = True
        else:
            merged_meta.pop(META_DO_NOT_SEND_AUTO_PREBLASTS, None)

        DbManager.update_record(
            Event,
            metadata["series_id"],
            fields={
                Event.name: series_name,
                Event.description: safe_get(form_data, actions.CALENDAR_ADD_SERIES_DESCRIPTION),
                Event.org_id: org_id,
                Event.location_id: location_id,
                Event.start_time: datetime.strptime(
                    safe_get(form_data, actions.CALENDAR_ADD_SERIES_START_TIME), "%H:%M"
                ).strftime("%H%M"),
                Event.end_time: end_time,
                Event.is_private: is_private,
                Event.meta: merged_meta,
                Event.highlight: highlight,
                Event.event_x_event_types: [EventType_x_Event(event_type_id=event_type_id)],
                Event.event_x_event_tags: [EventTag_x_Event(event_tag_id=event_tag_id)] if event_tag_id else [],
            },
        )
        edit_series_record: Event = DbManager.get(
            Event, metadata["series_id"], joinedloads=[Event.event_types, Event.event_tags]
        )
        update_events(edit_series_record)
        body["actions"] = [{"action_id": actions.CALENDAR_MANAGE_SERIES}]
        build_series_list_form(
            body, client, logger, context, region_record, update_view_id=safe_get(body, "view", "previous_view_id")
        )

    else:
        meta = {}
        if exclude_from_pax_vault:
            meta[META_EXCLUDE_FROM_PAX_VAULT] = True
        if do_not_send_auto_preblasts:
            meta[META_DO_NOT_SEND_AUTO_PREBLASTS] = True

        series_records = []
        for dow in day_of_weeks:
            series = Event(
                name=series_name,
                description=safe_get(form_data, actions.CALENDAR_ADD_SERIES_DESCRIPTION),
                org_id=org_id,
                location_id=location_id,
                event_x_event_types=[EventType_x_Event(event_type_id=event_type_id)],
                event_x_event_tags=[EventTag_x_Event(event_tag_id=event_tag_id)] if event_tag_id else [],
                start_date=datetime.strptime(safe_get(form_data, actions.CALENDAR_ADD_SERIES_START_DATE), "%Y-%m-%d"),
                end_date=end_date,
                start_time=datetime.strptime(
                    safe_get(form_data, actions.CALENDAR_ADD_SERIES_START_TIME), "%H:%M"
                ).strftime("%H%M"),
                end_time=end_time,
                recurrence_pattern=safe_get(form_data, actions.CALENDAR_ADD_SERIES_FREQUENCY)
                or edit_series_record.recurrence_pattern,
                recurrence_interval=recurrence_interval or edit_series_record.recurrence_interval,
                index_within_interval=index_within_interval or edit_series_record.index_within_interval,
                day_of_week=dow or edit_series_record.day_of_week,
                is_active=True,
                is_private=is_private,
                meta=meta,
                highlight=highlight,
            )
            series_records.append(series)
        records = DbManager.create_records(series_records)
        if records:
            event_ids = [record.id for record in records]
            records = DbManager.find_records(Event, [Event.id.in_(event_ids)], joinedloads="all")
            create_events(records)
    trigger_map_revalidation()


@dataclass
class MapUpdateData:
    eventId: int | None
    locationId: int | None
    orgId: int | None


@dataclass
class MapUpdate:
    version: str
    timestamp: str
    action: str
    data: MapUpdateData


def update_from_map(request: Request) -> Response:
    """
    This endpoint is used to update the map with new data.
    It is called by the map service when updates are made to the map data.

    Sample payload from Spuds:
    {
        "version": "1.0",
        "timestamp": "2025-05-07T19:45:12Z",
        "action": "map.updated", // OR map.created / map.deleted
        "data": {
            "eventId":   1123,   // may be null / omitted
            "locationId": 987,   // may be null / omitted
            "orgId":     null.   // may be null / omitted
        } // likely in the future I will send the actual data here too (like new address)
    }
    """

    if request.json:
        try:
            response_data = safe_get(request.json, "data") or {}
            map_update_data = MapUpdateData(
                eventId=safe_convert(safe_get(response_data, "eventId"), int),
                locationId=safe_convert(safe_get(response_data, "locationId"), int),
                orgId=safe_convert(safe_get(response_data, "orgId"), int),
            )
            map_update = MapUpdate(
                version=safe_get(request.json, "version"),
                timestamp=safe_get(request.json, "timestamp"),
                action=safe_get(request.json, "action"),
                data=map_update_data,
            )
            if map_update.data.orgId:
                if map_update.action in ["map.deleted"]:
                    DbManager.update_records(
                        Event,
                        filters=[Event.org_id == map_update.data.orgId],
                        fields={Event.is_active: False},
                    )
                    DbManager.update_records(
                        EventInstance,
                        filters=[EventInstance.org_id == map_update.data.orgId],
                        fields={EventInstance.is_active: False},
                    )
            elif map_update.data.eventId:
                if map_update.action in ["map.updated", "map.created"]:
                    series: Event = DbManager.get(Event, map_update.data.eventId, joinedloads="all")
                    # TODO: only recreate instances if certain things have changed (ie not just the description)
                    create_events([series], clear_first=True)
                elif map_update.action == "map.deleted":
                    DbManager.update_records(
                        EventInstance,
                        filters=[EventInstance.series_id == map_update.data.eventId],
                        fields={EventInstance.is_active: False},
                    )
        except Exception as e:
            print(f"Error parsing map update data: {e}")
            return Response("Invalid data", status=400)
    return Response("OK", status=200)


def create_events(
    records: list[Event],
    clear_first: bool = False,
    start_date: date | None = None,
):
    event_records = []
    for series in records:
        start_date = max(series.start_date, (start_date or current_date_cst()))
        current_date = start_date
        end_date = series.end_date or start_date.replace(year=start_date.year + 2)
        max_interval = series.recurrence_interval or 1
        index_within_interval = series.index_within_interval or 1
        recurrence_pattern = series.recurrence_pattern or Event_Cadence.weekly
        current_interval = 1
        current_index = 0
        series_type_id = series.event_types[0].id  # TODO: handle multiple event types
        series_tag_id = series.event_tags[0].id if series.event_tags else None  # TODO: handle multiple event tags
        # for monthly series, figure out which occurence of the day of the week the start date is within the month
        if recurrence_pattern.name == Event_Cadence.monthly.name:
            current_date = current_date.replace(day=1)
            while current_date <= start_date:
                if current_date.strftime("%A").lower() == series.day_of_week.name:
                    current_index += 1
                current_date += timedelta(days=1)

        # event creation algorithm
        while current_date <= end_date:
            if current_date.strftime("%A").lower() == series.day_of_week.name:
                current_index += 1
                if (current_index == index_within_interval) or (recurrence_pattern.name == Event_Cadence.weekly.name):
                    if current_interval == 1:
                        event = EventInstance(
                            name=series.name,
                            description=series.description,
                            org_id=series.org_id,
                            location_id=series.location_id,
                            event_instances_x_event_types=[EventType_x_EventInstance(event_type_id=series_type_id)],
                            event_instances_x_event_tags=[EventTag_x_EventInstance(event_tag_id=series_tag_id)]
                            if series_tag_id
                            else [],
                            start_date=current_date,
                            end_date=current_date,
                            start_time=series.start_time,
                            end_time=series.end_time,
                            is_active=True,
                            series_id=series.id,
                            is_private=series.is_private,
                            meta=series.meta,
                            highlight=series.highlight,
                        )
                        event_records.append(event)
                    current_interval = current_interval + 1 if current_interval < max_interval else 1
            current_date += timedelta(days=1)
            if current_date.day == 1:
                current_index = 0
    if clear_first and event_records:
        series_ids = {record.id for record in records}
        DbManager.delete_records(
            EventInstance,
            filters=[
                EventInstance.series_id.in_(series_ids),
                EventInstance.start_date >= datetime.now(),
            ],
        )
    DbManager.create_records(event_records)


def update_events(
    series: Event,
    start_date: date | None = None,
):
    # Update all future events for a series with the new details
    DbManager.update_records(
        EventInstance,
        filters=[
            EventInstance.series_id == series.id,
            EventInstance.start_date >= (start_date or current_date_cst()),
        ],
        fields={
            EventInstance.series_id: series.id,
            EventInstance.location_id: series.location_id,
            EventInstance.start_time: series.start_time,
            EventInstance.end_time: series.end_time,
            EventInstance.is_private: series.is_private,
            EventInstance.meta: series.meta,
            # EventInstance.name: series.name,
            EventInstance.description: series.description,
            EventInstance.highlight: series.highlight,
        },
    )
    # Update the event types for all future events
    event_instance_ids = [
        record.id
        for record in DbManager.find_records(
            EventInstance,
            [
                EventInstance.series_id == series.id,
                EventInstance.start_date >= (start_date or current_date_cst()),
            ],
        )
    ]
    DbManager.update_records(
        EventType_x_EventInstance,
        filters=[EventType_x_EventInstance.event_instance_id.in_(event_instance_ids)],
        fields={
            EventType_x_EventInstance.event_type_id: series.event_types[0].id,  # TODO: handle multiple event types
        },
    )
    # Update the event tags for all future events
    DbManager.delete_records(
        EventTag_x_EventInstance,
        filters=[EventTag_x_EventInstance.event_instance_id.in_(event_instance_ids)],
    )
    if series.event_tags:
        DbManager.create_records(
            [
                EventTag_x_EventInstance(event_tag_id=series.event_tags[0].id, event_instance_id=event_instance_id)
                for event_instance_id in event_instance_ids
            ]
        )


def build_series_list_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
    update_view_id=None,
    loading_form: bool = False,
):
    if loading_form:
        update_view_id = add_loading_form(body, client, new_or_add="add")

    filter_org = region_record.org_id
    filter_values = {}
    if safe_get(body, "actions", 0, "action_id") in [
        actions.CALENDAR_MANAGE_SERIES_AO,
    ]:
        filter_values = orm.BlockView(blocks=copy.deepcopy(SERIES_LIST_FILTERS)).get_selected_values(body)
        update_view_id = safe_get(body, "view", "id")
        if safe_get(filter_values, actions.CALENDAR_MANAGE_SERIES_AO):
            filter_org = safe_convert(safe_get(filter_values, actions.CALENDAR_MANAGE_SERIES_AO), int)

    title_text = "Delete or Edit a Series"
    confirm_text = "Are you sure you want to edit / delete this series? This cannot be undone. Also, editing or deleting a series will also edit or delete all future events associated with the series."  # noqa
    records = DbManager.find_join_records2(
        Event,
        Org,
        [
            or_((Event.org_id == filter_org), (Org.parent_id == filter_org)),
            Event.is_active,
        ],
    )

    records: list[Event | EventInstance] = [x[0] for x in records][:40]

    # TODO: separate into weekly / non-weekly series?
    ao_orgs = DbManager.find_records(
        Org,
        [Org.parent_id == region_record.org_id, Org.is_active, Org.org_type == Org_Type.ao],
    )
    form = orm.BlockView(blocks=copy.deepcopy(SERIES_LIST_FILTERS))
    form.set_options(
        {
            actions.CALENDAR_MANAGE_SERIES_AO: orm.as_selector_options(
                names=[ao.name for ao in ao_orgs],
                values=[str(ao.id) for ao in ao_orgs],
            ),
        }
    )
    form.set_initial_values(
        {
            actions.CALENDAR_MANAGE_SERIES_AO: safe_get(filter_values, actions.CALENDAR_MANAGE_SERIES_AO),
        }
    )

    for s in records:
        label = f"{s.name} ({s.day_of_week.name.capitalize()} @ {s.start_time})"[  # noqa
            :50
        ]

        form.blocks.append(
            orm.SectionBlock(
                label=label,
                action=f"{actions.SERIES_EDIT_DELETE}_{s.id}",
                element=orm.StaticSelectElement(
                    placeholder="Edit or Delete",
                    options=orm.as_selector_options(names=["Edit", "Delete"]),
                    confirm=orm.ConfirmObject(
                        title="Are you sure?",
                        text=confirm_text,
                        confirm="Yes, I'm sure",
                        deny="Whups, never mind",
                    ),
                ),
            )
        )
    if update_view_id:
        form.update_modal(
            client=client,
            view_id=update_view_id,
            callback_id=actions.EDIT_DELETE_SERIES_CALLBACK_ID,
            title_text=title_text,
            submit_button_text="None",
        )
    # else:
    #     form.post_modal(
    #         client=client,
    #         trigger_id=safe_get(body, "trigger_id"),
    #         title_text=title_text,
    #         callback_id=actions.EDIT_DELETE_SERIES_CALLBACK_ID,
    #         submit_button_text="None",
    #         new_or_add="add",
    #     )


def handle_series_edit_delete(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    series_id = safe_convert(safe_get(body, "actions", 0, "action_id").split("_")[1], int)
    action = safe_get(body, "actions", 0, "selected_option", "value")

    if action == "Edit":
        series: Event = DbManager.get(Event, series_id, joinedloads="all")
        build_series_add_form(body, client, logger, context, region_record, edit_event=series, loading_form=True)
    elif action == "Delete":
        DbManager.update_record(Event, series_id, fields={"is_active": False})
        DbManager.update_records(
            EventInstance,
            [EventInstance.series_id == series_id, EventInstance.start_date >= current_date_cst()],
            fields={"is_active": False},
        )
        trigger_map_revalidation()
        # set private_metadata to indicate this is a series
        body["view"]["private_metadata"] = json.dumps({"is_series": "True"})
        build_series_list_form(
            body, client, logger, context, region_record, update_view_id=safe_get(body, "view", "id")
        )


SERIES_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="AO",
            action=actions.CALENDAR_ADD_SERIES_AO,
            element=orm.StaticSelectElement(placeholder="Select an AO"),
            dispatch_action=True,
        ),
        orm.InputBlock(
            label="Default Location",
            action=actions.CALENDAR_ADD_SERIES_LOCATION,
            element=orm.StaticSelectElement(placeholder="Select the default location"),
            optional=True,
        ),
        orm.InputBlock(
            label="Default Event Type",
            action=actions.CALENDAR_ADD_SERIES_TYPE,
            element=orm.StaticSelectElement(placeholder="Select the event type"),
            optional=False,
        ),
        orm.InputBlock(
            label="Default Event Tag",
            action=actions.CALENDAR_ADD_SERIES_TAG,
            element=orm.MultiStaticSelectElement(placeholder="Select the event tag", max_selected_items=1),
            optional=True,
        ),
        orm.InputBlock(
            label="Start Date",
            action=actions.CALENDAR_ADD_SERIES_START_DATE,
            element=orm.DatepickerElement(placeholder="Enter the start date"),
            optional=False,
        ),
        orm.InputBlock(
            label="End Date",
            action=actions.CALENDAR_ADD_SERIES_END_DATE,
            element=orm.DatepickerElement(placeholder="Enter the end date"),
            hint="If no end date is provided, the series will continue indefinitely.",
        ),
        orm.InputBlock(
            label="Start Time",
            action=actions.CALENDAR_ADD_SERIES_START_TIME,
            element=orm.TimepickerElement(placeholder="Enter the start time"),
            optional=False,
        ),
        orm.InputBlock(
            label="End Time",
            action=actions.CALENDAR_ADD_SERIES_END_TIME,
            element=orm.TimepickerElement(placeholder="Enter the end time"),
            hint="If no end time is provided, the event will be defaulted to be one hour long.",
        ),
        orm.InputBlock(
            label="Day(s) of the Week",
            action=actions.CALENDAR_ADD_SERIES_DOW,
            element=orm.CheckboxInputElement(
                options=orm.as_selector_options(
                    names=[d.name.capitalize() for d in Day_Of_Week],
                    values=[d.name for d in Day_Of_Week],
                ),
            ),
            optional=False,
        ),
        orm.InputBlock(
            "Interval",
            action=actions.CALENDAR_ADD_SERIES_INTERVAL,
            element=orm.StaticSelectElement(
                placeholder="Select the interval",
                options=orm.as_selector_options(**constants.INTERVAL_OPTIONS),
                initial_value="1",
            ),
            optional=False,
        ),
        orm.InputBlock(
            label="Series Frequency",
            action=actions.CALENDAR_ADD_SERIES_FREQUENCY,
            element=orm.StaticSelectElement(
                placeholder="Select the frequency",
                options=orm.as_selector_options(names=["Week", "Month"], values=[p.name for p in Event_Cadence]),
                initial_value=Event_Cadence.weekly.name,
            ),
            optional=False,
        ),
        # orm.InputBlock(
        #     label="Interval",
        #     action=actions.CALENDAR_ADD_SERIES_INTERVAL,
        #     element=orm.NumberInputElement(
        #         placeholder="Enter the interval",
        #         is_decimal_allowed=False,
        #     ),
        #     optional=True,
        #     hint="For example, Interval=2 and Frequency=Weekly would mean every other week. If left blank, the interval will assumed to be 1.",  # noqa
        # ),
        orm.InputBlock(
            label="Which week of the month?",
            action=actions.CALENDAR_ADD_SERIES_INDEX,
            element=orm.NumberInputElement(
                placeholder="Enter the index",
                is_decimal_allowed=False,
                initial_value="1",
            ),
            optional=False,
            hint="Only relevant if Month is selected above.",  # noqa
        ),
        orm.InputBlock(
            label="Series Name",
            action=actions.CALENDAR_ADD_SERIES_NAME,
            element=orm.PlainTextInputElement(placeholder="Enter the series name"),
            hint="If left blank, will default to the AO name + event type.",
        ),
        orm.InputBlock(
            label="Description",
            action=actions.CALENDAR_ADD_SERIES_DESCRIPTION,
            element=orm.PlainTextInputElement(
                placeholder="Enter a description",
                multiline=True,
            ),
            optional=True,
        ),
        orm.InputBlock(
            label="Options",
            action=actions.CALENDAR_ADD_SERIES_OPTIONS,
            element=orm.CheckboxInputElement(
                options=orm.as_selector_options(
                    names=[
                        "Make event private",
                        "Exclude stats from PAX Vault",
                        "Do not send auto-preblasts",
                        "Highlight on Special Events List",
                    ],
                    values=[
                        "private",
                        "exclude_from_pax_vault",
                        "no_auto_preblasts",
                        "highlight",
                    ],
                    descriptions=[
                        "Hides series from Maps and Region Pages.",
                        "Can still be queried from BigQuery or custom dashboards.",
                        "Opts this series out of automated preblasts.",
                        "Shown in the calendar image channel if enabled.",
                    ],
                ),
            ),
            hint="If you want to exclude this series from stats, use the 'Off-The-Books' event tag.",
            optional=True,
        ),
    ]
)

SERIES_LIST_FILTERS = [
    orm.InputBlock(
        label="AO Filter",
        action=actions.CALENDAR_MANAGE_SERIES_AO,
        element=orm.StaticSelectElement(
            placeholder="Select an AO",
        ),
        optional=True,
        dispatch_action=True,
    ),
]
