from dataclasses import dataclass
from typing import Any, List

from f3_data_models.models import (
    Attendance,
    Attendance_x_AttendanceType,
    EventInstance,
    EventTag,
    EventType,
    EventType_x_EventInstance,
    Location,
    Org,
    Org_Type,
    Permission,
    Position,
    Position_x_Org_x_User,
    Role,
    Role_x_Permission,
    Role_x_User_x_Org,
    SlackUser,
    User,
)
from f3_data_models.utils import _joinedloads, get_session
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import joinedload

from utilities.constants import ALL_PERMISSIONS, PERMISSIONS


@dataclass
class CalendarHomeQuery:
    event: EventInstance
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
            Attendance.event_instance_id,
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
        .join(EventInstance, EventInstance.id == Attendance.event_instance_id)
        .join(EventType_x_EventInstance, EventType_x_EventInstance.event_instance_id == EventInstance.id)
        .join(EventType, EventType.id == EventType_x_EventInstance.event_type_id)
        .join(Org, Org.id == EventInstance.org_id)
        .filter(*filters)
        .group_by(Attendance.event_instance_id)
        .alias()
    )

    if open_q_only:
        filters.append(subquery.c.planned_qs == None)  # noqa: E711

    # Create the main query
    query = (
        select(EventInstance, Org, EventType, subquery.c.planned_qs, subquery.c.user_attending, subquery.c.user_q)
        .join(Org, Org.id == EventInstance.org_id)
        .join(EventType_x_EventInstance, EventType_x_EventInstance.event_instance_id == EventInstance.id)
        .join(EventType, EventType.id == EventType_x_EventInstance.event_type_id)
        .outerjoin(subquery, subquery.c.event_instance_id == EventInstance.id)
        .filter(*filters)
        .order_by(EventInstance.start_date, EventInstance.id, Org.name, EventInstance.start_time)
        .limit(limit)
    )

    # To execute the query and fetch all results
    results = session.execute(query).all()

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
    event: EventInstance
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


def event_attendance_query(attendance_filter: List[Any] = None, event_filter: List[Any] = None) -> List[EventInstance]:
    with get_session() as session:
        attendance_subquery = (
            select(Attendance.event_instance_id.distinct().label("event_instance_id"))
            .options(joinedload(Attendance.attendance_types))
            .filter(*(attendance_filter or []))
            .alias()
        )
        query = (
            select(EventInstance)
            .join(attendance_subquery, attendance_subquery.c.event_instance_id == EventInstance.id)
            .filter(*(event_filter or []))
            .order_by(EventInstance.start_date, EventInstance.start_time)
        )
        query = _joinedloads(EventInstance, query, "all")
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


def get_admin_users_list(org_id: int, slack_team_id: str) -> list[SlackUser]:
    with get_session() as session:
        query = (
            session.query(SlackUser)
            .join(Role_x_User_x_Org, Role_x_User_x_Org.user_id == SlackUser.user_id)
            .join(Role, Role.id == Role_x_User_x_Org.role_id)
            .join(Role_x_Permission, Role_x_Permission.role_id == Role.id)
            .join(Permission, Permission.id == Role_x_Permission.permission_id)
            .filter(
                Permission.name == PERMISSIONS[ALL_PERMISSIONS],
                Role_x_User_x_Org.org_id == org_id,
                SlackUser.slack_team_id == slack_team_id,
            )
        )
        return query.all()


@dataclass
class PositionExtended:
    position: Position
    slack_users: List[SlackUser]


def get_position_users(org_id: int, region_org_id: int, slack_team_id: str) -> List[PositionExtended]:
    org_type_level = Org_Type.region if region_org_id == org_id else Org_Type.ao
    with get_session() as session:
        query = (
            session.query(Position, SlackUser)
            .select_from(Position)
            .join(
                Position_x_Org_x_User,
                and_(Position_x_Org_x_User.position_id == Position.id, Position_x_Org_x_User.org_id == org_id),
                isouter=True,
            )
            .join(User, User.id == Position_x_Org_x_User.user_id, isouter=True)
            .join(SlackUser, and_(SlackUser.user_id == User.id, SlackUser.slack_team_id == slack_team_id), isouter=True)
            .filter(or_(Position.org_type == org_type_level, Position.org_type.is_(None)))
            .order_by(Position.id)
        )
        positions = {}
        for position, slack_user in query.all():
            positions.setdefault(position, []).append(slack_user)

        output = []
        for position, slack_users in positions.items():
            output.append(PositionExtended(position=position, slack_users=slack_users))

        return output


def get_admin_users(org_id: int, slack_team_id: str) -> List[tuple[User, SlackUser]]:
    with get_session() as session:
        query = (
            session.query(User, SlackUser)
            .join(Role_x_User_x_Org, and_(Role_x_User_x_Org.user_id == User.id, Role_x_User_x_Org.org_id == org_id))
            .join(Role, and_(Role.id == Role_x_User_x_Org.role_id, Role.name == "admin"))
            .join(SlackUser, and_(SlackUser.user_id == User.id, SlackUser.slack_team_id == slack_team_id), isouter=True)
        )
        return query.all()


def make_user_admin(org_id: int, user_id: int) -> None:
    with get_session() as session:
        # Check if the user is already an admin
        existing_admin = (
            session.query(Role_x_User_x_Org)
            .filter(Role_x_User_x_Org.user_id == user_id, Role_x_User_x_Org.org_id == org_id)
            .join(Role, Role.id == Role_x_User_x_Org.role_id)
            .filter(Role.name == "admin")
            .first()
        )
        if existing_admin:
            return  # User is already an admin

        # Create a new admin role if it doesn't exist
        admin_role = session.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            admin_role = Role(name="admin")
            session.add(admin_role)
            session.commit()

        # Assign the admin role to the user
        new_admin = Role_x_User_x_Org(user_id=user_id, org_id=org_id, role_id=admin_role.id)
        session.add(new_admin)
        session.commit()
