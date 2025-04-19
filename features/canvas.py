from datetime import date, timedelta
from logging import Logger
from typing import List

from f3_data_models.models import EventInstance, Org, Org_Type
from f3_data_models.utils import DbManager
from slack_sdk import WebClient

from utilities.database.orm import SlackSettings
from utilities.database.special_queries import get_position_users
from utilities.helper_functions import safe_get


def create_special_events_blocks(events: List[EventInstance], slack_settings: SlackSettings) -> str:
    text = ""
    for i, event in enumerate(events):
        text += f"{i + 1}. **{event.name}** - {event.start_date.strftime('%A, %B %d')} - {event.start_time} @ {event.org.name}\n"  # noqa

        if event.preblast_ts:
            # TODO: need to make this work for region-level events
            if slack_settings.default_preblast_destination == "specified_channel":
                channel_id = slack_settings.preblast_destination_channel
            else:
                channel_id = event.org.meta.get("slack_channel_id")

            if channel_id:
                text += f"\n<slack://channel?team={slack_settings.team_id}&id={channel_id}&ts={event.preblast_ts}|Click here to go to the preblast thread!>"  # noqa

    return text


def update_canvas(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    # show calendar image
    msg = "# :calendar: This Week\n\n"
    if region_record.calendar_image_current:
        msg += f"![This Week](https://slackblast-images.s3.amazonaws.com/{region_record.calendar_image_current})\n\n"

    # list special events
    special_events: List[EventInstance] = DbManager.find_records(
        cls=EventInstance,
        filters=[
            (
                EventInstance.org_id == region_record.org_id
                or EventInstance.org.has(Org.parent_id == region_record.org_id)
            ),
            EventInstance.start_date >= date.today(),
            EventInstance.start_date <= date.today() + timedelta(days=region_record.special_events_post_days),
            EventInstance.is_active,
            EventInstance.highlight,
        ],
        joinedloads=[EventInstance.org],
    )
    if len(special_events) > 0:
        msg += "# :tada: Special Events:\n\n"
        msg += create_special_events_blocks(special_events, region_record)
        msg += "\n"

    # list SLT members
    position_users = get_position_users(region_record.org_id, region_record.org_id)
    print(position_users)
    if len(position_users) > 0:
        msg += "# :busts_in_silhouette: Shared Leadership Team\n\n"
        for user in position_users:
            slack_user_id = None
            for slack_user in user.slack_users:
                if slack_user:
                    slack_user_id = slack_user.slack_id if slack_user.slack_team_id == region_record.team_id else None
            if slack_user_id:
                msg += f"**{user.position.name}**\n\n![](@{slack_user_id})\n\n"

    print(msg)

    # post to canvas
    if region_record.canvas_channel:
        channel_info = client.conversations_info(channel=region_record.canvas_channel)
        print(channel_info)
        canvas_id = safe_get(channel_info, "channel", "properties", "canvas", "file_id")

        if canvas_id:
            client.canvases_edit(
                canvas_id=canvas_id,
                changes=[
                    {
                        "operation": "replace",
                        "document_content": {"type": "markdown", "markdown": msg},
                    }
                ],
            )
        else:
            client.conversations_canvases_create(
                channel_id=region_record.canvas_channel,
                document_content={"type": "markdown", "markdown": msg},
            )


def update_all_canvases():
    regions: List[Org] = DbManager.find_records(
        cls=Org, filters=[Org.org_type == Org_Type.region], joinedloads=[Org.slack_space]
    )

    for region in regions:
        slack_settings = SlackSettings(**region.slack_space.settings)
        if slack_settings.canvas_channel and slack_settings.special_events_enabled:
            client = WebClient(token=slack_settings.bot_token)
            update_canvas({}, client, Logger(), {}, slack_settings)
