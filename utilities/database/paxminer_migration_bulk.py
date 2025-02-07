import argparse
import json
import os
import sys
from typing import Dict, List

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from f3_data_models.models import (
    Attendance,
    Attendance_x_AttendanceType,
    Event,
    EventType_x_Event,
    Org,
    SlackUser,
    User,
)
from f3_data_models.utils import DbManager
from sqlalchemy import text

from utilities.database.orm.paxminer import Attendance as PaxminerAttendance
from utilities.database.orm.paxminer import Backblast, PaxminerAO, PaxminerRegion, PaxminerUser, get_pm_engine


def extract_name(backblast: str) -> str:
    # extract the name of the event from the backblast
    # this is a very basic implementation, and will need to be updated
    # to handle the various ways that backblasts are formatted
    # this is just a placeholder
    name = backblast.split("\n")[0]
    if name:
        return name[:50]
    else:
        return "Backblast"


def convert_region(paxminer_region: PaxminerRegion) -> Org:
    return Org(
        org_type_id=2,
        name=paxminer_region.region,
        is_active=True,
    )


def convert_aos(paxminer_aos: list[PaxminerAO], org_id: int) -> List[Org]:
    aos: List[Org] = []
    aos = [
        Org(
            org_type_id=1,
            parent_id=org_id,
            name=ao.ao,
            is_active=True,
            meta={"slack_channel_id": ao.channel_id},
        )
        for ao in paxminer_aos
    ]
    return aos


def convert_users(paxminer_users: list[PaxminerUser], slack_team_id: str) -> List[SlackUser]:
    users: List[User] = []
    users = [
        User(
            f3_name=user.user_name,
            first_name=user.real_name.split(" ")[0],
            last_name=" ".join(user.real_name.split(" ")[1:]),
            email=user.user_id if user.email == "None" else user.email,
            phone=user.phone,
        )
        for user in paxminer_users
    ]
    DbManager.create_or_ignore(User, users)
    users = DbManager.find_records(User, filters=[True])
    user_dict = {user.email: user.id for user in users}

    slack_users: List[SlackUser] = []
    for user in paxminer_users:
        email = user.user_id if user.email == "None" else user.email
        slack_users.append(
            SlackUser(
                slack_id=user.user_id,
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


def convert_events(paxminer_backblasts: list[Backblast], slack_org_dict: Dict, region_org_id: int) -> List[Event]:
    events: List[Event] = []
    events = [
        Event(
            org_id=slack_org_dict.get(backblast.ao_id) or region_org_id,  # will return none if not found
            is_series=False,
            is_active=True,
            highlight=False,
            start_date=backblast.bd_date,
            end_date=backblast.bd_date,
            name=extract_name(backblast.backblast),
            pax_count=backblast.pax_count,
            fng_count=backblast.fng_count,
            backblast=backblast.backblast_parsed,
            meta=json.loads(backblast.json or "{}"),
            backblast_ts=None if backblast.timestamp or "" == "" else float(backblast.timestamp),
            event_x_event_types=[EventType_x_Event(event_type_id=1)],  # can we assume a type based on ao name?
        )
        for backblast in paxminer_backblasts
    ]

    return events


def get_event_id(event_lookup_dict: Dict, ao_id: str, date: str, q_user_id: str) -> int:
    if q_user_id[:5] == "https":
        q_user_id = q_user_id.split("/")[-1]
    event_id = event_lookup_dict.get(f"{ao_id}-{date}-{q_user_id}")
    # if not event_id:
    #     raise ValueError(f"Event not found for {ao_id}-{date}-{q_user_id}")
    return event_id


def convert_attendance(
    paxminer_attendance: list[PaxminerAttendance], slack_user_dict: Dict, event_lookup_dict: Dict
) -> List[Attendance]:
    attendance_list: List[Attendance] = []
    for attendance in paxminer_attendance:
        event_id = get_event_id(event_lookup_dict, attendance.ao_id, attendance.date, attendance.q_user_id)
        if event_id:
            attendance_type_id = 2 if attendance.q_user_id == attendance.user_id else 1  # need to update for coqs
            user_id = slack_user_dict.get(attendance.user_id)
            if user_id:  # this happens when the user_id is "https://", need to fix
                attendance_list.append(
                    Attendance(
                        event_id=event_id,
                        user_id=user_id,
                        attendance_x_attendance_types=[
                            Attendance_x_AttendanceType(attendance_type_id=attendance_type_id)
                        ],
                        is_planned=False,
                    )
                )

    return attendance_list


def build_event_lookup_dict(paxminer_backblasts: List[Backblast], events: List[Event]) -> Dict:
    event_lookup_dict = {}
    for i, backblast in enumerate(paxminer_backblasts):
        event_key = f"{backblast.ao_id}-{backblast.bd_date}-{backblast.q_user_id}"
        event_lookup_dict[event_key] = events[i].id

    return event_lookup_dict


def run_paxminer_migration(from_pm_schema: str = None):
    total_events = 0
    total_attendance = 0
    engine = get_pm_engine(schema="paxminer")
    with engine.connect() as conn:
        if from_pm_schema:
            regions = conn.execute(text(f"SELECT * FROM regions WHERE schema_name = '{from_pm_schema}'")).fetchall()
        else:
            regions = conn.execute(text("SELECT * FROM regions WHERE active = 1 AND team_id IS NOT NULL")).fetchall()
    regions = [PaxminerRegion(**region._mapping) for region in regions]
    engine.dispose()
    for paxminer_region in regions:
        # pull region paxminer data
        engine = get_pm_engine(schema=paxminer_region.schema_name)
        with engine.connect() as conn:
            paxminer_aos = conn.execute(text("SELECT * FROM aos")).fetchall()
            paxminer_backblasts = conn.execute(text("SELECT * FROM beatdowns")).fetchall()
            paxminer_attendance = conn.execute(text("SELECT * FROM bd_attendance")).fetchall()
            paxminer_users = conn.execute(text("SELECT * FROM users")).fetchall()
        paxminer_aos = [PaxminerAO(**ao._mapping) for ao in paxminer_aos]
        paxminer_backblasts = [Backblast(**backblast._mapping) for backblast in paxminer_backblasts]
        paxminer_attendance = [PaxminerAttendance(**attendance._mapping) for attendance in paxminer_attendance]
        paxminer_users = [PaxminerUser(**user._mapping) for user in paxminer_users]
        engine.dispose()

        # region record
        region_org = convert_region(paxminer_region)
        region_org: Org = DbManager.create_record(region_org)

        # ao records
        # creates an org for every channel
        aos = convert_aos(paxminer_aos, region_org.id)
        aos: List[Org] = DbManager.create_records(aos)
        slack_org_dict = {ao.meta["slack_channel_id"]: ao.id for ao in aos}

        # slack users
        slack_users = convert_users(paxminer_users, slack_team_id=paxminer_region.team_id or "NO_TEAM_ID")
        slack_users: List[SlackUser] = DbManager.create_records(slack_users)
        slack_user_dict = {user.slack_id: user.user_id for user in slack_users}

        # past events
        events = convert_events(paxminer_backblasts, slack_org_dict=slack_org_dict, region_org_id=region_org.id)
        events: List[Event] = DbManager.create_records(events)
        event_lookup_dict = build_event_lookup_dict(paxminer_backblasts, events)

        # past attendance
        attendance = convert_attendance(paxminer_attendance, slack_user_dict, event_lookup_dict)
        attendance = DbManager.create_records(attendance)

        print(f"Region: {region_org.name}")
        print(f"Backblasts found: {len(paxminer_backblasts)}")
        print(f"Events created: {len(events)}")
        print(f"Attendance records found: {len(paxminer_attendance)}")
        print(f"Attendance records created: {len(attendance)}")

        total_events += len(events)
        total_attendance += len(attendance)

    print(f"Total events created: {total_events}")
    print(f"Total attendance records created: {total_attendance}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--from_pm_schema", help="The schema name in the paxminer database to migrate from")
    args = parser.parse_args()
    run_paxminer_migration(args.from_pm_schema)
