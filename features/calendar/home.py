import copy
import datetime
import json
import time
from logging import Logger
from typing import List

import pytz
import requests
from f3_data_models.models import (
    Attendance,
    Attendance_x_AttendanceType,
    EventInstance,
    EventType,
    Org,
    Org_Type,
)
from f3_data_models.utils import DbManager
from slack_sdk.web import WebClient
from sqlalchemy import or_

from features.calendar import PREBLAST_MESSAGE_ACTION_ELEMENTS, event_instance
from features.calendar.event_preblast import (
    build_event_preblast_form,
    build_preblast_info,
    get_preblast_channel,
)
from utilities.constants import GCP_IMAGE_URL, LOCAL_DEVELOPMENT, S3_IMAGE_URL
from utilities.database.orm import SlackSettings
from utilities.database.special_queries import CalendarHomeQuery, get_admin_users, home_schedule_query
from utilities.helper_functions import get_user, safe_convert, safe_get
from utilities.slack import actions, orm


def handle_event_preblast_select_button(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    action = safe_get(body, "actions", 0, "action_id")
    view_id = safe_get(body, "view", "id")
    if action == actions.EVENT_PREBLAST_NEW_BUTTON:
        event_instance.build_event_instance_add_form(body, client, logger, context, region_record, new_preblast=True)
    elif action == actions.OPEN_CALENDAR_BUTTON:
        build_home_form(body, client, logger, context, region_record, update_view_id=view_id)


def build_home_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
    update_view_id: str = None,
):
    action_id = safe_get(body, "actions", 0, "action_id")
    if action_id == actions.CALENDAR_HOME_DATE_FILTER and not safe_get(body, "actions", 0, "selected_date"):
        return
    slack_user_id = safe_get(body, "user", "id") or safe_get(body, "user_id")
    user_id = get_user(slack_user_id, region_record, client, logger).user_id

    metadata = safe_convert(safe_get(body, "view", "metadata", "event_payload"), json.loads) or {}
    user_is_admin = safe_get(metadata, "user_is_admin")
    if user_is_admin is None:
        admin_users = get_admin_users(region_record.org_id, region_record.team_id)
        user_is_admin = any(u[0].id == user_id for u in admin_users)
        metadata["user_is_admin"] = user_is_admin

    start_time = time.time()
    ao_records = DbManager.find_records(
        Org, filters=[Org.parent_id == region_record.org_id, Org.org_type == Org_Type.ao, Org.is_active.is_(True)]
    )
    event_type_records: List[EventType] = DbManager.find_records(
        EventType,
        filters=[or_(EventType.specific_org_id == region_record.org_id, EventType.specific_org_id.is_(None))],
    )
    split_time = time.time()
    print(f"AO and Event Type time: {split_time - start_time}")
    start_time = time.time()

    # if LOCAL_DEVELOPMENT:
    #     this_week_url = S3_IMAGE_URL.format(
    #         image_name=region_record.calendar_image_current or "default.png",
    #     )
    #     next_week_url = S3_IMAGE_URL.format(
    #         image_name=region_record.calendar_image_next or "default.png",
    #     )
    # else:
    #     this_week_url = GCP_IMAGE_URL.format(
    #         bucket="f3nation-calendar-images",
    #         image_name=region_record.calendar_image_current or "default.png",
    #     )
    #     next_week_url = GCP_IMAGE_URL.format(
    #         bucket="f3nation-calendar-images",
    #         image_name=region_record.calendar_image_next or "default.png",
    #     )

    blocks = [
        orm.ActionsBlock(
            elements=[
                orm.ButtonElement(
                    ":calendar: Calendar Images", value="calendar", action=actions.OPEN_CALENDAR_IMAGE_BUTTON
                )
            ]
        ),
        orm.DividerBlock(),
        orm.SectionBlock(label="*Upcoming Schedule*"),
        orm.InputBlock(
            label="Filter AOs",
            action=actions.CALENDAR_HOME_AO_FILTER,
            element=orm.MultiStaticSelectElement(
                placeholder="Filter AOs",
                options=orm.as_selector_options(
                    names=[ao.name for ao in ao_records],
                    values=[str(ao.id) for ao in ao_records],
                ),
            ),
            dispatch_action=True,
        ),
        orm.InputBlock(
            label="Filter Event Types",
            action=actions.CALENDAR_HOME_EVENT_TYPE_FILTER,
            element=orm.MultiStaticSelectElement(
                placeholder="Filter Event Types",
                options=orm.as_selector_options(
                    names=[event_type.name for event_type in event_type_records],
                    values=[str(event_type.id) for event_type in event_type_records],
                ),
            ),
            dispatch_action=True,
        ),
        orm.InputBlock(
            label="Start Search Date",
            action=actions.CALENDAR_HOME_DATE_FILTER,
            element=orm.DatepickerElement(
                placeholder="Start Search Date",
            ),
            dispatch_action=True,
        ),
        orm.InputBlock(
            label="Other options",
            action=actions.CALENDAR_HOME_Q_FILTER,
            element=orm.CheckboxInputElement(
                options=orm.as_selector_options(
                    names=["Show only open Q slots", "Show only my events", "Include events from nearby regions"],
                    values=[actions.FILTER_OPEN_Q, actions.FILTER_MY_EVENTS],  # , actions.FILTER_NEARBY_REGIONS],
                ),
            ),
            dispatch_action=True,
        ),
        # orm.ActionsBlock(
        #     elements=[
        #         orm.StaticSelectElement(  # TODO: make these multi-selects?
        #             placeholder="Filter AOs",
        #             action=actions.CALENDAR_HOME_AO_FILTER,
        #             options=orm.as_selector_options(
        #                 names=[ao.name for ao in ao_records],
        #                 values=[str(ao.id) for ao in ao_records],
        #             ),
        #         ),
        #         orm.StaticSelectElement(  # TODO: make these multi-selects?
        #             placeholder="Filter Event Types",
        #             action=actions.CALENDAR_HOME_EVENT_TYPE_FILTER,
        #             options=orm.as_selector_options(
        #                 names=[event_type.name for event_type in event_type_records],
        #                 values=[str(event_type.id) for event_type in event_type_records],
        #             ),
        #         ),
        #         orm.DatepickerElement(
        #             action=actions.CALENDAR_HOME_DATE_FILTER,
        #             placeholder="Start Search Date",
        #         ),
        #         orm.CheckboxInputElement(
        #             action=actions.CALENDAR_HOME_Q_FILTER,
        #             options=orm.as_selector_options(names=["Show only open Q slots"], values=["yes"]),
        #         ),
        #     ],
        # ),
    ]

    # if region_record.calendar_image_current:
    #     blocks.insert(0, orm.ImageBlock(label="This week's schedule", alt_text="Current", image_url=this_week_url))
    # if region_record.calendar_image_next:
    #     blocks.insert(1, orm.ImageBlock(label="Next week's schedule", alt_text="Next", image_url=next_week_url))

    if safe_get(body, "view"):
        existing_filter_data = orm.BlockView(blocks=blocks).get_selected_values(body)
    else:
        existing_filter_data = {}

    # Build the filter
    start_date = safe_convert(
        safe_get(existing_filter_data, actions.CALENDAR_HOME_DATE_FILTER), datetime.datetime.strptime, ["%Y-%m-%d"]
    ) or datetime.datetime.now(tz=pytz.timezone("US/Central"))

    if safe_get(existing_filter_data, actions.CALENDAR_HOME_AO_FILTER) or ["Default"] != ["Default"]:
        filter_org_ids = [int(x) for x in safe_get(existing_filter_data, actions.CALENDAR_HOME_AO_FILTER)]
    else:
        filter_org_ids = [region_record.org_id]

    filter = [
        or_(EventInstance.org_id.in_(filter_org_ids), Org.parent_id.in_(filter_org_ids)),
        EventInstance.start_date >= start_date,
        EventInstance.is_active,
    ]

    if safe_get(existing_filter_data, actions.CALENDAR_HOME_EVENT_TYPE_FILTER):
        event_type_ids = [int(x) for x in safe_get(existing_filter_data, actions.CALENDAR_HOME_EVENT_TYPE_FILTER)]
        filter.append(EventType.id.in_(event_type_ids))

    open_q_only = actions.FILTER_OPEN_Q in (safe_get(existing_filter_data, actions.CALENDAR_HOME_Q_FILTER) or [])
    only_users_events = actions.FILTER_MY_EVENTS in (
        safe_get(existing_filter_data, actions.CALENDAR_HOME_Q_FILTER) or []
    )
    # Run the query
    # TODO: implement pagination / dynamic limit
    split_time = time.time()
    print(f"Block building time: {split_time - start_time}")
    start_time = time.time()
    events: list[CalendarHomeQuery] = home_schedule_query(
        user_id, filter, limit=100, open_q_only=open_q_only, only_users_events=only_users_events
    )

    split_time = time.time()
    print(f"Home schedule query: {split_time - start_time}")
    start_time = time.time()

    # Build the event list
    active_date = datetime.date(2020, 1, 1)
    block_count = 1
    for event in events:
        if block_count > 90:
            break
        if event.user_q:
            option_names = ["Edit Preblast"]
        else:
            option_names = ["View Preblast"]
        if event.event.start_date != active_date:
            active_date = event.event.start_date
            blocks.append(orm.SectionBlock(label=f":calendar: *{active_date.strftime('%A, %B %d')}*"))
            block_count += 1
        if event.series and event.series.name and event.org.name not in event.series.name:
            label = f"{event.series.name} @ {event.org.name} @ {event.event.start_time}"
        else:
            label = f"{event.org.name} {' / '.join(t.name for t in event.event_types)} @ {event.event.start_time}"  # noqa
        if event.planned_qs:
            label += f" / Q: {event.planned_qs}"
        else:
            label += " / Q: Open!"
            option_names.append("Take Q")
        if event.user_q:
            label += " :muscle:"
        if event.user_attending:
            label += " :white_check_mark:"
            option_names.append("Un-HC")
        else:
            option_names.append("HC")
        if event.event.preblast_rich:
            label += " :pencil:"
        if user_is_admin:
            option_names.append("Assign Q")
        blocks.append(
            orm.SectionBlock(
                label=label,
                element=orm.OverflowElement(
                    action=f"{actions.CALENDAR_HOME_EVENT}_{event.event.id}",
                    options=orm.as_selector_options(option_names),
                ),
            )
        )
        block_count += 1

    # TODO: add "next page" button
    form = orm.BlockView(blocks=blocks)
    form.set_initial_values(existing_filter_data)
    view_id = update_view_id or safe_get(body, actions.LOADING_ID) or safe_get(body, "view", "id")
    split_time = time.time()
    print(f"Block build 2 time: {split_time - start_time}")
    start_time = time.time()
    if view_id:
        form.update_modal(
            client=client,
            view_id=view_id,
            title_text="Calendar Home",
            callback_id=actions.CALENDAR_HOME_CALLBACK_ID,
            submit_button_text="None",
            parent_metadata=metadata,
        )
    else:
        form.post_modal(
            client=client,
            trigger_id=safe_get(body, "trigger_id"),
            title_text="Calendar Home",
            callback_id=actions.CALENDAR_HOME_CALLBACK_ID,
            new_or_add="new",
            parent_metadata=metadata,
        )
    split_time = time.time()
    print(f"Sending: {split_time - start_time}")
    start_time = time.time()


def build_calendar_image_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
):
    this_week_valid = False
    next_week_valid = False
    if LOCAL_DEVELOPMENT:
        try:
            this_week_valid = (
                requests.head(S3_IMAGE_URL.format(image_name=region_record.calendar_image_current)).status_code == 200
            )
            next_week_valid = (
                requests.head(S3_IMAGE_URL.format(image_name=region_record.calendar_image_next)).status_code == 200
            )
        except Exception as e:
            logger.error(f"Error checking S3 image URLs: {e}")
        if this_week_valid and next_week_valid:
            this_week_url = S3_IMAGE_URL.format(
                image_name=region_record.calendar_image_current or "default.png",
            )
            next_week_url = S3_IMAGE_URL.format(
                image_name=region_record.calendar_image_next or "default.png",
            )
    else:
        try:
            this_week_valid = (
                requests.head(
                    GCP_IMAGE_URL.format(
                        bucket="f3nation-calendar-images",
                        image_name=region_record.calendar_image_current or "default.png",
                    )
                ).status_code
                == 200
            )
            next_week_valid = (
                requests.head(
                    GCP_IMAGE_URL.format(
                        bucket="f3nation-calendar-images",
                        image_name=region_record.calendar_image_next or "default.png",
                    )
                ).status_code
                == 200
            )
        except Exception as e:
            logger.error(f"Error checking GCP image URLs: {e}")
        if this_week_valid and next_week_valid:
            this_week_url = GCP_IMAGE_URL.format(
                bucket="f3nation-calendar-images",
                image_name=region_record.calendar_image_current or "default.png",
            )
            next_week_url = GCP_IMAGE_URL.format(
                bucket="f3nation-calendar-images",
                image_name=region_record.calendar_image_next or "default.png",
            )
    if this_week_valid and next_week_valid:
        blocks = [
            orm.ImageBlock(label="This week's schedule", alt_text="Current", image_url=this_week_url),
            orm.ImageBlock(label="Next week's schedule", alt_text="Next", image_url=next_week_url),
        ]
    else:
        blocks = [orm.SectionBlock(label="No calendar images available. Please wait for them to generate.")]
    form = orm.BlockView(blocks=blocks)
    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text="Calendar Images",
        callback_id=actions.CALENDAR_HOME_CALLBACK_ID,
        new_or_add="add",
        submit_button_text="None",
    )


ASSIGN_Q_FORM = orm.BlockView(
    blocks=[
        orm.SectionBlock(label="Assign Q to this event"),
        orm.InputBlock(
            label="Select User",
            action=actions.CALENDAR_HOME_ASSIGN_Q_USER,
            element=orm.UsersSelectElement(
                placeholder="Select a user to assign to the Q",
                initial_value=None,
            ),
        ),
        orm.InputBlock(
            label="Select Co-Qs (optional)",
            action=actions.CALENDAR_HOME_ASSIGN_Q_CO_QS,
            element=orm.MultiUsersSelectElement(
                placeholder="Select users to assign as Co-Qs",
                initial_value=None,
            ),
            optional=True,
        ),
    ]
)


def build_assign_q_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
    event_instance_id: int,
    update_view_id: str = None,
):
    event_instance = DbManager.get(EventInstance, event_instance_id, joinedloads=[EventInstance.org])
    attendance = DbManager.find_records(
        Attendance,
        filters=[Attendance.event_instance_id == event_instance_id],
        joinedloads=[Attendance.slack_users, Attendance.attendance_types],
    )

    form = copy.deepcopy(ASSIGN_Q_FORM)
    form.blocks[0].label = (
        f"*AO:* {event_instance.org.name}\n"
        + f"*Event:* {event_instance.name}\n"
        + f"*Date:* {event_instance.start_date.strftime('%A, %B %d')}\n"
        + f"*Start Time:* {event_instance.start_time or 'TBD'}\n"
    )

    existing_q_slack_users = [a.slack_users for a in attendance if any(at.type == "Q" for at in a.attendance_types)]
    if existing_q_slack_users:
        slack_user_id = [su.slack_id for su in existing_q_slack_users[0] if su.slack_team_id == region_record.team_id]
        print(f"Existing Q slack user: {slack_user_id}")
        form.set_initial_values({actions.CALENDAR_HOME_ASSIGN_Q_USER: safe_get(slack_user_id, 0)})
    existing_co_q_slack_users = [
        a.slack_users for a in attendance if any(at.type == "Co-Q" for at in a.attendance_types)
    ]
    if existing_co_q_slack_users:
        slack_user_ids = []
        for slack_user in existing_co_q_slack_users:
            slack_user_id = [su.slack_id for su in slack_user if su.slack_team_id == region_record.team_id]
            slack_user_ids.append(safe_get(slack_user_id, 0))
        print(f"Existing Co-Q slack users: {slack_user_ids}")
        form.set_initial_values({actions.CALENDAR_HOME_ASSIGN_Q_CO_QS: slack_user_ids})

    metadata = {
        "event_instance_id": event_instance_id,
        "update_view_id": update_view_id,
        "event_instance_name": event_instance.name,
        "event_instance_date": event_instance.start_date.strftime("%A, %B %d"),
    }
    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text="Assign Q",
        callback_id=actions.HOME_ASSIGN_Q_CALLBACK_ID,
        submit_button_text="Assign Q",
        parent_metadata=metadata,
        new_or_add="add",
    )


def handle_assign_q_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
):
    user_id = safe_get(body, "user", "id") or safe_get(body, "user_id")
    form_data = ASSIGN_Q_FORM.get_selected_values(body)
    metadata = safe_convert(safe_get(body, "view", "private_metadata"), json.loads) or {}
    event_instance_id = safe_convert(safe_get(metadata, "event_instance_id"), int)
    event_instance_name = safe_get(metadata, "event_instance_name")
    event_instance_date = safe_get(metadata, "event_instance_date")

    # Get the selected user and co-Qs
    q_slack_user_id = safe_get(form_data, actions.CALENDAR_HOME_ASSIGN_Q_USER)
    q_user_id = get_user(q_slack_user_id, region_record, client, logger).user_id if q_slack_user_id else None
    co_qs_slack_ids = safe_get(form_data, actions.CALENDAR_HOME_ASSIGN_Q_CO_QS) or []
    co_qs_user_ids = [get_user(co_q, region_record, client, logger).user_id for co_q in co_qs_slack_ids]

    # Existing attendance records
    existing_attendance_records = DbManager.find_records(
        Attendance,
        filters=[Attendance.event_instance_id == event_instance_id],
        joinedloads=[Attendance.slack_users, Attendance.attendance_types],
    )

    # Assign existing Q / Co-Qs to "HC"
    for ea in existing_attendance_records:
        if any(at.type in ["Q", "Co-Q"] for at in ea.attendance_types):
            if 1 not in [at.id for at in ea.attendance_types]:
                DbManager.create_record(Attendance_x_AttendanceType(attendance_id=ea.id, attendance_type_id=1))
            DbManager.delete_records(
                cls=Attendance_x_AttendanceType,
                filters=[
                    Attendance_x_AttendanceType.attendance_id == ea.id,
                    Attendance_x_AttendanceType.attendance_type_id.in_([2, 3]),
                ],
            )

    # Existing attendance records again (probably a better way to do this)
    existing_attendance_records = DbManager.find_records(
        Attendance,
        filters=[Attendance.event_instance_id == event_instance_id],
        joinedloads=[Attendance.slack_users, Attendance.attendance_types],
    )

    if q_user_id:
        if q_user_id in [ea.user_id for ea in existing_attendance_records]:
            attendance_record = next((ea for ea in existing_attendance_records if ea.user_id == q_user_id), None)
            if attendance_record and 2 not in [at.id for at in attendance_record.attendance_types]:
                DbManager.create_record(
                    Attendance_x_AttendanceType(attendance_id=attendance_record.id, attendance_type_id=2)
                )
        else:
            DbManager.create_record(
                Attendance(
                    event_instance_id=event_instance_id,
                    user_id=q_user_id,
                    is_planned=True,
                    attendance_x_attendance_types=[
                        Attendance_x_AttendanceType(attendance_type_id=2)  # Q
                    ],
                )
            )

    if co_qs_user_ids:
        for co_q_user_id in co_qs_user_ids:
            if co_q_user_id in [ea.user_id for ea in existing_attendance_records]:
                attendance_record = next((ea for ea in existing_attendance_records if ea.user_id == co_q_user_id), None)
                if attendance_record and 3 not in [at.id for at in attendance_record.attendance_types]:
                    DbManager.create_record(
                        Attendance_x_AttendanceType(attendance_id=attendance_record.id, attendance_type_id=3)
                    )
            else:
                DbManager.create_record(
                    Attendance(
                        event_instance_id=event_instance_id,
                        user_id=co_q_user_id,
                        is_planned=True,
                        attendance_x_attendance_types=[
                            Attendance_x_AttendanceType(attendance_type_id=3)  # Co-Q
                        ],
                    )
                )

    # Update the home view if needed
    update_view_id = safe_get(metadata, "update_view_id")
    if update_view_id:
        build_home_form(body, client, logger, context, region_record, update_view_id=update_view_id)

    # Send messages to the assigned users
    if q_slack_user_id and q_slack_user_id != user_id:
        msg = f"<@{user_id}> has assigned you to Q {event_instance_name} on {event_instance_date}. Use the button below to set the preblast."  # noqa
        blocks: List[orm.BaseBlock] = [
            orm.SectionBlock(label=msg),
            orm.ActionsBlock(
                elements=[
                    orm.ButtonElement(
                        label="Fill Out Preblast",
                        value=str(event_instance_id),
                        style="primary",
                        action=actions.MSG_EVENT_PREBLAST_BUTTON,
                    ),
                ],
            ),
        ]
        client.chat_postMessage(
            channel=q_slack_user_id,
            text=msg,
            blocks=[b.as_form_field() for b in blocks],
        )
    for co_q_slack_id in co_qs_slack_ids:
        if co_q_slack_id != user_id:
            client.chat_postMessage(
                channel=co_q_slack_id,
                text=f"<@{user_id}> has assigned you to Co-Q {event_instance_name} on {event_instance_date}.",  # noqa
            )


def handle_home_event(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    event_instance_id = safe_convert(safe_get(body, "actions", 0, "action_id").split("_")[1], int)
    action = safe_get(body, "actions", 0, "selected_option", "value")
    user_id = get_user(safe_get(body, "user", "id"), region_record, client, logger).user_id
    view_id = safe_get(body, "view", "id")
    update_post = False

    if action in ["View Preblast", "Edit Preblast"]:
        build_event_preblast_form(body, client, logger, context, region_record, event_instance_id=event_instance_id)
    elif action == "Take Q":
        attendance_record = DbManager.find_records(
            Attendance,
            filters=[Attendance.event_instance_id == event_instance_id, Attendance.user_id == user_id],
            joinedloads=[Attendance.attendance_x_attendance_types],
        )
        if attendance_record:
            if 2 not in attendance_record[0].attendance_x_attendance_types:
                DbManager.create_record(
                    Attendance_x_AttendanceType(attendance_id=attendance_record[0].id, attendance_type_id=2)
                )
        else:
            DbManager.create_record(
                Attendance(
                    event_instance_id=event_instance_id,
                    user_id=user_id,
                    attendance_x_attendance_types=[Attendance_x_AttendanceType(attendance_type_id=2)],
                    is_planned=True,
                )
            )

        # TODO: build the q / preblast form
        update_post = True
        build_home_form(body, client, logger, context, region_record, update_view_id=view_id)
    elif action == "HC":
        DbManager.create_record(
            Attendance(
                event_instance_id=event_instance_id,
                user_id=user_id,
                attendance_x_attendance_types=[Attendance_x_AttendanceType(attendance_type_id=1)],
                is_planned=True,
            )
        )
        update_post = True
        build_home_form(body, client, logger, context, region_record, update_view_id=view_id)
    elif action == "Un-HC":
        DbManager.delete_records(
            cls=Attendance,
            filters=[
                Attendance.event_instance_id == event_instance_id,
                Attendance.user_id == user_id,
                Attendance.attendance_types.any(Attendance_x_AttendanceType.attendance_type_id == 1),
                Attendance.is_planned,
            ],
            joinedloads=[Attendance.attendance_types],
        )
        build_home_form(body, client, logger, context, region_record, update_view_id=view_id)
    elif action == "Assign Q":
        build_assign_q_form(
            body, client, logger, context, region_record, event_instance_id=event_instance_id, update_view_id=view_id
        )

    if update_post:
        preblast_info = build_preblast_info(body, client, logger, context, region_record, event_instance_id)
        if preblast_info.event_record.preblast_ts:
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
                ],  # noqa
            }
            try:
                client.chat_update(
                    channel=get_preblast_channel(region_record, preblast_info),
                    ts=safe_get(metadata, "preblast_ts") or str(preblast_info.event_record.preblast_ts),
                    blocks=blocks,
                    text="Event Preblast",
                    metadata={"event_type": "preblast", "event_payload": metadata},
                )
            except Exception as e:
                logger.error(f"Error updating preblast post, posting a new one: {e}")
                client.chat_postMessage(
                    channel=get_preblast_channel(region_record, preblast_info),
                    blocks=blocks,
                    text="Event Preblast",
                    metadata={"event_type": "preblast", "event_payload": metadata},
                )

    elif action == "edit":
        pass
