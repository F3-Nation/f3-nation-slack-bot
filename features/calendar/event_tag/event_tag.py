from logging import Logger

from slack_sdk.web import WebClient

from utilities.database.orm import SlackSettings
from utilities.helper_functions import safe_get

from .event_tag_service import EventTagService


def manage_event_tags(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    action = safe_get(body, "actions", 0, "selected_option", "value")

    if action == "add":
        EventTagService.build_event_tag_form(body, client, logger, context, region_record)
    elif action == "edit":
        EventTagService.build_event_tag_list_form(body, client, logger, context, region_record)
