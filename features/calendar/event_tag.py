import copy
import json
from logging import Logger
from typing import List

from f3_data_models.models import EventTag, Org
from f3_data_models.utils import DbManager
from slack_sdk.models.blocks import (
    ContextBlock,
    DividerBlock,
    InputBlock,
    SectionBlock,
)
from slack_sdk.models.blocks.basic_components import PlainTextObject
from slack_sdk.models.blocks.block_elements import PlainTextInputElement, StaticSelectElement
from slack_sdk.web import WebClient

from utilities.builders import add_loading_form
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


class EventTagService:
    """
    A service class for handling business logic related to event tags.
    """

    @staticmethod
    def get_org_event_tags(org_id: str) -> List[EventTag]:
        """
        Fetches the event tags associated with a specific organization.
        """
        org_record: Org = DbManager.get(Org, org_id, joinedloads="all")
        org_event_tags = [tag for tag in org_record.event_tags if tag.specific_org_id == org_id]
        return org_event_tags

    @staticmethod
    def get_available_global_tags(org_id: str) -> List[EventTag]:
        """
        Fetches global event tags that the organization has not yet added.
        """
        all_event_tags: List[EventTag] = DbManager.find_records(EventTag, [True])
        org_record: Org = DbManager.get(Org, org_id, joinedloads="all")
        org_event_tag_ids = {e.id for e in org_record.event_tags}
        return [tag for tag in all_event_tags if tag.id not in org_event_tag_ids]

    @staticmethod
    def add_global_tag_to_org(tag_id: int, org_id: str):
        """
        Associates an existing global event tag with an organization.
        """
        event_tag: EventTag = DbManager.get(EventTag, tag_id)
        DbManager.create_record(
            EventTag(
                name=event_tag.name,
                color=event_tag.color,
                specific_org_id=org_id,
            )
        )

    @staticmethod
    def create_org_specific_tag(name: str, color: str, org_id: str):
        """
        Creates a new event tag that is specific to an organization.
        """
        DbManager.create_record(
            EventTag(
                name=name,
                color=color,
                specific_org_id=org_id,
            )
        )

    @staticmethod
    def update_org_specific_tag(tag_id: int, name: str, color: str):
        """
        Updates an organization-specific event tag.
        """
        DbManager.update_record(
            EventTag,
            tag_id,
            {EventTag.color: color, EventTag.name: name},
        )

    @staticmethod
    def delete_org_specific_tag(tag_id: int):
        """
        Deletes an organization-specific event tag.
        """
        DbManager.delete_record(EventTag, tag_id)


class EventTagViews:
    """
    A class for building Slack modal views related to event tags.
    """

    @staticmethod
    def build_add_tag_modal(available_tags: List[EventTag], org_tags: List[EventTag]) -> SdkBlockView:
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
    def build_edit_tag_modal(tag_to_edit: EventTag, org_tags: List[EventTag]) -> SdkBlockView:
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
    def build_tag_list_modal(org_tags: List[EventTag]) -> SdkBlockView:
        """
        Constructs the modal that lists an organization's event tags, with options to edit or delete them.
        """
        blocks = [
            SectionBlock(
                text=s.name,
                block_id=f"{EVENT_TAG_EDIT_DELETE}_{s.id}",
                accessory=StaticSelectElement(
                    placeholder="Edit",  # TODO: Change to "Edit / Delete"
                    options=as_selector_options(names=["Edit"]),
                    # confirm=ConfirmObject(
                    #     title="Are you sure?",
                    #     text="Are you sure you want to edit / delete this Event Tag? This cannot be undone.",
                    #     confirm="Yes, I'm sure",
                    #     deny="Whups, never mind",
                    # ),
                    action_id=f"{EVENT_TAG_EDIT_DELETE}_{s.id}",
                ),
            )
            for s in org_tags
        ]
        blocks.append(
            ContextBlock(
                elements=[PlainTextObject(text="Only custom event tags can be edited or deleted.")],
            )
        )
        return SdkBlockView(blocks=blocks)


def manage_event_tags(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    action = safe_get(body, "actions", 0, "selected_option", "value")
    service = EventTagService()
    views = EventTagViews()

    if action == "add":
        update_view_id = add_loading_form(body, client, new_or_add="add")
        available_tags = service.get_available_global_tags(region_record.org_id)
        org_tags = service.get_org_event_tags(region_record.org_id)
        form = views.build_add_tag_modal(available_tags, org_tags)
        form.update_modal(
            client=client,
            view_id=update_view_id,
            title_text="Add an Event Tag",
            callback_id=CALENDAR_ADD_EVENT_TAG_CALLBACK_ID,
        )
    elif action == "edit":
        org_tags = service.get_org_event_tags(region_record.org_id)
        form = views.build_tag_list_modal(org_tags)
        form.post_modal(
            client=client,
            trigger_id=safe_get(body, "trigger_id"),
            title_text="Edit an Event Tag",  # TODO: Edit/Delete
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

    service = EventTagService()

    if event_tag_id:
        service.add_global_tag_to_org(event_tag_id, region_record.org_id)
    elif event_tag_name and event_color:
        if edit_event_tag_id:
            service.update_org_specific_tag(edit_event_tag_id, event_tag_name, event_color)
        else:
            service.create_org_specific_tag(event_tag_name, event_color, region_record.org_id)


def handle_event_tag_edit_delete(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    event_tag_id = safe_convert(safe_get(body, "actions", 0, "action_id").split("_")[1], int)
    action = safe_get(body, "actions", 0, "selected_option", "value")
    service = EventTagService()
    views = EventTagViews()

    if action == "Edit":
        update_view_id = add_loading_form(body, client, new_or_add="add")
        event_tag = DbManager.get(EventTag, event_tag_id)
        org_tags = service.get_org_event_tags(region_record.org_id)
        form = views.build_edit_tag_modal(event_tag, org_tags)
        form.update_modal(
            client=client,
            view_id=update_view_id,
            title_text="Edit an Event Tag",
            callback_id=CALENDAR_ADD_EVENT_TAG_CALLBACK_ID,
            parent_metadata={"edit_event_tag_id": event_tag.id},
        )
    elif action == "Delete":
        service.delete_org_specific_tag(event_tag_id)


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
