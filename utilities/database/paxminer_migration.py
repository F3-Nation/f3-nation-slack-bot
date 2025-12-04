import argparse
import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

import uuid
from datetime import date
from typing import Dict, List

from f3_data_models.models import (
    Attendance,
    Attendance_x_AttendanceType,
    EventInstance,
    EventType_x_EventInstance,
    Org,
    Org_Type,
    SlackUser,
    User,
)
from f3_data_models.utils import DbManager
from sqlalchemy import text

from utilities.database.orm import SlackSettings
from utilities.database.orm.paxminer import Attendance as PaxminerAttendance
from utilities.database.orm.paxminer import Backblast, PaxminerRegion, PaxminerUser, get_pm_engine
from utilities.helper_functions import safe_get


def extract_name(backblast: str = "No title") -> str:
    # extract the name of the event from the backblast
    # this is a very basic implementation, and will need to be updated
    # to handle the various ways that backblasts are formatted
    # this is just a placeholder
    backblast = backblast or "No title"
    name = backblast.split("\n")[0]
    if name:
        return name[:50]
    else:
        return "Backblast"


def convert_region(paxminer_region: PaxminerRegion) -> Org:
    return Org(
        org_type=Org_Type.region,
        name=paxminer_region.region,
        is_active=True,
    )


def convert_users(paxminer_users: list[PaxminerUser], slack_team_id: str) -> List[SlackUser]:
    users: List[User] = []
    users = [
        User(
            f3_name=user.user_name,
            first_name=user.real_name.split(" ")[0],
            last_name=" ".join(user.real_name.split(" ")[1:]),
            email=(user.user_id.lower() or uuid.uuid4()) if (user.email or "None") == "None" else user.email.lower(),
            phone=user.phone,
        )
        for user in paxminer_users
    ]
    DbManager.create_or_ignore(User, users)
    users = DbManager.find_records(User, filters=[True])
    user_dict = {user.email: user.id for user in users}

    slack_users: List[SlackUser] = []
    for user in paxminer_users:
        email = (user.user_id.lower() or uuid.uuid4()) if (user.email or "None") == "None" else user.email.lower()
        slack_users.append(
            SlackUser(
                slack_id=user.user_id or uuid.uuid4(),
                user_name=user.user_name,
                email=email,
                is_admin=False,
                is_owner=False,
                is_bot=user.app,
                user_id=user_dict.get(email),
                slack_team_id=slack_team_id,
            )
        )
    return slack_users


def convert_events(
    paxminer_backblasts: list[Backblast], slack_org_dict: Dict, region_org_id: int
) -> List[EventInstance]:
    events: List[EventInstance] = []
    for backblast in paxminer_backblasts:
        if type(backblast.bd_date) is str:
            backblast.bd_date = date(2010, 1, 1)
    for backblast in paxminer_backblasts:
        event = EventInstance(
            org_id=slack_org_dict.get(backblast.ao_id) or region_org_id,  # will return none if not found
            is_active=True,
            highlight=False,
            start_date=backblast.bd_date if backblast.bd_date > date(2010, 1, 1) else date(2010, 1, 1),
            end_date=backblast.bd_date if backblast.bd_date > date(2010, 1, 1) else date(2010, 1, 1),
            name=extract_name(backblast.backblast),
            pax_count=backblast.pax_count,
            fng_count=backblast.fng_count,
            backblast=backblast.backblast_parsed,
            meta=json.loads(backblast.json or "{}"),
            backblast_ts=None if backblast.timestamp or "" == "" else float(backblast.timestamp),
            event_instances_x_event_types=[
                EventType_x_EventInstance(event_type_id=1)  # assuming bootcamp
            ],
        )
        event.meta["source"] = "paxminer_import"
        event.meta["og_channel"] = backblast.ao_id
        events.append(event)
    return events


def get_event_instance_id(event_lookup_dict: Dict, ao_id: str, date: str, q_user_id: str) -> int:
    if q_user_id[:5] == "https":
        q_user_id = q_user_id.split("/")[-1]
    event_instance_id = event_lookup_dict.get(f"{ao_id}-{date}-{q_user_id}")
    # if not event_instance_id:
    #     raise ValueError(f"Event not found for {ao_id}-{date}-{q_user_id}")
    return event_instance_id


def convert_attendance(
    paxminer_attendance: list[PaxminerAttendance], slack_user_dict: Dict, event_lookup_dict: Dict
) -> List[Attendance]:
    attendance_list: List[Attendance] = []
    for attendance in paxminer_attendance:
        event_instance_id = get_event_instance_id(
            event_lookup_dict, attendance.ao_id, attendance.date, attendance.q_user_id
        )
        if event_instance_id:
            attendance_type_id = 2 if attendance.q_user_id == attendance.user_id else 1  # need to update for coqs
            user_id = slack_user_dict.get(attendance.user_id)
            if user_id:  # this happens when the user_id is "https://", need to fix
                attendance_list.append(
                    Attendance(
                        event_instance_id=event_instance_id,
                        user_id=user_id,
                        attendance_x_attendance_types=[
                            Attendance_x_AttendanceType(attendance_type_id=attendance_type_id)
                        ],
                        is_planned=False,
                        meta={"source": "paxminer_import", "og_channel": attendance.ao_id},
                    )
                )
    # remove duplicates on event_instance_id, user_id, and is_planned
    # TODO: this is a hack, need to fix the root cause
    attendance_dict = {f"{a.event_instance_id}-{a.user_id}-{a.is_planned}": a for a in attendance_list}
    attendance_list = list(attendance_dict.values())
    return attendance_list


def build_event_lookup_dict(paxminer_backblasts: List[Backblast], events: List[EventInstance]) -> Dict:
    event_lookup_dict = {}
    for i, backblast in enumerate(paxminer_backblasts):
        event_key = f"{backblast.ao_id}-{backblast.bd_date}-{backblast.q_user_id}"
        event_lookup_dict[event_key] = events[i].id

    return event_lookup_dict


def run_paxminer_migration(region_org_id: int):
    region_org_record = DbManager.get(Org, region_org_id, joinedloads=[Org.slack_space])
    region_record = SlackSettings(**region_org_record.slack_space.settings)
    engine = get_pm_engine(schema=region_record.paxminer_schema)
    with engine.connect() as conn:
        paxminer_backblasts = conn.execute(text("SELECT * FROM beatdowns")).fetchall()
        paxminer_attendance = conn.execute(text("SELECT * FROM bd_attendance")).fetchall()
    paxminer_backblasts = [
        Backblast(**{k: v for k, v in backblast._mapping.items() if k in Backblast.__annotations__})
        for backblast in paxminer_backblasts
    ]
    paxminer_attendance = [
        PaxminerAttendance(**{k: v for k, v in attendance._mapping.items() if k in PaxminerAttendance.__annotations__})
        for attendance in paxminer_attendance
    ]
    engine.dispose()

    # pull ao records
    aos = DbManager.find_records(Org, filters=[Org.parent_id == region_record.org_id, Org.org_type == Org_Type.ao])
    slack_org_dict = {safe_get(ao.meta, "slack_channel_id"): ao.id for ao in aos if ao.meta}
    # slack_org_dict.update(**AO_CHANNEL_MAP)

    # pull slack users
    slack_users: List[SlackUser] = DbManager.find_records(
        SlackUser, filters=[SlackUser.slack_team_id == region_record.team_id]
    )
    slack_user_dict = {user.slack_id: user.user_id for user in slack_users}

    # import past events
    events = convert_events(paxminer_backblasts, slack_org_dict=slack_org_dict, region_org_id=region_record.org_id)
    events: List[EventInstance] = DbManager.create_records(events)
    event_lookup_dict = build_event_lookup_dict(paxminer_backblasts, events)

    # import past attendance
    attendance = convert_attendance(paxminer_attendance, slack_user_dict, event_lookup_dict)
    attendance = DbManager.create_records(attendance)

    print(f"Imported {len(events)} events and {len(attendance)} attendance records.")
    print(f"Original {len(paxminer_backblasts)} backblasts and {len(paxminer_attendance)} attendance records.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--region_org_id", help="The region org id to migrate to")
    args = parser.parse_args()
    run_paxminer_migration(int(args.region_org_id))
