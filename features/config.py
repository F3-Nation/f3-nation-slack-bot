import copy
import json
import os
from logging import Logger

from cryptography.fernet import Fernet
from slack_sdk.web import WebClient

from utilities import constants
from utilities.database import DbManager
from utilities.database.orm import (
    SlackSettings,
    SlackSpace,
)
from utilities.database.special_queries import get_user_permission_list
from utilities.helper_functions import (
    get_user,
    safe_convert,
    safe_get,
    update_local_region_records,
)
from utilities.slack import actions, forms


def build_config_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    update_view_id = safe_get(body, actions.LOADING_ID)

    slack_user = get_user(user_id, region_record, client, logger)
    user_permissions = [p.name for p in get_user_permission_list(slack_user.user_id, region_record.org_id)]
    user_is_admin = constants.PERMISSIONS[constants.ALL_PERMISSIONS] in user_permissions

    if user_is_admin:
        config_form = copy.deepcopy(forms.CONFIG_FORM)
    else:
        config_form = copy.deepcopy(forms.CONFIG_NO_PERMISSIONS_FORM)

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
            actions.CONFIG_DEFAULT_DESTINATION: region_record.default_destination
            or constants.CONFIG_DESTINATION_AO["value"],
            actions.CONFIG_DESTINATION_CHANNEL: region_record.destination_channel,
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

    DbManager.update_record(
        cls=SlackSpace, id=region_record.team_id, fields={SlackSpace.settings: region_record.__dict__}
    )

    update_local_region_records()
    print(json.dumps({"event_type": "successful_config_update", "team_name": region_record.workspace_name}))


def handle_config_general_post(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    config_data = forms.CONFIG_GENERAL_FORM.get_selected_values(body)

    region_record.editing_locked = 1 if safe_get(config_data, actions.CONFIG_EDITING_LOCKED) == "yes" else 0
    region_record.default_destination = safe_get(config_data, actions.CONFIG_DEFAULT_DESTINATION)
    region_record.destination_channel = safe_get(config_data, actions.CONFIG_DESTINATION_CHANNEL)
    region_record.backblast_moleskin_template = safe_get(config_data, actions.CONFIG_BACKBLAST_MOLESKINE_TEMPLATE)
    region_record.preblast_moleskin_template = safe_get(config_data, actions.CONFIG_PREBLAST_MOLESKINE_TEMPLATE)
    region_record.strava_enabled = 1 if safe_get(config_data, actions.CONFIG_ENABLE_STRAVA) == "enable" else 0
    region_record.preblast_reminder_days = safe_convert(
        safe_get(config_data, actions.CONFIG_PREBLAST_REMINDER_DAYS), int
    )
    region_record.backblast_reminder_days = safe_convert(
        safe_get(config_data, actions.CONFIG_BACKBLAST_REMINDER_DAYS), int
    )

    DbManager.update_record(
        cls=SlackSpace, id=region_record.team_id, fields={SlackSpace.settings: region_record.__dict__}
    )

    update_local_region_records()
    print(json.dumps({"event_type": "successful_config_update", "team_name": region_record.workspace_name}))
