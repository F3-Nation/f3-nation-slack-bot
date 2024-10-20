from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Optional

from sqlalchemy import DateTime, Double, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import BYTEA, DATE, JSONB, TEXT, TIME
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, registry
from typing_extensions import Annotated

mapper_registry = registry()

str30 = Annotated[str, String(30)]
str45 = Annotated[str, String(45)]
str90 = Annotated[str, String(90)]
str100 = Annotated[str, String(100)]
str255 = Annotated[str, String(255)]
intpk = Annotated[int, mapped_column(Integer, primary_key=True, autoincrement=True)]
smallint = Annotated[int, mapped_column(Integer, default=0)]
smallint1 = Annotated[int, mapped_column(Integer, default=1)]
text = Annotated[str, TEXT]
jsonb = Annotated[dict, JSONB]
dt_create = Annotated[datetime, mapped_column(DateTime, server_default=func.timezone("utc", func.now()))]
dt_update = Annotated[
    datetime,
    mapped_column(DateTime, server_default=func.timezone("utc", func.now()), onupdate=func.timezone("utc", func.now())),
]
str45pk = Annotated[str, mapped_column(String(45), primary_key=True)]
datepk = Annotated[date, mapped_column(DATE, primary_key=True)]
bytea = Annotated[bytes, BYTEA]
dec16_6 = Annotated[float, mapped_column(Double(precision=16, decimal_return_scale=6))]
time_notz = Annotated[time, TIME]
dt = Annotated[datetime, DateTime]


class BaseClass(DeclarativeBase):
    type_annotation_map = {
        str30: String(30),
        str45: String(45),
        str90: String(90),
        str100: String(100),
        str255: String(255),
        dict[str, Any]: JSONB,
        text: TEXT,
        time_notz: TIME,
    }


class GetDBClass:
    def get_id(self):
        return self.id

    def get(self, attr):
        if attr in [c.key for c in self.__table__.columns]:
            return getattr(self, attr)
        return None

    def to_json(self):
        return {c.key: self.get(c.key) for c in self.__table__.columns if c.key not in ["created", "updated"]}

    def __repr__(self):
        return str(self.to_json())

    def _update(self, fields):
        for k, v in fields.items():
            attr_name = str(k).split(".")[-1]
            setattr(self, attr_name, v)
        return self


# class SlackSettings(BaseClass, GetDBClass):
#     __tablename__ = "slack_spaces"
#     id: Mapped[intpk]
#     team_id: Mapped[str100]
#     workspace_name: Mapped[Optional[str100]]
#     bot_token: Mapped[Optional[str100]]
#     email_enabled: Mapped[smallint]
#     email_server: Mapped[Optional[str100]]
#     email_server_port: Mapped[Optional[int]]
#     email_user: Mapped[Optional[str100]]
#     email_password: Mapped[Optional[text]]
#     email_to: Mapped[Optional[str100]]
#     email_option_show: Mapped[Optional[smallint]]
#     postie_format: Mapped[Optional[smallint1]]
#     editing_locked: Mapped[smallint]
#     default_destination: Mapped[Optional[str]] = mapped_column(String(30), default="ao_channel")
#     destination_channel: Mapped[Optional[str100]]
#     backblast_moleskin_template: Mapped[Optional[dict[str, Any]]]
#     preblast_moleskin_template: Mapped[Optional[dict[str, Any]]]
#     strava_enabled: Mapped[Optional[smallint1]]
#     custom_fields: Mapped[Optional[dict[str, Any]]]
#     welcome_dm_enable: Mapped[Optional[smallint]]
#     welcome_dm_template: Mapped[Optional[dict[str, Any]]]
#     welcome_channel_enable: Mapped[Optional[smallint]]
#     welcome_channel: Mapped[Optional[str100]]
#     send_achievements: Mapped[Optional[smallint1]]
#     send_aoq_reports: Mapped[Optional[smallint1]]
#     achievement_channel: Mapped[Optional[str100]]
#     default_siteq: Mapped[Optional[str45]]
#     NO_POST_THRESHOLD: Mapped[Optional[int]] = mapped_column(Integer, default=2)
#     REMINDER_WEEKS: Mapped[Optional[int]] = mapped_column(Integer, default=2)
#     HOME_AO_CAPTURE: Mapped[Optional[int]] = mapped_column(Integer, default=8)
#     NO_Q_THRESHOLD_WEEKS: Mapped[Optional[int]] = mapped_column(Integer, default=4)
#     NO_Q_THRESHOLD_POSTS: Mapped[Optional[int]] = mapped_column(Integer, default=4)
#     org_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("orgs.id"))
#     calendar_image_current: Mapped[Optional[str255]]
#     calendar_image_next: Mapped[Optional[str255]]
#     preblast_reminder_days: Mapped[Optional[int]]
#     backblast_reminder_days: Mapped[Optional[int]]
#     special_events_enabled: Mapped[Optional[smallint]]
#     special_events_channel: Mapped[Optional[str100]]
#     special_events_post_days: Mapped[Optional[int]]
#     created: Mapped[dt_create]
#     updated: Mapped[dt_update]

#     def get_id():
#         return SlackSettings.team_id


@dataclass
class SlackSettings:
    team_id: str
    db_id: Optional[int] = None
    workspace_name: Optional[str] = None
    bot_token: Optional[str] = None
    email_enabled: Optional[int] = None
    email_server: Optional[str] = None
    email_server_port: Optional[int] = None
    email_user: Optional[str] = None
    email_password: Optional[str] = None
    email_to: Optional[str] = None
    email_option_show: Optional[int] = None
    postie_format: Optional[int] = None
    editing_locked: Optional[int] = None
    default_backblast_destination: Optional[str] = None
    backblast_destination_channel: Optional[str] = None
    default_preblast_destination: Optional[str] = None
    preblast_destination_channel: Optional[str] = None
    backblast_moleskin_template: Optional[dict[str, Any]] = None
    preblast_moleskin_template: Optional[dict[str, Any]] = None
    strava_enabled: Optional[int] = None
    custom_fields: Optional[dict[str, Any]] = None
    welcome_dm_enable: Optional[int] = None
    welcome_dm_template: Optional[dict[str, Any]] = None
    welcome_channel_enable: Optional[int] = None
    welcome_channel: Optional[str] = None
    send_achievements: Optional[int] = None
    send_aoq_reports: Optional[int] = None
    achievement_channel: Optional[str] = None
    default_siteq: Optional[str] = None
    NO_POST_THRESHOLD: Optional[int] = None
    REMINDER_WEEKS: Optional[int] = None
    HOME_AO_CAPTURE: Optional[int] = None
    NO_Q_THRESHOLD_WEEKS: Optional[int] = None
    NO_Q_THRESHOLD_POSTS: Optional[int] = None
    org_id: Optional[int] = (
        None  # NOTE: down the road, we may not want this here, for example if we want a slack space to be associated with multiple orgs # noqa
    )
    calendar_image_current: Optional[str] = None
    calendar_image_next: Optional[str] = None
    preblast_reminder_days: Optional[int] = None
    backblast_reminder_days: Optional[int] = None
    special_events_enabled: Optional[int] = None
    special_events_channel: Optional[str] = None
    special_events_post_days: Optional[int] = None


class SlackSpace(BaseClass, GetDBClass):
    __tablename__ = "slack_spaces"
    # id: Mapped[intpk]
    team_id: Mapped[str100] = mapped_column(String(100), primary_key=True)
    workspace_name: Mapped[Optional[str100]]
    bot_token: Mapped[Optional[str100]]
    settings: Mapped[Optional[dict[str, Any]]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return SlackSpace.team_id


class Org_x_Slack(BaseClass, GetDBClass):
    __tablename__ = "orgs_x_slack"
    id: Mapped[intpk]
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("orgs.id"))
    slack_id: Mapped[str100]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return Org_x_Slack.id


class Event(BaseClass, GetDBClass):
    __tablename__ = "events"

    id: Mapped[intpk]
    org_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("orgs.id"))
    location_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("locations.id"))
    event_type_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("event_types.id"))
    event_tag_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("event_tags.id"))
    series_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("events.id"))
    is_series: Mapped[bool]
    is_active: Mapped[bool]
    highlight: Mapped[bool]
    start_date: Mapped[date]
    end_date: Mapped[Optional[date]]
    start_time: Mapped[Optional[time_notz]]
    end_time: Mapped[Optional[time_notz]]
    day_of_week: Mapped[Optional[int]]
    name: Mapped[str100]
    description: Mapped[Optional[text]]
    recurrence_pattern: Mapped[Optional[str30]]
    recurrence_interval: Mapped[Optional[int]]
    index_within_interval: Mapped[Optional[int]]
    pax_count: Mapped[Optional[int]]
    fng_count: Mapped[Optional[int]]
    preblast: Mapped[Optional[text]]
    backblast: Mapped[Optional[text]]
    preblast_rich: Mapped[Optional[dict[str, Any]]]
    backblast_rich: Mapped[Optional[dict[str, Any]]]
    preblast_ts: Mapped[Optional[dec16_6]]
    backblast_ts: Mapped[Optional[dec16_6]]
    meta: Mapped[Optional[dict[str, Any]]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return Event.id


class EventType(BaseClass, GetDBClass):
    __tablename__ = "event_types"

    id: Mapped[intpk]
    name: Mapped[str100]
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("event_categories.id"))
    description: Mapped[Optional[text]]
    acronym: Mapped[Optional[str30]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return EventType.id


class EventCategory(BaseClass, GetDBClass):
    __tablename__ = "event_categories"

    id: Mapped[intpk]
    name: Mapped[str100]
    description: Mapped[Optional[text]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return EventCategory.id


class Location(BaseClass, GetDBClass):
    __tablename__ = "locations"

    id: Mapped[intpk]
    org_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("orgs.id"))
    name: Mapped[str100]
    description: Mapped[Optional[text]]
    is_active: Mapped[bool]
    lat: Mapped[Optional[float]]
    lon: Mapped[Optional[float]]
    address_street: Mapped[Optional[str255]]
    address_city: Mapped[Optional[str100]]
    address_state: Mapped[Optional[str45]]
    address_zip: Mapped[Optional[str45]]
    meta: Mapped[Optional[dict[str, Any]]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return Location.id


class User(BaseClass, GetDBClass):
    __tablename__ = "users"

    id: Mapped[intpk]
    f3_name: Mapped[str100]
    email: Mapped[str255] = mapped_column(String(255), unique=True)
    home_region_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("orgs.id"))
    avatar_url: Mapped[Optional[str255]]
    meta: Mapped[Optional[dict[str, Any]]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return User.id


class SlackUser(BaseClass, GetDBClass):
    __tablename__ = "slack_users"

    id: Mapped[intpk]
    slack_id: Mapped[str100]
    user_name: Mapped[str100]
    email: Mapped[str255]
    is_admin: Mapped[bool]
    is_owner: Mapped[bool]
    is_bot: Mapped[bool]
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    avatar_url: Mapped[Optional[str255]]
    slack_team_id: Mapped[str100]
    strava_access_token: Mapped[Optional[str100]]
    strava_refresh_token: Mapped[Optional[str100]]
    strava_expires_at: Mapped[Optional[datetime]]
    strava_athlete_id: Mapped[Optional[int]]
    meta: Mapped[Optional[dict[str, Any]]]
    slack_updated: Mapped[Optional[datetime]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return SlackUser.id


class Attendance(BaseClass, GetDBClass):
    __tablename__ = "attendance"

    id: Mapped[intpk]
    event_id: Mapped[int] = mapped_column(Integer, ForeignKey("events.id"))
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    attendance_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("attendance_types.id"))
    is_planned: Mapped[bool]
    meta: Mapped[Optional[dict[str, Any]]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    __table_args__ = (UniqueConstraint("event_id", "user_id", "attendance_type_id", "is_planned", name="event_user"),)

    def get_id():
        return Attendance.id


class AttendanceType(BaseClass, GetDBClass):
    __tablename__ = "attendance_types"

    id: Mapped[intpk]
    type: Mapped[str100]
    description: Mapped[Optional[text]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return AttendanceType.id


class Org(BaseClass, GetDBClass):
    __tablename__ = "orgs"

    id: Mapped[intpk]
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("orgs.id"))
    org_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("org_types.id"))
    default_location_id: Mapped[Optional[int]]  # = mapped_column(Integer, ForeignKey("locations.id"))
    name: Mapped[str100]
    description: Mapped[Optional[text]]
    is_active: Mapped[bool]
    logo: Mapped[Optional[bytea]]
    website: Mapped[Optional[str100]]
    email: Mapped[Optional[str255]]
    twitter: Mapped[Optional[str100]]
    facebook: Mapped[Optional[str100]]
    instagram: Mapped[Optional[str100]]
    last_annual_review: Mapped[Optional[date]]
    meta: Mapped[Optional[dict[str, Any]]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return Org.id


class OrgType(BaseClass, GetDBClass):
    __tablename__ = "org_types"

    id: Mapped[intpk]
    name: Mapped[str100]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return OrgType.id


class EventType_x_Org(BaseClass, GetDBClass):
    __tablename__ = "event_types_x_org"

    id: Mapped[intpk]
    event_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("event_types.id"))
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("orgs.id"))
    is_default: Mapped[bool]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return EventType_x_Org.id


class EventTag(BaseClass, GetDBClass):
    __tablename__ = "event_tags"

    id: Mapped[intpk]
    name: Mapped[str100]
    description: Mapped[Optional[text]]
    color: Mapped[Optional[str30]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return EventTag.id


class EventTag_x_Org(BaseClass, GetDBClass):
    __tablename__ = "event_tags_x_org"

    id: Mapped[intpk]
    event_tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("event_tags.id"))
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("orgs.id"))
    color_override: Mapped[Optional[str30]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return EventTag_x_Org.id


class Role(BaseClass, GetDBClass):
    __tablename__ = "roles"

    id: Mapped[intpk]
    name: Mapped[str100]
    description: Mapped[Optional[text]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return Role.id


class Permission(BaseClass, GetDBClass):
    __tablename__ = "permissions"

    id: Mapped[intpk]
    name: Mapped[str100]
    description: Mapped[Optional[text]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return Permission.id


class Role_x_Permission(BaseClass, GetDBClass):
    __tablename__ = "roles_x_permissions"

    id: Mapped[intpk]
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"))
    permission_id: Mapped[int] = mapped_column(Integer, ForeignKey("permissions.id"))
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return Role_x_Permission.id


class Role_x_User_x_Org(BaseClass, GetDBClass):
    __tablename__ = "roles_x_users_x_orgs"
    __table_args__ = (UniqueConstraint("role_id", "user_id", "org_id", name="_role_user_org_uc"),)

    id: Mapped[intpk]
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"))
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("orgs.id"))
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return Role_x_User_x_Org.id


class Achievement(BaseClass, GetDBClass):
    __tablename__ = "achievements"

    id: Mapped[intpk]
    name: Mapped[str100]
    description: Mapped[Optional[text]]
    verb: Mapped[str100]
    image_url: Mapped[Optional[str255]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return Achievement.id


class Achievement_x_User(BaseClass, GetDBClass):
    __tablename__ = "achievements_x_users"

    id: Mapped[intpk]
    achievement_id: Mapped[int] = mapped_column(Integer, ForeignKey("achievements.id"))
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    date_awarded: Mapped[date]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return Achievement_x_User.id


class Achievement_x_Org(BaseClass, GetDBClass):
    __tablename__ = "achievements_x_orgs"

    id: Mapped[intpk]
    achievement_id: Mapped[int] = mapped_column(Integer, ForeignKey("achievements.id"))
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("orgs.id"))
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return Achievement_x_Org.id
