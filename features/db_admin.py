import copy
import os
from datetime import datetime
from logging import Logger

from alembic import command, config, script
from alembic.runtime import migration
from f3_data_models.models import Event, Org, Org_x_SlackSpace, Role_x_User_x_Org, SlackSpace
from f3_data_models.utils import DbManager
from slack_sdk.web import WebClient
from sqlalchemy import engine, or_

from features import user as user_form
from features.calendar.series import create_events
from scripts.calendar_images import generate_calendar_images
from scripts.q_lineups import send_lineups
from scripts.update_slack_users import update_slack_users
from utilities.database.orm import SlackSettings
from utilities.database.paxminer_migration_bulk import run_paxminer_migration as run_paxminer_migration_bulk
from utilities.helper_functions import current_date_cst, get_user, safe_convert, safe_get, trigger_map_revalidation
from utilities.slack import actions, orm


def check_current_head(alembic_cfg: config.Config, connectable: engine.Engine) -> bool:
    # type: (config.Config, engine.Engine) -> bool
    directory = script.ScriptDirectory.from_config(alembic_cfg)
    with connectable.begin() as connection:
        context = migration.MigrationContext.configure(connection)
        return set(context.get_current_heads()) == set(directory.get_heads())


def build_db_admin_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
    update_view_id: str = None,
    message: str = None,
):
    update_view_id = update_view_id or safe_get(body, actions.LOADING_ID)
    if body.get("text") == os.environ.get("DB_ADMIN_PASSWORD") or message:
        form = copy.deepcopy(DB_ADMIN_FORM)
        form.blocks[-1].label = message or " "
    else:
        form = copy.deepcopy(DB_WRONG_PASSWORD_FORM)

    form.update_modal(
        client=client,
        view_id=update_view_id,
        callback_id=actions.DB_ADMIN_CALLBACK_ID,
        title_text="DB Admin",
    )


def handle_db_admin_upgrade(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
):
    alembic_cfg = config.Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    view_id = safe_get(body, "view", "id")
    body["text"] = os.environ.get("DB_ADMIN_PASSWORD")
    build_db_admin_form(
        body, client, logger, context, region_record, update_view_id=view_id, message="Database upgraded!"
    )


def handle_db_admin_reset(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
):
    alembic_cfg = config.Config("alembic.ini")
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")
    view_id = safe_get(body, "view", "id")
    body["text"] = os.environ.get("DB_ADMIN_PASSWORD")
    build_db_admin_form(body, client, logger, context, region_record, update_view_id=view_id, message="Database reset!")


def handle_calendar_image_refresh(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
):
    generate_calendar_images()


def handle_slack_user_refresh(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
):
    update_slack_users()


def handle_paxminer_migration(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
):
    form_data = DB_ADMIN_FORM.get_selected_values(body)
    region = safe_get(form_data, actions.PAXMINER_MIGRATION_REGION)
    region = None if region == "" else region
    view_id = safe_get(body, "view", "id")
    if region:
        build_db_admin_form(
            body,
            client,
            logger,
            context,
            region_record,
            update_view_id=view_id,
            message="Paxminer migration started!",
        )
        msg = run_paxminer_migration_bulk(region)
    build_db_admin_form(
        body,
        client,
        logger,
        context,
        region_record,
        update_view_id=view_id,
        message=f"Paxminer migration complete!\n{msg}",
    )


def handle_paxminer_migration_all(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
):
    form_data = DB_ADMIN_FORM.get_selected_values(body)
    region = safe_get(form_data, actions.PAXMINER_MIGRATION_REGION)
    region = None if region == "" else region
    run_paxminer_migration_bulk(region)


def handle_make_admin(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
):
    slack_user_id = safe_get(body, "user", "id")
    user = get_user(slack_user_id, region_record, client, logger)
    DbManager.create_record(
        Role_x_User_x_Org(
            user_id=user.user_id,
            org_id=region_record.org_id,
            role_id=1,
        )
    )


def handle_make_org(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
):
    form_data = DB_ADMIN_FORM.get_selected_values(body)
    region_org_id = safe_convert(safe_get(form_data, user_form.USER_FORM_HOME_REGION), int)
    team_id = safe_get(body, "team", "id") or safe_get(body, "team_id")
    if region_org_id and team_id:
        slack_space_record = DbManager.find_first_record(SlackSpace, [SlackSpace.team_id == team_id])
        if slack_space_record:
            connect_record = Org_x_SlackSpace(
                org_id=region_org_id,
                slack_space_id=slack_space_record.id,
            )
            DbManager.create_record(connect_record)

        region_record.org_id = region_org_id
        DbManager.update_records(
            cls=SlackSpace,
            filters=[SlackSpace.team_id == region_record.team_id],
            fields={SlackSpace.settings: region_record.__dict__},
        )


def handle_ao_lineups(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
):
    send_lineups(force=True)


def handle_preblast_reminders(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
):
    from scripts.preblast_reminders import send_preblast_reminders

    send_preblast_reminders()


def handle_generate_instances(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
):
    event_records = DbManager.find_records(
        Event,
        filters=[
            Event.is_active,
            or_(Event.org_id == region_record.org_id, Event.org.has(Org.parent_id == region_record.org_id)),
            or_(Event.end_date >= current_date_cst(), Event.end_date.is_(None)),
        ],
        joinedloads="all",
    )
    start_date = (
        safe_convert(region_record.migration_date, datetime.strptime, args=["%Y-%m-%d"]) or datetime.now()
    ).date()
    create_events(event_records, clear_first=True, start_date=start_date)


def handle_trigger_map_revalidation(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
):
    trigger_map_revalidation()


DB_ADMIN_FORM = orm.BlockView(
    blocks=[
        orm.ActionsBlock(
            elements=[
                orm.ButtonElement(
                    label="Calendar Images",
                    action=actions.SECRET_MENU_CALENDAR_IMAGES,
                ),
                orm.ButtonElement(
                    label="AO Lineups",
                    action=actions.SECRET_MENU_AO_LINEUPS,
                ),
                orm.ButtonElement(
                    label="Preblast Reminders",
                    action=actions.SECRET_MENU_PREBLAST_REMINDERS,
                ),
                # orm.ButtonElement(
                #     label="Paxminer Migration (Selected Region)",
                #     action=actions.SECRET_MENU_PAXMINER_MIGRATION,
                # ),
                # orm.ButtonElement(
                #     label="Paxminer Migration (All Regions)",
                #     action=actions.SECRET_MENU_PAXMINER_MIGRATION_ALL,
                # ),
                orm.ButtonElement(
                    label="Update Canvas",
                    action=actions.SECRET_MENU_UPDATE_CANVAS,
                ),
                orm.ButtonElement(
                    label="Connect to Org",
                    action=actions.SECRET_MENU_MAKE_ORG,
                ),
                orm.ButtonElement(
                    label="Make myself an admin",
                    action=actions.SECRET_MENU_MAKE_ADMIN,
                ),
                orm.ButtonElement(
                    label="Generate Event Instances",
                    action=actions.SECRET_MENU_GENERATE_EVENT_INSTANCES,
                ),
                orm.ButtonElement(
                    label="Trigger Map Revalidation",
                    action=actions.SECRET_MENU_TRIGGER_MAP_REVALIDATION,
                ),
                orm.ButtonElement(
                    label="Refresh Slack Users",
                    action=actions.SECRET_MENU_REFRESH_SLACK_USERS,
                ),
            ],
        ),
        orm.InputBlock(
            label="Paxminer region to migrate",
            action=actions.PAXMINER_MIGRATION_REGION,
            element=orm.PlainTextInputElement(placeholder="Enter the region to migrate"),
        ),
        orm.SectionBlock(
            action=actions.DB_ADMIN_TEXT,
            label=" ",
        ),
        orm.InputBlock(
            label="External Test",
            action=actions.USER_OPTION_LOAD,
            optional=True,
            element=orm.MultiExternalSelectElement(min_query_length=3),
        ),
        orm.InputBlock(
            label="Region Org",
            action=user_form.USER_FORM_HOME_REGION,
            optional=True,
            element=orm.ExternalSelectElement(min_query_length=3, placeholder="Select a region org"),
        ),
    ]
)

DB_WRONG_PASSWORD_FORM = orm.BlockView(
    blocks=[
        orm.SectionBlock(
            action=actions.DB_ADMIN_TEXT,
            label="Wrong password.",
        ),
    ]
)
