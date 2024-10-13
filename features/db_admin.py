import copy
import os
from logging import Logger

from slack_sdk.web import WebClient
from sqlalchemy import engine

from alembic import command, config, script
from alembic.runtime import migration
from scripts.calendar_images import generate_calendar_images
from utilities.database import get_engine
from utilities.database.orm import SlackSettings
from utilities.helper_functions import safe_get
from utilities.slack import actions, orm


def check_current_head(alembic_cfg: config.Config, connectable: engine.Engine) -> bool:
    # type: (config.Config, engine.Engine) -> bool
    directory = script.ScriptDirectory.from_config(alembic_cfg)
    with connectable.begin() as connection:
        context = migration.MigrationContext.configure(connection)
        print(context.get_current_heads())
        print(directory.get_heads())
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
    if body.get("text") == os.environ.get("DB_ADMIN_PASSWORD"):
        form = copy.deepcopy(DB_ADMIN_FORM)
        alembic_cfg = config.Config("alembic.ini")
        engine = get_engine()
        db_at_head = check_current_head(alembic_cfg, engine)
        if message:
            msg = message + "\n\n"
        else:
            msg = ""

        if db_at_head:
            msg += "Database is at the latest version."
            form.blocks.append(
                orm.ActionsBlock(
                    elements=[
                        orm.ButtonElement(
                            label="Reset database",
                            action=actions.DB_ADMIN_RESET,
                        ),
                    ],
                )
            )
        else:
            msg += "Database is not at the latest version."
            form.blocks.append(
                orm.ActionsBlock(
                    elements=[
                        orm.ButtonElement(
                            label="Upgrade database",
                            action=actions.DB_ADMIN_UPGRADE,
                        ),
                    ],
                )
            )
        form.blocks[1].label = msg
    else:
        form = copy.deepcopy(DB_WRONG_PASSWORD_FORM)

    form.update_modal(
        client=client,
        view_id=update_view_id,
        callback_id=actions.DB_ADMIN_CALLBACK_ID,
        title_text="DB Admin",
        submit_button_text="None",
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


DB_ADMIN_FORM = orm.BlockView(
    blocks=[
        orm.ActionsBlock(
            elements=[
                orm.ButtonElement(
                    label="Calendar Images",
                    action=actions.SECRET_MENU_CALENDAR_IMAGES,
                ),
            ],
        ),
        orm.SectionBlock(
            action=actions.DB_ADMIN_TEXT,
            label="Database is at the latest version.",
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
