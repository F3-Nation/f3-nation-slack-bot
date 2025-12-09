from logging import Logger
from typing import List

from f3_data_models.models import Org, Org_Type
from f3_data_models.utils import DbManager
from slack_sdk.models.blocks import (
    DividerBlock,
    InputBlock,
)
from slack_sdk.models.blocks.basic_components import Option
from slack_sdk.models.blocks.block_elements import ChannelSelectElement, ExternalDataSelectElement, SelectElement
from slack_sdk.web import WebClient

from utilities.database.orm import SlackSettings
from utilities.helper_functions import safe_convert, safe_get
from utilities.slack.sdk_orm import SdkBlockView

# Action IDs
PAXMINER_ORIGINATING_CHANNEL = "paxminer-originating-channel"
PAXMINER_EVENT_TYPE = "paxminer-event-type"
PAXMINER_AO = "paxminer-assign-ao"
PAXMINER_MAPPING_ID = "paxminer-mapping-id"
PAXMINER_REGION = "paxminer-assign-region"


def build_paxminer_mapping_form(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    if safe_get(body, "actions", 0, "action_id") in [PAXMINER_ORIGINATING_CHANNEL, PAXMINER_REGION]:
        initial_channel = safe_get(
            body, "state", "values", PAXMINER_ORIGINATING_CHANNEL, PAXMINER_ORIGINATING_CHANNEL, "selected_channel"
        )
        initial_org = safe_convert(
            safe_get(body, "state", "values", PAXMINER_REGION, PAXMINER_REGION, "selected_option", "value"), int
        )

        org_record = DbManager.get(Org, (initial_org or region_record.org_id), joinedloads=[Org.event_types])
        event_type_options = [Option(label=et.name, value=str(et.id)) for et in org_record.event_types]
        intial_event_type = next(et for et in event_type_options if et.label == "Bootcamp")
        initial_region = Option(label=org_record.name, value=str(org_record.id))
        ao_records: List[Org] = DbManager.find_records(
            Org,
            [
                Org.parent_id == (initial_org or region_record.org_id),
                Org.org_type == Org_Type.ao,
                Org.is_active.is_(True),
            ],
        )
        added_blocks = [
            DividerBlock(),
            InputBlock(
                label="Assign to Region",
                block_id=PAXMINER_REGION,
                element=ExternalDataSelectElement(
                    action_id=PAXMINER_REGION,
                    placeholder="Select a region...",
                    initial_option=initial_region,
                ),
                optional=False,
                dispatch_action=True,
            ),
            InputBlock(
                label="Assign to AO",
                block_id=PAXMINER_AO,
                element=SelectElement(
                    action_id=PAXMINER_AO,
                    options=[Option(label=ao.name, value=str(ao.id)) for ao in ao_records],
                ),
                optional=False,
            ),
            InputBlock(
                label="Assign to Event Type",
                block_id=PAXMINER_EVENT_TYPE,
                element=SelectElement(
                    action_id=PAXMINER_EVENT_TYPE,
                    options=event_type_options,
                    initial_option=intial_event_type,
                ),
                optional=False,
            ),
        ]
        update_view_id = safe_get(body, "view", "id")
    else:
        initial_channel = None
        added_blocks = []
        update_view_id = None

    form = SdkBlockView(
        blocks=[
            InputBlock(
                label="Originating Channel",
                block_id=PAXMINER_ORIGINATING_CHANNEL,
                element=ChannelSelectElement(
                    action_id=PAXMINER_ORIGINATING_CHANNEL,
                    initial_channel=initial_channel,
                ),
                dispatch_action=True,
            ),
            *added_blocks,
        ],
    )
    if update_view_id:
        form.update_modal(
            client=client,
            view_id=update_view_id,
            title_text="Paxminer Data Mapping",
            callback_id=PAXMINER_MAPPING_ID,
        )
    else:
        form.post_modal(
            client=client,
            trigger_id=safe_get(body, "trigger_id"),
            title_text="Paxminer Data Mapping",
            callback_id=PAXMINER_MAPPING_ID,
            new_or_add="add",
            submit_button_text="None",
        )


def handle_paxminer_mapping_post(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    pass
