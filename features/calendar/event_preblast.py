import datetime
import json
from copy import deepcopy
from dataclasses import dataclass
from logging import Logger
from typing import List

from f3_data_models.models import (
    Attendance,
    Attendance_x_AttendanceType,
    AttendanceType,
    Event,
    EventTag,
    EventTag_x_Event,
    EventTag_x_Org,
    Location,
)
from f3_data_models.utils import DbManager
from slack_sdk.web import WebClient

from features.calendar import PREBLAST_MESSAGE_ACTION_ELEMENTS
from utilities import constants
from utilities.database.orm import SlackSettings
from utilities.database.special_queries import event_attendance_query
from utilities.helper_functions import get_user, get_user_names, safe_convert, safe_get
from utilities.slack import actions, orm


@dataclass
class PreblastInfo:
    event_record: Event
    attendance_records: list[Attendance]
    preblast_blocks: list[orm.BaseBlock]
    action_blocks: list[orm.BaseElement]
    user_is_q: bool = False


def get_preblast_channel(region_record: SlackSettings, preblast_info: PreblastInfo) -> str:
    if (
        region_record.default_preblast_destination == constants.CONFIG_DESTINATION_SPECIFIED["value"]
        and region_record.preblast_destination_channel
    ):
        return region_record.preblast_destination_channel
    return preblast_info.event_record.org.meta.get("slack_channel_id")


def build_event_preblast_select_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
):
    user_id = get_user(safe_get(body, "user", "id") or safe_get(body, "user_id"), region_record, client, logger).user_id
    event_records = event_attendance_query(
        attendance_filter=[
            Attendance.user_id == user_id,
            Attendance.is_planned,
            Attendance.attendance_types.any(AttendanceType.id.in_([2, 3])),
        ],
        event_filter=[
            Event.start_date <= datetime.date.today(),
            Event.preblast_ts.is_(None),
            Event.is_active,
        ],
    )

    if event_records:
        select_block = orm.InputBlock(
            label="Select an upcoming Q",
            action=actions.EVENT_PREBLAST_SELECT,
            dispatch_action=True,
            element=orm.StaticSelectElement(
                placeholder="Select an event",
                options=orm.as_selector_options(
                    names=[
                        f"{r.start_date} {r.org.name} {r.event_types[0].name}" for r in event_records
                    ],  # TODO: handle multiple event types and current data format
                    values=[str(r.id) for r in event_records],
                ),
            ),
        )
    else:
        select_block = orm.SectionBlock(label="No upcoming events for you to send a preblast for!")

    blocks = [
        select_block,
        orm.ActionsBlock(
            elements=[
                orm.ButtonElement(
                    label=":heavy_plus_sign: New Unscheduled Event", action=actions.EVENT_PREBLAST_NEW_BUTTON
                ),
                orm.ButtonElement(label=":calendar: Open Calendar", action=actions.OPEN_CALENDAR_BUTTON),
            ]
        ),
    ]
    form = orm.BlockView(blocks=blocks)
    form.update_modal(
        client=client,
        view_id=safe_get(body, actions.LOADING_ID),
        callback_id=actions.EVENT_PREBLAST_SELECT_CALLBACK_ID,
        title_text="Select Preblast",
        submit_button_text="None",
    )


def handle_event_preblast_select(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
):
    event_id = safe_get(body, "actions", 0, "selected_option", "value")
    view_id = safe_get(body, "view", "id")
    build_event_preblast_form(
        body, client, logger, context, region_record, event_id=int(event_id), update_view_id=view_id
    )


def build_event_preblast_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
    event_id: int = None,
    update_view_id: str = None,
):
    preblast_info = build_preblast_info(body, client, logger, context, region_record, event_id)
    record = preblast_info.event_record
    view_id = safe_get(body, "view", "id")
    action_value = safe_get(body, "actions", 0, "value") or safe_get(body, "actions", 0, "selected_option", "value")

    preblast_channel = get_preblast_channel(region_record, preblast_info)
    if action_value == "Edit Preblast" or preblast_info.user_is_q:
        form = deepcopy(EVENT_PREBLAST_FORM)

        location_records: list[Location] = DbManager.find_records(Location, [Location.org_id == region_record.org_id])
        tag_records: list[tuple[EventTag, EventTag_x_Org]] = DbManager.find_join_records2(
            EventTag, EventTag_x_Org, [EventTag_x_Org.org_id == region_record.org_id]
        )
        # TODO: filter locations to AO?
        # TODO: show hardcoded details (date, time, etc.)
        form.set_options(
            {
                actions.EVENT_PREBLAST_LOCATION: orm.as_selector_options(
                    names=[location.name for location in location_records],
                    values=[str(location.id) for location in location_records],
                ),
                actions.EVENT_PREBLAST_TAG: orm.as_selector_options(
                    names=[tag.name for tag, _ in tag_records if tag.name != "Open"],
                    values=[str(tag.id) for tag, _ in tag_records if tag.name != "Open"],
                ),
            }
        )
        initial_values = {
            actions.EVENT_PREBLAST_TITLE: record.name,
            actions.EVENT_PREBLAST_LOCATION: str(record.location.id),
            actions.EVENT_PREBLAST_MOLESKINE_EDIT: record.preblast_rich or region_record.preblast_moleskin_template,
            # actions.EVENT_PREBLAST_TAG: safe_convert(getattr(record.event_tags, "id", None), str),
        }
        if record.event_tags:
            initial_values[actions.EVENT_PREBLAST_TAG] = str(
                record.event_tags[0].id
            )  # TODO: handle multiple event types and current data format
        coq_list = [
            r.slack_user.slack_id for r in preblast_info.attendance_records if 3 in [t.id for t in r.attendance_types]
        ]
        if coq_list:
            initial_values[actions.EVENT_PREBLAST_COQS] = coq_list

        form.set_initial_values(initial_values)
        title_text = "Edit Event Preblast"
        submit_button_text = "Update"
        # TODO: take out the send block if AO not associated with a channel
        if not preblast_channel or not view_id or preblast_info.event_record.preblast_ts:
            form.blocks = form.blocks[:-1]
        else:
            form.blocks[-1].label = f"When would you like to send the preblast to <#{preblast_channel}>?"
    else:
        blocks = [
            *preblast_info.preblast_blocks,
            orm.ActionsBlock(elements=preblast_info.action_blocks),
        ]
        if preblast_info.event_record.preblast_ts:
            blocks.append(
                orm.SectionBlock(
                    label=f"\n*This preblast has been posted, <slack://channel?team={body['team']['id']}&id={preblast_channel}&ts={preblast_info.event_record.preblast_ts}|check it out in the channel>*"  # noqa
                )
            )  # noqa

        form = orm.BlockView(blocks=blocks)
        title_text = "Event Preblast"
        submit_button_text = "None"

    metadata = {
        "event_id": event_id,
        "preblast_ts": str(preblast_info.event_record.preblast_ts),
    }

    if update_view_id:
        form.update_modal(
            client=client,
            view_id=update_view_id,
            title_text=title_text,
            submit_button_text=submit_button_text,
            parent_metadata=metadata,
            callback_id=actions.EVENT_PREBLAST_CALLBACK_ID,
        )
    else:
        if view_id:
            new_or_add = "add"
            callback_id = actions.EVENT_PREBLAST_CALLBACK_ID
        else:
            new_or_add = "new"
            callback_id = actions.EVENT_PREBLAST_POST_CALLBACK_ID
        form.post_modal(
            client=client,
            trigger_id=safe_get(body, "trigger_id"),
            callback_id=callback_id,
            title_text=title_text,
            submit_button_text=submit_button_text,
            new_or_add=new_or_add,
            parent_metadata=metadata,
        )


def handle_event_preblast_edit(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    form_data = EVENT_PREBLAST_FORM.get_selected_values(body)
    metadata = json.loads(safe_get(body, "view", "private_metadata") or "{}")
    event_id = safe_get(metadata, "event_id")
    callback_id = safe_get(body, "view", "callback_id")
    slack_user_id = safe_get(body, "user", "id") or safe_get(body, "user_id")
    update_fields = {
        Event.name: form_data[actions.EVENT_PREBLAST_TITLE],
        Event.location_id: form_data[actions.EVENT_PREBLAST_LOCATION],
        Event.preblast_rich: form_data[actions.EVENT_PREBLAST_MOLESKINE_EDIT],
    }
    DbManager.update_record(Event, event_id, update_fields)
    if form_data[actions.EVENT_PREBLAST_TAG]:
        DbManager.delete_records(
            cls=EventTag_x_Event,
            filters=[EventTag_x_Event.event_id == event_id],
        )
        DbManager.create_record(
            EventTag_x_Event(
                event_id=event_id,
                event_tag_id=form_data[actions.EVENT_PREBLAST_TAG],
            )
        )

    coq_list = safe_get(form_data, actions.EVENT_PREBLAST_COQS) or []
    user_ids = [get_user(slack_id, region_record, client, logger).user_id for slack_id in coq_list]
    # better way to upsert / on conflict do nothing?
    if user_ids:
        DbManager.delete_records(
            cls=Attendance,
            filters=[
                Attendance.event_id == event_id,
                Attendance.attendance_x_attendance_types.has(Attendance_x_AttendanceType.attendance_type_id == 3),
                Attendance.is_planned,
                Attendance.user_id.in_(user_ids),
            ],
            joinedloads=[Attendance.attendance_x_attendance_types],
        )
        new_records = [
            Attendance(
                event_id=event_id,
                user_id=user_id,
                attendance_x_attendance_types=[Attendance_x_AttendanceType(attendance_type_id=3)],
                is_planned=True,
            )
            for user_id in user_ids
        ]
        DbManager.create_records(new_records)

    if (
        form_data[actions.EVENT_PREBLAST_SEND_OPTIONS] == "Send now"
        or callback_id == actions.EVENT_PREBLAST_POST_CALLBACK_ID
        or safe_get(metadata, "preblast_ts")
    ):
        preblast_info = build_preblast_info(body, client, logger, context, region_record, event_id)
        blocks = [
            *preblast_info.preblast_blocks,
            orm.ActionsBlock(elements=PREBLAST_MESSAGE_ACTION_ELEMENTS),
        ]
        blocks = [b.as_form_field() for b in blocks]
        metadata = {
            "event_id": event_id,
            "attendees": [r.user.id for r in preblast_info.attendance_records],
            "qs": [
                r.user.id
                for r in preblast_info.attendance_records
                if bool({t.id for t in r.attendance_types}.intersection([2, 3]))
            ],
        }
        q_name, q_url = get_user_names([slack_user_id], logger, client, return_urls=True)
        q_name = (q_name or [""])[0]
        q_url = q_url[0]
        preblast_channel = get_preblast_channel(region_record, preblast_info)

        if preblast_info.event_record.preblast_ts or safe_get(metadata, "preblast_ts"):
            client.chat_update(
                channel=preblast_channel,
                ts=safe_get(metadata, "preblast_ts") or str(preblast_info.event_record.preblast_ts),
                blocks=blocks,
                text="Event Preblast",
                metadata={"event_type": "preblast", "event_payload": metadata},
                username=f"{q_name} (via F3 Nation)",
                icon_url=q_url,
            )
        else:
            res = client.chat_postMessage(
                channel=preblast_channel,
                blocks=blocks,
                text="Event Preblast",
                metadata={"event_type": "preblast", "event_payload": metadata},
                unfurl_links=False,
                username=f"{q_name} (via F3 Nation)",
                icon_url=q_url,
            )
            DbManager.update_record(Event, event_id, {Event.preblast_ts: float(res["ts"])})

    # elif form_data[actions.EVENT_PREBLAST_SEND_OPTIONS] == "Schedule 24 hours before event":
    #     pass  # schedule preblast
    else:
        pass


def build_preblast_info(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
    event_id: int,
) -> PreblastInfo:
    event_record: Event = DbManager.get(Event, event_id, joinedloads="all")
    attendance_records: List[Attendance] = DbManager.find_records(
        Attendance, [Attendance.event_id == event_id], joinedloads="all"
    )

    action_blocks = []
    hc_list = " ".join([f"<@{r.slack_user.slack_id}>" for r in attendance_records])
    hc_list = hc_list if hc_list else "None"
    hc_count = len({r.user.id for r in attendance_records})

    user_id = get_user(safe_get(body, "user", "id") or safe_get(body, "user_id"), region_record, client, logger).user_id
    user_is_q = any(
        r.user.id == user_id
        for r in attendance_records
        if bool({t.id for t in r.attendance_types}.intersection([2, 3]))
    )

    q_list = " ".join(
        [
            f"<@{r.slack_user.slack_id}>"
            for r in attendance_records
            if bool({t.id for t in r.attendance_types}.intersection([2, 3]))
        ]
    )
    if not q_list:
        q_list = "Open!"
        action_blocks.append(
            orm.ButtonElement(
                label="Take Q",
                action=actions.EVENT_PREBLAST_TAKE_Q,
                value=str(event_record.id),
            )
        )
    elif user_is_q:
        action_blocks.append(
            orm.ButtonElement(
                label="Remove Q",
                action=actions.EVENT_PREBLAST_REMOVE_Q,
                value=str(event_record.id),
            )
        )

    user_hc = any(r.user.id == user_id for r in attendance_records)
    if user_hc:
        action_blocks.append(
            orm.ButtonElement(
                label="Un-HC",
                action=actions.EVENT_PREBLAST_UN_HC,
                value=str(event_record.id),
            )
        )
    else:
        action_blocks.append(
            orm.ButtonElement(
                label="HC",
                action=actions.EVENT_PREBLAST_HC,
                value=str(event_record.id),
            )
        )

    location = ""
    if event_record.org.meta.get("slack_channel_id"):
        location += f"<#{event_record.org.meta['slack_channel_id']}> - "
    if event_record.location.lat and event_record.location.lon:
        location += f"<https://www.google.com/maps/search/?api=1&query={event_record.location.lat},{event_record.location.lon}|{event_record.location.name}>"
    else:
        location += event_record.location.name

    event_details = f"*Preblast: {event_record.name}*"
    event_details += f"\n*Date:* {event_record.start_date.strftime('%A, %B %d')}"
    event_details += f"\n*Time:* {event_record.start_time.strftime('%H%M')}"
    event_details += f"\n*Where:* {location}"
    event_details += f"\n*Event Type:* {' / '.join([t.name for t in event_record.event_types])}"
    if event_record.event_tags:
        event_details += f"\n*Event Tag:* {', '.join([tag.name for tag in event_record.event_tags])}"
    event_details += f"\n*Q:* {q_list}"
    event_details += f"\n*HC Count:* {hc_count}"
    event_details += f"\n*HCs:* {hc_list}"

    preblast_blocks = [
        orm.SectionBlock(label=event_details),
        orm.RichTextBlock(label=event_record.preblast_rich or DEFAULT_PREBLAST),
    ]
    return PreblastInfo(
        event_record=event_record,
        attendance_records=attendance_records,
        preblast_blocks=preblast_blocks,
        action_blocks=action_blocks,
        user_is_q=user_is_q,
    )


def handle_event_preblast_action(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    action_id = safe_get(body, "actions", 0, "action_id")
    metadata = json.loads(safe_get(body, "view", "private_metadata") or "{}") or safe_get(
        body, "message", "metadata", "event_payload"
    )
    event_id = safe_get(metadata, "event_id")
    slack_user_id = safe_get(body, "user", "id") or safe_get(body, "user_id")
    user_id = get_user(slack_user_id, region_record, client, logger).user_id
    view_id = safe_get(body, "view", "id")

    if view_id:
        if action_id == actions.EVENT_PREBLAST_HC:
            DbManager.create_record(
                Attendance(
                    event_id=event_id,
                    user_id=user_id,
                    attendance_x_attendance_types=[Attendance_x_AttendanceType(attendance_type_id=1)],
                    is_planned=True,
                )
            )
        elif action_id == actions.EVENT_PREBLAST_UN_HC:
            DbManager.delete_records(
                cls=Attendance,
                filters=[
                    Attendance.event_id == event_id,
                    Attendance.user_id == user_id,
                    Attendance.is_planned,
                    Attendance.attendance_x_attendance_types.has(Attendance_x_AttendanceType.attendance_type_id == 1),
                ],
                joinedloads=[Attendance.attendance_x_attendance_types],
            )
        elif action_id == actions.EVENT_PREBLAST_TAKE_Q:
            DbManager.create_record(
                Attendance(
                    event_id=event_id,
                    user_id=user_id,
                    attendance_x_attendance_types=[Attendance_x_AttendanceType(attendance_type_id=2)],
                    is_planned=True,
                )
            )
        elif action_id == actions.EVENT_PREBLAST_REMOVE_Q:
            DbManager.delete_records(
                cls=Attendance,
                filters=[
                    Attendance.event_id == event_id,
                    Attendance.user_id == user_id,
                    Attendance.attendance_x_attendance_types.any(
                        Attendance_x_AttendanceType.attendance_type_id.in_([2, 3])
                    ),
                    Attendance.is_planned,
                ],
                joinedloads=[Attendance.attendance_x_attendance_types],
            )
        if metadata.get("preblast_ts"):
            preblast_info = build_preblast_info(body, client, logger, context, region_record, event_id)
            blocks = [
                *preblast_info.preblast_blocks,
                orm.ActionsBlock(elements=PREBLAST_MESSAGE_ACTION_ELEMENTS),
            ]
            blocks = [b.as_form_field() for b in blocks]

            q_name, q_url = get_user_names([slack_user_id], logger, client, return_urls=True)
            q_name = (q_name or [""])[0]
            q_url = q_url[0]
            preblast_channel = get_preblast_channel(region_record, preblast_info)
            client.chat_update(
                channel=preblast_channel,
                ts=metadata["preblast_ts"],
                blocks=blocks,
                text="Event Preblast",
                metadata={"event_type": "preblast", "event_payload": metadata},
                username=f"{q_name} (via F3 Nation)",
                icon_url=q_url,
            )
        build_event_preblast_form(
            body, client, logger, context, region_record, event_id=event_id, update_view_id=view_id
        )
    else:
        if action_id == actions.EVENT_PREBLAST_HC_UN_HC:
            already_hcd = user_id in metadata["attendees"]
            if already_hcd:
                DbManager.delete_records(
                    cls=Attendance,
                    filters=[
                        Attendance.event_id == event_id,
                        Attendance.user_id == user_id,
                        Attendance.attendance_types.any(AttendanceType.id == 1),
                        Attendance.is_planned,
                    ],
                    joinedloads=[Attendance.attendance_types],
                )
            else:
                DbManager.create_record(
                    Attendance(
                        event_id=event_id,
                        user_id=user_id,
                        attendance_x_attendance_types=[Attendance_x_AttendanceType(attendance_type_id=1)],
                        is_planned=True,
                    )
                )
            preblast_info = build_preblast_info(body, client, logger, context, region_record, event_id)
            metadata = {
                "event_id": event_id,
                "attendees": [r.user.id for r in preblast_info.attendance_records],
                "qs": [
                    r.user.id
                    for r in preblast_info.attendance_records
                    if bool({t.id for t in r.attendance_types}.intersection([2, 3]))
                ],
            }
            blocks = [*preblast_info.preblast_blocks, orm.ActionsBlock(elements=PREBLAST_MESSAGE_ACTION_ELEMENTS)]
            q_name, q_url = get_user_names([slack_user_id], logger, client, return_urls=True)
            q_name = (q_name or [""])[0]
            q_url = q_url[0]
            preblast_channel = get_preblast_channel(region_record, preblast_info)
            client.chat_update(
                channel=preblast_channel,
                ts=body["message"]["ts"],
                blocks=[b.as_form_field() for b in blocks],
                text="Preblast",
                metadata={"event_type": "preblast", "event_payload": metadata},
                username=f"{q_name} (via F3 Nation)",
                icon_url=q_url,
            )
        elif action_id == actions.EVENT_PREBLAST_EDIT:
            if user_id in metadata["qs"]:
                build_event_preblast_form(body, client, logger, context, region_record, event_id=event_id)
            else:
                client.chat_postEphemeral(
                    channel=body["channel"]["id"],
                    user=slack_user_id,
                    text=":warning: Only Qs can edit the preblast! :warning:",
                )
        elif action_id == actions.MSG_EVENT_PREBLAST_BUTTON:
            event_id = safe_convert(body["actions"][0]["value"], int)
            build_event_preblast_form(body, client, logger, context, region_record, event_id=event_id)


DEFAULT_PREBLAST = {
    "type": "rich_text",
    "elements": [{"type": "rich_text_section", "elements": [{"text": "No preblast text entered", "type": "text"}]}],
}

EVENT_PREBLAST_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="Title",
            action=actions.EVENT_PREBLAST_TITLE,
            element=orm.PlainTextInputElement(
                placeholder="Event Title",
            ),
            optional=False,
            hint="Studies show that fun titles generate 42% more HC's!",
        ),
        orm.InputBlock(
            label="Location",
            action=actions.EVENT_PREBLAST_LOCATION,
            element=orm.StaticSelectElement(),
            optional=False,
        ),
        orm.InputBlock(
            label="Co-Qs",
            action=actions.EVENT_PREBLAST_COQS,
            element=orm.MultiUsersSelectElement(placeholder="Select Co-Qs"),
            optional=True,
        ),
        orm.InputBlock(
            label="Event Tag",
            action=actions.EVENT_PREBLAST_TAG,
            element=orm.StaticSelectElement(placeholder="Select Event Tag"),
            optional=True,
        ),
        orm.InputBlock(
            label="Preblast",
            action=actions.EVENT_PREBLAST_MOLESKINE_EDIT,
            element=orm.RichTextInputElement(placeholder="Give us an event preview!"),
            optional=False,
        ),
        orm.InputBlock(
            label="When to send preblast?",
            action=actions.EVENT_PREBLAST_SEND_OPTIONS,
            element=orm.RadioButtonsElement(
                options=orm.as_selector_options(
                    names=["Send now", "Do not send now"],
                ),
            ),
            optional=False,
        ),
    ]
)
