import copy
from logging import Logger
from typing import List

from f3_data_models.models import EventCategory, EventType
from f3_data_models.utils import DbManager
from slack_sdk.web import WebClient

from utilities.database.orm import SlackSettings
from utilities.helper_functions import safe_get
from utilities.slack import actions, orm


def build_event_type_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    form = copy.deepcopy(EVENT_TYPE_FORM)

    event_types_all: List[EventType] = DbManager.find_records(EventType, [True])
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

    event_categories: List[EventCategory] = DbManager.find_records(EventCategory, [True])
    form.set_options(
        {
            actions.CALENDAR_ADD_EVENT_TYPE_SELECT: orm.as_selector_options(
                names=[event_type.name for event_type in event_types_other_org],
                values=[str(event_type.id) for event_type in event_types_other_org],
            ),
            actions.CALENDAR_ADD_EVENT_TYPE_CATEGORY: orm.as_selector_options(
                names=[event_category.name for event_category in event_categories],
                values=[str(event_category.id) for event_category in event_categories],
                descriptions=[event_category.description for event_category in event_categories],
            ),
        }
    )

    event_type_labels = [f" - {event_type.name}: {event_type.acronym}" for event_type in event_types_in_org]
    form.blocks[-1].label = "Event types in use:\n\n" + "\n".join(event_type_labels)

    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text="Add an Event Type",
        callback_id=actions.CALENDAR_ADD_EVENT_TYPE_CALLBACK_ID,
        new_or_add="add",
    )


def handle_event_type_add(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    form_data = EVENT_TYPE_FORM.get_selected_values(body)
    event_type_name = form_data.get(actions.CALENDAR_ADD_EVENT_TYPE_NEW)
    event_type_id = form_data.get(actions.CALENDAR_ADD_EVENT_TYPE_SELECT)
    event_category_id = form_data.get(actions.CALENDAR_ADD_EVENT_TYPE_CATEGORY)
    event_type_acronym = form_data.get(actions.CALENDAR_ADD_EVENT_TYPE_ACRONYM)

    if event_type_id:
        event_type: EventType = DbManager.get(EventType, event_type_id)
        DbManager.create_record(
            EventType(
                name=event_type.name,
                category_id=event_type.category_id,
                acronym=event_type.acronym,
                specific_org_id=region_record.org_id,
            )
        )

    elif event_type_name and event_category_id:
        event_type: EventType = DbManager.create_record(
            EventType(
                name=event_type_name,
                category_id=event_category_id,
                acronym=event_type_acronym or event_type_name[:2],
                specific_org_id=region_record.org_id,
            )
        )


EVENT_TYPE_FORM = orm.BlockView(
    blocks=[
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
