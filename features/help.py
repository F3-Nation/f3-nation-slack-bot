import json
import os
from logging import Logger

from slack_sdk.models.blocks import ActionsBlock, ButtonElement
from slack_sdk.web import WebClient

from utilities.database.orm import SlackSettings
from utilities.slack import actions


def build_help_menu(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
):
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "utilities", "default_help.json")) as f:
        default_help_text = json.load(f)

    existing_view = body.get("view", {})

    button_block = ActionsBlock(
        elements=[
            ButtonElement(
                text=":calendar: Open Calendar",
                action_id=actions.OPEN_CALENDAR_BUTTON,
            ),
            ButtonElement(
                text=":memo: Create Preblast",
                action_id=actions.PREBLAST_NEW_BUTTON,
            ),
        ]
    ).to_dict()

    if default_help_text:  # TODO: customize per region in the future
        view = {
            "type": "modal",
            "title": {"type": "plain_text", "text": "Help Menu"},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": [button_block, default_help_text],
        }
        if existing_view:
            client.views_update(view_id=existing_view.get("id"), view=view)
        else:
            client.views_open(trigger_id=body.get("trigger_id"), view=view)
