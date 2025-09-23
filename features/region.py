import copy
import re
from logging import Logger

import requests
from slack_sdk.models import blocks
from slack_sdk.web import WebClient

from application.org.command_handlers import OrgCommandHandler
from application.org.commands import UpdateRegionProfile
from features import connect
from infrastructure.persistence.sqlalchemy.org_repository import SqlAlchemyOrgRepository
from utilities.database.orm import SlackSettings
from utilities.database.special_queries import get_admin_users
from utilities.helper_functions import get_user, safe_get, upload_files_to_storage
from utilities.slack import actions
from utilities.slack.sdk_orm import SdkBlockView

REGION_ADMINS_NON_SLACK = "region_admins_non_slack"

# Local copies of Slack action constants used in this module to reduce dependency on utilities.slack.actions
# Keep only actions.USER_OPTION_LOAD imported from actions.
REGION_NAME = "region_name"
REGION_DESCRIPTION = "region_description"
REGION_LOGO = "region_logo"
REGION_CALLBACK_ID = "region-id"
REGION_WEBSITE = "region_website"
REGION_EMAIL = "region_email"
REGION_TWITTER = "region_twitter"
REGION_INSTAGRAM = "region_instagram"
REGION_FACEBOOK = "region_facebook"
REGION_ADMINS = "region_admins"


def build_region_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
):
    form = copy.deepcopy(REGION_FORM)
    # DDD: fetch domain org via repository
    repo = SqlAlchemyOrgRepository()
    org_record = repo.get(int(region_record.org_id))

    if not org_record:
        connect.build_connect_options_form(body, client, logger, context)
    else:
        admin_users = get_admin_users(region_record.org_id, slack_team_id=region_record.team_id)
        admin_slack_user_ids = [u[1].slack_id for u in admin_users if u[1] and u[1].slack_id]
        admin_non_slack_users = [u[0] for u in admin_users if u[1] is None or not u[1].slack_id]

        non_slack = []
        if admin_non_slack_users:
            non_slack = [{"text": r.f3_name, "value": str(r.id)} for r in admin_non_slack_users]

        form.set_initial_values(
            {
                REGION_NAME: getattr(org_record.name, "value", org_record.name),
                REGION_DESCRIPTION: getattr(org_record, "description", None),
                REGION_LOGO: getattr(org_record, "logo_url", None),
                REGION_WEBSITE: getattr(org_record, "website", None),
                REGION_EMAIL: getattr(org_record, "email", None),
                REGION_TWITTER: getattr(org_record, "twitter", None),
                REGION_FACEBOOK: getattr(org_record, "facebook", None),
                REGION_INSTAGRAM: getattr(org_record, "instagram", None),
                REGION_ADMINS: admin_slack_user_ids,
                REGION_ADMINS_NON_SLACK: non_slack,
            }
        )

        if getattr(org_record, "logo_url", None):
            try:
                logo_url = getattr(org_record, "logo_url", None)
                if logo_url and requests.head(logo_url).status_code == 200:
                    form.blocks.insert(2, blocks.ImageBlock(image_url=logo_url, alt_text="Region Logo"))
            except requests.RequestException as e:
                logger.error(f"Error fetching region logo: {e}")

        form.post_modal(
            client=client,
            trigger_id=safe_get(body, "trigger_id"),
            title_text="Edit Region",
            callback_id=REGION_CALLBACK_ID,
            new_or_add="add",
        )


def handle_region_edit(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    form_data = REGION_FORM.get_selected_values(body)

    file = safe_get(form_data, REGION_LOGO, 0)
    if file:
        file_list, file_send_list, file_ids, low_rez_file_ids = upload_files_to_storage(
            files=[file], logger=logger, client=client, enforce_square=True, max_height=512
        )
        logo_url = file_list[0]
    else:
        logo_url = None

    email = safe_get(form_data, REGION_EMAIL)
    if email and not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        email = None

    website = safe_get(form_data, REGION_WEBSITE) or ""
    if not re.match(
        r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6}\b([-a-zA-Z0-9@:%_\+.~#?&//=]*)", website
    ):
        website = None

    # DDD-only path
    repo = SqlAlchemyOrgRepository()
    handler = OrgCommandHandler(repo)
    cmd = UpdateRegionProfile(
        org_id=region_record.org_id,
        name=safe_get(form_data, REGION_NAME),
        description=safe_get(form_data, REGION_DESCRIPTION),
        website=website,
        email=email,
        twitter=safe_get(form_data, REGION_TWITTER),
        facebook=safe_get(form_data, REGION_FACEBOOK),
        instagram=safe_get(form_data, REGION_INSTAGRAM),
        logo_url=logo_url,
    )
    # admins handled after we collect user ids below

    admin_users_slack = safe_get(form_data, REGION_ADMINS) or []
    admin_users = [get_user(user_id, region_record, client, logger) for user_id in admin_users_slack]
    admin_user_ids = [u.user_id for u in admin_users if u is not None]

    admin_users_non_slack = safe_get(form_data, REGION_ADMINS_NON_SLACK) or []
    admin_user_ids += [int(u["value"]) for u in admin_users_non_slack]

    cmd.admin_user_ids = admin_user_ids
    handler.handle(cmd)


REGION_FORM = SdkBlockView(
    blocks=[
        blocks.InputBlock(
            label="Region Title",
            block_id=REGION_NAME,
            element=blocks.PlainTextInputElement(placeholder="Enter the Region name"),
            optional=False,
        ),
        blocks.InputBlock(
            label="Region Description",
            block_id=REGION_DESCRIPTION,
            element=blocks.PlainTextInputElement(placeholder="Enter a description for the Region", multiline=True),
            optional=True,
        ),
        blocks.InputBlock(
            label="Region Logo",
            block_id=REGION_LOGO,
            optional=True,
            element=blocks.block_elements.FileInputElement(
                max_files=1,
                filetypes=[
                    "png",
                    "jpg",
                    "heic",
                    "bmp",
                ],
            ),
        ),
        blocks.InputBlock(
            label="Region Admins",
            block_id=REGION_ADMINS,
            element=blocks.UserMultiSelectElement(placeholder="Select the Region admins"),
            hint="These users will have admin permissions for the Region (modify schedules, backblasts, etc.)",
            optional=False,
        ),
        blocks.InputBlock(
            label="Region Admins (non-Slack users)",
            block_id="region_admins_non_slack",
            element=blocks.ExternalDataMultiSelectElement(
                placeholder="Enter the names of non-Slack users",
                min_query_length=3,
                action_id=actions.USER_OPTION_LOAD,
            ),
        ),
        blocks.InputBlock(
            label="Region Website",
            block_id=REGION_WEBSITE,
            element=blocks.UrlInputElement(placeholder="Enter the Region website"),
            optional=True,
        ),
        blocks.InputBlock(
            label="Region email",
            block_id=REGION_EMAIL,
            element=blocks.EmailInputElement(placeholder="Enter the Region email"),
            optional=True,
        ),
        blocks.InputBlock(
            label="Region Twitter",
            block_id=REGION_TWITTER,
            element=blocks.PlainTextInputElement(placeholder="Enter the Region Twitter"),
            optional=True,
        ),
        blocks.InputBlock(
            label="Region Facebook",
            block_id=REGION_FACEBOOK,
            element=blocks.PlainTextInputElement(placeholder="Enter the Region Facebook"),
            optional=True,
        ),
        blocks.InputBlock(
            label="Region Instagram",
            block_id=REGION_INSTAGRAM,
            element=blocks.PlainTextInputElement(placeholder="Enter the Region Instagram"),
            optional=True,
        ),
    ]
)
