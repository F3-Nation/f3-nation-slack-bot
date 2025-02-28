import copy
import json
from logging import Logger
from typing import Any, Dict, List, Optional

from f3_data_models.models import EventTag
from slack_sdk.web import WebClient

from utilities.database.orm import SlackSettings
from utilities.helper_functions import safe_convert, safe_get
from utilities.slack import orm

from . import event_tag_ui
from .event_tag_db import EventTagDB


class EventTagService:
    @staticmethod
    def build_event_tag_form(
        body: dict,
        client: WebClient,
        logger: Logger,
        context: dict,
        region_record: SlackSettings,
        edit_event_tag: Optional[EventTag] = None,
    ):
        form = copy.deepcopy(event_tag_ui.EVENT_TAG_FORM)
        all_event_tags = EventTagDB.get_all_event_tags()
        org_record = EventTagDB.get_org_record(region_record.org_id)

        event_tags_new = EventTagService.filter_new_event_tags(all_event_tags, org_record.event_tags)

        if edit_event_tag:
            EventTagService.setup_edit_event_tag_form(form, edit_event_tag)
            title_text = "Edit an Event Tag"
            metadata = {"edit_event_tag_id": edit_event_tag.id}
        else:
            EventTagService.setup_add_event_tag_form(form, event_tags_new)
            title_text = "Add an Event Tag"
            metadata = {}

        EventTagService.set_color_list(form, org_record.event_tags)
        EventTagService.post_event_tag_form(form, client, body, title_text, metadata)

    @staticmethod
    def filter_new_event_tags(all_event_tags: List[EventTag], existing_event_tags: List[EventTag]) -> List[EventTag]:
        existing_ids = {e.id for e in existing_event_tags}
        return [event_tag for event_tag in all_event_tags if event_tag.id not in existing_ids]

    @staticmethod
    def setup_edit_event_tag_form(form: orm.BlockView, edit_event_tag: EventTag):
        form.set_initial_values(
            {
                event_tag_ui.CALENDAR_ADD_EVENT_TAG_NEW: edit_event_tag.name,
                event_tag_ui.CALENDAR_ADD_EVENT_TAG_COLOR: edit_event_tag.color,
            }
        )
        form.blocks.pop(0)
        form.blocks.pop(0)
        form.blocks[0].label = "Edit Event Tag"
        form.blocks[0].element.placeholder = "Edit Event Tag"

    @staticmethod
    def setup_add_event_tag_form(form: orm.BlockView, event_tags_new: List[EventTag]):
        form.set_options(
            {
                event_tag_ui.CALENDAR_ADD_EVENT_TAG_SELECT: orm.as_selector_options(
                    names=[event_tag.name for event_tag in event_tags_new],
                    values=[str(event_tag.id) for event_tag in event_tags_new],
                    descriptions=[event_tag.color for event_tag in event_tags_new],
                ),
            }
        )

    @staticmethod
    def set_color_list(form: orm.BlockView, event_tags: List[EventTag]):
        color_list = [f"{e.name} - {e.color}" for e in event_tags]
        form.blocks[-1].label = f"Colors already in use: \n - {'\n - '.join(color_list)}"

    @staticmethod
    def post_event_tag_form(
        form: orm.BlockView, client: WebClient, body: dict, title_text: str, metadata: Dict[str, Any]
    ):
        form.post_modal(
            client=client,
            trigger_id=safe_get(body, "trigger_id"),
            title_text=title_text,
            callback_id=event_tag_ui.CALENDAR_ADD_EVENT_TAG_CALLBACK_ID,
            new_or_add="add",
            parent_metadata=metadata,
        )

    @staticmethod
    def handle_event_tag_add(
        body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
    ):
        form_data = event_tag_ui.EVENT_TAG_FORM.get_selected_values(body)
        event_tag_name = form_data.get(event_tag_ui.CALENDAR_ADD_EVENT_TAG_NEW)
        event_tag_id = form_data.get(event_tag_ui.CALENDAR_ADD_EVENT_TAG_SELECT)
        event_color = form_data.get(event_tag_ui.CALENDAR_ADD_EVENT_TAG_COLOR)
        metadata = json.loads(safe_get(body, "view", "private_metadata") or "{}")
        edit_event_tag_id = safe_convert(metadata.get("edit_event_tag_id"), int)

        if event_tag_id:
            EventTagService.add_existing_event_tag(event_tag_id, region_record.org_id)
        elif event_tag_name and event_color:
            if edit_event_tag_id:
                EventTagService.update_event_tag(edit_event_tag_id, event_tag_name, event_color)
            else:
                EventTagService.create_new_event_tag(event_tag_name, event_color, region_record.org_id)

    @staticmethod
    def add_existing_event_tag(event_tag_id: int, org_id: int):
        event_tag = EventTagDB.get_event_tag(event_tag_id)
        EventTagDB.create_event_tag(
            EventTag(
                name=event_tag.name,
                color=event_tag.color,
                specific_org_id=org_id,
            )
        )

    @staticmethod
    def update_event_tag(event_tag_id: int, event_tag_name: str, event_color: str):
        EventTagDB.update_event_tag(event_tag_id, event_tag_name, event_color)

    @staticmethod
    def create_new_event_tag(event_tag_name: str, event_color: str, org_id: int = None):
        EventTagDB.create_event_tag(
            EventTag(
                name=event_tag_name,
                color=event_color,
                specific_org_id=org_id,
            )
        )

    @staticmethod
    def build_event_tag_list_form(
        body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
    ):
        org_record = EventTagDB.get_org_record(region_record.org_id)
        blocks = EventTagService.create_event_tag_blocks(org_record.event_tags)
        form = orm.BlockView(blocks=blocks)
        EventTagService.post_event_tag_list_form(form, client, body)

    @staticmethod
    def create_event_tag_blocks(event_tags: List[EventTag]) -> List[orm.BaseBlock]:
        return [
            orm.SectionBlock(
                label=s.name,
                action=f"{event_tag_ui.EVENT_TAG_EDIT_DELETE}_{s.id}",
                element=orm.StaticSelectElement(
                    placeholder="Edit or Delete",
                    options=orm.as_selector_options(names=["Edit", "Delete"]),
                    confirm=orm.ConfirmObject(
                        title="Are you sure?",
                        text="Are you sure you want to edit / delete this Event Tag? This cannot be undone.",
                        confirm="Yes, I'm sure",
                        deny="Whups, never mind",
                    ),
                ),
            )
            for s in event_tags
        ]

    @staticmethod
    def post_event_tag_list_form(form: orm.BlockView, client: WebClient, body: dict):
        form.post_modal(
            client=client,
            trigger_id=safe_get(body, "trigger_id"),
            title_text="Edit/Delete an Event Tag",
            callback_id=event_tag_ui.EDIT_DELETE_AO_CALLBACK_ID,
            submit_button_text="None",
            new_or_add="add",
        )

    @staticmethod
    def handle_event_tag_edit_delete(
        body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
    ):
        event_tag_id = safe_convert(safe_get(body, "actions", 0, "action_id").split("_")[-1], int)
        action = safe_get(body, "actions", 0, "selected_option", "value")

        if action == "Edit":
            event_tag = EventTagDB.get_event_tag(event_tag_id)
            EventTagService.build_event_tag_form(body, client, logger, context, region_record, edit_event_tag=event_tag)
        # elif action == "Delete":
        #     EventTagDB.delete_event_tag(event_tag_id)
