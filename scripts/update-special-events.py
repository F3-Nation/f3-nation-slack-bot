import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, timedelta
from typing import List, Tuple

from slack_sdk.web import WebClient

from utilities.database import DbManager
from utilities.database.orm import (
    Event,
    Org,
    SlackSettings,
)
from utilities.slack import orm


def create_special_events_blocks(records: List[Tuple[Event, Org]]) -> List[dict]:
    blocks: List[orm.BaseBlock] = []
    for i, (event, org) in enumerate(records):
        text = f"*{i+1}. {event.name}*\n{event.start_date.strftime('%A, %B %d')} - {event.start_time.strftime('%H%M')}\n{org.name}"  # noqa

        if event.preblast_ts:
            # TODO: need to make this work when the preblast gets posted to a particular channel rather than the AO channel # noqa
            # TODO: also need to make this work for region-level events
            text += f"\n<slack://channel?team={slack_settings.team_id}&id={org.slack_id}&ts={event.preblast_ts}|Click here to go to the preblast!>"  # noqa
        blocks.append(
            orm.SectionBlock(
                label=text,
                # TODO: add HC button?
            )
        )
    blocks = [block.as_form_field() for block in blocks]
    return blocks


all_regions: List[Org] = DbManager.find_records(Org, [Org.org_type_id == 2])
for region in all_regions:
    slack_settings = SlackSettings(**region.slack_app_settings)
    if slack_settings.special_events_enabled:
        number_of_days = slack_settings.special_events_post_days or 30
        records: List[Tuple[Event, Org]] = DbManager.find_join_records2(
            Event,
            Org,
            [
                (Event.org_id == region.id or Org.parent_id == region.id),
                Event.start_date >= date.today(),
                Event.end_date <= date.today() + timedelta(days=number_of_days),
                Event.highlight,
            ],
        )
        if records and slack_settings.special_events_channel:
            blocks = create_special_events_blocks(records)
            WebClient(token=slack_settings.bot_token).chat_postMessage(
                channel=slack_settings.special_events_channel,
                text=f"Upcoming events for {region.name}:",
                blocks=blocks,
            )
