import copy
import json
from logging import Logger

from f3_data_models.models import Event_Category
from slack_sdk.models import blocks
from slack_sdk.web import WebClient

from application.org.command_handlers import OrgCommandHandler
from application.org.commands import (
    AddEventType,
    CloneGlobalEventType,
    SoftDeleteEventType,
    UpdateEventType,
)
from application.services.org_query_service import OrgQueryService
from infrastructure.persistence.sqlalchemy.org_repository import SqlAlchemyOrgRepository
from utilities.database.orm import SlackSettings
from utilities.helper_functions import safe_convert, safe_get
from utilities.slack.sdk_orm import SdkBlockView, as_selector_options

# Local copies of Slack action constants used in this module to avoid importing utilities.slack.actions
# Values mirror those defined in utilities/slack/actions.py
CALENDAR_ADD_EVENT_TYPE_SELECT = "calendar-add-event-type-select"
CALENDAR_ADD_EVENT_TYPE_NEW = "calendar-add-event-type-new"
CALENDAR_ADD_EVENT_TYPE_CATEGORY = "calendar-add-event-type-category"
CALENDAR_ADD_EVENT_TYPE_CALLBACK_ID = "calendar-add-event-type-id"
CALENDAR_ADD_EVENT_TYPE_ACRONYM = "calendar-add-event-type-acronym"
CALENDAR_ADD_EVENT_TYPE_LIST = "calendar-add-event-type-list"
EDIT_DELETE_EVENT_TYPE_CALLBACK_ID = "edit-delete-event-type-id"
EVENT_TYPE_EDIT_DELETE = "event-type-edit-delete"


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
    edit_event_type: object | None = None,
):
    form = copy.deepcopy(EVENT_TYPE_FORM)

    repo = SqlAlchemyOrgRepository()
    qs = OrgQueryService(repo)

    selection_event_types = qs.get_event_types(region_record.org_id, include_global=True, only_active=True)
    event_types_in_org = selection_event_types

    if not selection_event_types:
        form.blocks.pop(0)
        form.blocks.pop(0)
        form.blocks[0].label = "Create a new event type"

    form.set_options(
        {
            CALENDAR_ADD_EVENT_TYPE_SELECT: as_selector_options(
                names=[dto.name for dto in selection_event_types],
                values=[str(dto.id) for dto in selection_event_types],
            ),
            CALENDAR_ADD_EVENT_TYPE_CATEGORY: as_selector_options(
                names=[c.name.capitalize() for c in Event_Category],
                values=[c.name for c in Event_Category],
            ),
        }
    )

    if edit_event_type:
        form.set_initial_values(
            {
                CALENDAR_ADD_EVENT_TYPE_NEW: getattr(edit_event_type, "name", None),
                CALENDAR_ADD_EVENT_TYPE_CATEGORY: getattr(edit_event_type, "category", None),
                CALENDAR_ADD_EVENT_TYPE_ACRONYM: getattr(edit_event_type, "acronym", None),
            }
        )
        form.blocks.pop(0)
        form.blocks[0].label = "Edit Event Type"
        form.blocks[0].element.placeholder = "Edit Event Type"
        title_text = "Edit an Event Type"
        metadata = {"edit_event_type_id": getattr(edit_event_type, "id", None)}
    else:
        title_text = "Add an Event Type"
        metadata = {}

    event_type_labels = [
        f" - {dto.name}: {dto.acronym or (dto.name[:2] if dto.name else '')}" for dto in event_types_in_org
    ]
    form.blocks[-1].label = "Event types in use:\n\n" + "\n".join(event_type_labels)

    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text=title_text,
        callback_id=CALENDAR_ADD_EVENT_TYPE_CALLBACK_ID,
        new_or_add="add",
        parent_metadata=metadata,
    )


def handle_event_type_add(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    form_data = EVENT_TYPE_FORM.get_selected_values(body)
    event_type_name = form_data.get(CALENDAR_ADD_EVENT_TYPE_NEW)
    event_type_id = form_data.get(CALENDAR_ADD_EVENT_TYPE_SELECT)
    event_category = form_data.get(CALENDAR_ADD_EVENT_TYPE_CATEGORY)
    event_type_acronym = form_data.get(CALENDAR_ADD_EVENT_TYPE_ACRONYM)
    metadata = safe_convert(safe_get(body, "view", "private_metadata"), json.loads) or {}

    # DDD path
    repo = SqlAlchemyOrgRepository()
    handler = OrgCommandHandler(repo)
    org_id_int = int(region_record.org_id)

    try:
        if safe_get(metadata, "edit_event_type_id"):
            handler.handle(
                UpdateEventType(
                    org_id=org_id_int,
                    event_type_id=int(safe_get(metadata, "edit_event_type_id")),
                    name=event_type_name,
                    category=event_category,
                    acronym=event_type_acronym,
                )
            )
        elif event_type_id:
            handler.handle(CloneGlobalEventType(org_id=org_id_int, global_event_type_id=int(event_type_id)))
        elif event_type_name and event_category:
            handler.handle(
                AddEventType(
                    org_id=org_id_int,
                    name=event_type_name,
                    category=event_category,
                    acronym=event_type_acronym or (event_type_name[:2] if event_type_name else None),
                )
            )
    except ValueError as e:
        logger.error(f"Event type operation failed: {e}")


def build_event_type_list_form(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    repo = SqlAlchemyOrgRepository()
    qs = OrgQueryService(repo)
    event_types_in_org = qs.get_event_types(region_record.org_id, include_global=False, only_active=True)

    blocks_list = [
        blocks.ContextBlock(
            element=blocks.TextObject("Only region-specific event types can be edited or deleted."),
        )
    ]
    for s in event_types_in_org:
        blocks_list.append(
            blocks.SectionBlock(
                label=s.name,
                block_id=f"{EVENT_TYPE_EDIT_DELETE}_{s.id}",
                element=blocks.StaticSelectElement(
                    placeholder="Edit or Delete",
                    action_id=f"{EVENT_TYPE_EDIT_DELETE}_{s.id}",
                    options=as_selector_options(names=["Edit", "Delete"]),
                    confirm=blocks.ConfirmObject(
                        title="Are you sure?",
                        text="Are you sure you want to edit / delete this Event Type? This cannot be undone.",
                        confirm="Yes, I'm sure",
                        deny="Whups, never mind",
                    ),
                ),
            )
        )

    form = SdkBlockView(blocks=blocks_list)

    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text="Edit/Delete Event Types",
        callback_id=EDIT_DELETE_EVENT_TYPE_CALLBACK_ID,
        submit_button_text="None",
        new_or_add="add",
    )


def handle_event_type_edit_delete(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    action = safe_get(body, "actions", 0, "selected_option", "value")
    event_type_id = safe_get(body, "actions", 0, "action_id").split("_")[-1]

    if action == "Edit":
        repo = SqlAlchemyOrgRepository()
        qs = OrgQueryService(repo)
        try:
            dtos = qs.get_event_types(region_record.org_id, include_global=False, only_active=True)
        except Exception as e:
            logger.error(f"Failed to fetch event types for edit: {e}")
            return
        et_dto = next((d for d in dtos if str(d.id) == str(event_type_id)), None)
        if not et_dto:
            logger.error(f"Event type not found for edit: {event_type_id}")
            return
        build_event_type_form(body, client, logger, context, region_record, edit_event_type=et_dto)
    elif action == "Delete":
        repo = SqlAlchemyOrgRepository()
        handler = OrgCommandHandler(repo)
        org_id_int = int(region_record.org_id)
        try:
            handler.handle(SoftDeleteEventType(org_id=org_id_int, event_type_id=int(event_type_id)))
        except ValueError as e:
            logger.error(f"Failed to delete event type: {e}")


EVENT_TYPE_FORM = SdkBlockView(
    blocks=[
        blocks.SectionBlock(
            label="Note: Event Types are used to describe what you'll be doing at an event. They are different from Event Tags, which are used to give context to an event but do not change what you'll be doing at the event (e.g. 'VQ', 'Convergence', etc.).",  # noqa
        ),
        blocks.InputBlock(
            label="Select from commonly used event types",
            element=blocks.StaticSelectElement(placeholder="Select from commonly used event types"),
            optional=True,
            block_id=CALENDAR_ADD_EVENT_TYPE_SELECT,
        ),
        blocks.DividerBlock(),
        blocks.InputBlock(
            label="Or create a new event type",
            element=blocks.PlainTextInputElement(placeholder="New event type"),
            block_id=CALENDAR_ADD_EVENT_TYPE_NEW,
            optional=True,
        ),
        blocks.InputBlock(
            label="Select an event category",
            element=blocks.StaticSelectElement(placeholder="Select an event category"),
            block_id=CALENDAR_ADD_EVENT_TYPE_CATEGORY,
            optional=True,
            hint="If entering a new event type, this is required for national aggregations (achievements, etc).",
        ),
        blocks.InputBlock(
            label="Event type acronym",
            element=blocks.PlainTextInputElement(placeholder="Two letter acronym", max_length=2),
            block_id=CALENDAR_ADD_EVENT_TYPE_ACRONYM,
            optional=True,
            hint="This is used for the calendar view to save on space. Defaults to first two letters of event type name. Make sure it's unique!",  # noqa
        ),
        blocks.SectionBlock(
            label="Event types in use:\n\n",
            block_id=CALENDAR_ADD_EVENT_TYPE_LIST,
        ),
    ]
)
