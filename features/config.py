import copy
import json
import os
from logging import Logger
from typing import List

from cryptography.fernet import Fernet
from f3_data_models.models import Org, Org_Type, Position, Position_x_Org_x_User, SlackSpace
from f3_data_models.utils import DbManager
from slack_sdk.web import WebClient

from features import db_admin
from utilities import constants
from utilities.database.orm import SlackSettings
from utilities.database.special_queries import get_admin_users, get_position_users, make_user_admin
from utilities.helper_functions import (
    get_user,
    safe_convert,
    safe_get,
    update_local_region_records,
)
from utilities.slack import actions, forms, orm


def build_config_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    update_view_id = safe_get(body, actions.LOADING_ID)
    if body.get("text") == os.environ.get("DB_ADMIN_PASSWORD"):
        db_admin.build_db_admin_form(body, client, logger, context, region_record, update_view_id)
    else:
        slack_user = get_user(user_id, region_record, client, logger)
        # user_permissions = [p.name for p in get_user_permission_list(slack_user.user_id, region_record.org_id)]
        # user_is_admin = constants.PERMISSIONS[constants.ALL_PERMISSIONS] in user_permissions
        admin_users = get_admin_users(region_record.org_id, region_record.team_id)
        user_is_admin = any(u[0].id == slack_user.user_id for u in admin_users)

        if user_is_admin:
            config_form = copy.deepcopy(forms.CONFIG_FORM)
        else:
            if region_record.org_id is None:
                config_form = copy.deepcopy(forms.CONFIG_NO_ORG_FORM)
            elif len(admin_users) == 0:
                make_user_admin(region_record.org_id, slack_user.user_id)
                config_form = copy.deepcopy(forms.CONFIG_FORM)
            else:
                config_form = copy.deepcopy(forms.CONFIG_NO_PERMISSIONS_FORM)
                config_form.blocks[1].label += " Your region's admin users are: "
                user_labels = []
                for admin_user in admin_users:
                    if admin_user[1]:
                        user_labels.append(f" <@{admin_user[1].slack_id}>")
                    else:
                        user_labels.append(admin_user[0].f3_name or "")
                config_form.blocks[1].label += ", ".join(user_labels)

        config_form.update_modal(
            client=client,
            view_id=update_view_id,
            callback_id=actions.CONFIG_CALLBACK_ID,
            title_text="F3 Nation Settings",
            submit_button_text="None",
        )


def build_config_email_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    config_form = copy.deepcopy(forms.CONFIG_EMAIL_FORM)

    if region_record.email_password:
        fernet = Fernet(os.environ[constants.PASSWORD_ENCRYPT_KEY].encode())
        email_password_decrypted = fernet.decrypt(region_record.email_password.encode()).decode()
    else:
        email_password_decrypted = "SamplePassword123!"

    config_form.set_initial_values(
        {
            actions.CONFIG_EMAIL_ENABLE: "enable" if region_record.email_enabled == 1 else "disable",
            actions.CONFIG_EMAIL_SHOW_OPTION: "yes" if region_record.email_option_show == 1 else "no",
            actions.CONFIG_EMAIL_FROM: region_record.email_user or "example_sender@gmail.com",
            actions.CONFIG_EMAIL_TO: region_record.email_to or "example_destination@gmail.com",
            actions.CONFIG_EMAIL_SERVER: region_record.email_server or "smtp.gmail.com",
            actions.CONFIG_EMAIL_PORT: str(region_record.email_server_port or 587),
            actions.CONFIG_EMAIL_PASSWORD: email_password_decrypted,
            actions.CONFIG_POSTIE_ENABLE: "yes" if region_record.postie_format == 1 else "no",
        }
    )

    config_form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        callback_id=actions.CONFIG_EMAIL_CALLBACK_ID,
        title_text="Email Settings",
        new_or_add="add",
    )


def build_config_general_form(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    config_form = copy.deepcopy(forms.CONFIG_GENERAL_FORM)

    config_form.set_initial_values(
        {
            actions.CONFIG_EDITING_LOCKED: "yes" if region_record.editing_locked == 1 else "no",
            actions.CONFIG_DEFAULT_DESTINATION: region_record.default_backblast_destination
            or constants.CONFIG_DESTINATION_AO["value"],
            actions.CONFIG_DESTINATION_CHANNEL: region_record.backblast_destination_channel,
            actions.CONFIG_DEFAULT_PREBLAST_DESTINATION: region_record.default_preblast_destination
            or constants.CONFIG_DESTINATION_AO["value"],
            actions.CONFIG_PREBLAST_DESTINATION_CHANNEL: region_record.preblast_destination_channel,
            actions.CONFIG_BACKBLAST_MOLESKINE_TEMPLATE: region_record.backblast_moleskin_template
            or constants.DEFAULT_BACKBLAST_MOLESKINE_TEMPLATE,
            actions.CONFIG_PREBLAST_MOLESKINE_TEMPLATE: region_record.preblast_moleskin_template
            or constants.DEFAULT_PREBLAST_MOLESKINE_TEMPLATE,
            actions.CONFIG_ENABLE_STRAVA: "enable" if region_record.strava_enabled == 1 else "disable",
            actions.CONFIG_PREBLAST_REMINDER_DAYS: region_record.preblast_reminder_days,
            actions.CONFIG_BACKBLAST_REMINDER_DAYS: region_record.backblast_reminder_days,
        }
    )

    config_form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        callback_id=actions.CONFIG_GENERAL_CALLBACK_ID,
        title_text="General Settings",
        new_or_add="add",
    )


def handle_config_email_post(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    config_data = forms.CONFIG_EMAIL_FORM.get_selected_values(body)

    if safe_get(config_data, actions.CONFIG_EMAIL_ENABLE) == "enable":
        fernet = Fernet(os.environ[constants.PASSWORD_ENCRYPT_KEY].encode())
        email_password_decrypted = safe_get(config_data, actions.CONFIG_EMAIL_PASSWORD)
        if email_password_decrypted:
            email_password_encrypted = fernet.encrypt(
                safe_get(config_data, actions.CONFIG_EMAIL_PASSWORD).encode()
            ).decode()
        else:
            email_password_encrypted = None

        region_record.email_enabled = 1 if safe_get(config_data, actions.CONFIG_EMAIL_ENABLE) == "enable" else 0
        region_record.email_option_show = 1 if safe_get(config_data, actions.CONFIG_EMAIL_SHOW_OPTION) == "yes" else 0
        region_record.email_server = safe_get(config_data, actions.CONFIG_EMAIL_SERVER)
        region_record.email_server_port = safe_convert(safe_get(config_data, actions.CONFIG_EMAIL_PORT), int)
        region_record.email_user = safe_get(config_data, actions.CONFIG_EMAIL_FROM)
        region_record.email_to = safe_get(config_data, actions.CONFIG_EMAIL_TO)
        region_record.email_password = email_password_encrypted
        region_record.postie_format = 1 if safe_get(config_data, actions.CONFIG_POSTIE_ENABLE) == "yes" else 0

    DbManager.update_records(
        cls=SlackSpace,
        filters=[SlackSpace.team_id == region_record.team_id],
        fields={SlackSpace.settings: region_record.__dict__},
    )

    update_local_region_records()


def handle_config_general_post(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    config_data = forms.CONFIG_GENERAL_FORM.get_selected_values(body)

    region_record.editing_locked = 1 if safe_get(config_data, actions.CONFIG_EDITING_LOCKED) == "yes" else 0
    region_record.default_backblast_destination = safe_get(config_data, actions.CONFIG_DEFAULT_DESTINATION)
    region_record.backblast_destination_channel = safe_get(config_data, actions.CONFIG_DESTINATION_CHANNEL)
    region_record.default_preblast_destination = safe_get(config_data, actions.CONFIG_DEFAULT_PREBLAST_DESTINATION)
    region_record.preblast_destination_channel = safe_get(config_data, actions.CONFIG_PREBLAST_DESTINATION_CHANNEL)
    region_record.backblast_moleskin_template = safe_get(config_data, actions.CONFIG_BACKBLAST_MOLESKINE_TEMPLATE)
    region_record.preblast_moleskin_template = safe_get(config_data, actions.CONFIG_PREBLAST_MOLESKINE_TEMPLATE)
    region_record.strava_enabled = 1 if safe_get(config_data, actions.CONFIG_ENABLE_STRAVA) == "enable" else 0
    region_record.preblast_reminder_days = safe_convert(
        safe_get(config_data, actions.CONFIG_PREBLAST_REMINDER_DAYS), int
    )
    region_record.backblast_reminder_days = safe_convert(
        safe_get(config_data, actions.CONFIG_BACKBLAST_REMINDER_DAYS), int
    )

    DbManager.update_records(
        cls=SlackSpace,
        filters=[SlackSpace.team_id == region_record.team_id],
        fields={SlackSpace.settings: region_record.__dict__},
    )

    update_local_region_records()


def build_config_slt_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
    update_view_id: str = None,
    selected_org_id: int = None,
):
    if safe_get(body, "actions", 0, "action_id") == actions.SLT_LEVEL_SELECT:
        org_id = safe_convert(safe_get(body, "actions", 0, "selected_option", "value"), int)
        org_id = org_id if org_id != 0 else region_record.org_id
        update_view_id = safe_get(body, "view", "id")
    else:
        org_id = selected_org_id or region_record.org_id

    position_users = get_position_users(org_id, region_record.org_id, slack_team_id=region_record.team_id)
    aos: List[Org] = DbManager.find_records(
        cls=Org,
        filters=[Org.parent_id == region_record.org_id],
    )
    level_options = [orm.SelectorOption(name="Region", value="0")]
    for a in aos:
        level_options.append(orm.SelectorOption(name=a.name, value=str(a.id)))

    blocks = [
        orm.InputBlock(
            label="Select the SLT positions for...",
            action=actions.SLT_LEVEL_SELECT,
            element=orm.StaticSelectElement(
                options=level_options,
                initial_value="0" if org_id == region_record.org_id else str(org_id),
            ),
            dispatch_action=True,
        ),
    ]

    for p in position_users:
        blocks.append(
            orm.InputBlock(
                label=p.position.name,
                action=actions.SLT_SELECT + str(p.position.id),
                optional=True,
                element=orm.MultiUsersSelectElement(
                    placeholder="Select SLT Members...",
                    initial_value=[u.slack_id for u in p.slack_users if u is not None],
                ),
                hint=p.position.description,
            )
        )

    blocks.append(
        orm.ActionsBlock(
            elements=[
                orm.ButtonElement(
                    label=":heavy_plus_sign: New Position",
                    action=actions.CONFIG_NEW_POSITION,
                )
            ]
        )
    )

    form = orm.BlockView(blocks=blocks)
    if update_view_id:
        form.update_modal(
            client=client,
            view_id=update_view_id,
            callback_id=actions.CONFIG_SLT_CALLBACK_ID,
            title_text="SLT Members",
        )
    else:
        form.post_modal(
            client=client,
            trigger_id=safe_get(body, "trigger_id"),
            callback_id=actions.CONFIG_SLT_CALLBACK_ID,
            title_text="SLT Members",
            new_or_add="add",
        )


def build_new_position_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    form = copy.deepcopy(forms.CONFIG_NEW_POSITION_FORM)
    selected_org_id = safe_convert(
        safe_get(
            body,
            "view",
            "state",
            "values",
            actions.SLT_LEVEL_SELECT,
            actions.SLT_LEVEL_SELECT,
            "selected_option",
            "value",
        ),
        int,
    )
    selected_org_id = selected_org_id if selected_org_id != 0 else region_record.org_id

    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        callback_id=actions.NEW_POSITION_CALLBACK_ID,
        title_text="New Position",
        new_or_add="add",
        parent_metadata={"org_id": selected_org_id},
    )


def handle_new_position_post(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    form_data = forms.CONFIG_NEW_POSITION_FORM.get_selected_values(body)
    metadata = json.loads(safe_get(body, "view", "private_metadata") or "{}")
    org_type = Org_Type.region if metadata.get("org_id") == region_record.org_id else Org_Type.ao

    DbManager.create_record(
        Position(
            name=safe_get(form_data, actions.CONFIG_NEW_POSITION_NAME),
            description=safe_get(form_data, actions.CONFIG_NEW_POSITION_DESCRIPTION),
            org_id=region_record.org_id,
            org_type=org_type,
        )
    )
    build_config_slt_form(
        body,
        client,
        logger,
        context,
        region_record,
        update_view_id=safe_get(body, "view", "previous_view_id"),
        selected_org_id=metadata.get("org_id"),
    )


def handle_config_slt_post(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    form_data = body["view"]["state"]["values"]
    org_id = safe_convert(
        safe_get(form_data, actions.SLT_LEVEL_SELECT, actions.SLT_LEVEL_SELECT, "selected_option", "value"), int
    )
    org_id = org_id if org_id != 0 else region_record.org_id
    new_assignments: List[Position_x_Org_x_User] = []

    for key, value in form_data.items():
        if key.startswith(actions.SLT_SELECT):
            position_id = int(key.replace(actions.SLT_SELECT, ""))
            users = [get_user(u, region_record, client, logger) for u in value[key]["selected_users"]]

            for u in users:
                if u:
                    new_assignments.append(
                        Position_x_Org_x_User(
                            org_id=org_id,
                            position_id=position_id,
                            user_id=u.user_id,
                        )
                    )

    DbManager.delete_records(
        Position_x_Org_x_User,
        filters=[Position_x_Org_x_User.org_id == org_id],
    )

    DbManager.create_records(new_assignments)
