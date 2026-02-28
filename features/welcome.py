import copy
import random
from logging import Logger

from f3_data_models.models import SlackSpace, SlackUser, User
from f3_data_models.utils import DbManager
from slack_sdk.web import WebClient

from utilities import constants
from utilities.database.orm import SlackSettings
from utilities.helper_functions import (
    SLACK_USERS,
    create_user,
    safe_get,
    update_local_region_records,
    update_local_slack_users,
)
from utilities.slack import actions, forms


def build_welcome_config_form(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    welcome_message_config_form = copy.deepcopy(forms.WELCOME_MESSAGE_CONFIG_FORM)

    welcome_message_config_form.set_initial_values(
        {
            actions.WELCOME_DM_TEMPLATE: region_record.welcome_dm_template,
            actions.WELCOME_DM_ENABLE: "enable" if region_record.welcome_dm_enable else "disable",
            actions.WELCOME_CHANNEL: region_record.welcome_channel or "",
            actions.WELCOME_CHANNEL_ENABLE: "enable" if region_record.welcome_channel_enable else "disable",
        }
    )

    welcome_message_config_form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        callback_id=actions.WELCOME_MESSAGE_CONFIG_CALLBACK_ID,
        title_text="Welcomebot Settings",
        new_or_add="add",
    )


# eventually will not need this when we take out the /config-welcome-message command
def build_welcome_message_form(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    update_view_id = safe_get(body, actions.LOADING_ID)
    welcome_message_config_form = copy.deepcopy(forms.WELCOME_MESSAGE_CONFIG_FORM)

    welcome_message_config_form.set_initial_values(
        {
            actions.WELCOME_DM_TEMPLATE: region_record.welcome_dm_template,
            actions.WELCOME_DM_ENABLE: "enable" if region_record.welcome_dm_enable else "disable",
            actions.WELCOME_CHANNEL: region_record.welcome_channel or "",
            actions.WELCOME_CHANNEL_ENABLE: "enable" if region_record.welcome_channel_enable else "disable",
        }
    )

    welcome_message_config_form.update_modal(
        client=client,
        view_id=update_view_id,
        callback_id=actions.WELCOME_MESSAGE_CONFIG_CALLBACK_ID,
        title_text="Welcomebot Settings",
        parent_metadata=None,
    )


def handle_welcome_message_config_post(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    welcome_config_data = forms.WELCOME_MESSAGE_CONFIG_FORM.get_selected_values(body)

    region_record.welcome_dm_enable = 1 if safe_get(welcome_config_data, actions.WELCOME_DM_ENABLE) == "enable" else 0
    region_record.welcome_dm_template = safe_get(welcome_config_data, actions.WELCOME_DM_TEMPLATE) or ""
    region_record.welcome_channel_enable = (
        1 if safe_get(welcome_config_data, actions.WELCOME_CHANNEL_ENABLE) == "enable" else 0
    )
    region_record.welcome_channel = safe_get(welcome_config_data, actions.WELCOME_CHANNEL) or ""

    DbManager.update_records(
        cls=SlackSpace,
        filters=[SlackSpace.team_id == region_record.team_id],
        fields={SlackSpace.settings: region_record.__dict__},
    )

    update_local_region_records()


def handle_user_change(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    slack_user_info = safe_get(body, "event", "user") or {}
    slack_id = slack_user_info.get("id")
    new_display_name = safe_get(slack_user_info, "profile", "display_name") or safe_get(
        slack_user_info, "profile", "real_name"
    )

    if not slack_id or not new_display_name:
        return

    slack_user: SlackUser | None = safe_get(SLACK_USERS, slack_id)
    if not slack_user:
        slack_user = safe_get(DbManager.find_records(SlackUser, filters=[SlackUser.slack_id == slack_id]), 0)
        if not slack_user:
            return

    if slack_user.user_name == new_display_name:
        return

    old_display_name = slack_user.user_name

    DbManager.update_record(SlackUser, slack_user.id, {SlackUser.user_name: new_display_name})
    slack_user.user_name = new_display_name
    update_local_slack_users(slack_user)

    # Only sync f3_name if:
    # 1. It hasn't been manually customized (still matches the old Slack display name)
    # 2. The change came from the user's home region workspace
    if slack_user.user_id:
        user: User | None = DbManager.get(User, slack_user.user_id)
        if (
            user
            and user.f3_name == old_display_name
            and region_record.org_id
            and user.home_region_id == region_record.org_id
        ):
            DbManager.update_record(User, slack_user.user_id, {User.f3_name: new_display_name})


def handle_team_join(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    welcome_channel = region_record.welcome_channel
    workspace_name = region_record.workspace_name
    slack_user_info = safe_get(body, "event", "user") or {}
    user_id = slack_user_info.get("id")

    try:
        create_user(slack_user_info, region_record.org_id)
    except Exception:
        pass

    if region_record.welcome_dm_enable:
        client.chat_postMessage(channel=user_id, blocks=[region_record.welcome_dm_template], text="Welcome!")
    if region_record.welcome_channel_enable:
        client.chat_postMessage(
            channel=welcome_channel,
            text=random.choice(constants.WELCOME_MESSAGE_TEMPLATES).format(user=f"<@{user_id}>", region=workspace_name),
        )
