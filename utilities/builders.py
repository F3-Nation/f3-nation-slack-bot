import copy
import time
from logging import Logger
from typing import Any, Dict

from slack_sdk.models.blocks import (
    ContextBlock,
    DividerBlock,
    SectionBlock,
)
from slack_sdk.models.blocks.basic_components import PlainTextObject
from slack_sdk.models.views import View
from slack_sdk.web import WebClient

from utilities import constants
from utilities.database.orm import SlackSettings
from utilities.helper_functions import safe_get
from utilities.slack import actions, forms, sdk_orm

# from pymysql.err import ProgrammingError


def submit_modal() -> Dict[str, Any]:
    return {
        "response_action": "update",
        "view": View(
            type="modal",
            title="Submitting...",
            external_id=actions.SUBMIT_MODAL_EXTERNAL_ID,
            blocks=[
                SectionBlock(
                    text=PlainTextObject(text="Submitting your form, please wait... :hourglass_flowing_sand:")
                ),
                DividerBlock(),
                ContextBlock(
                    elements=[
                        PlainTextObject(
                            text="If this takes longer than 10 seconds, please check back later or contact support."
                        )
                    ]
                ),
            ],
        ),
    }


def submit_modal_success() -> Dict[str, Any]:
    return {
        "response_action": "update",
        "view": View(
            type="modal",
            title="Submitting...",
            external_id=actions.SUBMIT_MODAL_EXTERNAL_ID,
            blocks=[
                SectionBlock(
                    text=PlainTextObject(
                        text=":white_check_mark: Your data was saved successfully! You can close this form now."
                    )  # noqa: E501
                ),
            ],
        ),
    }


def update_submit_modal(client: WebClient, logger: Logger, text: str) -> Dict[str, Any]:
    form = sdk_orm.SdkBlockView(
        blocks=[
            SectionBlock(text=f":white_check_mark: {text} You can close this form now."),
        ]
    )
    try:
        form.update_modal(
            client=client,
            title_text="Success!",
            submit_button_text="None",
            external_id=actions.SUBMIT_MODAL_EXTERNAL_ID,
            callback_id="submit_form_success",
            view_id="not_used",
        )
    except Exception as e:
        logger.error(f"Failed to update submit modal: {e}")


def add_loading_form(body: dict, client: WebClient, new_or_add: str = "new") -> str:
    trigger_id = safe_get(body, "trigger_id")
    loading_form_response = forms.LOADING_FORM.post_modal(
        client=client,
        trigger_id=trigger_id,
        title_text="Loading...",
        submit_button_text="None",
        callback_id="loading-id",
        new_or_add=new_or_add,
    )
    # wait 0.1 seconds
    time.sleep(0.3)
    return safe_get(loading_form_response, "view", "id")


def add_debug_form(body: dict, client: WebClient, new_or_add: str = "new") -> str:
    trigger_id = safe_get(body, "trigger_id")
    debug_form_response = forms.DEBUG_FORM.post_modal(
        client=client,
        trigger_id=trigger_id,
        title_text="Debug Info",
        submit_button_text="None",
        callback_id="debug-id",
        new_or_add=new_or_add,
    )
    # wait 0.1 seconds
    time.sleep(0.3)
    return safe_get(debug_form_response, "view", "id")


def ignore_event(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    logger.debug("Ignoring event")


def send_error_response(body: dict, client: WebClient, error: str) -> None:
    error_form = copy.deepcopy(forms.ERROR_FORM)
    error_msg = constants.ERROR_FORM_MESSAGE_TEMPLATE.format(error=error)
    error_form.set_initial_values({actions.ERROR_FORM_MESSAGE: error_msg})

    # if safe_get(body, actions.LOADING_ID):
    #     update_view_id = safe_get(body, actions.LOADING_ID)
    #     error_form.update_modal(
    #         client=client,
    #         view_id=update_view_id,
    #         title_text="F3 Nation Error",
    #         submit_button_text="None",
    #         callback_id="error-id",
    #     )
    # else:
    blocks = [block.as_form_field() for block in error_form.blocks]
    client.chat_postMessage(channel=safe_get(body, "user", "id"), text=error, blocks=blocks)
