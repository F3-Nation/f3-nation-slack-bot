from dataclasses import dataclass
from typing import Any, List

from f3_data_models.models import (
    Attendance,
    Attendance_x_AttendanceType,
    Event,
    EventTag,
    EventType,
    EventType_x_Event,
    Location,
    Org,
    Permission,
    Role,
    Role_x_Permission,
    Role_x_User_x_Org,
    SlackUser,
    User,
)
from f3_data_models.utils import _joinedloads, get_session
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import joinedload

from utilities.constants import ALL_PERMISSIONS, PERMISSIONS


@dataclass
class CalendarHomeQuery:
    event: Event
    org: Org
    event_types: List[EventType]
    planned_qs: str = None
    user_attending: int = None
    user_q: int = None


def home_schedule_query(
    user_id: int, filters: list, limit: int = 45, open_q_only: bool = False
) -> list[CalendarHomeQuery]:
    session = get_session()
    # Create an alias for Attendance to use in the subquery
    # AttendanceAlias = aliased(AttendanceNew)

    # Create the subquery
    subquery = (
        select(
            Attendance.event_id,
            func.string_agg(
                case((Attendance_x_AttendanceType.attendance_type_id.in_([2, 3]), User.f3_name), else_=None), ","
            ).label("planned_qs"),
            func.max(case((Attendance.user_id == user_id, 1), else_=0)).label("user_attending"),
            func.max(
                case(
                    (
                        and_(Attendance.user_id == user_id, Attendance_x_AttendanceType.attendance_type_id.in_([2, 3])),
                        1,
                    ),
                    else_=0,
                )
            ).label("user_q"),
        )
        .select_from(Attendance)
        .join(User, User.id == Attendance.user_id)
        .join(Attendance_x_AttendanceType, Attendance.id == Attendance_x_AttendanceType.attendance_id)
        .group_by(Attendance.event_id)
        .alias()
    )

    if open_q_only:
        filters.append(subquery.c.planned_qs == None)  # noqa: E711

    # Create the main query
    query = (
        select(Event, Org, EventType, subquery.c.planned_qs, subquery.c.user_attending, subquery.c.user_q)
        .join(Org, Org.id == Event.org_id)
        .join(EventType_x_Event, EventType_x_Event.event_id == Event.id)
        .join(EventType, EventType.id == EventType_x_Event.event_type_id)
        .outerjoin(subquery, subquery.c.event_id == Event.id)
        .filter(*filters)
        .order_by(Event.start_date, Event.id, Org.name, Event.start_time)
        .limit(limit)
    )

    # To execute the query and fetch all results
    results = session.execute(query).all()

    # results: List[Tuple[Event, Org, EventType, str, str, str]] = result.scalars().all()
    # print(results)

    # Turn EventType into a list of EventType objects for each Event.id
    event_types = {}
    for r in results:
        event_types.setdefault(r[0].id, []).append(r[2])

    # Turn the results into a list of CalendarHomeQuery objects
    output = []

    for r in results:
        output.append(
            CalendarHomeQuery(
                event=r[0],
                org=r[1],
                event_types=event_types.get(r[0].id, []),
                planned_qs=r[3],
                user_attending=r[4],
                user_q=r[5],
            )
        )
    session.close()
    return output


@dataclass
class EventExtended:
    event: Event
    org: Org
    event_types: List[EventType]
    location: Location
    event_tags: List[EventTag]
    org_slack_id: str


@dataclass
class AttendanceExtended:
    attendance: Attendance
    user: User
    slack_user: SlackUser


def event_attendance_query(attendance_filter: List[Any] = None, event_filter: List[Any] = None) -> List[Event]:
    with get_session() as session:
        attendance_subquery = (
            select(Attendance.event_id.distinct().label("event_id"))
            .options(joinedload(Attendance.attendance_types))
            .filter(*(attendance_filter or []))
            .alias()
        )
        query = (
            select(Event)
            .join(attendance_subquery, attendance_subquery.c.event_id == Event.id)
            .filter(*(event_filter or []))
            .order_by(Event.start_date, Event.start_time)
        )
        query = _joinedloads(Event, query, "all")
        event_records = session.scalars(query).unique().all()
        return event_records


def get_user_permission_list(user_id: int, org_id: int) -> list[Permission]:
    with get_session() as session:
        query = (
            session.query(Permission)
            .join(Role_x_Permission, Role_x_Permission.permission_id == Permission.id)
            .join(Role, Role.id == Role_x_Permission.role_id)
            .join(Role_x_User_x_Org, Role_x_User_x_Org.role_id == Role.id)
            .filter(Role_x_User_x_Org.user_id == user_id, Role_x_User_x_Org.org_id == org_id)
        )
        return query.all()


def get_admin_users_list(org_id: int) -> list[SlackUser]:
    with get_session() as session:
        query = (
            session.query(SlackUser)
            .join(Role_x_User_x_Org, Role_x_User_x_Org.user_id == SlackUser.user_id)
            .join(Role, Role.id == Role_x_User_x_Org.role_id)
            .join(Role_x_Permission, Role_x_Permission.role_id == Role.id)
            .join(Permission, Permission.id == Role_x_Permission.permission_id)
            .filter(Permission.name == PERMISSIONS[ALL_PERMISSIONS], Role_x_User_x_Org.org_id == org_id)
        )
        return query.all()
