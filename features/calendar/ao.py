import copy
import datetime
import json
from logging import Logger
from typing import List

import requests
from f3_data_models.models import Event, EventInstance, EventType, Location, Org, Org_Type
from f3_data_models.utils import DbManager
from slack_sdk.web import WebClient

from utilities.database.orm import SlackSettings
from utilities.helper_functions import safe_convert, safe_get, trigger_map_revalidation, upload_files_to_storage
from utilities.slack import actions, orm


def manage_aos(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    action = safe_get(body, "actions", 0, "selected_option", "value")

    if action == "add":
        build_ao_add_form(body, client, logger, context, region_record)
    elif action == "edit":
        build_ao_list_form(body, client, logger, context, region_record)


def build_ao_add_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
    edit_ao: Org = None,
    update_view_id: str = None,
    update_metadata: dict = None,
):
    form = copy.deepcopy(AO_FORM)

    # Pull locations and event types for the region
    region_org_record: Org = DbManager.get(Org, region_record.org_id, joinedloads="all")
    locations: List[Location] = sorted(region_org_record.locations, key=lambda x: x.name)
    event_types: List[EventType] = sorted(region_org_record.event_types, key=lambda x: x.name)

    form.set_options(
        {
            actions.CALENDAR_ADD_AO_LOCATION: orm.as_selector_options(
                names=[location.name for location in locations],
                values=[str(location.id) for location in locations],
                # descriptions=[location.description for location in locations],
            ),
            actions.CALENDAR_ADD_AO_TYPE: orm.as_selector_options(
                names=[event_type.name for event_type in event_types],
                values=[str(event_type.id) for event_type in event_types],
                # descriptions=[event_type.description for event_type in event_types],
            ),
        }
    )

    if edit_ao:
        slack_id = safe_get(edit_ao.meta, "slack_channel_id")
        form.set_initial_values(
            {
                actions.CALENDAR_ADD_AO_NAME: edit_ao.name,
                actions.CALENDAR_ADD_AO_DESCRIPTION: edit_ao.description,
                actions.CALENDAR_ADD_AO_CHANNEL: slack_id,
            }
        )
        if edit_ao.default_location_id:
            form.set_initial_values({actions.CALENDAR_ADD_AO_LOCATION: str(edit_ao.default_location_id)})
        title_text = "Edit AO"
        if edit_ao.logo_url:
            try:
                if requests.head(edit_ao.logo_url).status_code == 200:
                    form.blocks.insert(5, orm.ImageBlock(image_url=edit_ao.logo_url, alt_text="AO Logo"))
            except requests.RequestException as e:
                logger.error(f"Error fetching AO logo: {e}")
    else:
        title_text = "Add an AO"

    if update_view_id:
        form.set_initial_values(update_metadata)
        form.update_modal(
            client=client,
            view_id=update_view_id,
            title_text=title_text,
            callback_id=actions.ADD_AO_CALLBACK_ID,
        )
    else:
        form.post_modal(
            client=client,
            trigger_id=safe_get(body, "trigger_id"),
            title_text=title_text,
            callback_id=actions.ADD_AO_CALLBACK_ID,
            new_or_add="add",
            parent_metadata={"ao_id": edit_ao.id} if edit_ao else {},
        )


def handle_ao_add(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    form_data = AO_FORM.get_selected_values(body)
    region_org_id = region_record.org_id
    metatdata = safe_convert(safe_get(body, "view", "private_metadata"), json.loads)

    file = safe_get(form_data, actions.CALENDAR_ADD_AO_LOGO, 0)
    if file:
        file_list, file_send_list, file_ids = upload_files_to_storage(
            files=[file], logger=logger, client=client, enforce_square=True, max_height=512
        )
        logo_url = file_list[0]
        # try:
        #     r = requests.get(file["url_private_download"], headers={"Authorization": f"Bearer {client.token}"})
        #     r.raise_for_status()
        #     logo = r.content
        # except Exception as exc:
        #     logger.error(f"Error downloading file: {exc}")
        #     logo = None
    else:
        logo_url = None

    slack_id = safe_get(form_data, actions.CALENDAR_ADD_AO_CHANNEL)
    ao: Org = Org(
        parent_id=region_org_id,
        org_type=Org_Type.ao,
        is_active=True,
        name=safe_get(form_data, actions.CALENDAR_ADD_AO_NAME),
        description=safe_get(form_data, actions.CALENDAR_ADD_AO_DESCRIPTION),
        meta={"slack_channel_id": slack_id},
        default_location_id=safe_get(form_data, actions.CALENDAR_ADD_AO_LOCATION),
        logo_url=logo_url,
    )

    if safe_get(metatdata, "ao_id"):
        update_dict = ao.__dict__
        update_dict.pop("_sa_instance_state")
        if not logo_url:
            update_dict.pop("logo_url", None)
        DbManager.update_record(Org, metatdata["ao_id"], fields=update_dict)
    else:
        DbManager.create_record(ao)
    trigger_map_revalidation()


def build_ao_list_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    ao_records: List[Org] = DbManager.find_records(
        Org, [Org.parent_id == region_record.org_id, Org.org_type == Org_Type.ao]
    )

    blocks = [
        orm.SectionBlock(
            label=s.name,
            action=f"{actions.AO_EDIT_DELETE}_{s.id}",
            element=orm.StaticSelectElement(
                placeholder="Edit or Delete",
                options=orm.as_selector_options(names=["Edit", "Delete"]),
                confirm=orm.ConfirmObject(
                    title="Are you sure?",
                    text="Are you sure you want to edit / delete this AO? This cannot be undone. Deleting an AO will also delete all associated series and events.",  # noqa
                    confirm="Yes, I'm sure",
                    deny="Whups, never mind",
                ),
            ),
        )
        for s in ao_records
    ]

    form = orm.BlockView(blocks=blocks)
    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text="Edit or Delete an AO",
        callback_id=actions.EDIT_DELETE_AO_CALLBACK_ID,
        submit_button_text="None",
        new_or_add="add",
    )


def handle_ao_edit_delete(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    ao_id = safe_convert(safe_get(body, "actions", 0, "action_id").split("_")[1], int)
    action = safe_get(body, "actions", 0, "selected_option", "value")

    if action == "Edit":
        ao: Org = DbManager.get(Org, ao_id, joinedloads="all")
        build_ao_add_form(body, client, logger, context, region_record, edit_ao=ao)
    elif action == "Delete":
        DbManager.update_record(Org, ao_id, fields={"is_active": False})
        DbManager.update_records(Event, [Event.org_id == ao_id], fields={"is_active": False})
        DbManager.update_records(
            EventInstance,
            [EventInstance.org_id == ao_id, EventInstance.start_date >= datetime.datetime.now()],
            fields={"is_active": False},
        )
        trigger_map_revalidation()


AO_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="AO Title",
            action=actions.CALENDAR_ADD_AO_NAME,
            element=orm.PlainTextInputElement(placeholder="Enter the AO name"),
            optional=False,
        ),
        orm.InputBlock(
            label="Description",
            action=actions.CALENDAR_ADD_AO_DESCRIPTION,
            element=orm.PlainTextInputElement(placeholder="Enter a description for the AO", multiline=True),
        ),
        orm.InputBlock(
            label="Channel associated with this AO:",
            action=actions.CALENDAR_ADD_AO_CHANNEL,
            element=orm.ChannelsSelectElement(placeholder="Select a channel"),
            optional=False,
        ),
        orm.InputBlock(
            label="Default Location",
            action=actions.CALENDAR_ADD_AO_LOCATION,
            element=orm.StaticSelectElement(placeholder="Select a location"),
        ),
        orm.ActionsBlock(
            elements=[
                orm.ButtonElement(
                    label="Add Location",
                    action=actions.CALENDAR_ADD_AO_NEW_LOCATION,
                    value="add",
                )
            ],
        ),
        orm.InputBlock(
            label="AO Logo",
            action=actions.CALENDAR_ADD_AO_LOGO,
            optional=True,
            element=orm.FileInputElement(
                max_files=1,
                filetypes=[
                    "png",
                    "jpg",
                    "heic",
                    "bmp",
                ],
            ),
        ),
    ]
)
