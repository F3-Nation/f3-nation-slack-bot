from datetime import date, timedelta
from typing import Dict, List

from f3_data_models.models import EventInstance, Org
from f3_data_models.utils import DbManager
from slack_sdk import WebClient

from utilities.database.orm import SlackSettings
from utilities.slack import actions
from utilities.slack.orm import (
    ActionsBlock,
    BaseBlock,
    ButtonElement,
    DividerBlock,
    ImageBlock,
    SectionBlock,
)

from .preblast_reminders import PreblastItem, PreblastList


def send_lineups():
    # Figure out current and next weeks based on current start of day
    # I have the week start on Monday and end on Sunday - if this is run on Sunday, "current" week will start tomorrow
    tomorrow_day_of_week = (date.today() + timedelta(days=1)).weekday()
    this_week_start = date.today() + timedelta(days=-tomorrow_day_of_week)
    this_week_end = date.today() + timedelta(days=7 - tomorrow_day_of_week)

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
            send_q_lineup_message(org_record, blocks, slack_settings)


def build_lineup_blocks(org_events: List[PreblastItem], org: Org) -> List[dict]:
    blocks: List[BaseBlock] = [
        SectionBlock(label=f"Hello HIMs of {org.name}! Here is your Q lineup for the week\n\n*Weekly Q Lineup:*"),
        DividerBlock(),
    ]

    for event in org_events:
        if event.q_name:
            q_label = f"<@{event.slack_user_id}|{event.q_name}>" if event.slack_user_id else f"@{event.q_name}"
            label = f"*{event.event.start_date}*\n{event.event_type.name} {event.event.start_time}\n{q_label}"
            image_url = event.q_avatar_url or "https://www.publicdomainpictures.net/pictures/40000/t2/question-mark.jpg"
        else:
            # TODO: add a button to sign up for the Q?
            label = f"*{event.event.start_date}*\n{event.event_type.name} {event.event.start_time}\n*OPEN!*"
            image_url = "https://www.publicdomainpictures.net/pictures/40000/t2/question-mark.jpg"
        blocks.append(
            SectionBlock(
                label=label,
                element=ImageBlock(
                    image_url=image_url,
                    alt_text="Q Lineup",
                ),
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


def send_q_lineup_message(org: Org, blocks: List[dict], slack_settings: SlackSettings):
    slack_bot_token = slack_settings.bot_token
    if slack_bot_token:
        slack_client = WebClient(slack_bot_token)
        resp = slack_client.chat_postMessage(
            channel=org.meta.get("slack_channel_id"),
            text="Q Lineup",
            blocks=blocks,
        )
        org.meta["q_lineup_ts"] = resp["ts"]
        DbManager.update_record(Org, org.id, {Org.meta: org.meta})


if __name__ == "__main__":
    send_lineups()
