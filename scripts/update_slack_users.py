import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from f3_data_models.models import SlackSpace, SlackUser
from f3_data_models.utils import DbManager
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from utilities.helper_functions import safe_get


def update_slack_users():
    """
    Update Slack users in the database with their latest information from Slack.
    """
    all_slack_users = DbManager.find_records(cls=SlackUser, filters=[True])
    slack_user_dict = {user.slack_id: user for user in all_slack_users}
    all_slack_spaces = DbManager.find_records(cls=SlackSpace, filters=[True])

    for slack_space in all_slack_spaces:
        client = WebClient(token=slack_space.bot_token)
        try:
            response = client.users_list()  # TODO: Add pagination handling if needed
            users = response["members"]

            for user in users:
                if user["is_bot"] or user["id"] == "USLACKBOT":
                    continue  # Skip bots and the Slackbot

                slack_user = slack_user_dict.get(user["id"])
                if slack_user is None:
                    continue
                if slack_user.slack_updated and slack_user.slack_updated >= user["updated"]:
                    continue
                else:
                    if slack_user is None:
                        continue
                        # TODO: create a new SlackUser / User record if it doesn't exist
                    else:
                        update_fields = {
                            SlackUser.user_name: safe_get(user, "profile", "real_name") or safe_get(user, "name"),
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


if __name__ == "__main__":
    update_slack_users()
