import os
import ssl
from logging import Logger

from slack_sdk.models.blocks import (
    ActionsBlock,
    HeaderBlock,
    InputBlock,
    RichTextBlock,
    RichTextListElement,
    RichTextSectionElement,
    SectionBlock,
)
from slack_sdk.models.blocks.block_elements import (
    ButtonElement,
    ExternalDataSelectElement,
    PlainTextInputElement,
)
from slack_sdk.models.views import View, ViewState
from slack_sdk.web import WebClient

from utilities.database.orm import SlackSettings
from utilities.helper_functions import safe_get

CONNECT_EXISTING_REGION = "connect_existing_region"
CREATE_NEW_REGION = "create_new_region"
CONNECT_EXISTING_REGION_CALLBACK_ID = "connect_existing_region"
CREATE_NEW_REGION_CALLBACK_ID = "create_new_region"
SELECT_REGION = "select_region"
NEW_REGION_NAME = "new_region_name"
STARFISH_EXISTING_REGION = "connect_region_starfish"
SEARCH_REGION = "search_region"


def build_connect_options_form(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    # Create the form
    # should start with text saying "Connect your workspace to a F3 region"
    # then two buttons: "Connect to an existing region" and "Create a new region"
    form: View = View(
        type="modal",
        title="Connect your workspace",
        blocks=[
            SectionBlock(
                text="This Slack workspace is not currently connected to a F3 region. Please select an option below to request a connection.",  # noqa
            ),
            ActionsBlock(
                elements=[
                    ButtonElement(
                        text="Connect to an existing region",
                        action_id=CONNECT_EXISTING_REGION,
                    ),
                    # ButtonElement(
                    #     text="Create a new region",
                    #     action_id=CREATE_NEW_REGION,
                    # ),
                    # ButtonElement(
                    #     text="Starfish from an exisiting region",
                    #     action_id=STARFISH_EXISTING_REGION,
                    # ),
                ]
            ),
        ],
    )
    client.views_push(trigger_id=safe_get(body, "trigger_id"), view=form)
    # client.views_push(interactivity_pointer=safe_get(body, "trigger_id"), view=form)


def handle_connect_options(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    action_id = safe_get(body, "actions", 0, "action_id")
    if action_id == CONNECT_EXISTING_REGION:
        build_existing_region_form(body, client, logger, context)
    elif action_id == CREATE_NEW_REGION:
        build_new_region_form(body, client, logger, context)
    elif not action_id:
        if safe_get(body, "view", "callback_id") == CONNECT_EXISTING_REGION_CALLBACK_ID:
            handle_existing_region_selection(body, client, logger, context)
        else:
            build_connect_options_form(body, client, logger, context)
    elif action_id == SEARCH_REGION:
        build_existing_region_form(body, client, logger, context)


def build_existing_region_form(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    form: View = View(
        type="modal",
        callback_id=CONNECT_EXISTING_REGION_CALLBACK_ID,
        title="Connect existing region",
        blocks=[
            InputBlock(
                label="Search for a region",
                block_id=SELECT_REGION,
                element=ExternalDataSelectElement(
                    action_id=SELECT_REGION,
                    placeholder="Start typing to search...",
                    min_query_length=3,
                ),
                optional=False,
            ),
        ],
        submit="Request Connection",
    )

    client.views_update(view_id=safe_get(body, "view", "id"), view=form)


def build_new_region_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    form: View = View(
        type="modal",
        callback_id=CREATE_NEW_REGION_CALLBACK_ID,
        title="Create a new region",
        blocks=[
            InputBlock(
                label="Region Name",
                block_id=NEW_REGION_NAME,
                element=PlainTextInputElement(
                    placeholder="Enter the region name",
                    action_id=NEW_REGION_NAME,
                ),
            ),
        ],
        submit="Request Creation",
    )
    client.views_update(view_id=safe_get(body, "view", "id"), view=form)


def handle_existing_region_selection(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    state = ViewState(**safe_get(body, "view", "state"))
    region_select = state.values.get(SELECT_REGION).get(SELECT_REGION)
    print(region_select)
    blocks = [
        HeaderBlock(text="Region Connection Request"),
        RichTextBlock(
            elements=[
                RichTextListElement(
                    style="bullet",
                    indent=0,
                    elements=[
                        RichTextSectionElement(
                            elements=[
                                {
                                    "type": "text",
                                    "text": f"Region: {region_select.selected_option.get('text').get('text')}",
                                }
                            ]
                        ),
                        RichTextSectionElement(
                            elements=[
                                {
                                    "type": "text",
                                    "text": f"Workspace Domain: {safe_get(body, 'team', 'domain')}",
                                }
                            ]
                        ),
                        RichTextSectionElement(
                            elements=[
                                {
                                    "type": "text",
                                    "text": f"Requestor: {safe_get(body, 'user', 'name')}",
                                }
                            ]
                        ),
                    ],
                ),
            ]
        ),
        ActionsBlock(
            elements=[
                ButtonElement(
                    text="Approve",
                    action_id="approve_connection",
                    value=region_select.selected_option.get("value"),
                    style="primary",
                ),
                ButtonElement(
                    text="Deny",
                    action_id="deny_connection",
                    value=region_select.selected_option.get("value"),
                    style="danger",
                ),
            ]
        ),
    ]
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    if os.environ.get("ADMIN_BOT_TOKEN") and os.environ.get("ADMIN_CHANNEL_ID"):
        try:
            send_client = WebClient(token=os.environ.get("ADMIN_BOT_TOKEN"), ssl=ssl_context)
            send_client.chat_postMessage(
                channel=os.environ.get("ADMIN_CHANNEL_ID"),
                text="Region Connection Request",
                blocks=blocks,
            )
        except Exception as e:
            logger.error(f"Error sending region connection request: {e}")


def handle_new_region_creation(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    state = ViewState(**safe_get(body, "view", "state"))
    region_name = state.values.get(NEW_REGION_NAME).get(NEW_REGION_NAME)
    print(f"Creating new region with name {region_name.value}")
