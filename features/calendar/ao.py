import copy
import json
from logging import Logger

import requests
from slack_sdk.models import blocks
from slack_sdk.web import WebClient

from application.org.command_handlers import OrgCommandHandler
from application.org.commands import CreateAo, DeactivateAo, UpdateAoProfile
from application.services.org_query_service import OrgQueryService
from infrastructure.persistence.sqlalchemy.org_repository import SqlAlchemyOrgRepository
from utilities.database.orm import SlackSettings
from utilities.helper_functions import (
    safe_convert,
    safe_get,
    trigger_map_revalidation,
    upload_files_to_storage,
)
from utilities.slack.sdk_orm import SdkBlockView, as_selector_options

CALENDAR_ADD_AO_LOCATION = "calendar_add_ao_location"
CALENDAR_ADD_AO_TYPE = "calendar_add_ao_type"
CALENDAR_ADD_AO_NAME = "calendar_add_ao_name"
CALENDAR_ADD_AO_DESCRIPTION = "calendar_add_ao_description"
CALENDAR_ADD_AO_CHANNEL = "calendar_add_ao_channel"
CALENDAR_ADD_AO_LOGO = "calendar_add_ao_logo"
CALENDAR_ADD_AO_NEW_LOCATION = "calendar-add-ao-new-location"
ADD_AO_CALLBACK_ID = "add-ao-id"
AO_EDIT_DELETE = "ao-edit-delete"
EDIT_DELETE_AO_CALLBACK_ID = "edit-delete-ao-id"


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
    edit_ao_id: int | None = None,
    update_view_id: str | None = None,
    update_metadata: dict | None = None,
):
    form = copy.deepcopy(AO_FORM)

    # Pull locations and event types via query service (includes global types for event types)
    repo = SqlAlchemyOrgRepository()
    qs = OrgQueryService(repo)
    location_dtos = qs.get_locations(region_record.org_id)
    event_type_dtos = qs.get_event_types(region_record.org_id, include_global=True)

    form.set_options(
        {
            CALENDAR_ADD_AO_LOCATION: as_selector_options(
                names=[dto.name for dto in location_dtos],
                values=[str(dto.id) for dto in location_dtos],
            ),
            CALENDAR_ADD_AO_TYPE: as_selector_options(
                names=[dto.name for dto in event_type_dtos],
                values=[str(dto.id) for dto in event_type_dtos],
            ),
        }
    )

    edit_ao = None
    if edit_ao_id is not None:
        # fetch AO via repository to avoid direct Db access here
        edit_ao = repo.get(edit_ao_id)
    if edit_ao:
        slack_id = safe_get(edit_ao.meta, "slack_channel_id")
        form.set_initial_values(
            {
                CALENDAR_ADD_AO_NAME: edit_ao.name,
                CALENDAR_ADD_AO_DESCRIPTION: edit_ao.description,
                CALENDAR_ADD_AO_CHANNEL: slack_id,
            }
        )
        if edit_ao.default_location_id:
            form.set_initial_values({CALENDAR_ADD_AO_LOCATION: str(edit_ao.default_location_id)})
        title_text = "Edit AO"
        if edit_ao.logo_url:
            try:
                if requests.head(edit_ao.logo_url).status_code == 200:
                    form.blocks.insert(5, blocks.ImageBlock(image_url=edit_ao.logo_url, alt_text="AO Logo"))
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
            callback_id=ADD_AO_CALLBACK_ID,
        )
    else:
        form.post_modal(
            client=client,
            trigger_id=safe_get(body, "trigger_id"),
            title_text=title_text,
            callback_id=ADD_AO_CALLBACK_ID,
            new_or_add="add",
            parent_metadata={"ao_id": int(edit_ao.id)} if edit_ao else {},
        )


def handle_ao_add(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    form_data = AO_FORM.get_selected_values(body)
    region_org_id = region_record.org_id
    metatdata = safe_convert(safe_get(body, "view", "private_metadata"), json.loads)

    file = safe_get(form_data, CALENDAR_ADD_AO_LOGO, 0)
    if file:
        file_list, file_send_list, file_ids, low_rez_file_ids = upload_files_to_storage(
            files=[file], logger=logger, client=client, enforce_square=True, max_height=512
        )
        logo_url = safe_get(file_list, 0)
    else:
        logo_url = None

    slack_id = safe_get(form_data, CALENDAR_ADD_AO_CHANNEL)

    # DDD command path only
    repo = SqlAlchemyOrgRepository()
    handler = OrgCommandHandler(repo)
    region_id_int = int(region_org_id)
    name = safe_get(form_data, CALENDAR_ADD_AO_NAME)
    description = safe_get(form_data, CALENDAR_ADD_AO_DESCRIPTION)
    default_location_id = safe_convert(safe_get(form_data, CALENDAR_ADD_AO_LOCATION), int)
    try:
        if safe_get(metatdata, "ao_id"):
            handler.handle(
                UpdateAoProfile(
                    ao_id=int(safe_get(metatdata, "ao_id")),
                    name=name,
                    description=description,
                    default_location_id=default_location_id,
                    slack_channel_id=slack_id,
                    logo_url=logo_url,
                )
            )
        else:
            handler.handle(
                CreateAo(
                    region_id=region_id_int,
                    name=name,
                    description=description,
                    default_location_id=default_location_id,
                    slack_channel_id=slack_id,
                    logo_url=logo_url,
                )
            )
    except ValueError as e:
        logger.error(f"AO operation failed: {e}")
        return
    trigger_map_revalidation()


def build_ao_list_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    repo = SqlAlchemyOrgRepository()
    ao_records = repo.list_children(region_record.org_id, include_inactive=False)

    block_list = [
        blocks.SectionBlock(
            text=s.name,
            block_id=f"{AO_EDIT_DELETE}_{s.id}",
            accessory=blocks.StaticSelectElement(
                placeholder="Edit or Delete",
                options=as_selector_options(names=["Edit", "Delete"]),
                confirm=blocks.ConfirmObject(
                    title="Are you sure?",
                    text="Are you sure you want to edit / delete this AO? This cannot be undone. Deleting an AO will also delete all associated series and events.",  # noqa
                    confirm="Yes, I'm sure",
                    deny="Whups, never mind",
                ),
                action_id=f"{AO_EDIT_DELETE}_{s.id}",
            ),
        )
        for s in ao_records
    ]

    form = SdkBlockView(blocks=block_list)
    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text="Edit or Delete an AO",
        callback_id=EDIT_DELETE_AO_CALLBACK_ID,
        submit_button_text="None",
        new_or_add="add",
    )


def handle_ao_edit_delete(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    ao_id = safe_convert(safe_get(body, "actions", 0, "action_id").split("_")[1], int)
    action = safe_get(body, "actions", 0, "selected_option", "value")

    if action == "Edit":
        build_ao_add_form(body, client, logger, context, region_record, edit_ao_id=ao_id)
    elif action == "Delete":
        repo = SqlAlchemyOrgRepository()
        handler = OrgCommandHandler(repo)
        try:
            handler.handle(DeactivateAo(ao_id=ao_id))
        except ValueError as e:
            logger.error(f"Failed to deactivate AO: {e}")
        trigger_map_revalidation()


AO_FORM = SdkBlockView(
    blocks=[
        blocks.InputBlock(
            label="AO Title",
            element=blocks.PlainTextInputElement(
                placeholder="Enter the AO name",
                action_id=CALENDAR_ADD_AO_NAME,
            ),
            block_id=CALENDAR_ADD_AO_NAME,
            optional=False,
        ),
        blocks.InputBlock(
            label="Description",
            element=blocks.PlainTextInputElement(
                placeholder="Enter a description for the AO",
                multiline=True,
                action_id=CALENDAR_ADD_AO_DESCRIPTION,
            ),  # noqa
            block_id=CALENDAR_ADD_AO_DESCRIPTION,
        ),
        blocks.InputBlock(
            label="Channel associated with this AO:",
            element=blocks.ChannelSelectElement(
                placeholder="Select a channel",
                action_id=CALENDAR_ADD_AO_CHANNEL,
            ),
            block_id=CALENDAR_ADD_AO_CHANNEL,
            optional=False,
        ),
        blocks.InputBlock(
            label="Default Location",
            element=blocks.StaticSelectElement(
                placeholder="Select a location",
                action_id=CALENDAR_ADD_AO_LOCATION,
            ),
            block_id=CALENDAR_ADD_AO_LOCATION,
        ),
        blocks.ActionsBlock(
            elements=[
                blocks.ButtonElement(
                    text="Add Location",
                    action_id=CALENDAR_ADD_AO_NEW_LOCATION,
                    value="add",
                )
            ],
        ),
        blocks.InputBlock(
            label="AO Logo",
            block_id=CALENDAR_ADD_AO_LOGO,
            optional=True,
            element=blocks.block_elements.FileInputElement(
                action_id=CALENDAR_ADD_AO_LOGO,
                max_files=1,
                file_types=[
                    "png",
                    "jpg",
                    "heic",
                    "bmp",
                ],
            ),
        ),
    ]
)
