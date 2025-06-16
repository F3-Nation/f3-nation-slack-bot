import copy
from logging import Logger

from f3_data_models.models import SlackUser, User
from f3_data_models.utils import DbManager
from slack_sdk import WebClient

from utilities.database.orm import SlackSettings
from utilities.helper_functions import get_user, safe_get, upload_files_to_storage
from utilities.slack.orm import (
    BlockView,
    ContextBlock,
    ContextElement,
    ExternalSelectElement,
    FileInputElement,
    ImageBlock,
    InputBlock,
    PlainTextInputElement,
)

USER_FORM_USERNAME = "user_name"
USER_FORM_HOME_REGION = "user_home_region"
USER_FORM_IMAGE = "user_image"
USER_FORM_IMAGE_UPLOAD = "user_image_upload"
USER_FORM_ID = "user_form_id"


def build_user_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    form = copy.deepcopy(FORM)

    slack_user: SlackUser = get_user(
        safe_get(body, "user", "id") or safe_get(body, "user_id"), region_record, client, logger
    )
    user = DbManager.get(User, slack_user.user_id, joinedloads=[User.home_region_org])

    initial_values = {
        USER_FORM_USERNAME: user.f3_name,
    }
    if user.home_region_id:
        form.blocks[
            1
        ].hint = f"Your current home region is {user.home_region_org.name}. You can change this at any time."
    if user.avatar_url:
        initial_values[USER_FORM_IMAGE] = user.avatar_url
    else:
        form.delete_block(USER_FORM_IMAGE)
    form.set_initial_values(initial_values)

    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text="User Settings",
        callback_id=USER_FORM_ID,
        new_or_add="add",
    )


def handle_user_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    form_data = FORM.get_selected_values(body)
    slack_user: SlackUser = get_user(
        safe_get(body, "user", "id") or safe_get(body, "user_id"), region_record, client, logger
    )

    update_fields = {
        User.f3_name: safe_get(form_data, USER_FORM_USERNAME),
        User.home_region_id: safe_get(form_data, USER_FORM_HOME_REGION),
    }

    file = safe_get(form_data, USER_FORM_IMAGE_UPLOAD, 0)
    if file:
        file_list, file_send_list, file_ids = upload_files_to_storage([file], client=client, logger=logger)
        update_fields[User.avatar_url] = file_list[0]

    DbManager.update_record(User, slack_user.user_id, update_fields)


FORM = BlockView(
    blocks=[
        InputBlock(
            label="Username",
            action=USER_FORM_USERNAME,
            element=PlainTextInputElement(placeholder="Enter your username"),
            optional=False,
            hint="This is the username that will be used to identify globally. Do not include your home region",
        ),
        InputBlock(
            label="Home Region",
            action=USER_FORM_HOME_REGION,
            element=ExternalSelectElement(placeholder="Select a new home region"),
            optional=False,
            hint="This is the region you will be associated with. You can change this at any time.",
        ),
        ImageBlock(action=USER_FORM_IMAGE, image_url="https://example.com/image.png", alt_text="User Image"),
        ContextBlock(
            element=ContextElement(
                initial_value="This avatar is used in the Nation dashboard and can be different from your Slack avatar."
            )
        ),
        InputBlock(
            label="New Profile Picture",
            action=USER_FORM_IMAGE_UPLOAD,
            element=FileInputElement(
                max_files=1,
                filetypes=[
                    "png",
                    "jpg",
                    "heic",
                    "bmp",
                ],
            ),
            optional=True,
        ),
    ]
)
