import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from f3_data_models.models import Org_x_SlackSpace, SlackSpace, SlackUser
from f3_data_models.utils import DbManager
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from utilities.helper_functions import create_user, safe_get


def update_slack_users(force=False):
    """
    Update Slack users in the database with their latest information from Slack.
    """
    all_slack_users = DbManager.find_records(cls=SlackUser, filters=[True])
    slack_user_dict = {user.slack_id: user for user in all_slack_users}
    all_slack_spaces: list[tuple[SlackSpace, Org_x_SlackSpace]] = DbManager.find_join_records2(
        SlackSpace,
        Org_x_SlackSpace,
        filters=[True],
    )

    for slack_space_record in all_slack_spaces:
        slack_space = slack_space_record[0]
        region_org_record = slack_space_record[1]
        client = WebClient(token=slack_space.bot_token)
        try:
            users: list[dict] = []

            response = client.users_list()
            users = response["members"]
            while response.get("response_metadata", {}).get("next_cursor"):
                response = client.users_list(cursor=response["response_metadata"]["next_cursor"])
                users.extend(response["members"])

            for user in users:
                if user["is_bot"] or user["id"] == "USLACKBOT":
                    continue  # Skip bots and the Slackbot

                slack_user = slack_user_dict.get(user["id"])
                if not safe_get(slack_user, "user_id"):
                    print(f"Creating new Slack user {user['id']} ({user.get('name')})")
                    slack_user = create_user(user, region_org_record.org_id)
                elif slack_user.slack_updated and slack_user.slack_updated >= user["updated"] and not force:
                    continue
                else:
                    update_fields = {
                        SlackUser.user_name: safe_get(user, "profile", "display_name")
                        or safe_get(user, "profile", "real_name")
                        or safe_get(user, "name"),
                        SlackUser.slack_updated: safe_get(user, "updated"),
                        SlackUser.is_admin: safe_get(user, "is_admin") or False,
                        SlackUser.is_owner: safe_get(user, "is_owner") or False,
                        SlackUser.is_bot: safe_get(user, "is_bot") or False,
                        SlackUser.avatar_url: safe_get(user, "profile", "image_512"),
                    }
                    DbManager.update_record(SlackUser, slack_user.id, update_fields)

            print("Slack users updated successfully.")

        except SlackApiError as e:
            print(f"Error updating Slack users: {e.response['error']}")
            continue


if __name__ == "__main__":
    update_slack_users()
