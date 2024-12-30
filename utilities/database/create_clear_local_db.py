import argparse
import os
import sys

from sqlalchemy import text

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

import logging

from f3_data_models import models
from f3_data_models.utils import get_engine, get_session
from sqlalchemy.engine import Engine
from sqlalchemy_utils import create_database, database_exists

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
logger.addHandler(handler)

parser = argparse.ArgumentParser()


def create_tables():
    logger.info("Creating schemas and tables...")

    schema_table_map = {
        "f3": [
            models.OrgType,
            models.Org,
            models.EventCategory,
            models.EventType,
            models.Location,
            models.Event,
            models.EventType_x_Org,
            models.AttendanceType,
            models.User,
            models.Attendance,
            models.SlackUser,
            models.EventTag,
            models.EventTag_x_Org,
            models.Role,
            models.Permission,
            models.Role_x_Permission,
            models.Role_x_User_x_Org,
            models.Achievement,
            models.Achievement_x_Org,
            models.Achievement_x_User,
            models.SlackSpace,
            models.Org_x_SlackSpace,
        ],
        # "f3devregion": [
        #     models.AchievementsList,
        #     models.AchievementsAwarded,
        # ],
    }

    for schema, tables in schema_table_map.items():
        tables = [t.__table__ for t in tables]
        engine: Engine = get_engine(schema=schema)
        if not database_exists(engine.url):
            create_database(engine.url)
        with engine.connect() as conn:
            # models.BaseClass.metadata.create_all(bind=conn, tables=tables)
            conn.commit()
        engine.dispose()

    logger.info("Schemas and tables created!")


def initialize_tables():
    logger.info("Initializing tables with data from Slack...")

    # slack_bot_token = os.environ["SLACK_BOT_TOKEN"]
    # client = WebClient(token=slack_bot_token)
    # users = client.users_list().get("members")

    # user_list = [
    #     models.User(
    #         id=i + 1,
    #         f3_name=u["profile"]["display_name"] or u["profile"]["real_name"],
    #         email=u["profile"].get("email") or u["id"],
    #         # home_region_id=1,
    #     )
    #     for i, u in enumerate(users)
    # ]

    # slack_user_list = [
    #     models.SlackUser(
    #         id=i + 1,
    #         slack_id=u["id"],
    #         slack_team_id=u["team_id"],
    #         user_name=u["profile"]["display_name"] or u["profile"]["real_name"],
    #         email=u["profile"].get("email") or u["id"],
    #         user_id=i + 1,
    #         avatar_url=u["profile"]["image_192"],
    #     )
    #     for i, u in enumerate(users)
    # ]

    achievement_list = [
        models.Achievement(
            name="The Priest",
            description="Post for 25 QSource lessons",
            verb="posting for 25 QSource lessons",
        ),
        models.Achievement(
            name="The Monk",
            description="Post at 4 QSources in a month",
            verb="posting at 4 QSources in a month",
        ),
        models.Achievement(
            name="Leader of Men",
            description="Q at 4 beatdowns in a month",
            verb="Qing at 4 beatdowns in a month",
        ),
    ]

    org_type_list = [
        models.OrgType(name="AO"),
        models.OrgType(name="Region"),
        models.OrgType(name="Area"),
        models.OrgType(name="Sector"),
    ]

    event_category_list = [
        models.EventCategory(
            name="1st F - Core Workout", description="The core F3 activity - must meet all 5 core principles."
        ),
        models.EventCategory(
            name="1st F - Pre Workout", description="Pre-workout activities (pre-rucks, pre-runs, etc)."
        ),
        models.EventCategory(
            name="1st F - Off the books",
            description="Fitness activities that didn't meet all 5 core principles (unscheduled, open to all men, etc).",  # noqa: E501
        ),
        models.EventCategory(name="2nd F - Fellowship", description="General category for 2nd F events."),
        models.EventCategory(name="3rd F - Faith", description="General category for 3rd F events."),
    ]

    event_type_list = [
        models.EventType(name="Bootcamp", category_id=1, acronym="BC"),
        models.EventType(name="Run", category_id=1, acronym="RU"),
        models.EventType(name="Ruck", category_id=1, acronym="RK"),
        models.EventType(name="QSource", category_id=3, acronym="QS"),
    ]

    attendance_type_list = [
        models.AttendanceType(type="PAX"),
        models.AttendanceType(type="Q"),
        models.AttendanceType(type="Co-Q"),
    ]

    event_tag_list = [
        models.EventTag(name="Open", color="Green"),
        models.EventTag(name="VQ", color="Blue"),
        models.EventTag(name="Manniversary", color="Yellow"),
        models.EventTag(name="Convergence", color="Orange"),
    ]

    role_list = [
        models.Role(name="Admin"),
    ]

    permission_list = [
        models.Permission(name="All"),
        # models.Permission(name="Create Event"),
        # models.Permission(name="Edit Event"),
        # models.Permission(name="Delete Event"),
        # models.Permission(name="Create User"),
        # models.Permission(name="Edit User"),
        # models.Permission(name="Delete User"),
        # models.Permission(name="Create Role"),
        # models.Permission(name="Edit Role"),
        # models.Permission(name="Delete Role"),
        # models.Permission(name="Create Permission"),
        # models.Permission(name="Edit Permission"),
        # models.Permission(name="Delete Permission"),
    ]

    role_x_permission_list = [
        models.Role_x_Permission(role_id=1, permission_id=1),
    ]

    session = get_session(schema="f3")
    session.add_all(org_type_list)
    session.add_all(event_category_list)
    session.add_all(event_type_list)
    session.add_all(attendance_type_list)
    session.add_all(event_tag_list)
    session.add_all(achievement_list)
    session.add_all(role_list)
    session.add_all(permission_list)
    session.add_all(role_x_permission_list)
    session.commit()
    session.close()

    logger.info("Tables initialized!")


def drop_database():
    logger.info("Resetting database...")
    engine = get_engine(schema="postgres")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text("DROP DATABASE IF EXISTS f3devregion WITH (FORCE);"))
        connection.execute(text("DROP DATABASE IF EXISTS f3 WITH (FORCE);"))


if __name__ == "__main__":
    parser.add_argument("--reset", action="store_true", help="Reset the database")
    args = parser.parse_args()
    if args.reset:
        drop_database()
    create_tables()
    # initialize_tables()
