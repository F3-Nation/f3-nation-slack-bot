import copy
import json
from logging import Logger
from typing import List

from f3_data_models.models import EventTag, Org
from f3_data_models.utils import DbManager
from slack_sdk.web import WebClient

from utilities.constants import EVENT_TAG_COLORS
from utilities.database.orm import SlackSettings
from utilities.helper_functions import safe_convert, safe_get
from utilities.slack import actions, orm


def manage_event_tags(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    action = safe_get(body, "actions", 0, "selected_option", "value")

    if action == "add":
        build_event_tag_form(body, client, logger, context, region_record)
    elif action == "edit":
        build_event_tag_list_form(body, client, logger, context, region_record)


def build_event_tag_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
    edit_event_tag: EventTag = None,
):
    form = copy.deepcopy(EVENT_TAG_FORM)

    all_event_tags: List[EventTag] = DbManager.find_records(EventTag, [True])
    org_record: Org = DbManager.get(Org, region_record.org_id, joinedloads="all")

    event_tags_new = [
        event_tag for event_tag in all_event_tags if event_tag.id not in [e.id for e in org_record.event_tags]
    ]

    if edit_event_tag:
        form.set_initial_values(
            {
                actions.CALENDAR_ADD_EVENT_TAG_NEW: edit_event_tag.name,
                actions.CALENDAR_ADD_EVENT_TAG_COLOR: edit_event_tag.color,
            }
        )
        form.blocks.pop(0)
        form.blocks.pop(0)
        form.blocks[0].label = "Edit Event Tag"
        form.blocks[0].element.placeholder = "Edit Event Tag"
        title_text = "Edit an Event Tag"
        metadata = {"edit_event_tag_id": edit_event_tag.id}
    else:
        form.set_options(
            {
                actions.CALENDAR_ADD_EVENT_TAG_SELECT: orm.as_selector_options(
                    names=[event_tag.name for event_tag in event_tags_new],
                    values=[str(event_tag.id) for event_tag in event_tags_new],
                    descriptions=[event_tag.color for event_tag in event_tags_new],
                ),
            }
        )
        title_text = "Add an Event Tag"
        metadata = {}

    # set list of colors already in use
    color_list = [f"{e.name} - {e.color}" for e in org_record.event_tags]
    form.blocks[-1].label = f"Colors already in use: \n - {'\n - '.join(color_list)}"

    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text=title_text,
        callback_id=actions.CALENDAR_ADD_EVENT_TAG_CALLBACK_ID,
        new_or_add="add",
        parent_metadata=metadata,
    )


def handle_event_tag_add(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    form_data = EVENT_TAG_FORM.get_selected_values(body)
    event_tag_name = form_data.get(actions.CALENDAR_ADD_EVENT_TAG_NEW)
    event_tag_id = form_data.get(actions.CALENDAR_ADD_EVENT_TAG_SELECT)
    event_color = form_data.get(actions.CALENDAR_ADD_EVENT_TAG_COLOR)
    metadata = json.loads(safe_get(body, "view", "private_metadata") or "{}")
    edit_event_tag_id = safe_convert(metadata.get("edit_event_tag_id"), int)

    if event_tag_id:
        event_tag: EventTag = DbManager.get(EventTag, event_tag_id)
        DbManager.create_record(
            EventTag(
                name=event_tag.name,
                color=event_tag.color,
                specific_org_id=region_record.org_id,
            )
        )

    elif event_tag_name and event_color:
        if edit_event_tag_id:
            DbManager.update_record(
                EventTag,
                edit_event_tag_id,
                {EventTag.color: event_color, EventTag.name: event_tag_name},
            )
        else:
            DbManager.create_record(
                EventTag(
                    name=event_tag_name,
                    color=event_color,
                    specific_org_id=region_record.org_id,
                )
            )


def build_event_tag_list_form(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    org_record: Org = DbManager.get(Org, region_record.org_id, joinedloads="all")

    blocks = [
        orm.SectionBlock(
            label=s.name,
            action=f"{actions.EVENT_TAG_EDIT_DELETE}_{s.id}",
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
        for s in org_record.event_tags
    ]

    form = orm.BlockView(blocks=blocks)
    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text="Edit/Delete an Event Tag",
        callback_id=actions.EDIT_DELETE_AO_CALLBACK_ID,
        submit_button_text="None",
        new_or_add="add",
    )


def handle_event_tag_edit_delete(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    event_tag_id = safe_convert(safe_get(body, "actions", 0, "action_id").split("_")[1], int)
    action = safe_get(body, "actions", 0, "selected_option", "value")

    if action == "Edit":
        event_tag = DbManager.get(EventTag, event_tag_id)
        build_event_tag_form(body, client, logger, context, region_record, edit_event_tag=event_tag)
    # elif action == "Delete":
    #     DbManager.delete_record(EventTag_x_Org, event_tag_org_id)


EVENT_TAG_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="Select from commonly used event tags",
            element=orm.StaticSelectElement(placeholder="Select from commonly used event tags"),
            optional=True,
            action=actions.CALENDAR_ADD_EVENT_TAG_SELECT,
        ),
        orm.DividerBlock(),
        orm.InputBlock(
            label="Or create a new event tag",
            element=orm.PlainTextInputElement(placeholder="New event tag"),
            action=actions.CALENDAR_ADD_EVENT_TAG_NEW,
            optional=True,
        ),
        orm.InputBlock(
            label="Event tag color",
            element=orm.StaticSelectElement(
                placeholder="Select a color",
                options=orm.as_selector_options(names=list(EVENT_TAG_COLORS.keys())),
            ),
            action=actions.CALENDAR_ADD_EVENT_TAG_COLOR,
            optional=True,
            hint="This is the color that will be shown on the calendar",
        ),
        orm.SectionBlock(label="Colors already in use:"),
    ]
)
