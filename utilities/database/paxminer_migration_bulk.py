import argparse
import json
import os
import sys
import uuid
from datetime import date
from typing import Dict, List

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

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

from utilities.database.orm.paxminer import Attendance as PaxminerAttendance
from utilities.database.orm.paxminer import Backblast, PaxminerAO, PaxminerRegion, PaxminerUser, get_pm_engine

AO_MAP = {
    "C02Q94GPSHE": {"org_id": 34200, "event_type_id": 1},
    "C02Q94HAM40": {"org_id": 45530, "event_type_id": 1},
    "C02PCMMSM9C": {"org_id": 47013, "event_type_id": 1},
    "C02Q94GUFLG": {"org_id": 48592, "event_type_id": 1},
    "C02PMLKCYLU": {"org_id": 34214, "event_type_id": 1},
    "C02NH9HJ1RD": {"org_id": 34225, "event_type_id": 1},
    "C02PY1Y9TLZ": {"org_id": 25221, "event_type_id": 1},
    "C02Q79ZMSMP": {"org_id": 48592, "event_type_id": 1},
    "C02PKDPEU3D": {"org_id": 32138, "event_type_id": 1},
    "C02PKDQJDHR": {"org_id": 40331, "event_type_id": 1},
    "C02PMLM65BN": {"org_id": 34226, "event_type_id": 1},
    "C02PGLVJLLT": {"org_id": 40945, "event_type_id": 1},
    "C02T0MZDPED": {"org_id": 36346, "event_type_id": 1},
    "C02SRR8HZQD": {"org_id": 25221, "event_type_id": 1},
    "C04DM8RNRCP": {"org_id": 44073, "event_type_id": 1},
    "C02P22R0HCP": {"org_id": 34225, "event_type_id": 1},
    "C05LCSGEN02": {"org_id": 43510, "event_type_id": 1},
    "C02P1AAA1T9": {"org_id": 34200, "event_type_id": 1},
    "C02P4FUM8E9": {"org_id": 45530, "event_type_id": 1},
    "C056TJAJ0KE": {"org_id": 45664, "event_type_id": 1},
    "C05T7UPSDMW": {"org_id": 34226, "event_type_id": 1},
    "C02PKCPLGR0": {"org_id": 34200, "event_type_id": 1},
    "C05HB2UJN5B": {"org_id": 25221, "event_type_id": 1},
    "C050YKMRF8D": {"org_id": 42193, "event_type_id": 1},
    "C079XGFJS9J": {"org_id": 47013, "event_type_id": 1},
    "C07MUDM864R": {"org_id": 47979, "event_type_id": 1},
    "C06Q28HD58T": {"org_id": 48592, "event_type_id": 1},
    "C04GYJTKMK5": {"org_id": 46848, "event_type_id": 1},
    "C9FQMABPV": {"org_id": 25221, "event_type_id": 4},
    "C07GK1KJCJ1": {"org_id": 48395, "event_type_id": 1},
    "C086QV4B8BY": {"org_id": 25221, "event_type_id": 1},
    "C04N44M8C2Z": {"org_id": 25221, "event_type_id": 1},
    "C9FTHRZMY": {"org_id": 25221, "event_type_id": 1},
    "C03S3C100HK": {"org_id": 25221, "event_type_id": 1},
    "C06LUBZCGDP": {"org_id": 25221, "event_type_id": 4},
    "C07KXQ0PGTC": {"org_id": 48592, "event_type_id": 1},
    "C07KV060FE1": {"org_id": 32138, "event_type_id": 1},
    "C07KV04LRPX": {"org_id": 44073, "event_type_id": 1},
    "C07KXS2CLN6": {"org_id": 36346, "event_type_id": 1},
    "C07LAGDSGE5": {"org_id": 48395, "event_type_id": 1},
    "C07KXRUUAEN": {"org_id": 48592, "event_type_id": 1},
    "C07KV027WE9": {"org_id": 42193, "event_type_id": 1},
    "C08DKE114UU": {"org_id": 49393, "event_type_id": 1},
    "C07L0AUG1AQ": {"org_id": 48180, "event_type_id": 1},
    "C07KV015V1T": {"org_id": 48180, "event_type_id": 1},
    "C04KZDLT84C": {"org_id": 40945, "event_type_id": 1},
    "C04KX00DYD8": {"org_id": 43842, "event_type_id": 1},
    "C04LLLD1400": {"org_id": 46848, "event_type_id": 1},
    "C04SDFYHLR4": {"org_id": 46850, "event_type_id": 1},
    "C04KWRYHLSF": {"org_id": 41195, "event_type_id": 1},
    "C058ZE4EJ1G": {"org_id": 43842, "event_type_id": 1},
    "C050DF95FU4": {"org_id": 43842, "event_type_id": 1},
    "C071QU7NP0F": {"org_id": 46851, "event_type_id": 1},
    "C076A7B1JR1": {"org_id": 43842, "event_type_id": 1},
    "C04R6QJ7F37": {"org_id": 43842, "event_type_id": 1},
    "C04KURJNU3C": {"org_id": 43842, "event_type_id": 1},
    "C050B1ZMMQS": {"org_id": 43842, "event_type_id": 1},
    "C08N24J2QG1": {"org_id": 43842, "event_type_id": 1},
    "C04F1EDFB8R": {"org_id": 37815, "event_type_id": 1},
    "C04GPEG78HH": {"org_id": 43403, "event_type_id": 1},
    "C04GYBW77SR": {"org_id": 46299, "event_type_id": 1},
    "C04RQPFM743": {"org_id": 41674, "event_type_id": 1},
    "C05MK8JP142": {"org_id": 43769, "event_type_id": 1},
    "C060K5ZB160": {"org_id": 44339, "event_type_id": 1},
    "C05509F94JD": {"org_id": 42479, "event_type_id": 1},
    "C059ZTAQYUA": {"org_id": 42887, "event_type_id": 1},
    "C06HX4WCM40": {"org_id": 45681, "event_type_id": 1},
    "C04HD3J9CRZ": {"org_id": 40364, "event_type_id": 1},
    "C06AFTF7S9M": {"org_id": 40364, "event_type_id": 1},
    "C04EKSK73L5": {"org_id": 40364, "event_type_id": 1},
    "C04E891BACF": {"org_id": 40364, "event_type_id": 1},
}
AO_CHANNEL_MAP = {k: v["org_id"] for k, v in AO_MAP.items()}
AO_TYPE_MAP = {k: v["event_type_id"] for k, v in AO_MAP.items()}


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


def convert_aos(paxminer_aos: list[PaxminerAO], org_id: int) -> List[Org]:
    aos: List[Org] = []
    for ao in paxminer_aos:
        if ao.channel_id not in AO_CHANNEL_MAP:
            aos.append(
                Org(
                    org_type=Org_Type.ao,
                    parent_id=org_id,
                    name=ao.ao,
                    is_active=True,
                    meta={"slack_channel_id": ao.channel_id},
                )
            )
    return aos


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
            backblast.bd_date = date(2020, 1, 1)
    events = [
        EventInstance(
            org_id=slack_org_dict.get(backblast.ao_id) or region_org_id,  # will return none if not found
            is_active=True,
            highlight=False,
            start_date=backblast.bd_date if backblast.bd_date > date(2020, 1, 1) else date(2020, 1, 1),
            end_date=backblast.bd_date if backblast.bd_date > date(2020, 1, 1) else date(2020, 1, 1),
            name=extract_name(backblast.backblast),
            pax_count=backblast.pax_count,
            fng_count=backblast.fng_count,
            backblast=backblast.backblast_parsed,
            meta=json.loads(backblast.json or "{}"),
            backblast_ts=None if backblast.timestamp or "" == "" else float(backblast.timestamp),
            event_instances_x_event_types=[
                EventType_x_EventInstance(event_type_id=AO_TYPE_MAP.get(backblast.ao_id) or 1)
            ],
        )
        for backblast in paxminer_backblasts
    ]

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


def run_paxminer_migration(from_pm_schema: str = None, to_region_org_id: int = None) -> str:
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
            paxminer_aos = conn.execute(
                text("SELECT a.* FROM aos a INNER JOIN beatdowns b on a.channel_id = b.ao_id")
            ).fetchall()
            paxminer_backblasts = conn.execute(text("SELECT * FROM beatdowns")).fetchall()
            paxminer_attendance = conn.execute(text("SELECT * FROM bd_attendance")).fetchall()
            paxminer_users = conn.execute(text("SELECT * FROM users")).fetchall()
        paxminer_aos = [
            PaxminerAO(**{k: v for k, v in ao._mapping.items() if k in PaxminerAO.__annotations__})
            for ao in paxminer_aos
        ]
        paxminer_backblasts = [
            Backblast(**{k: v for k, v in backblast._mapping.items() if k in Backblast.__annotations__})
            for backblast in paxminer_backblasts
        ]
        paxminer_attendance = [
            PaxminerAttendance(
                **{k: v for k, v in attendance._mapping.items() if k in PaxminerAttendance.__annotations__}
            )
            for attendance in paxminer_attendance
        ]
        paxminer_users = [
            PaxminerUser(**{k: v for k, v in user._mapping.items() if k in PaxminerUser.__annotations__})
            for user in paxminer_users
        ]
        engine.dispose()

        # region record
        if to_region_org_id:
            region_org = DbManager.get(Org, to_region_org_id)
        else:
            region_org = convert_region(paxminer_region)
            region_org: Org = DbManager.create_record(region_org)

        # ao records
        # creates an org for every channel
        aos = convert_aos(paxminer_aos, region_org.id)
        aos: List[Org] = DbManager.create_records(aos)
        slack_org_dict = {ao.meta["slack_channel_id"]: ao.id for ao in aos}
        slack_org_dict.update(**AO_CHANNEL_MAP)

        # slack users
        slack_users = convert_users(paxminer_users, slack_team_id=paxminer_region.team_id or "NO_TEAM_ID")
        slack_users: List[SlackUser] = DbManager.create_records(slack_users)
        slack_user_dict = {user.slack_id: user.user_id for user in slack_users}

        # past events
        events = convert_events(paxminer_backblasts, slack_org_dict=slack_org_dict, region_org_id=region_org.id)
        events: List[EventInstance] = DbManager.create_records(events)
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

    msg = f"Total events created: {total_events}\nTotal attendance records created: {total_attendance}"
    print(msg)
    return msg


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--from_pm_schema", help="The schema name in the paxminer database to migrate from")
    parser.add_argument("--to_region_org_id", help="The region org id to migrate to")
    args = parser.parse_args()
    print(args)
    run_paxminer_migration(args.from_pm_schema, int(args.to_region_org_id) if args.to_region_org_id else None)
