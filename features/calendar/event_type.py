import copy
import json
from logging import Logger
from typing import List

from f3_data_models.models import Event_Category, EventType
from f3_data_models.utils import DbManager
from slack_sdk.web import WebClient

from utilities.database.orm import SlackSettings
from utilities.helper_functions import safe_convert, safe_get
from utilities.slack import actions, orm


def manage_event_types(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    action = safe_get(body, "actions", 0, "selected_option", "value")

    if action == "add":
        build_event_type_form(body, client, logger, context, region_record)
    elif action == "edit":
        build_event_type_list_form(body, client, logger, context, region_record)


def build_event_type_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
    edit_event_type: EventType = None,
):
    form = copy.deepcopy(EVENT_TYPE_FORM)

    event_types_all: List[EventType] = DbManager.find_records(EventType, [EventType.is_active])
    event_types_org = [
        type.id
        for type in event_types_all
        if type.specific_org_id == region_record.org_id or type.specific_org_id is None
    ]
    event_types_other_org = [event_type for event_type in event_types_all if event_type.id not in event_types_org]
    event_types_in_org = [event_type for event_type in event_types_all if event_type.id in event_types_org]
    if not event_types_other_org:
        form.blocks.pop(0)
        form.blocks.pop(0)
        form.blocks[0].label = "Create a new event type"

    form.set_options(
        {
            actions.CALENDAR_ADD_EVENT_TYPE_SELECT: orm.as_selector_options(
                names=[event_type.name for event_type in event_types_other_org],
                values=[str(event_type.id) for event_type in event_types_other_org],
            ),
            actions.CALENDAR_ADD_EVENT_TYPE_CATEGORY: orm.as_selector_options(
                names=[c.name.capitalize() for c in Event_Category],
                values=[c.name for c in Event_Category],
            ),
        }
    )

    if edit_event_type:
        form.set_initial_values(
            {
                actions.CALENDAR_ADD_EVENT_TYPE_NEW: edit_event_type.name,
                actions.CALENDAR_ADD_EVENT_TYPE_CATEGORY: edit_event_type.event_category.name,
                actions.CALENDAR_ADD_EVENT_TYPE_ACRONYM: edit_event_type.acronym,
            }
        )
        form.blocks.pop(0)
        # form.blocks.pop(0)
        form.blocks[0].label = "Edit Event Type"
        form.blocks[0].element.placeholder = "Edit Event Type"
        title_text = "Edit an Event Type"
        metadata = {"edit_event_type_id": edit_event_type.id}
    else:
        title_text = "Add an Event Type"
        metadata = {}

    event_type_labels = [f" - {event_type.name}: {event_type.acronym}" for event_type in event_types_in_org]
    form.blocks[-1].label = "Event types in use:\n\n" + "\n".join(event_type_labels)

    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text=title_text,
        callback_id=actions.CALENDAR_ADD_EVENT_TYPE_CALLBACK_ID,
        new_or_add="add",
        parent_metadata=metadata,
    )


def handle_event_type_add(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    form_data = EVENT_TYPE_FORM.get_selected_values(body)
    event_type_name = form_data.get(actions.CALENDAR_ADD_EVENT_TYPE_NEW)
    event_type_id = form_data.get(actions.CALENDAR_ADD_EVENT_TYPE_SELECT)
    event_category = form_data.get(actions.CALENDAR_ADD_EVENT_TYPE_CATEGORY)
    event_type_acronym = form_data.get(actions.CALENDAR_ADD_EVENT_TYPE_ACRONYM)
    metadata = safe_convert(safe_get(body, "view", "private_metadata"), json.loads) or {}

    if safe_get(metadata, "edit_event_type_id"):
        event_type_id = safe_get(metadata, "edit_event_type_id")
        event_type: EventType = DbManager.get(EventType, event_type_id)
        DbManager.update_record(
            EventType,
            event_type_id,
            fields={
                EventType.name: event_type_name or event_type.name,
                EventType.event_category: event_category or event_type.event_category,
                EventType.acronym: event_type_acronym or event_type.acronym,
                EventType.specific_org_id: region_record.org_id,
            },
        )

    elif event_type_id:
        event_type: EventType = DbManager.get(EventType, event_type_id)
        DbManager.create_record(
            EventType(
                name=event_type.name,
                event_category=event_type.event_category,
                acronym=event_type.acronym,
                specific_org_id=region_record.org_id,
            )
        )

    elif event_type_name and event_category:
        event_type: EventType = DbManager.create_record(
            EventType(
                name=event_type_name,
                event_category=event_category,
                acronym=event_type_acronym or event_type_name[:2],
                specific_org_id=region_record.org_id,
            )
        )


def build_event_type_list_form(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    event_types_all: List[EventType] = DbManager.find_records(EventType, [EventType.is_active])
    event_types_org = [type.id for type in event_types_all if type.specific_org_id == region_record.org_id]
    event_types_in_org = [event_type for event_type in event_types_all if event_type.id in event_types_org]

    blocks = [
        orm.ContextBlock(
            element=orm.ContextElement(initial_value="Only region-specific event types can be edited or deleted."),
        )
    ]
    for s in event_types_in_org:
        blocks.append(
            orm.SectionBlock(
                label=s.name,
                action=f"{actions.EVENT_TYPE_EDIT_DELETE}_{s.id}",
                element=orm.StaticSelectElement(
                    placeholder="Edit or Delete",
                    options=orm.as_selector_options(names=["Edit", "Delete"]),
                    confirm=orm.ConfirmObject(
                        title="Are you sure?",
                        text="Are you sure you want to edit / delete this Event Type? This cannot be undone.",
                        confirm="Yes, I'm sure",
                        deny="Whups, never mind",
                    ),
                ),
            )
        )

    form = orm.BlockView(blocks=blocks)

    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text="Edit/Delete Event Types",
        callback_id=actions.EDIT_DELETE_EVENT_TYPE_CALLBACK_ID,
        submit_button_text="None",
        new_or_add="add",
    )


def handle_event_type_edit_delete(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    action = safe_get(body, "actions", 0, "selected_option", "value")
    event_type_id = safe_get(body, "actions", 0, "action_id").split("_")[-1]

    if action == "Edit":
        event_type: EventType = DbManager.get(EventType, event_type_id)
        build_event_type_form(body, client, logger, context, region_record, edit_event_type=event_type)
    elif action == "Delete":
        DbManager.update_record(
            EventType,
            event_type_id,
            fields={
                EventType.is_active: False,
            },
        )


EVENT_TYPE_FORM = orm.BlockView(
    blocks=[
        orm.SectionBlock(
            label="Note: Event Types are used to describe what you'll be doing at an event. They are different from Event Tags, which are used to give context to an event but do not change what you'll be doing at the event (e.g. 'VQ', 'Convergence', etc.).",  # noqa
        ),
        orm.InputBlock(
            label="Select from commonly used event types",
            element=orm.StaticSelectElement(placeholder="Select from commonly used event types"),
            optional=True,
            action=actions.CALENDAR_ADD_EVENT_TYPE_SELECT,
        ),
        orm.DividerBlock(),
        orm.InputBlock(
            label="Or create a new event type",
            element=orm.PlainTextInputElement(placeholder="New event type"),
            action=actions.CALENDAR_ADD_EVENT_TYPE_NEW,
            optional=True,
        ),
        orm.InputBlock(
            label="Select an event category",
            element=orm.StaticSelectElement(placeholder="Select an event category"),
            action=actions.CALENDAR_ADD_EVENT_TYPE_CATEGORY,
            optional=True,
            hint="If entering a new event type, this is required for national aggregations (achievements, etc).",
        ),
        orm.InputBlock(
            label="Event type acronym",
            element=orm.PlainTextInputElement(placeholder="Two letter acronym", max_length=2),
            action=actions.CALENDAR_ADD_EVENT_TYPE_ACRONYM,
            optional=True,
            hint="This is used for the calendar view to save on space. Defaults to first two letters of event type name. Make sure it's unique!",  # noqa
        ),
        orm.SectionBlock(
            label="Event types in use:\n\n",
            action=actions.CALENDAR_ADD_EVENT_TYPE_LIST,
        ),
    ]
)
