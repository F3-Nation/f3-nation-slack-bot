from typing import Dict, List

from sqlalchemy import text

from utilities.database import DbManager, get_engine

from .orm import Attendance, Event, Org_x_Slack, SlackSettings, SlackSpace, SlackUser
from .orm.paxminer import Attendance as PaxminerAttendance
from .orm.paxminer import Backblast, PaxminerRegion


def convert_settings(slack_settings: SlackSettings, paxminer_region: PaxminerRegion) -> SlackSettings:
    slack_settings.email_enabled = paxminer_region.email_enabled
    slack_settings.email_server = paxminer_region.email_server
    slack_settings.email_server_port = paxminer_region.email_server_port
    slack_settings.email_user = paxminer_region.email_user
    slack_settings.email_password = paxminer_region.email_password
    slack_settings.email_to = paxminer_region.email_to
    slack_settings.email_option_show = paxminer_region.email_option_show
    slack_settings.postie_format = paxminer_region.postie_format
    slack_settings.editing_locked = paxminer_region.editing_locked
    slack_settings.default_backblast_destination = paxminer_region.default_destination
    slack_settings.backblast_moleskin_template = paxminer_region.backblast_moleskin_template
    slack_settings.preblast_moleskin_template = paxminer_region.preblast_moleskin_template
    slack_settings.strava_enabled = paxminer_region.strava_enabled
    slack_settings.custom_fields = paxminer_region.custom_fields
    slack_settings.welcome_dm_enable = paxminer_region.welcome_dm_enable
    slack_settings.welcome_dm_template = paxminer_region.welcome_dm_template
    slack_settings.welcome_channel_enable = paxminer_region.welcome_channel_enable
    slack_settings.welcome_channel = paxminer_region.welcome_channel
    slack_settings.send_achievements = paxminer_region.send_achievements
    slack_settings.send_aoq_reports = paxminer_region.send_aoq_reports
    slack_settings.achievement_channel = paxminer_region.achievement_channel
    slack_settings.default_siteq = paxminer_region.default_siteq
    slack_settings.NO_POST_THRESHOLD = paxminer_region.NO_POST_THRESHOLD
    slack_settings.REMINDER_WEEKS = paxminer_region.REMINDER_WEEKS
    slack_settings.HOME_AO_CAPTURE = paxminer_region.HOME_AO_CAPTURE
    slack_settings.NO_Q_THRESHOLD_WEEKS = paxminer_region.NO_Q_THRESHOLD_WEEKS
    slack_settings.NO_Q_THRESHOLD_POSTS = paxminer_region.NO_Q_THRESHOLD_POSTS
    return slack_settings


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


def convert_events(paxminer_backblasts: list[Backblast], slack_org_dict: Dict, region_org_id: int) -> List[Event]:
    events: List[Event] = []
    events = [
        Event(
            org_id=slack_org_dict.get(backblast.ao_id) or region_org_id,  # will return none if not found
            event_type_id=1,  # can we assume a type based on ao name?
            is_series=False,
            is_active=True,
            highlight=False,
            start_date=backblast.bd_date,
            end_date=backblast.bd_date,
            name=extract_name(backblast.backblast),
            pax_count=backblast.pax_count,
            fng_count=backblast.fng_count,
            backblast=backblast.backblast_parsed,
            meta=backblast.json,
            backblast_ts=backblast.timestamp,
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
            attendance_list.append(
                Attendance(
                    event_id=event_id,
                    user_id=slack_user_dict.get(attendance.user_id),  # need to handle if user not found?
                    attendance_type_id=2
                    if attendance.q_user_id == attendance.user_id
                    else 1,  # need to update for coqs
                    is_planned=False,
                )
            )

    return attendance_list


def build_event_lookup_dict(paxminer_backblasts: List[Backblast], events: List[Event]) -> Dict:
    event_lookup_dict = {}
    for i, backblast in enumerate(paxminer_backblasts):
        event_key = f"{backblast.ao_id}-{backblast.bd_date}-{backblast.q_user_id}"
        event_lookup_dict[event_key] = events[i].id

    for i, backblast in enumerate(paxminer_backblasts):
        if backblast.coq_user_id:
            event_key = f"{backblast.ao_id}-{backblast.bd_date}-{backblast.coq_user_id}"
            event_lookup_dict[event_key] = events[i].id

    return event_lookup_dict


def run_paxminer_migration(from_pm_schema: str, slack_team_id: str):
    # pull paxminer data
    engine = get_engine(schema="paxminer", paxminer_db=True)
    with engine.connect() as conn:
        paxminer_region = conn.execute(text(f"SELECT * FROM regions WHERE schema_name = '{from_pm_schema}'")).fetchone()
    paxminer_region = PaxminerRegion(**paxminer_region._mapping)
    # pull region paxminer data
    engine = get_engine(schema=from_pm_schema, paxminer_db=True)
    with engine.connect() as conn:
        paxminer_backblasts = conn.execute(text("SELECT * FROM beatdowns")).fetchall()
        paxminer_attendance = conn.execute(text("SELECT * FROM bd_attendance")).fetchall()
        # paxminer_aos = conn.execute(text("SELECT * FROM aos")).fetchall()
    paxminer_backblasts = [Backblast(**backblast._mapping) for backblast in paxminer_backblasts]
    paxminer_attendance = [PaxminerAttendance(**attendance._mapping) for attendance in paxminer_attendance]
    # paxminer_aos = [PaxminerAO(**ao) for ao in paxminer_aos]
    engine.dispose()

    # insert paxminer data

    # region settings
    slack_space: SlackSpace = DbManager.get_record(SlackSpace, slack_team_id)
    slack_settings = SlackSettings(**slack_space.settings)
    # slack_settings = convert_settings(slack_settings, paxminer_region)
    # DbManager.update_record(
    #     cls=SlackSpace, id=slack_space.team_id, fields={SlackSpace.settings: slack_settings.__dict__}
    # )

    # past events
    org_x_slack: List[Org_x_Slack] = DbManager.find_records(Org_x_Slack, filters=[True])
    slack_org_dict = {org.slack_id: org.org_id for org in org_x_slack}
    events = convert_events(paxminer_backblasts, slack_org_dict, region_org_id=slack_settings.org_id)
    print(len(events))
    print(len(paxminer_backblasts))
    events = DbManager.create_records(events)
    event_lookup_dict = build_event_lookup_dict(paxminer_backblasts, events)
    print(len(events))
    print(len(event_lookup_dict))

    # past attendance
    slack_users: List[SlackUser] = DbManager.find_records(SlackUser, filters=[True])
    slack_user_dict = {user.slack_id: user.user_id for user in slack_users}
    attendance = convert_attendance(paxminer_attendance, slack_user_dict, event_lookup_dict)
    print(len(paxminer_attendance))
    print(len(attendance))
    attendance = DbManager.create_records(attendance)
