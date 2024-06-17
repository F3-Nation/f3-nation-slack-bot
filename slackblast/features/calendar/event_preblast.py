import json
from copy import deepcopy
from dataclasses import dataclass
from logging import Logger

from slack_sdk.web import WebClient

from utilities.database import DbManager, get_session
from utilities.database.orm import AttendanceNew, Event, EventType, Location, Org, Region, SlackUser, UserNew
from utilities.helper_functions import get_user_id, safe_get, time_int_to_str
from utilities.slack import actions, orm


@dataclass
class EventExtended:
    event: Event
    org: Org
    event_type: EventType
    location: Location


@dataclass
class AttendanceExtended:
    attendance: AttendanceNew
    user: UserNew
    slack_user: SlackUser


@dataclass
class PreblastInfo:
    event_extended: EventExtended
    attendance_records: list[AttendanceExtended]
    preblast_blocks: list[orm.BaseBlock]
    action_blocks: list[orm.BaseElement]
    user_is_q: bool = False


def event_preblast_query(event_id: int) -> tuple[EventExtended, list[AttendanceExtended]]:
    with get_session() as session:
        query = (
            session.query(Event, Org, EventType, Location)
            .select_from(Event)
            .join(Org, Org.id == Event.org_id)
            .join(EventType, EventType.id == Event.event_type_id)
            .join(Location, Location.id == Event.location_id)
            .filter(Event.id == event_id)
        )
        record = EventExtended(*query.one_or_none())

        query = (
            session.query(AttendanceNew, UserNew, SlackUser)
            .select_from(AttendanceNew)
            .join(UserNew)
            .join(SlackUser)
            .filter(AttendanceNew.event_id == event_id, AttendanceNew.is_planned)
        )
        attendance_records = [AttendanceExtended(*r) for r in query.all()]

    return record, attendance_records


def build_event_preblast_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: Region,
    event_id: int = None,
    update_view_id: str = None,
):
    preblast_info = build_preblast_info(body, client, logger, context, region_record, event_id)
    record = preblast_info.event_extended

    if safe_get(body, "actions", 0, "selected_option", "value") == "Edit Preblast" or preblast_info.user_is_q:
        form = deepcopy(EVENT_PREBLAST_FORM)

        location_records: list[Location] = DbManager.find_records(Location, [Location.org_id == region_record.org_id])
        # TODO: filter locations to AO?
        # TODO: show hardcoded details (date, time, etc.)
        form.set_options(
            {
                actions.EVENT_PREBLAST_LOCATION: orm.as_selector_options(
                    names=[location.name for location in location_records],
                    values=[str(location.id) for location in location_records],
                ),
            }
        )
        initial_values = {
            actions.EVENT_PREBLAST_TITLE: record.event.name,
            actions.EVENT_PREBLAST_LOCATION: str(record.location.id),
            actions.EVENT_PREBLAST_MOLESKINE_EDIT: record.event.preblast_rich,
        }
        coq_list = [
            r.slack_user.slack_id for r in preblast_info.attendance_records if r.attendance.attendance_type_id == 3
        ]
        if coq_list:
            initial_values[actions.EVENT_PREBLAST_COQS] = coq_list

        form.set_initial_values(initial_values)
        title_text = "Edit Event Preblast"
        submit_button_text = "Update"
        # TODO: take out the send block if AO not associated with a channel
        if not record.org.slack_id:
            form.blocks = form.blocks[:-1]
        else:
            form.blocks[-1].label = f"When would you like to send the preblast to <#{record.org.slack_id}>?"
    else:
        blocks = [
            *preblast_info.preblast_blocks,
            orm.ActionsBlock(elements=preblast_info.action_blocks),
        ]

        form = orm.BlockView(blocks=blocks)
        title_text = "Event Preblast"
        submit_button_text = "None"

    metadata = {
        "event_id": event_id,
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
        form.post_modal(
            client=client,
            trigger_id=safe_get(body, "trigger_id"),
            callback_id=actions.EVENT_PREBLAST_CALLBACK_ID,
            title_text=title_text,
            submit_button_text=submit_button_text,
            new_or_add="add",
            parent_metadata=metadata,
        )


def handle_event_preblast_edit(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    form_data = EVENT_PREBLAST_FORM.get_selected_values(body)
    metadata = json.loads(safe_get(body, "view", "private_metadata") or "{}")
    event_id = safe_get(metadata, "event_id")
    update_fields = {
        Event.name: form_data[actions.EVENT_PREBLAST_TITLE],
        Event.location_id: form_data[actions.EVENT_PREBLAST_LOCATION],
        Event.preblast_rich: form_data[actions.EVENT_PREBLAST_MOLESKINE_EDIT],
    }
    DbManager.update_record(Event, event_id, update_fields)

    coq_list = safe_get(form_data, actions.EVENT_PREBLAST_COQS) or []
    print(coq_list)
    user_ids = [get_user_id(slack_id, region_record, client, logger) for slack_id in coq_list]
    # better way to upsert / on conflict do nothing?
    DbManager.delete_records(
        cls=AttendanceNew,
        filters=[
            AttendanceNew.event_id == event_id,
            AttendanceNew.attendance_type_id == 3,
            AttendanceNew.is_planned,
            AttendanceNew.user_id.in_(user_ids),
        ],
    )
    new_records = [
        AttendanceNew(
            event_id=event_id,
            user_id=user_id,
            attendance_type_id=3,
            is_planned=True,
        )
        for user_id in user_ids
    ]
    DbManager.create_records(new_records)

    if form_data[actions.EVENT_PREBLAST_SEND_OPTIONS] == "Send now":
        preblast_info = build_preblast_info(body, client, logger, context, region_record, event_id)
        blocks = [
            *preblast_info.preblast_blocks,
            orm.ActionsBlock(
                elements=[
                    orm.ButtonElement(label="Edit Preblast", action=actions.EVENT_PREBLAST_EDIT),
                    orm.ButtonElement(label="HC/Un-HC", action=actions.EVENT_PREBLAST_HC_UN_HC),
                ]
            ),
        ]
        blocks = [b.as_form_field() for b in blocks]
        res = client.chat_postMessage(
            channel=preblast_info.event_extended.org.slack_id,
            blocks=blocks,
            text="Event Preblast",
        )
        DbManager.update_record(Event, event_id, {Event.preblast_ts: float(res["ts"])})

    elif form_data[actions.EVENT_PREBLAST_SEND_OPTIONS] == "Schedule 24 hours before event":
        pass  # schedule preblast
    else:
        pass


def build_preblast_info(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: Region,
    event_id: int,
) -> PreblastInfo:
    event_record, attendance_records = event_preblast_query(event_id)

    action_blocks = []
    hc_list = " ".join([f"<@{r.slack_user.slack_id}>" for r in attendance_records])
    hc_list = hc_list if hc_list else "None"
    hc_count = len({r.user.id for r in attendance_records})

    user_id = get_user_id(safe_get(body, "user", "id") or safe_get(body, "user_id"), region_record, client, logger)
    user_is_q = any(r.user.id == user_id for r in attendance_records if r.attendance.attendance_type_id in [2, 3])

    q_list = " ".join(
        [f"<@{r.slack_user.slack_id}>" for r in attendance_records if r.attendance.attendance_type_id in [2, 3]]
    )
    if not q_list:
        q_list = "Open!"
        action_blocks.append(
            orm.ButtonElement(
                label="Take Q",
                action=actions.EVENT_PREBLAST_TAKE_Q,
                value=str(event_record.event.id),
            )
        )
    elif user_is_q:
        action_blocks.append(
            orm.ButtonElement(
                label="Remove Q",
                action=actions.EVENT_PREBLAST_REMOVE_Q,
                value=str(event_record.event.id),
            )
        )

    user_hc = any(r.user.id == user_id for r in attendance_records)
    if user_hc:
        action_blocks.append(
            orm.ButtonElement(
                label="Un-HC",
                action=actions.EVENT_PREBLAST_UN_HC,
                value=str(event_record.event.id),
            )
        )
    else:
        action_blocks.append(
            orm.ButtonElement(
                label="HC",
                action=actions.EVENT_PREBLAST_HC,
                value=str(event_record.event.id),
            )
        )

    location = ""
    if event_record.org.slack_id:
        location += f"<#{event_record.org.slack_id}> - "
    if event_record.location.lat and event_record.location.lon:
        location += f"<https://www.google.com/maps/search/?api=1&query={event_record.location.lat},{event_record.location.lon}|{event_record.location.name}>"
    else:
        location += event_record.location.name

    event_details = f"*Preblast: {event_record.event.name}*"
    event_details += f"\n*Date:* {event_record.event.start_date.strftime('%A, %B %d')}"
    event_details += f"\n*Start Time:* {time_int_to_str(event_record.event.start_time)}"
    event_details += f"\n*Where:* {location}"
    event_details += f"\n*Event Type:* {event_record.event_type.name}"
    event_details += f"\n*Q:* {q_list}"
    event_details += f"\n*HC Count:* {hc_count}"
    event_details += f"\n*HCs:* {hc_list}"

    preblast_blocks = [
        orm.SectionBlock(label=event_details),
        orm.RichTextBlock(label=event_record.event.preblast_rich or DEFAULT_PREBLAST),
    ]
    return PreblastInfo(
        event_extended=event_record,
        attendance_records=attendance_records,
        preblast_blocks=preblast_blocks,
        action_blocks=action_blocks,
        user_is_q=user_is_q,
    )


def handle_event_preblast_action(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    action_id = safe_get(body, "actions", 0, "action_id")
    metadata = json.loads(safe_get(body, "view", "private_metadata") or "{}")
    event_id = safe_get(metadata, "event_id")
    user_id = get_user_id(safe_get(body, "user", "id") or safe_get(body, "user_id"), region_record, client, logger)
    view_id = safe_get(body, "view", "id")

    if action_id == actions.EVENT_PREBLAST_HC:
        DbManager.create_record(
            AttendanceNew(
                event_id=event_id,
                user_id=user_id,
                attendance_type_id=1,
                is_planned=True,
            )
        )
    elif action_id == actions.EVENT_PREBLAST_UN_HC:
        DbManager.delete_records(
            cls=AttendanceNew,
            filters=[
                AttendanceNew.event_id == event_id,
                AttendanceNew.user_id == user_id,
                AttendanceNew.attendance_type_id == 1,
                AttendanceNew.is_planned,
            ],
        )
    elif action_id == actions.EVENT_PREBLAST_TAKE_Q:
        DbManager.create_record(
            AttendanceNew(
                event_id=event_id,
                user_id=user_id,
                attendance_type_id=2,
                is_planned=True,
            )
        )
    elif action_id == actions.EVENT_PREBLAST_REMOVE_Q:
        DbManager.delete_records(
            cls=AttendanceNew,
            filters=[
                AttendanceNew.event_id == event_id,
                AttendanceNew.user_id == user_id,
                AttendanceNew.attendance_type_id.in_([2, 3]),
                AttendanceNew.is_planned,
            ],
        )
    build_event_preblast_form(body, client, logger, context, region_record, event_id=event_id, update_view_id=view_id)


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
                    names=["Send now", "Schedule 24 hours before event", "Do not send"],
                ),
            ),
            optional=False,
        ),
    ]
)
