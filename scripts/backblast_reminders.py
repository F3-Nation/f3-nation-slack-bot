import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List

from slack_sdk.web import WebClient
from sqlalchemy import and_, func, select
from sqlalchemy.orm import aliased

from utilities.database import get_session
from utilities.database.orm import (
    Attendance,
    Event,
    EventType,
    Org,
    Org_x_Slack,
    SlackSettings,
    SlackSpace,
    SlackUser,
    User,
)
from utilities.slack import actions, orm

MSG_TEMPLATE = "Hey there, {q_name}! I hope that the {event_name} on {event_date} at {event_ao} went well! I have not seen a backblast posted for this event yet... Please click the button below to fill out the backblast so we can track those stats!"  # noqa


@dataclass
class BackblastItem:
    event: Event
    event_type: EventType
    org: Org
    parent_org: Org
    q_name: str
    slack_user_id: str
    slack_settings: SlackSettings


@dataclass
class BackblastList:
    items: List[BackblastItem] = field(default_factory=list)

    def pull_data(self):
        session = get_session()
        ParentOrg = aliased(Org)

        firstq_subquery = (
            select(
                Attendance.event_id,
                User.f3_name.label("q_name"),
                SlackUser.slack_id,
                func.row_number().over(partition_by=Attendance.event_id, order_by=Attendance.created).label("rn"),
            )
            .select_from(Attendance)
            .join(User, Attendance.user_id == User.id)
            .join(SlackUser, User.id == SlackUser.user_id)
            .filter(Attendance.attendance_type_id == 2)
            .alias()
        )

        query = (
            session.query(
                Event,
                EventType,
                Org,
                ParentOrg,
                firstq_subquery.c.q_name,
                firstq_subquery.c.slack_id,
                SlackSpace.settings,
            )
            .select_from(Event)
            .join(Org, Org.id == Event.org_id)
            .join(EventType, EventType.id == Event.event_type_id)
            .join(ParentOrg, Org.parent_id == ParentOrg.id)
            .join(Org_x_Slack, Org_x_Slack.org_id == Org.id)
            .join(SlackSpace, Org_x_Slack.slack_id == SlackSpace.team_id)
            .join(
                firstq_subquery,
                and_(Event.id == firstq_subquery.c.event_id, firstq_subquery.c.rn == 1),
            )
            .filter(
                Event.start_date < date.today(),  # + timedelta(days=1),  # eventually configurable
                Event.start_date >= (date.today() - timedelta(days=3)),  # eventually configurable
                Event.backblast_ts.is_(None),  # not already sent
                Event.is_active,  # not canceled
                ~Event.is_series,  # not a series
            )
            .order_by(ParentOrg.name, Org.name, Event.start_time)
        )
        records = query.all()
        self.items = [
            BackblastItem(
                event=r[0],
                event_type=r[1],
                org=r[2],
                parent_org=r[3],
                q_name=r[4],
                slack_user_id=r[5],
                slack_settings=SlackSettings(**r[6]),
            )
            for r in records
        ]
        session.expunge_all()
        session.close()


def send_backblast_reminders():
    backblast_list = BackblastList()
    backblast_list.pull_data()

    for backblast in backblast_list.items:
        # TODO: add some handling for missing stuff
        msg = MSG_TEMPLATE.format(
            q_name=backblast.q_name,
            event_name=backblast.event_type.name,
            event_date=backblast.event.start_date.strftime("%m/%d"),
            event_ao=backblast.org.name,
        )

        slack_bot_token = backblast.slack_settings.bot_token
        if slack_bot_token and backblast.slack_user_id:
            slack_client = WebClient(slack_bot_token)
            blocks: List[orm.BaseBlock] = [
                orm.SectionBlock(label=msg),
                orm.ActionsBlock(
                    elements=[
                        orm.ButtonElement(
                            label="Fill Out Backblast",
                            value=str(backblast.event.id),
                            style="primary",
                            action=actions.MSG_EVENT_BACKBLAST_BUTTON,
                        ),
                    ],
                ),
            ]
            blocks = [b.as_form_field() for b in blocks]
            slack_client.chat_postMessage(channel=backblast.slack_user_id, text=msg, blocks=blocks)


if __name__ == "__main__":
    send_backblast_reminders()
