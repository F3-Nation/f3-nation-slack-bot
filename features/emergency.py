import copy
from logging import Logger

from f3_data_models.models import SlackUser, User
from f3_data_models.utils import DbManager
from slack_sdk import WebClient

from utilities.database.orm import SlackSettings
from utilities.helper_functions import get_user, safe_get
from utilities.slack import actions
from utilities.slack.orm import (
    BlockView,
    ContextBlock,
    ContextElement,
    DividerBlock,
    ExternalSelectElement,
    HeaderBlock,
    InputBlock,
    SectionBlock,
    UsersSelectElement,
)

# Action IDs
EMERGENCY_SEARCH_FORM_ID = "emergency_search_form_id"
EMERGENCY_LOCAL_USER_SELECT = "emergency_local_user_select"
EMERGENCY_DR_USER_SELECT = "emergency_dr_user_select"
EMERGENCY_INFO_CALLBACK_ID = "emergency_info_callback_id"

# Meta key for DR sharing (used in user.meta)
USER_EMERGENCY_INFO_DR_SHARING = "user_emergency_info_dr_sharing"


def build_emergency_search_form(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    """Build the emergency info search modal with local and external user selectors."""
    form = copy.deepcopy(EMERGENCY_SEARCH_FORM)

    if safe_get(body, actions.LOADING_ID):
        form.update_modal(
            client=client,
            view_id=safe_get(body, actions.LOADING_ID),
            title_text="Emergency Info",
            callback_id=EMERGENCY_SEARCH_FORM_ID,
            submit_button_text="None",
        )
    else:
        form.post_modal(
            client=client,
            trigger_id=safe_get(body, "trigger_id"),
            title_text="Emergency Info",
            callback_id=EMERGENCY_SEARCH_FORM_ID,
            new_or_add="add",
            submit_button_text="None",
        )


def handle_local_user_select(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    """Handle selection of a local Slack user to view their emergency info."""
    selected_user_id = safe_get(body, "actions", 0, "selected_user")
    if not selected_user_id:
        return

    # Get the SlackUser and associated User record
    slack_user: SlackUser = get_user(selected_user_id, region_record, client, logger)
    if not slack_user or not slack_user.user_id:
        _show_error_modal(client, body, "User not found in the system.")
        return

    user = DbManager.get(User, slack_user.user_id)
    if not user:
        _show_error_modal(client, body, "User record not found.")
        return

    _show_emergency_info_modal(client, body, user, is_local=True)


def handle_dr_user_select(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    """Handle selection of an external (downrange) user to view their emergency info."""
    selected_value = safe_get(body, "actions", 0, "selected_option", "value")
    if not selected_value:
        return

    try:
        user_id = int(selected_value)
    except (ValueError, TypeError):
        _show_error_modal(client, body, "Invalid user selection.")
        return

    user = DbManager.get(User, user_id)
    if not user:
        _show_error_modal(client, body, "User not found.")
        return

    # Check if user has opted into DR sharing
    dr_sharing_enabled = safe_get(user.meta, USER_EMERGENCY_INFO_DR_SHARING)
    if not dr_sharing_enabled:
        _show_error_modal(
            client,
            body,
            "This user has not enabled downrange emergency info sharing. "
            "Their emergency information cannot be accessed from outside their Slack workspace.",
        )
        return

    _show_emergency_info_modal(client, body, user, is_local=False)


def _show_emergency_info_modal(client: WebClient, body: dict, user: User, is_local: bool):
    """Display the emergency information for a user."""
    blocks = [
        HeaderBlock(label=f"Emergency Info for {user.f3_name or 'Unknown'}").as_form_field(),
        DividerBlock().as_form_field(),
    ]

    # Emergency contact information
    if user.emergency_contact:
        blocks.append(
            SectionBlock(
                label=f"*Emergency Contact:* {user.emergency_contact}",
            ).as_form_field()
        )
    else:
        blocks.append(
            SectionBlock(
                label="*Emergency Contact:* _Not provided_",
            ).as_form_field()
        )

    if user.emergency_phone:
        blocks.append(
            SectionBlock(
                label=f"*Phone:* {user.emergency_phone}",
            ).as_form_field()
        )
    else:
        blocks.append(
            SectionBlock(
                label="*Phone:* _Not provided_",
            ).as_form_field()
        )

    if user.emergency_notes:
        blocks.append(
            SectionBlock(
                label=f"*Notes:* {user.emergency_notes}",
            ).as_form_field()
        )

    blocks.append(DividerBlock().as_form_field())
    blocks.append(
        ContextBlock(
            element=ContextElement(
                initial_value=":warning: The user has been notified that their emergency information was accessed."
            )
        ).as_form_field()
    )

    client.views_push(
        trigger_id=safe_get(body, "trigger_id"),
        view={
            "type": "modal",
            "callback_id": EMERGENCY_INFO_CALLBACK_ID,
            "title": {"type": "plain_text", "text": "Emergency Info"},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": blocks,
        },
    )


def _show_error_modal(client: WebClient, body: dict, message: str):
    """Display an error message in a modal."""
    client.views_push(
        trigger_id=safe_get(body, "trigger_id"),
        view={
            "type": "modal",
            "title": {"type": "plain_text", "text": "Error"},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f":x: {message}"},
                }
            ],
        },
    )


EMERGENCY_SEARCH_FORM = BlockView(
    blocks=[
        HeaderBlock(label="Search for Emergency Info"),
        ContextBlock(
            element=ContextElement(
                initial_value=":warning: *Important:* The user will be notified that their emergency "
                "information was accessed. Only use this feature in genuine emergency situations."
            )
        ),
        DividerBlock(),
        SectionBlock(label="*Option 1: Local Slack User*"),
        ContextBlock(element=ContextElement(initial_value="Search for a user in this Slack workspace.")),
        InputBlock(
            label="Select Local User",
            action=EMERGENCY_LOCAL_USER_SELECT,
            element=UsersSelectElement(placeholder="Select a user from this workspace"),
            optional=True,
            dispatch_action=True,
        ),
        DividerBlock(),
        SectionBlock(label="*Option 2: Downrange User Search*"),
        ContextBlock(
            element=ContextElement(
                initial_value="Search for users from other regions who have opted into downrange sharing. "
                "Start typing a user's F3 name to search."
            )
        ),
        InputBlock(
            label="Search External User",
            action=EMERGENCY_DR_USER_SELECT,
            element=ExternalSelectElement(
                placeholder="Type to search for a user by F3 name",
                min_query_length=2,
            ),
            optional=True,
            dispatch_action=True,
        ),
    ]
)
