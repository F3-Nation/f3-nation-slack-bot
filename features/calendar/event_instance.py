import copy
import json
from datetime import datetime, timedelta
from logging import Logger
from typing import List

from f3_data_models.models import (
    Attendance,
    Attendance_x_AttendanceType,
    EventInstance,
    EventTag_x_EventInstance,
    EventType,
    EventType_x_EventInstance,
    Location,
    Org,
    Org_Type,
)
from f3_data_models.utils import DbManager
from slack_sdk.web import WebClient
from sqlalchemy import or_

from features.calendar import event_preblast
from utilities.database.orm import SlackSettings
from utilities.helper_functions import (
    current_date_cst,
    get_user,
    parse_rich_block,
    replace_user_channel_ids,
    safe_convert,
    safe_get,
)
from utilities.slack import actions, orm

# Constants for action IDs
CALENDAR_ADD_EVENT_INSTANCE_PREBLAST = "calendar_add_event_instance_preblast"
CALENDAR_ADD_EVENT_INSTANCE_AO = "calendar_add_event_instance_ao"
CALENDAR_ADD_EVENT_INSTANCE_LOCATION = "calendar_add_event_instance_location"
CALENDAR_ADD_EVENT_INSTANCE_TYPE = "calendar_add_event_instance_type"
CALENDAR_ADD_EVENT_INSTANCE_TAG = "calendar_add_event_instance_tag"
CALENDAR_ADD_EVENT_INSTANCE_START_DATE = "calendar_add_event_instance_start_date"
CALENDAR_ADD_EVENT_INSTANCE_END_DATE = "calendar_add_event_instance_end_date"
CALENDAR_ADD_EVENT_INSTANCE_START_TIME = "calendar_add_event_instance_start_time"
CALENDAR_ADD_EVENT_INSTANCE_END_TIME = "calendar_add_event_instance_end_time"
CALENDAR_ADD_EVENT_INSTANCE_NAME = "calendar_add_event_instance_name"
CALENDAR_ADD_EVENT_INSTANCE_HIGHLIGHT = "calendar_add_event_instance_highlight"
CALENDAR_ADD_EVENT_INSTANCE_DOW = "calendar_add_event_instance_dow"
CALENDAR_ADD_EVENT_AO = "calendar_add_event_ao"
CALENDAR_ADD_EVENT_INSTANCE_FREQUENCY = "calendar_add_event_instance_frequency"
CALENDAR_ADD_EVENT_INSTANCE_DESCRIPTION = "calendar_add_event_instance_description"
ADD_EVENT_INSTANCE_CALLBACK_ID = "add_event_instance_callback_id"
CALENDAR_MANAGE_EVENT_INSTANCE = "calendar_manage_event_instance"
EDIT_DELETE_EVENT_INSTANCE_CALLBACK_ID = "edit_delete_event_instance_callback_id"
CALENDAR_MANAGE_EVENT_INSTANCE_AO = "calendar_manage_event_instance_ao"
CALENDAR_MANAGE_EVENT_INSTANCE_DATE = "calendar_manage_event_instance_date"


def manage_event_instances(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    action = safe_get(body, "actions", 0, "selected_option", "value")

    if action == "add":
        build_event_instance_add_form(body, client, logger, context, region_record)
    elif action == "edit":
        build_event_instance_list_form(body, client, logger, context, region_record)


def build_event_instance_add_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
    edit_event_instance: EventInstance | None = None,
    new_preblast: bool = False,
):
    parent_metadata = {"event_instance_id": edit_event_instance.id} if edit_event_instance else {}
    view_metadata = safe_convert(safe_get(body, "view", "private_metadata"), json.loads)

    title_text = "Add an Event"
    form = copy.deepcopy(INSTANCE_FORM)
    if new_preblast or (safe_get(view_metadata, "is_preblast") == "True"):
        # Add a moleskin block if this is a new event
        form.blocks.insert(
            -1,
            orm.InputBlock(
                label="Preblast",
                action=CALENDAR_ADD_EVENT_INSTANCE_PREBLAST,
                element=orm.RichTextInputElement(placeholder="Give us an event preview!"),
                optional=False,
            ),
        )
        parent_metadata.update({"is_preblast": "True"})

    aos: List[Org] = DbManager.find_records(
        Org, [Org.parent_id == region_record.org_id, Org.is_active, Org.org_type == Org_Type.ao]
    )
    region_org_record: Org = DbManager.get(Org, region_record.org_id, joinedloads="all")
    locations = [location for location in region_org_record.locations if location.is_active]
    location_records2 = DbManager.find_join_records2(
        Location,
        Org,
        [Location.org_id == Org.id, Org.parent_id == region_record.org_id],
    )
    locations.extend(record[0] for record in location_records2)

    form.set_options(
        {
            CALENDAR_ADD_EVENT_INSTANCE_AO: orm.as_selector_options(
                names=[ao.name for ao in aos],
                values=[str(ao.id) for ao in aos],
            ),
            CALENDAR_ADD_EVENT_INSTANCE_LOCATION: orm.as_selector_options(
                names=[location.name for location in locations],
                values=[str(location.id) for location in locations],
            ),
            CALENDAR_ADD_EVENT_INSTANCE_TYPE: orm.as_selector_options(
                names=[event_type.name for event_type in region_org_record.event_types],
                values=[str(event_type.id) for event_type in region_org_record.event_types],
            ),
            CALENDAR_ADD_EVENT_INSTANCE_TAG: orm.as_selector_options(
                names=[tag.name for tag in region_org_record.event_tags],
                values=[str(tag.id) for tag in region_org_record.event_tags],
            ),
        }
    )

    initial_values = {}
    if edit_event_instance:
        initial_values = {
            CALENDAR_ADD_EVENT_INSTANCE_NAME: edit_event_instance.name,
            CALENDAR_ADD_EVENT_INSTANCE_DESCRIPTION: edit_event_instance.description,
            CALENDAR_ADD_EVENT_INSTANCE_AO: str(edit_event_instance.org_id),
            CALENDAR_ADD_EVENT_INSTANCE_LOCATION: safe_convert(edit_event_instance.location_id, str),
            CALENDAR_ADD_EVENT_INSTANCE_TYPE: str(
                edit_event_instance.event_types[0].id
            ),  # TODO: handle multiple event types
            CALENDAR_ADD_EVENT_INSTANCE_START_DATE: safe_convert(
                edit_event_instance.start_date, datetime.strftime, ["%Y-%m-%d"]
            ),
            CALENDAR_ADD_EVENT_INSTANCE_END_DATE: safe_convert(
                edit_event_instance.end_date, datetime.strftime, ["%Y-%m-%d"]
            ),
            CALENDAR_ADD_EVENT_INSTANCE_START_TIME: safe_convert(
                edit_event_instance.start_time, lambda t: t[:2] + ":" + t[2:]
            ),
            CALENDAR_ADD_EVENT_INSTANCE_END_TIME: safe_convert(
                edit_event_instance.end_time, lambda t: t[:2] + ":" + t[2:]
            ),
        }
        if edit_event_instance.event_tags:
            initial_values[CALENDAR_ADD_EVENT_INSTANCE_TAG] = [
                str(edit_event_instance.event_tags[0].id)
            ]  # TODO: handle multiple event tags

    # This is triggered when the AO is selected, defaults are loaded for the location
    # TODO: is there a better way to update the modal without having to rebuild everything?
    action_id = safe_get(body, "actions", 0, "action_id")
    if action_id == CALENDAR_ADD_EVENT_INSTANCE_AO:
        form_data = INSTANCE_FORM.get_selected_values(body)
        ao: Org = DbManager.get(Org, safe_convert(safe_get(form_data, action_id), int))
        if ao:
            if ao.default_location_id:
                initial_values[CALENDAR_ADD_EVENT_INSTANCE_LOCATION] = str(ao.default_location_id)

        form.set_initial_values(initial_values)
        form.update_modal(
            client=client,
            view_id=safe_get(body, "view", "id"),
            callback_id=ADD_EVENT_INSTANCE_CALLBACK_ID,
            title_text=title_text,
            parent_metadata=parent_metadata,
        )
    else:
        form.set_initial_values(initial_values)
        form.post_modal(
            client=client,
            trigger_id=safe_get(body, "trigger_id"),
            title_text=title_text,
            callback_id=ADD_EVENT_INSTANCE_CALLBACK_ID,
            new_or_add="add",
            parent_metadata=parent_metadata,
        )


def handle_event_instance_add(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    metadata = safe_convert(safe_get(body, "view", "private_metadata"), json.loads)
    form = copy.deepcopy(INSTANCE_FORM)
    if safe_get(metadata, "is_preblast") == "True":
        form.blocks.insert(
            -1,
            orm.InputBlock(
                label="Preblast",
                action=CALENDAR_ADD_EVENT_INSTANCE_PREBLAST,
                element=orm.RichTextInputElement(placeholder="Give us an event preview!"),
                optional=False,
            ),
        )
    form_data = form.get_selected_values(body)

    if safe_get(form_data, CALENDAR_ADD_EVENT_INSTANCE_END_TIME):
        end_time: str = safe_get(form_data, CALENDAR_ADD_EVENT_INSTANCE_END_TIME).replace(":", "")
    else:
        end_time = (
            datetime.strptime(safe_get(form_data, CALENDAR_ADD_EVENT_INSTANCE_START_TIME), "%H:%M") + timedelta(hours=1)
        ).strftime("%H%M")

    # Slack won't return the selection for location and event type after being defaulted, so we need to get the initial value # noqa
    view_blocks = safe_get(body, "view", "blocks")
    location_block = [block for block in view_blocks if block["block_id"] == CALENDAR_ADD_EVENT_INSTANCE_LOCATION][0]
    location_initial_value = safe_get(location_block, "element", "initial_option", "value")
    location_id = form_data.get(CALENDAR_ADD_EVENT_INSTANCE_LOCATION) or location_initial_value
    event_type_block = [block for block in view_blocks if block["block_id"] == CALENDAR_ADD_EVENT_INSTANCE_TYPE][0]
    event_type_initial_value = safe_get(event_type_block, "element", "initial_option", "value")
    event_type_id = form_data.get(CALENDAR_ADD_EVENT_INSTANCE_TYPE) or event_type_initial_value

    # Apply int conversion to all values if not null
    location_id = safe_convert(location_id, int)
    event_type_id = safe_convert(event_type_id, int)
    org_id = (
        safe_convert(
            safe_get(form_data, CALENDAR_ADD_EVENT_INSTANCE_AO) or safe_get(form_data, CALENDAR_ADD_EVENT_AO),
            int,
        )
        or region_record.org_id
    )
    event_tag_id = safe_convert(safe_get(form_data, CALENDAR_ADD_EVENT_INSTANCE_TAG, 0), int)

    if safe_get(form_data, CALENDAR_ADD_EVENT_INSTANCE_NAME):
        event_instance_name = safe_get(form_data, CALENDAR_ADD_EVENT_INSTANCE_NAME)
    else:
        org: Org = DbManager.get(Org, org_id)
        event_type: EventType = DbManager.get(EventType, event_type_id)
        event_instance_name = f"{org.name} {event_type.name if event_type else ''}"

    # if safe_get(metadata, "event_instance_id"):
    #     edit_event_instance_record: Event = DbManager.get(Event, metadata["event_instance_id"])
    event_instance_record = EventInstance(
        name=event_instance_name,
        description=safe_get(form_data, CALENDAR_ADD_EVENT_INSTANCE_DESCRIPTION),
        org_id=org_id,
        location_id=location_id,
        event_instances_x_event_types=[EventType_x_EventInstance(event_type_id=event_type_id)],
        event_instances_x_event_tags=[EventTag_x_EventInstance(event_tag_id=event_tag_id)] if event_tag_id else [],
        start_date=datetime.strptime(safe_get(form_data, CALENDAR_ADD_EVENT_INSTANCE_START_DATE), "%Y-%m-%d"),
        start_time=datetime.strptime(safe_get(form_data, CALENDAR_ADD_EVENT_INSTANCE_START_TIME), "%H:%M").strftime(
            "%H%M"
        ),
        end_time=end_time,
        is_active=True,
        highlight=safe_get(form_data, CALENDAR_ADD_EVENT_INSTANCE_HIGHLIGHT) == ["True"],
        preblast_rich=safe_get(form_data, CALENDAR_ADD_EVENT_INSTANCE_PREBLAST),
    )
    if safe_get(form_data, CALENDAR_ADD_EVENT_INSTANCE_PREBLAST):
        event_instance_record.preblast = replace_user_channel_ids(
            parse_rich_block(form_data[CALENDAR_ADD_EVENT_INSTANCE_PREBLAST]),
            region_record,
            client,
            logger,
        )

    if safe_get(metadata, "event_instance_id"):
        # event_instance_id is passed in the metadata if this is an edit
        update_fields = event_instance_record.to_update_dict()
        # drop the fields that are None, as we don't want to update them
        update_fields = {k: v for k, v in update_fields.items() if v is not None}
        DbManager.update_record(EventInstance, metadata["event_instance_id"], fields=update_fields)
        record = DbManager.get(
            EventInstance,
            metadata["event_instance_id"],
            joinedloads=[EventInstance.event_types, EventInstance.event_tags],
        )

    else:
        record = DbManager.create_record(event_instance_record)
    # trigger_map_revalidation()

    if safe_get(metadata, "event_instance_id"):
        body["actions"] = [{"action_id": CALENDAR_MANAGE_EVENT_INSTANCE}]
        build_event_instance_list_form(
            body, client, logger, context, region_record, update_view_id=safe_get(body, "view", "previous_view_id")
        )

    if safe_get(metadata, "is_preblast") == "True":
        # If this is for a new unscheduled event, we need to set attendance and post the preblast
        event_instance: EventInstance = record
        slack_user_id = safe_get(body, "user", "id") or safe_get(body, "user_id")
        DbManager.create_record(
            Attendance(
                event_instance_id=event_instance.id,
                user_id=get_user(slack_user_id, region_record, client, logger).user_id,
                is_planned=True,
                attendance_x_attendance_types=[Attendance_x_AttendanceType(attendance_type_id=2)],  # 2 = Q
            )
        )
        event_preblast.send_preblast(body, client, logger, context, region_record, event_instance.id)


def build_event_instance_list_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
    update_view_id=None,
):
    title_text = "Delete or Edit an Event"
    confirm_text = "Are you sure you want to edit / delete this event? This cannot be undone."

    start_date = current_date_cst()
    filter_org = region_record.org_id
    filter_values = {}
    if safe_get(body, "actions", 0, "action_id") in [
        CALENDAR_MANAGE_EVENT_INSTANCE_AO,
        CALENDAR_MANAGE_EVENT_INSTANCE_DATE,
    ]:
        filter_values = orm.BlockView(blocks=copy.deepcopy(EVENT_LIST_FILTERS)).get_selected_values(body)
        update_view_id = safe_get(body, "view", "id")
        if safe_get(filter_values, CALENDAR_MANAGE_EVENT_INSTANCE_AO):
            filter_org = safe_convert(safe_get(filter_values, CALENDAR_MANAGE_EVENT_INSTANCE_AO), int)
        if safe_get(filter_values, CALENDAR_MANAGE_EVENT_INSTANCE_DATE):
            date_str = safe_get(filter_values, CALENDAR_MANAGE_EVENT_INSTANCE_DATE)
            start_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    records = DbManager.find_join_records2(
        EventInstance,
        Org,
        [
            or_(EventInstance.org_id == filter_org, Org.parent_id == filter_org),
            EventInstance.is_active,
            EventInstance.start_date >= start_date,
        ],
    )
    records: list[EventInstance] = [x[0] for x in records]
    records.sort(key=lambda x: (x.start_date, x.start_time, x.name))
    records = records[:40]

    # TODO: separate into weekly / non-weekly event_instance?
    ao_orgs = DbManager.find_records(
        Org,
        [Org.parent_id == region_record.org_id, Org.is_active, Org.org_type == Org_Type.ao],
    )
    form = orm.BlockView(blocks=copy.deepcopy(EVENT_LIST_FILTERS))
    form.set_options(
        {
            CALENDAR_MANAGE_EVENT_INSTANCE_AO: orm.as_selector_options(
                names=[ao.name for ao in ao_orgs],
                values=[str(ao.id) for ao in ao_orgs],
            ),
        }
    )
    form.set_initial_values(
        {
            CALENDAR_MANAGE_EVENT_INSTANCE_AO: safe_get(filter_values, CALENDAR_MANAGE_EVENT_INSTANCE_AO),
            CALENDAR_MANAGE_EVENT_INSTANCE_DATE: safe_get(filter_values, CALENDAR_MANAGE_EVENT_INSTANCE_DATE),
        }
    )

    print(len(records), "event instances found")
    print(len(form.blocks), "blocks in the form")

    for s in records:
        label = f"{s.name} ({s.start_date.strftime('%m/%d/%Y')})"[:50]

        form.blocks.append(
            orm.SectionBlock(
                label=label,
                action=f"{actions.EVENT_INSTANCE_EDIT_DELETE}_{s.id}",
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
            callback_id=EDIT_DELETE_EVENT_INSTANCE_CALLBACK_ID,
            title_text=title_text,
            submit_button_text="None",
        )
    else:
        form.post_modal(
            client=client,
            trigger_id=safe_get(body, "trigger_id"),
            title_text=title_text,
            callback_id=EDIT_DELETE_EVENT_INSTANCE_CALLBACK_ID,
            submit_button_text="None",
            new_or_add="add",
        )


def handle_event_instance_edit_delete(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    event_instance_id = safe_convert(safe_get(body, "actions", 0, "action_id").split("_")[1], int)
    action = safe_get(body, "actions", 0, "selected_option", "value")

    if action == "Edit":
        event_instance: EventInstance = DbManager.get(EventInstance, event_instance_id, joinedloads="all")
        build_event_instance_add_form(body, client, logger, context, region_record, edit_event_instance=event_instance)
    elif action == "Delete":
        DbManager.update_record(EventInstance, event_instance_id, fields={"is_active": False})
        build_event_instance_list_form(
            body, client, logger, context, region_record, update_view_id=safe_get(body, "view", "id")
        )


INSTANCE_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="AO",
            action=CALENDAR_ADD_EVENT_INSTANCE_AO,
            element=orm.StaticSelectElement(placeholder="Select an AO"),
            dispatch_action=True,
            optional=False,
        ),
        orm.InputBlock(
            label="Location",
            action=CALENDAR_ADD_EVENT_INSTANCE_LOCATION,
            element=orm.StaticSelectElement(placeholder="Select the location"),
            optional=False,
        ),
        orm.InputBlock(
            label="Event Type",
            action=CALENDAR_ADD_EVENT_INSTANCE_TYPE,
            # element=orm.MultiStaticSelectElement(placeholder="Select the event types"),
            element=orm.StaticSelectElement(placeholder="Select the event type"),
            optional=False,
        ),
        orm.InputBlock(
            label="Event Tag",
            action=CALENDAR_ADD_EVENT_INSTANCE_TAG,
            element=orm.MultiStaticSelectElement(placeholder="Select the event tag", max_selected_items=1),
            optional=True,
        ),
        orm.InputBlock(
            label="Date",
            action=CALENDAR_ADD_EVENT_INSTANCE_START_DATE,
            element=orm.DatepickerElement(placeholder="Enter the start date"),
            optional=False,
        ),
        orm.InputBlock(
            label="Start Time",
            action=CALENDAR_ADD_EVENT_INSTANCE_START_TIME,
            element=orm.TimepickerElement(placeholder="Enter the start time"),
            optional=False,
        ),
        orm.InputBlock(
            label="End Time",
            action=CALENDAR_ADD_EVENT_INSTANCE_END_TIME,
            element=orm.TimepickerElement(placeholder="Enter the end time"),
            hint="If no end time is provided, the event will be defaulted to be one hour long.",
        ),
        orm.InputBlock(
            label="Event Name",
            action=CALENDAR_ADD_EVENT_INSTANCE_NAME,
            element=orm.PlainTextInputElement(placeholder="Enter the event name"),
            hint="If left blank, will default to the AO name + event type.",
        ),
        orm.InputBlock(
            label="Highlight on Special Events Page?",
            action=CALENDAR_ADD_EVENT_INSTANCE_HIGHLIGHT,
            element=orm.CheckboxInputElement(
                options=orm.as_selector_options(names=["Yes"], values=["True"]),
            ),
            hint="Primarily used for 2nd F events, convergences, etc.",
        ),
    ]
)

EVENT_LIST_FILTERS = [
    orm.InputBlock(
        label="AO Filter",
        action=CALENDAR_MANAGE_EVENT_INSTANCE_AO,
        element=orm.StaticSelectElement(
            placeholder="Select an AO",
        ),
        optional=True,
        dispatch_action=True,
    ),
    orm.InputBlock(
        label="Date Filter",
        action=CALENDAR_MANAGE_EVENT_INSTANCE_DATE,
        element=orm.DatepickerElement(
            placeholder="Select a date",
        ),
        optional=True,
        dispatch_action=True,
    ),
]
