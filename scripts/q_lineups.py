import json
import os
import ssl
import sys
from logging import Logger

import pytz

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, datetime, timedelta
from typing import Dict, List

from f3_data_models.models import Attendance, Attendance_x_AttendanceType, EventInstance, Org
from f3_data_models.utils import DbManager
from slack_sdk import WebClient
from slack_sdk.models.metadata import Metadata

from scripts.preblast_reminders import PreblastItem, PreblastList
from utilities.database.orm import SlackSettings
from utilities.helper_functions import current_date_cst, get_user, safe_convert, safe_get
from utilities.slack import actions
from utilities.slack.orm import (
    ActionsBlock,
    BaseBlock,
    ButtonElement,
    DividerBlock,
    ImageBlock,
    SectionBlock,
)


def send_lineups(force: bool = False):
    # get the current time in US/Central timezone
    current_time = datetime.now(pytz.timezone("US/Central"))
    # check if the current time is between 5:00 PM and 6:00 PM on Sundays, eventually configurable
    if (current_time.hour == 7 and current_time.weekday() == 1) or force:
        # Figure out current and next weeks based on current start of day
        # I have the week start on Monday and end on Sunday - if this is run on Sunday, "current" week will start tomorrow # noqa
        tomorrow_day_of_week = (current_date_cst() + timedelta(days=1)).weekday()
        this_week_start = current_date_cst() + timedelta(days=-tomorrow_day_of_week)
        this_week_end = current_date_cst() + timedelta(days=7 - tomorrow_day_of_week)
        event_list = PreblastList()
        event_list.pull_data(
            filters=[
                EventInstance.start_date >= this_week_start,
                EventInstance.start_date <= this_week_end,
                EventInstance.is_active,  # not canceled
                # may want to filter out pre-events?
            ]
        )
        event_org_list: Dict[int, List[PreblastItem]] = {}
        for event in event_list.items:
            event_org_list.setdefault(event.org.id, []).append(event)

        for org in event_org_list:
            org_events = event_org_list[org]
            org_record = org_events[0].org
            slack_settings = org_events[0].slack_settings
            if slack_settings.send_q_lineups:
                blocks = build_lineup_blocks(org_events, org_record)
                # Send the Q Lineup message to the Slack channel
                send_q_lineup_message(org_record, blocks, slack_settings, this_week_start, this_week_end)


def build_lineup_blocks(org_events: List[PreblastItem], org: Org) -> List[dict]:
    org_events.sort(key=lambda x: x.event.start_date + timedelta(hours=int(x.event.start_time[:2])))
    blocks: List[BaseBlock] = [
        SectionBlock(label=f"Hello HIMs of {org.name}! Here is your Q lineup for the week\n\n*Weekly Q Lineup:*"),
        DividerBlock(),
    ]

    for event in org_events:
        if event.q_name:
            q_label = f"@{event.q_name}"  # f"<@{event.slack_user_id}>" if event.slack_user_id else
            label = f"*{event.event.start_date}*\n{event.event_type.name} {event.event.start_time}\n{q_label}"
            image_url = event.q_avatar_url or "https://www.publicdomainpictures.net/pictures/40000/t2/question-mark.jpg"
            accessory = ImageBlock(
                image_url=image_url,
                alt_text="Q Lineup",
            )
        else:
            label = f"*{event.event.start_date}*\n{event.event_type.name} {event.event.start_time}\n*OPEN!*"
            # image_url = "https://www.publicdomainpictures.net/pictures/40000/t2/question-mark.jpg"
            accessory = ButtonElement(
                label=":calendar: Sign Me Up!",
                action=f"{actions.LINEUP_SIGNUP_BUTTON}_{event.event.id}",
                value=str(event.event.id),
                style="primary",
            )
        blocks.append(
            SectionBlock(
                label=label,
                element=accessory,
            )
        )
    blocks.append(
        ActionsBlock(
            elements=[
                ButtonElement(
                    label=":calendar: Open Calendar",
                    action=actions.OPEN_CALENDAR_MSG_BUTTON,
                )
            ]
        )
    )
    return [b.as_form_field() for b in blocks]


def send_q_lineup_message(
    org: Org,
    blocks: List[dict],
    slack_settings: SlackSettings,
    week_start: date = None,
    week_end: date = None,
    update: bool = False,
):
    slack_bot_token = slack_settings.bot_token
    metadata = Metadata(event_type="q_lineup", event_payload={})
    if week_start and week_end:
        metadata.event_payload["week_start"] = week_start.strftime("%y-%m-%d")
        metadata.event_payload["week_end"] = week_end.strftime("%y-%m-%d")
    if slack_bot_token:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        slack_client = WebClient(slack_bot_token, ssl=ssl_context)
        if update and safe_get(org.meta, "q_lineup_ts"):
            # Update the existing message
            slack_client.chat_update(
                channel=org.meta.get("slack_channel_id"),
                ts=org.meta["q_lineup_ts"],
                text="Q Lineup",
                blocks=blocks,
                metadata=metadata,
            )
        else:
            resp = slack_client.chat_postMessage(
                channel=org.meta.get("slack_channel_id"),
                text="Q Lineup",
                blocks=blocks,
                metadata=metadata,
            )
            org.meta["q_lineup_ts"] = resp["ts"]
            DbManager.update_record(Org, org.id, {Org.meta: org.meta})


def handle_lineup_signup(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    event_instance_id = int(body["actions"][0]["value"])
    slack_user_id = body["user"]["id"]
    slack_channel_id = body["channel"]["id"]
    user_id = get_user(slack_user_id, region_record, client, logger).user_id

    metadata = safe_convert(safe_get(body, "message", "metadata", "event_payload"), json.loads)
    week_start = safe_get(metadata, "week_start")
    week_end = safe_get(metadata, "week_end")
    if week_start and week_end:
        this_week_start = datetime.strptime(week_start, "%y-%m-%d").date()
        this_week_end = datetime.strptime(week_end, "%y-%m-%d").date()
    else:
        # Default to the current week
        tomorrow_day_of_week = (current_date_cst() + timedelta(days=1)).weekday()
        this_week_start = current_date_cst() + timedelta(days=-tomorrow_day_of_week)
        this_week_end = current_date_cst() + timedelta(days=7 - tomorrow_day_of_week)

    preblast_info = PreblastList()
    preblast_info.pull_data(filters=[EventInstance.id == event_instance_id])
    event_info: PreblastItem = safe_get(preblast_info.items, 0)
    # Check if a user is already signed up for the event
    if event_info.q_name:
        client.chat_postEphemeral(
            user=slack_user_id,
            channel=slack_channel_id,
            text=f"Sorry, {event_info.q_name} already signed up for this event.",
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
    # Update the Q Lineup
    org_info = PreblastList()
    org_info.pull_data(
        filters=[
            EventInstance.org_id == event_info.org.id,
            EventInstance.start_date >= this_week_start,
            EventInstance.start_date <= this_week_end,
            EventInstance.is_active,
        ],
    )
    blocks = build_lineup_blocks(org_info.items, event_info.org)
    send_q_lineup_message(
        event_info.org, blocks, region_record, update=True, week_start=this_week_start, week_end=this_week_end
    )


if __name__ == "__main__":
    send_lineups()
