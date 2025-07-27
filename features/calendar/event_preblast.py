import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from logging import Logger
from typing import List

from f3_data_models.models import (
    Attendance,
    Attendance_x_AttendanceType,
    AttendanceType,
    EventInstance,
    EventTag,
    EventTag_x_EventInstance,
    Location,
    Org,
)
from f3_data_models.utils import DbManager
from slack_sdk.web import WebClient
from sqlalchemy import or_

from features import preblast_legacy
from features.calendar import PREBLAST_MESSAGE_ACTION_ELEMENTS
from utilities import constants
from utilities.database.orm import SlackSettings
from utilities.database.special_queries import event_attendance_query
from utilities.helper_functions import (
    current_date_cst,
    get_user,
    get_user_names,
    parse_rich_block,
    replace_user_channel_ids,
    safe_convert,
    safe_get,
)
from utilities.slack import actions, orm


@dataclass
class PreblastInfo:
    event_record: EventInstance
    attendance_records: list[Attendance]
    preblast_blocks: list[orm.BaseBlock]
    action_blocks: list[orm.BaseElement]
    user_is_q: bool = False
    attendance_slack_dict: dict[Attendance, str] = None


def get_preblast_channel(region_record: SlackSettings, preblast_info: PreblastInfo) -> str:
    if (
        region_record.default_preblast_destination == constants.CONFIG_DESTINATION_SPECIFIED["value"]
        and region_record.preblast_destination_channel
    ):
        return region_record.preblast_destination_channel
    return preblast_info.event_record.org.meta.get("slack_channel_id")


def preblast_middleware(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
):
    if (
        region_record.org_id is None
        or (safe_convert(region_record.migration_date, datetime.strptime, args=["%Y-%m-%d"]) or datetime.now())
        > datetime.now()
    ):
        preblast_legacy.build_preblast_form(body, client, logger, context, region_record)
    else:
        build_event_preblast_select_form(body, client, logger, context, region_record)


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
            EventInstance.start_date >= current_date_cst(),
            EventInstance.preblast_ts.is_(None),
            EventInstance.is_active,
            or_(
                EventInstance.org_id == region_record.org_id,
                EventInstance.org.has(Org.parent_id == region_record.org_id),
            ),
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
    event_instance_id = safe_get(body, "actions", 0, "selected_option", "value")
    view_id = safe_get(body, "view", "id")
    build_event_preblast_form(
        body, client, logger, context, region_record, event_instance_id=int(event_instance_id), update_view_id=view_id
    )


def build_event_preblast_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
    event_instance_id: int = None,
    update_view_id: str = None,
):
    preblast_info = build_preblast_info(body, client, logger, context, region_record, event_instance_id)
    record = preblast_info.event_record
    view_id = safe_get(body, "view", "id")
    action_value = safe_get(body, "actions", 0, "value") or safe_get(body, "actions", 0, "selected_option", "value")

    preblast_channel = get_preblast_channel(region_record, preblast_info)
    if action_value == "Edit Preblast" or preblast_info.user_is_q:
        form = deepcopy(EVENT_PREBLAST_FORM)

        location_records: list[Location] = DbManager.find_records(Location, [Location.org_id == region_record.org_id])
        event_tags: list[EventTag] = DbManager.find_records(
            EventTag, [or_(EventTag.specific_org_id == region_record.org_id, EventTag.specific_org_id.is_(None))]
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
                    names=[tag.name for tag in event_tags if tag.name != "Open"],
                    values=[str(tag.id) for tag in event_tags if tag.name != "Open"],
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
            initial_values[actions.EVENT_PREBLAST_TAG] = [
                str(record.event_tags[0].id)
            ]  # TODO: handle multiple event types and current data format
        coq_list = [
            s for a, s in preblast_info.attendance_slack_dict.items() if 3 in [t.id for t in a.attendance_types]
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
        form.blocks.append(orm.ActionsBlock(elements=preblast_info.action_blocks))
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
        "event_instance_id": event_instance_id,
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
    event_instance_id = safe_get(metadata, "event_instance_id")
    callback_id = safe_get(body, "view", "callback_id")
    update_fields = {
        EventInstance.name: form_data[actions.EVENT_PREBLAST_TITLE],
        EventInstance.location_id: form_data[actions.EVENT_PREBLAST_LOCATION],
        EventInstance.preblast_rich: form_data[actions.EVENT_PREBLAST_MOLESKINE_EDIT],
        EventInstance.preblast: replace_user_channel_ids(
            parse_rich_block(form_data[actions.EVENT_PREBLAST_MOLESKINE_EDIT]),
            region_record,
            client,
            logger,
        ),
    }
    DbManager.update_record(EventInstance, event_instance_id, update_fields)
    if form_data[actions.EVENT_PREBLAST_TAG]:
        DbManager.delete_records(
            cls=EventTag_x_EventInstance,
            filters=[EventTag_x_EventInstance.event_instance_id == event_instance_id],
        )
        DbManager.create_record(
            EventTag_x_EventInstance(
                event_instance_id=event_instance_id,
                event_tag_id=safe_get(form_data, actions.EVENT_PREBLAST_TAG, 0),
            )
        )

    coq_list = safe_get(form_data, actions.EVENT_PREBLAST_COQS) or []
    user_ids = [get_user(slack_id, region_record, client, logger).user_id for slack_id in coq_list]
    # better way to upsert / on conflict do nothing?
    if user_ids:
        DbManager.delete_records(
            cls=Attendance,
            filters=[
                Attendance.event_instance_id == event_instance_id,
                Attendance.attendance_x_attendance_types.any(Attendance_x_AttendanceType.attendance_type_id == 3),
                Attendance.is_planned,
                Attendance.user_id.in_(user_ids),
            ],
            joinedloads=[Attendance.attendance_x_attendance_types],
        )
        new_records = [
            Attendance(
                event_instance_id=event_instance_id,
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
        or (safe_get(metadata, "preblast_ts") or "None") != "None"
    ):
        send_preblast(
            body,
            client,
            logger,
            context,
            region_record,
            event_instance_id,
        )

    # elif form_data[actions.EVENT_PREBLAST_SEND_OPTIONS] == "Schedule 24 hours before event":
    #     pass  # schedule preblast
    else:
        pass


def send_preblast(
    body: dict = None,
    client: WebClient = None,
    logger: Logger = None,
    context: dict = None,
    region_record: SlackSettings = None,
    event_instance_id: int = None,
):
    slack_user_id = safe_get(body, "user", "id") or safe_get(body, "user_id")
    preblast_info = build_preblast_info(body, client, logger, context, region_record, event_instance_id)
    blocks = [
        *preblast_info.preblast_blocks,
        orm.ActionsBlock(elements=PREBLAST_MESSAGE_ACTION_ELEMENTS),
    ]
    blocks = [b.as_form_field() for b in blocks]
    metadata = {
        "event_instance_id": event_instance_id,
        "attendees": [r.user.id for r in preblast_info.attendance_records],
        "qs": [
            r.user.id
            for r in preblast_info.attendance_records
            if bool({t.id for t in r.attendance_types}.intersection([2, 3]))
        ],
    }
    if not body:
        # this will happen if called outside a user interaction
        username = None
        icon_url = None
    else:
        q_name, q_url = get_user_names([slack_user_id], logger, client, return_urls=True)
        q_name = (q_name or [""])[0]
        q_url = q_url[0]
        username = f"{q_name} (via F3 Nation)"
        icon_url = q_url
    preblast_channel = get_preblast_channel(region_record, preblast_info)

    if preblast_info.event_record.preblast_ts or safe_get(metadata, "preblast_ts"):
        client.chat_update(
            channel=preblast_channel,
            ts=safe_get(metadata, "preblast_ts") or str(preblast_info.event_record.preblast_ts),
            blocks=blocks,
            text="Event Preblast",
            metadata={"event_type": "preblast", "event_payload": metadata},
            username=username,
            icon_url=icon_url,
        )
    else:
        res = client.chat_postMessage(
            channel=preblast_channel,
            blocks=blocks,
            text="Event Preblast",
            metadata={"event_type": "preblast", "event_payload": metadata},
            unfurl_links=False,
            username=username,
            icon_url=icon_url,
        )
        DbManager.update_record(EventInstance, event_instance_id, {EventInstance.preblast_ts: float(res["ts"])})


def build_preblast_info(
    body: dict = None,
    client: WebClient = None,
    logger: Logger = None,
    context: dict = None,
    region_record: SlackSettings = None,
    event_instance_id: int = None,
) -> PreblastInfo:
    event_record: EventInstance = DbManager.get(EventInstance, event_instance_id, joinedloads="all")
    attendance_records: List[Attendance] = DbManager.find_records(
        Attendance, [Attendance.event_instance_id == event_instance_id, Attendance.is_planned], joinedloads="all"
    )
    attendance_slack_dict = {
        r: next((s.slack_id for s in (r.slack_users or []) if s.slack_team_id == region_record.team_id), None)
        for r in attendance_records
    }

    action_blocks = []
    # build list of attenance_slack_dict where the value is not None
    hc_list = " ".join([f"<@{s}>" for a, s in attendance_slack_dict.items() if s is not None])
    hc_list += " ".join([f"@{a.user.f3_name or 'Unknown'}" for a, s in attendance_slack_dict.items() if s is None])
    hc_list = hc_list if hc_list else "None"
    hc_count = len({r.user.id for r in attendance_records})

    if not body:
        # this will happen if called outside a user interaction
        user_id = None
        user_is_q = False
    else:
        user_id = get_user(
            safe_get(body, "user", "id") or safe_get(body, "user_id"), region_record, client, logger
        ).user_id
        user_is_q = any(
            r.user.id == user_id
            for r in attendance_records
            if bool({t.id for t in r.attendance_types}.intersection([2, 3]))
        )

    q_list = " ".join(
        [
            f"<@{attendance_slack_dict[r]}>"
            for r in attendance_records
            if bool({t.id for t in r.attendance_types}.intersection([2, 3])) and attendance_slack_dict[r]
        ]
    )
    q_list += " ".join(
        [
            f"@{r.user.f3_name or 'Unknown'}"
            for r in attendance_records
            if bool({t.id for t in r.attendance_types}.intersection([2, 3])) and not attendance_slack_dict[r]
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
                label="Take myself off Q",
                action=actions.EVENT_PREBLAST_REMOVE_Q,
                value=str(event_record.id),
            )
        )

    user_hc = any(r.user.id == user_id for r in attendance_records)
    if user_hc:
        if not user_is_q:
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
    if event_record.location.latitude and event_record.location.longitude:
        location += f"<https://www.google.com/maps/search/?api=1&query={event_record.location.latitude},{event_record.location.longitude}|{event_record.location.name}>"
    else:
        location += event_record.location.name

    event_details = f"*Preblast: {event_record.name}*"
    event_details += f"\n*Date:* {event_record.start_date.strftime('%A, %B %d')}"
    event_details += f"\n*Time:* {event_record.start_time}"
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
        attendance_slack_dict=attendance_slack_dict,
    )


def handle_event_preblast_action(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    action_id = safe_get(body, "actions", 0, "action_id")
    metadata = json.loads(safe_get(body, "view", "private_metadata") or "{}") or safe_get(
        body, "message", "metadata", "event_payload"
    )
    event_instance_id = safe_get(metadata, "event_instance_id")
    slack_user_id = safe_get(body, "user", "id") or safe_get(body, "user_id")
    user_id = get_user(slack_user_id, region_record, client, logger).user_id
    view_id = safe_get(body, "view", "id")

    if view_id:
        if action_id == actions.EVENT_PREBLAST_HC:
            DbManager.create_record(
                Attendance(
                    event_instance_id=event_instance_id,
                    user_id=user_id,
                    attendance_x_attendance_types=[Attendance_x_AttendanceType(attendance_type_id=1)],
                    is_planned=True,
                )
            )
        elif action_id == actions.EVENT_PREBLAST_UN_HC:
            DbManager.delete_records(
                cls=Attendance,
                filters=[
                    Attendance.event_instance_id == event_instance_id,
                    Attendance.user_id == user_id,
                    Attendance.is_planned,
                    Attendance.attendance_x_attendance_types.has(Attendance_x_AttendanceType.attendance_type_id == 1),
                ],
                joinedloads=[Attendance.attendance_x_attendance_types],
            )
        elif action_id == actions.EVENT_PREBLAST_TAKE_Q:
            DbManager.delete_records(
                cls=Attendance,
                filters=[
                    Attendance.event_instance_id == event_instance_id,
                    Attendance.user_id == user_id,
                    Attendance.is_planned,
                ],
                joinedloads=[Attendance.attendance_x_attendance_types],
            )
            DbManager.create_record(
                Attendance(
                    event_instance_id=event_instance_id,
                    user_id=user_id,
                    attendance_x_attendance_types=[Attendance_x_AttendanceType(attendance_type_id=2)],
                    is_planned=True,
                )
            )
        elif action_id == actions.EVENT_PREBLAST_REMOVE_Q:
            DbManager.delete_records(
                cls=Attendance,
                filters=[
                    Attendance.event_instance_id == event_instance_id,
                    Attendance.user_id == user_id,
                    Attendance.attendance_x_attendance_types.any(
                        Attendance_x_AttendanceType.attendance_type_id.in_([2, 3])
                    ),
                    Attendance.is_planned,
                ],
                joinedloads=[Attendance.attendance_x_attendance_types],
            )
        if metadata.get("preblast_ts") and metadata["preblast_ts"] != "None":
            preblast_info = build_preblast_info(body, client, logger, context, region_record, event_instance_id)
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
            body, client, logger, context, region_record, event_instance_id=event_instance_id, update_view_id=view_id
        )
    else:
        if action_id == actions.EVENT_PREBLAST_HC_UN_HC:
            already_hcd = user_id in (safe_get(metadata, "attendees") or [])
            if already_hcd:
                DbManager.delete_records(
                    cls=Attendance,
                    filters=[
                        Attendance.event_instance_id == event_instance_id,
                        Attendance.user_id == user_id,
                        Attendance.attendance_types.any(AttendanceType.id == 1),
                        Attendance.is_planned,
                    ],
                    joinedloads=[Attendance.attendance_types],
                )
            else:
                DbManager.create_record(
                    Attendance(
                        event_instance_id=event_instance_id,
                        user_id=user_id,
                        attendance_x_attendance_types=[Attendance_x_AttendanceType(attendance_type_id=1)],
                        is_planned=True,
                    )
                )
            preblast_info = build_preblast_info(body, client, logger, context, region_record, event_instance_id)
            q_id_list = [
                r.user.id
                for r in preblast_info.attendance_records
                if bool({t.id for t in r.attendance_types}.intersection([2, 3]))
            ]
            metadata = {
                "event_instance_id": event_instance_id,
                "attendees": [r.user.id for r in preblast_info.attendance_records],
                "qs": q_id_list,
            }
            button_blocks = PREBLAST_MESSAGE_ACTION_ELEMENTS
            # if not q_id_list:
            #     button_blocks.append(
            #         orm.ButtonElement(
            #             ":raising_hand: Take Q", action=actions.EVENT_PREBLAST_TAKE_Q, value=str(event_instance_id)
            #         )
            #     )
            blocks = [*preblast_info.preblast_blocks, orm.ActionsBlock(elements=button_blocks)]
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
                build_event_preblast_form(
                    body, client, logger, context, region_record, event_instance_id=event_instance_id
                )
            else:
                client.chat_postEphemeral(
                    channel=body["channel"]["id"],
                    user=slack_user_id,
                    text=":warning: Only Qs can edit the preblast! :warning:",
                )
        elif action_id == actions.MSG_EVENT_PREBLAST_BUTTON:
            event_instance_id = safe_convert(body["actions"][0]["value"], int)
            build_event_preblast_form(body, client, logger, context, region_record, event_instance_id=event_instance_id)
        elif action_id == actions.EVENT_PREBLAST_TAKE_Q:
            event_instance_id = safe_convert(body["actions"][0]["value"], int)
            DbManager.delete_records(
                cls=Attendance,
                filters=[
                    Attendance.event_instance_id == event_instance_id,
                    Attendance.user_id == user_id,
                    Attendance.is_planned,
                ],
                joinedloads=[Attendance.attendance_x_attendance_types],
            )
            DbManager.create_record(
                Attendance(
                    event_instance_id=event_instance_id,
                    user_id=user_id,
                    attendance_x_attendance_types=[Attendance_x_AttendanceType(attendance_type_id=2)],
                    is_planned=True,
                )
            )
            build_event_preblast_form(body, client, logger, context, region_record, event_instance_id=event_instance_id)


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
            element=orm.MultiStaticSelectElement(placeholder="Select Event Tag", max_selected_items=1),
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
                    names=["Send now", "Send a day before the event"],
                ),
                initial_value="Send a day before the event",
            ),
            optional=False,
        ),
    ]
)
