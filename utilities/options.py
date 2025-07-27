from logging import Logger

from f3_data_models.models import Org, Org_Type, User
from f3_data_models.utils import DbManager
from slack_sdk import WebClient
from sqlalchemy import and_

from features import user as user_form
from utilities.database.orm import SlackSettings
from utilities.helper_functions import safe_get
from utilities.slack import actions


def handle_request(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
):
    action_id = safe_get(body, "action_id")
    value = safe_get(body, "value")

    if action_id == actions.USER_OPTION_LOAD:
        user_records = DbManager.find_records(
            cls=User,
            filters=[User.f3_name.ilike(f"%{value}%")],
            joinedloads=[User.home_region_org],
        )
        options = []
        for user in user_records[:10]:
            display_name = user.f3_name
            if user.home_region_org:
                display_name += f" ({user.home_region_org.name})"
            options.append(
                {
                    "text": {"type": "plain_text", "text": display_name},
                    "value": str(user.id),
                }
            )
        return options
    elif action_id == user_form.USER_FORM_HOME_REGION:
        # Handle the home region selection
        org_records = DbManager.find_records(
            cls=Org,
            filters=[and_(Org.name.ilike(f"%{value}%"), Org.org_type == Org_Type.region)],
            # TODO: add area / sector as description
        )
        options = []
        for org in org_records[:10]:
            display_name = org.name
            options.append(
                {
                    "text": {"type": "plain_text", "text": display_name},
                    "value": str(org.id),
                }
            )
        return options
