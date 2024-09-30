import os
import sys
from datetime import date, timedelta

from slack_sdk import WebClient

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from typing import List, Tuple

from utilities.database import DbManager, get_session
from utilities.database.orm import (
    Event,
    Org,
    Org_x_Slack,
    SlackSettings,
    SlackSpace,
)
from utilities.slack import orm


def create_special_events_blocks(
    records: List[Tuple[Event, Org, Org_x_Slack]], slack_settings: SlackSettings
) -> List[dict]:
    blocks: List[orm.BaseBlock] = []
    for i, (event, org, org_x_slack) in enumerate(records):
        text = f"*{i+1}. {event.name}*\n{event.start_date.strftime('%A, %B %d')} - {event.start_time.strftime('%H%M')}\n{org.name}"  # noqa

        if event.preblast_ts:
            # TODO: need to make this work when the preblast gets posted to a particular channel rather than the AO channel # noqa
            # TODO: also need to make this work for region-level events
            text += f"\n<slack://channel?team={slack_settings.team_id}&id={org_x_slack.slack_id}&ts={event.preblast_ts}|Click here to go to the preblast thread!>"  # noqa
        blocks.append(
            orm.SectionBlock(
                label=text,
                # TODO: add HC button?
            )
        )
    blocks = [block.as_form_field() for block in blocks]
    return blocks


def update_special_events():
    with get_session() as session:
        query = (
            session.query(
                Org,
                Org_x_Slack,
                SlackSpace,
            )
            .select_from(Org)
            .join(Org_x_Slack, Org.id == Org_x_Slack.org_id)
            .join(SlackSpace, Org_x_Slack.slack_id == SlackSpace.team_id)
            .filter(Org.org_type_id == 2)
        )
        all_regions_records = query.all()

    for record in all_regions_records:
        slack_settings = SlackSettings(**record[2].settings)
        region = record[0]
        if slack_settings.special_events_enabled:
            number_of_days = slack_settings.special_events_post_days or 30
            records: List[Tuple[Event, Org, Org_x_Slack]] = DbManager.find_join_records3(
                Event,
                Org,
                Org_x_Slack,
                [
                    (Event.org_id == region.id or Org.parent_id == region.id),
                    Event.start_date >= date.today(),
                    Event.start_date <= date.today() + timedelta(days=number_of_days),
                    Event.is_active,
                    ~Event.is_series,
                    Event.highlight,
                ],
            )
            if records and slack_settings.special_events_channel:
                blocks = create_special_events_blocks(records, slack_settings)
                WebClient(token=slack_settings.bot_token).chat_postMessage(
                    channel=slack_settings.special_events_channel,
                    text=f"Upcoming events for {region.name}:",
                    blocks=blocks,
                )


if __name__ == "__main__":
    update_special_events()
