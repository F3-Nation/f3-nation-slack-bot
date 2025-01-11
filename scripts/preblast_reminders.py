import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List

from f3_data_models.models import (
    Attendance,
    Attendance_x_AttendanceType,
    Event,
    EventType,
    EventType_x_Event,
    Org,
    Org_x_SlackSpace,
    SlackSpace,
    SlackUser,
    User,
)
from f3_data_models.utils import get_session
from slack_sdk.web import WebClient
from sqlalchemy import and_, func, select
from sqlalchemy.orm import aliased

from utilities.database.orm import SlackSettings
from utilities.slack import actions, orm

MSG_TEMPLATE = "Hey there, {q_name}! I see you have an upcoming {event_name} Q on {event_date} at {event_ao}. Please click the button below to fill out the preblast form below to let everyone know what to expect. If you're not able to complete the form, I'll still send one out on your behalf. Thanks for leading!"  # noqa


@dataclass
class PreblastItem:
    event: Event
    event_type: EventType
    org: Org
    parent_org: Org
    q_name: str
    slack_user_id: str
    slack_settings: SlackSettings


@dataclass
class PreblastList:
    items: List[PreblastItem] = field(default_factory=list)

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
            .join(Attendance_x_AttendanceType, Attendance.id == Attendance_x_AttendanceType.attendance_id)
            .filter(Attendance_x_AttendanceType.attendance_type_id == 2)
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
            .join(EventType_x_Event, EventType_x_Event.event_id == Event.id)
            .join(EventType, EventType.id == EventType_x_Event.event_type_id)
            .join(ParentOrg, Org.parent_id == ParentOrg.id)
            .join(
                firstq_subquery,
                and_(Event.id == firstq_subquery.c.event_id, firstq_subquery.c.rn == 1),
            )
            .join(Org_x_SlackSpace, ParentOrg.id == Org_x_SlackSpace.org_id)
            .join(SlackSpace, Org_x_SlackSpace.slack_space_id == SlackSpace.id)
            .filter(
                Event.start_date == date.today() + timedelta(days=1),  # eventually configurable
                Event.preblast_ts.is_(None),  # not already sent
                Event.is_active,  # not canceled
                ~Event.is_series,  # not a series
            )
            .order_by(ParentOrg.name, Org.name, Event.start_time)
        )
        records = query.all()
        self.items = [
            PreblastItem(
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


def send_preblast_reminders():
    preblast_list = PreblastList()
    preblast_list.pull_data()
    print(f"Found {len(preblast_list.items)} preblasts to send.")

    for preblast in preblast_list.items:
        # TODO: add some handling for missing stuff
        msg = MSG_TEMPLATE.format(
            q_name=preblast.q_name,
            event_name=preblast.event_type.name,
            event_date=preblast.event.start_date.strftime("%m/%d"),
            event_ao=preblast.org.name,
        )

        slack_bot_token = preblast.slack_settings.bot_token
        if slack_bot_token and preblast.slack_user_id:
            slack_client = WebClient(slack_bot_token)
            blocks: List[orm.BaseBlock] = [
                orm.SectionBlock(label=msg),
                orm.ActionsBlock(
                    elements=[
                        orm.ButtonElement(
                            label="Fill Out Preblast",
                            value=str(preblast.event.id),
                            style="primary",
                            action=actions.MSG_EVENT_PREBLAST_BUTTON,
                        ),
                    ],
                ),
            ]
            blocks = [b.as_form_field() for b in blocks]
            slack_client.chat_postMessage(channel=preblast.slack_user_id, text=msg, blocks=blocks)


if __name__ == "__main__":
    send_preblast_reminders()
