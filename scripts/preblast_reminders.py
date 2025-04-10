import os
import sys

import pytz

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List

from f3_data_models.models import (
    Attendance,
    Attendance_x_AttendanceType,
    EventInstance,
    EventType,
    EventType_x_EventInstance,
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
    event: EventInstance
    event_type: EventType
    org: Org
    parent_org: Org
    q_name: str
    slack_user_id: str
    q_avatar_url: str
    slack_settings: SlackSettings


@dataclass
class PreblastList:
    items: List[PreblastItem] = field(default_factory=list)

    def pull_data(self, filters: List):
        session = get_session()
        ParentOrg = aliased(Org)

        firstq_subquery = (
            select(
                Attendance.event_instance_id,
                User.f3_name.label("q_name"),
                SlackUser.slack_id,
                User.avatar_url.label("q_avatar_url"),
                func.row_number()
                .over(partition_by=Attendance.event_instance_id, order_by=Attendance.created)
                .label("rn"),
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
                EventInstance,
                EventType,
                Org,
                ParentOrg,
                firstq_subquery.c.q_name,
                firstq_subquery.c.slack_id,
                firstq_subquery.c.q_avatar_url,
                SlackSpace.settings,
            )
            .select_from(EventInstance)
            .join(Org, Org.id == EventInstance.org_id)
            .join(EventType_x_EventInstance, EventType_x_EventInstance.event_instance_id == EventInstance.id)
            .join(EventType, EventType.id == EventType_x_EventInstance.event_type_id)
            .join(ParentOrg, Org.parent_id == ParentOrg.id)
            .join(
                firstq_subquery,
                and_(EventInstance.id == firstq_subquery.c.event_instance_id, firstq_subquery.c.rn == 1),
                isouter=True,
            )
            .join(Org_x_SlackSpace, ParentOrg.id == Org_x_SlackSpace.org_id)
            .join(SlackSpace, Org_x_SlackSpace.slack_space_id == SlackSpace.id)
            .filter(*filters)
            .order_by(ParentOrg.name, Org.name, EventInstance.start_time)
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
                q_avatar_url=r[6],
                slack_settings=SlackSettings(**r[7]),
            )
            for r in records
        ]
        session.expunge_all()
        session.close()


def send_preblast_reminders():
    # get the current time in US/Central timezone
    current_time = datetime.now(pytz.timezone("US/Central"))
    # check if the current time is between 5:00 PM and 6:00 PM, eventually configurable
    if current_time.hour == 17:
        preblast_list = PreblastList()
        preblast_list.pull_data(
            filters=[
                EventInstance.start_date == date.today() + timedelta(days=1),  # eventually configurable
                EventInstance.preblast_ts.is_(None),  # not already sent
                EventInstance.is_active,  # not canceled
            ]
        )
        preblast_list.items = [item for item in preblast_list.items if item.q_name is not None]
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
