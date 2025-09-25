import copy
import json
from logging import Logger
from typing import List

from slack_sdk.models.blocks import DividerBlock, InputBlock, SectionBlock
from slack_sdk.models.blocks.basic_components import ConfirmObject, PlainTextObject
from slack_sdk.models.blocks.block_elements import PlainTextInputElement, StaticSelectElement
from slack_sdk.web import WebClient

from application.dto import EventTagDTO
from application.org.command_handlers import OrgCommandHandler
from application.org.commands import (
    AddEventTag,
    CloneGlobalEventTag,
    SoftDeleteEventTag,
    UpdateEventTag,
)
from application.services.org_query_service import OrgQueryService
from infrastructure.persistence.sqlalchemy.org_repository import SqlAlchemyOrgRepository
from utilities.constants import EVENT_TAG_COLORS
from utilities.database.orm import SlackSettings
from utilities.helper_functions import safe_convert, safe_get
from utilities.slack.sdk_orm import SdkBlockView, as_selector_options

# Action IDs
CALENDAR_MANAGE_EVENT_TAGS = "calendar-manage-event-tags"
CALENDAR_ADD_EVENT_TAG_SELECT = "calendar-add-event-tag-select"
CALENDAR_ADD_EVENT_TAG_NEW = "calendar-add-event-tag-new"
CALENDAR_ADD_EVENT_TAG_COLOR = "calendar-add-event-tag-color"
EVENT_TAG_EDIT_DELETE = "event-tag-edit-delete"
CALENDAR_ADD_EVENT_TAG_CALLBACK_ID = "calendar-add-event-tag-id"
EDIT_DELETE_AO_CALLBACK_ID = "edit-delete-ao-id"
CALENDAR_EVENT_TAG_COLORS_IN_USE = "calendar-event-tag-colors-in-use"


class EventTagViews:
    """
    A class for building Slack modal views related to event tags.
    """

    @staticmethod
    def build_add_tag_modal(available_tags: List[EventTagDTO], org_tags: List[EventTagDTO]) -> SdkBlockView:
        """
        Constructs the modal for adding a new or existing event tag.
        """
        form = copy.deepcopy(EVENT_TAG_FORM)
        form.set_options(
            {
                CALENDAR_ADD_EVENT_TAG_SELECT: as_selector_options(
                    names=[tag.name for tag in available_tags],
                    values=[str(tag.id) for tag in available_tags],
                    descriptions=[tag.color for tag in available_tags],
                ),
            }
        )
        color_list = [f"{e.name} - {e.color}" for e in org_tags]
        if color_block := form.get_block(CALENDAR_EVENT_TAG_COLORS_IN_USE):
            color_block.text.text = f"Colors already in use: \n - {'\n - '.join(color_list)}"
        return form

    @staticmethod
    def build_edit_tag_modal(tag_to_edit: EventTagDTO, org_tags: List[EventTagDTO]) -> SdkBlockView:
        """
        Constructs the modal for editing an existing event tag.
        """
        form = copy.deepcopy(EVENT_TAG_FORM)
        form.set_initial_values(
            {
                CALENDAR_ADD_EVENT_TAG_NEW: tag_to_edit.name,
                CALENDAR_ADD_EVENT_TAG_COLOR: tag_to_edit.color,
            }
        )

        # Remove blocks that are not needed for editing
        form.delete_block(CALENDAR_ADD_EVENT_TAG_SELECT)

        # Find the input block for the tag name and change its label
        if name_input_block := form.get_block(CALENDAR_ADD_EVENT_TAG_NEW):
            name_input_block.label.text = "Edit Event Tag"
            name_input_block.element.placeholder.text = "Edit Event Tag"

        # Update the list of colors in use
        color_list = [f"{e.name} - {e.color}" for e in org_tags]
        if color_block := form.get_block(CALENDAR_EVENT_TAG_COLORS_IN_USE):
            color_block.text.text = f"Colors already in use: \n - {'\n - '.join(color_list)}"

        return form

    @staticmethod
    def build_tag_list_modal(org_tags: List[EventTagDTO]) -> SdkBlockView:
        """
        Constructs the modal that lists an organization's event tags, with options to edit or delete them.
        """
        blocks = [
            SectionBlock(
                text=s.name,
                block_id=f"{EVENT_TAG_EDIT_DELETE}_{s.id}",
                accessory=StaticSelectElement(
                    placeholder="Edit or Delete",
                    options=as_selector_options(names=["Edit", "Delete"]),
                    confirm=ConfirmObject(
                        title="Are you sure?",
                        text="Are you sure you want to edit / delete this Event Tag? This cannot be undone.",
                        confirm="Yes, I'm sure",
                        deny="Whups, never mind",
                    ),
                    action_id=f"{EVENT_TAG_EDIT_DELETE}_{s.id}",
                ),
            )
            for s in org_tags
        ]
        return SdkBlockView(blocks=blocks)


def manage_event_tags(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    action = safe_get(body, "actions", 0, "selected_option", "value")
    views = EventTagViews()

    repo = SqlAlchemyOrgRepository()
    qs = OrgQueryService(repo)

    if action == "add":
        # available = (global + region) - (region)
        org_tags = qs.get_event_tags(region_record.org_id, include_global=False)
        all_tags = qs.get_event_tags(region_record.org_id, include_global=True)
        org_ids = {t.id for t in org_tags}
        available_tags = [t for t in all_tags if t.id not in org_ids]
        form = views.build_add_tag_modal(available_tags, all_tags)
        form.post_modal(
            client=client,
            trigger_id=safe_get(body, "trigger_id"),
            title_text="Add an Event Tag",
            callback_id=CALENDAR_ADD_EVENT_TAG_CALLBACK_ID,
            new_or_add="add",
        )
    elif action == "edit":
        org_tags = qs.get_event_tags(region_record.org_id, include_global=False)
        form = views.build_tag_list_modal(org_tags)
        form.post_modal(
            client=client,
            trigger_id=safe_get(body, "trigger_id"),
            title_text="Edit/Delete an Event Tag",
            callback_id=EDIT_DELETE_AO_CALLBACK_ID,
            submit_button_text="None",
            new_or_add="add",
        )


def handle_event_tag_add(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    form_data = EVENT_TAG_FORM.get_selected_values(body)
    event_tag_name = form_data.get(CALENDAR_ADD_EVENT_TAG_NEW)
    event_tag_id = form_data.get(CALENDAR_ADD_EVENT_TAG_SELECT)
    event_color = form_data.get(CALENDAR_ADD_EVENT_TAG_COLOR)
    metadata = json.loads(safe_get(body, "view", "private_metadata") or "{}")
    edit_event_tag_id = safe_convert(metadata.get("edit_event_tag_id"), int)

    # DDD path only
    repo = SqlAlchemyOrgRepository()
    handler = OrgCommandHandler(repo)
    org_id_int = int(region_record.org_id)
    try:
        if event_tag_id:
            # Clone global tag
            handler.handle(CloneGlobalEventTag(org_id=org_id_int, global_tag_id=int(event_tag_id)))
        elif event_tag_name and event_color:
            if edit_event_tag_id:
                handler.handle(
                    UpdateEventTag(
                        org_id=org_id_int,
                        tag_id=int(edit_event_tag_id),
                        name=event_tag_name,
                        color=event_color,
                    )
                )
            else:
                handler.handle(AddEventTag(org_id=org_id_int, name=event_tag_name, color=event_color))
    except ValueError as e:
        logger.error(f"Event tag operation failed: {e}")
        # TODO: optionally send ephemeral error to user


def handle_event_tag_edit_delete(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    event_tag_id = safe_convert(safe_get(body, "actions", 0, "action_id").split("_")[1], int)
    action = safe_get(body, "actions", 0, "selected_option", "value")
    views = EventTagViews()
    repo = SqlAlchemyOrgRepository()
    qs = OrgQueryService(repo)

    if action == "Edit":
        all_tags = qs.get_event_tags(region_record.org_id, include_global=True)
        event_tag = next((t for t in all_tags if int(t.id) == int(event_tag_id) and t.scope == "region"), None)
        if not event_tag:
            logger.error("Event tag not found for edit")
            return
        form = views.build_edit_tag_modal(event_tag, all_tags)
        form.post_modal(
            client=client,
            trigger_id=safe_get(body, "trigger_id"),
            title_text="Edit an Event Tag",
            callback_id=CALENDAR_ADD_EVENT_TAG_CALLBACK_ID,
            new_or_add="add",
            parent_metadata={"edit_event_tag_id": int(event_tag.id)},
        )
    elif action == "Delete":
        handler = OrgCommandHandler(repo)
        org_id_int = int(region_record.org_id)
        try:
            handler.handle(SoftDeleteEventTag(org_id=org_id_int, tag_id=int(event_tag_id)))
        except ValueError as e:
            logger.error(f"Failed to delete event tag: {e}")


EVENT_TAG_FORM = SdkBlockView(
    blocks=[
        SectionBlock(
            text=PlainTextObject(
                text="Note: Event tags are a way to add context about an event. They are different from Event Types, which are used to define the 'what you will do' of an event.",  # noqa
            ),
        ),
        InputBlock(
            label=PlainTextObject(text="Select from commonly used event tags"),
            element=StaticSelectElement(placeholder=PlainTextObject(text="Select from commonly used event tags")),
            optional=True,
            block_id=CALENDAR_ADD_EVENT_TAG_SELECT,
        ),
        DividerBlock(),
        InputBlock(
            label=PlainTextObject(text="Or create a new event tag"),
            element=PlainTextInputElement(placeholder=PlainTextObject(text="New event tag")),
            block_id=CALENDAR_ADD_EVENT_TAG_NEW,
            optional=True,
        ),
        InputBlock(
            label=PlainTextObject(text="Event tag color"),
            element=StaticSelectElement(
                placeholder=PlainTextObject(text="Select a color"),
                options=as_selector_options(names=list(EVENT_TAG_COLORS.keys())),
            ),
            block_id=CALENDAR_ADD_EVENT_TAG_COLOR,
            optional=True,
            hint="This is the color that will be shown on the calendar",
        ),
        SectionBlock(text="Colors already in use:", block_id=CALENDAR_EVENT_TAG_COLORS_IN_USE),
    ]
)
