import os
import sys
from datetime import date, timedelta

from slack_sdk import WebClient

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from typing import List

from f3_data_models.models import (
    Event,
    Org,
)
from f3_data_models.utils import DbManager

from utilities.database.orm import SlackSettings
from utilities.slack import orm

# TODO: future option for this to live on a Canvas?!?


def create_special_events_blocks(events: List[Event], slack_settings: SlackSettings) -> List[dict]:
    blocks: List[orm.BaseBlock] = []
    for i, event in enumerate(events):
        text = f"*{i + 1}. {event.name}*\n{event.start_date.strftime('%A, %B %d')} - {event.start_time.strftime('%H%M')}\n{event.org.name}"  # noqa

        if event.preblast_ts:
            # TODO: need to make this work for region-level events
            if slack_settings.default_preblast_destination == "specified_channel":
                channel_id = slack_settings.preblast_destination_channel
            else:
                channel_id = event.org.meta.get("slack_channel_id")

            if channel_id:
                text += f"\n<slack://channel?team={slack_settings.team_id}&id={channel_id}&ts={event.preblast_ts}|Click here to go to the preblast thread!>"  # noqa
        blocks.append(
            orm.SectionBlock(
                label=text,
                # TODO: add HC button?
            )
        )
    blocks = [block.as_form_field() for block in blocks]
    return blocks


def update_special_events():
    regions: List[Org] = DbManager.find_records(cls=Org, filters=[Org.org_type_id == 2], joinedloads=[Org.slack_space])

    for region in regions:
        slack_settings = SlackSettings(**region.slack_space.settings)
        if slack_settings.special_events_enabled:
            number_of_days = slack_settings.special_events_post_days or 30
            events: List[Event] = DbManager.find_records(
                cls=Event,
                filters=[
                    (Event.org_id == region.id or Event.org.has(Org.parent_id == region.id)),
                    Event.start_date >= date.today(),
                    Event.start_date <= date.today() + timedelta(days=number_of_days),
                    Event.is_active,
                    ~Event.is_series,
                    Event.highlight,
                ],
                joinedloads=[Event.org],
            )
            if events and slack_settings.special_events_channel:
                blocks = create_special_events_blocks(events, slack_settings)
                WebClient(token=slack_settings.bot_token).chat_postMessage(
                    channel=slack_settings.special_events_channel,
                    text=f"Upcoming events for {region.name}:",
                    blocks=blocks,
                )


if __name__ == "__main__":
    update_special_events()
