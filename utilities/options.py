from logging import Logger

from f3_data_models.models import User
from f3_data_models.utils import DbManager
from slack_sdk import WebClient

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
        print(f"User records: {user_records}")
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
