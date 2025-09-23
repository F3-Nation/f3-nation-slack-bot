import copy
import json
from logging import Logger
from typing import List, Optional

from slack_sdk.models import blocks
from slack_sdk.web import WebClient

from application.dto import LocationDTO
from application.org.command_handlers import OrgCommandHandler
from application.org.commands import AddLocation, SoftDeleteLocation, UpdateLocation
from application.services.org_query_service import OrgQueryService
from features.calendar import ao
from infrastructure.persistence.sqlalchemy.org_repository import SqlAlchemyOrgRepository
from utilities.database.orm import SlackSettings
from utilities.helper_functions import safe_convert, safe_get, trigger_map_revalidation
from utilities.slack.sdk_orm import SdkBlockView, as_selector_options

# Local copies of Slack action constants used in this module to avoid importing utilities.slack.actions
# Values mirror those defined in utilities/slack/actions.py
CALENDAR_ADD_LOCATION_NAME = "calendar_add_location_name"
CALENDAR_ADD_LOCATION_DESCRIPTION = "calendar_add_location_description"
CALENDAR_ADD_LOCATION_LAT = "calendar_add_location_lat"
CALENDAR_ADD_LOCATION_LON = "calendar_add_location_lon"
CALENDAR_ADD_LOCATION_STREET = "calendar-add-location-street"
CALENDAR_ADD_LOCATION_STREET2 = "calendar-add-location-street2"
CALENDAR_ADD_LOCATION_CITY = "calendar-add-location-city"
CALENDAR_ADD_LOCATION_STATE = "calendar-add-location-state"
CALENDAR_ADD_LOCATION_ZIP = "calendar-add-location-zip"
CALENDAR_ADD_LOCATION_COUNTRY = "calendar-add-location-country"
ADD_LOCATION_CALLBACK_ID = "add-location-id"
EDIT_DELETE_LOCATION_CALLBACK_ID = "edit-delete-location-id"
LOCATION_EDIT_DELETE = "location-edit-delete"


def manage_locations(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    action = safe_get(body, "actions", 0, "selected_option", "value")

    if action == "add":
        build_location_add_form(body, client, logger, context, region_record)
    elif action == "edit":
        build_location_list_form(body, client, logger, context, region_record)


def build_location_add_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
    edit_location: Optional[LocationDTO] = None,
):
    form = copy.deepcopy(LOCATION_FORM)
    action_id = safe_get(body, "actions", 0, "action_id")

    if edit_location:
        form.set_initial_values(
            {
                CALENDAR_ADD_LOCATION_NAME: edit_location.name,
                CALENDAR_ADD_LOCATION_DESCRIPTION: edit_location.description,
                CALENDAR_ADD_LOCATION_STREET: edit_location.address_street,
                CALENDAR_ADD_LOCATION_STREET2: edit_location.address_street2,
                CALENDAR_ADD_LOCATION_CITY: edit_location.address_city,
                CALENDAR_ADD_LOCATION_STATE: edit_location.address_state,
                CALENDAR_ADD_LOCATION_ZIP: edit_location.address_zip,
                CALENDAR_ADD_LOCATION_COUNTRY: edit_location.address_country,
            }
        )
        if edit_location.latitude and edit_location.longitude:
            form.set_initial_values(
                {
                    CALENDAR_ADD_LOCATION_LAT: edit_location.latitude,
                    CALENDAR_ADD_LOCATION_LON: edit_location.longitude,
                }
            )
        title_text = "Edit Location"
    else:
        title_text = "Add a Location"

    parent_metadata = (
        {"update_view_id": safe_get(body, "view", "id")} if action_id == ao.CALENDAR_ADD_AO_NEW_LOCATION else {}
    )
    parent_metadata = {}
    if action_id == ao.CALENDAR_ADD_AO_NEW_LOCATION:
        parent_metadata["update_view_id"] = safe_get(body, "view", "id")
        form_data = ao.AO_FORM.get_selected_values(body)
        parent_metadata.update(form_data)
    if edit_location:
        parent_metadata["location_id"] = int(edit_location.id)

    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text=title_text,
        callback_id=ADD_LOCATION_CALLBACK_ID,
        new_or_add="add",
        parent_metadata=parent_metadata,
    )


def handle_location_add(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    form_data = LOCATION_FORM.get_selected_values(body)
    metadata = safe_convert(safe_get(body, "view", "private_metadata"), json.loads)

    name = safe_get(form_data, CALENDAR_ADD_LOCATION_NAME)
    description = safe_get(form_data, CALENDAR_ADD_LOCATION_DESCRIPTION)
    latitude = safe_convert(safe_get(form_data, CALENDAR_ADD_LOCATION_LAT), float)
    longitude = safe_convert(safe_get(form_data, CALENDAR_ADD_LOCATION_LON), float)
    address_street = safe_get(form_data, CALENDAR_ADD_LOCATION_STREET)
    address_street2 = safe_get(form_data, CALENDAR_ADD_LOCATION_STREET2)
    address_city = safe_get(form_data, CALENDAR_ADD_LOCATION_CITY)
    address_state = safe_get(form_data, CALENDAR_ADD_LOCATION_STATE)
    address_zip = safe_get(form_data, CALENDAR_ADD_LOCATION_ZIP)
    address_country = safe_get(form_data, CALENDAR_ADD_LOCATION_COUNTRY)

    # DDD path via application commands
    repo = SqlAlchemyOrgRepository()
    handler = OrgCommandHandler(repo)
    org_id_int = int(region_record.org_id)
    try:
        if safe_get(metadata, "location_id"):
            handler.handle(
                UpdateLocation(
                    org_id=org_id_int,
                    location_id=int(safe_get(metadata, "location_id")),
                    name=name,
                    description=description,
                    latitude=latitude,
                    longitude=longitude,
                    address_street=address_street,
                    address_street2=address_street2,
                    address_city=address_city,
                    address_state=address_state,
                    address_zip=address_zip,
                    address_country=address_country,
                )
            )
            new_location_id = safe_get(metadata, "location_id")
        else:
            handler.handle(
                AddLocation(
                    org_id=org_id_int,
                    name=name,
                    description=description,
                    latitude=latitude,
                    longitude=longitude,
                    address_street=address_street,
                    address_street2=address_street2,
                    address_city=address_city,
                    address_state=address_state,
                    address_zip=address_zip,
                    address_country=address_country,
                )
            )
            # retrieve created id by name from aggregate (names are unique by domain rule)
            org = repo.get(org_id_int)
            new_location_id = None
            if org:
                for loc in org.locations.values():
                    if getattr(loc.name, "value", None) == name:
                        new_location_id = int(loc.id)
                        break
    except ValueError as e:
        logger.error(f"Location operation failed: {e}")
        return

    trigger_map_revalidation()

    if safe_get(metadata, "update_view_id"):
        update_metadata = {
            ao.CALENDAR_ADD_AO_NAME: safe_get(metadata, ao.CALENDAR_ADD_AO_NAME),
            ao.CALENDAR_ADD_AO_DESCRIPTION: safe_get(metadata, ao.CALENDAR_ADD_AO_DESCRIPTION),
            ao.CALENDAR_ADD_AO_CHANNEL: safe_get(metadata, ao.CALENDAR_ADD_AO_CHANNEL),
            ao.CALENDAR_ADD_AO_LOCATION: str(new_location_id) if new_location_id is not None else None,
            ao.CALENDAR_ADD_AO_TYPE: safe_get(metadata, ao.CALENDAR_ADD_AO_TYPE),
        }
        ao.build_ao_add_form(
            body,
            client,
            logger,
            context,
            region_record,
            update_view_id=metadata["update_view_id"],
            update_metadata=update_metadata,
        )


def build_location_list_form(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    repo = SqlAlchemyOrgRepository()
    qs = OrgQueryService(repo)

    # Region-owned locations
    locs: List[LocationDTO] = qs.get_locations(region_record.org_id, only_active=True)

    # Also include locations owned by AOs under this region
    try:
        children = repo.list_children(int(region_record.org_id), include_inactive=False)
    except Exception:
        children = []
    for child in children:
        try:
            locs.extend(qs.get_locations(int(child.id), only_active=True))
        except Exception:
            continue

    # De-duplicate by id
    seen = set()
    unique_locs: List[LocationDTO] = []
    for loc in locs:
        if int(loc.id) not in seen:
            seen.add(int(loc.id))
            unique_locs.append(loc)

    def display_name(dto: LocationDTO) -> str:
        if (dto.name or "").strip() != "":
            return dto.name
        if (dto.description or "") != "":
            return (dto.description or "")[:30]
        if (dto.address_street or "") != "":
            return (dto.address_street or "")[:30]
        return "Unnamed Location"

    block_list = [
        blocks.SectionBlock(
            label=display_name(s),
            block_id=f"{LOCATION_EDIT_DELETE}_{s.id}",
            element=blocks.StaticSelectElement(
                placeholder="Edit or Delete",
                options=as_selector_options(names=["Edit", "Delete"]),
                action_id=f"{LOCATION_EDIT_DELETE}_{s.id}",
                confirm=blocks.ConfirmObject(
                    title="Are you sure?",
                    text="Are you sure you want to edit / delete this location? This cannot be undone.",  # noqa
                    confirm="Yes, I'm sure",
                    deny="Whups, never mind",
                ),
            ),
        )
        for s in unique_locs
    ]

    # TODO: add a "next page" button if there are more than 50 locations

    form = SdkBlockView(blocks=block_list)
    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text="Edit/Delete a Location",
        callback_id=EDIT_DELETE_LOCATION_CALLBACK_ID,
        submit_button_text="None",
        new_or_add="add",
    )


def handle_location_edit_delete(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    location_id = safe_convert(safe_get(body, "actions", 0, "action_id").split("_")[1], int)
    action = safe_get(body, "actions", 0, "selected_option", "value")

    if action == "Edit":
        # Find the location among region and AO children
        repo = SqlAlchemyOrgRepository()
        qs = OrgQueryService(repo)
        candidates: List[LocationDTO] = qs.get_locations(region_record.org_id, only_active=True)
        try:
            for child in repo.list_children(int(region_record.org_id), include_inactive=False):
                candidates.extend(qs.get_locations(int(child.id), only_active=True))
        except Exception:
            pass
        loc_dto = next((loc for loc in candidates if int(loc.id) == int(location_id)), None)
        build_location_add_form(body, client, logger, context, region_record, loc_dto)
    elif action == "Delete":
        repo = SqlAlchemyOrgRepository()
        handler = OrgCommandHandler(repo)
        org_id_int = int(region_record.org_id)
        try:
            handler.handle(SoftDeleteLocation(org_id=org_id_int, location_id=int(location_id)))
        except ValueError as e:
            logger.error(f"Failed to delete location: {e}")
        trigger_map_revalidation()


LOCATION_FORM = SdkBlockView(
    blocks=[
        blocks.InputBlock(
            label="Location Name",
            block_id=CALENDAR_ADD_LOCATION_NAME,
            element=blocks.PlainTextInputElement(placeholder="ie Central Park - Main Entrance"),
            optional=False,
            hint="Use the actual name of the location, ie park name, etc. You will define the F3 AO name when you create AOs.",  # noqa
        ),
        blocks.InputBlock(
            label="Description",
            block_id=CALENDAR_ADD_LOCATION_DESCRIPTION,
            element=blocks.PlainTextInputElement(
                placeholder="Notes about the meetup spot, ie 'Meet at the flagpole near the entrance'",  # noqa
                multiline=True,
            ),
        ),
        blocks.InputBlock(
            label="Latitude",
            block_id=CALENDAR_ADD_LOCATION_LAT,
            element=blocks.NumberInputElement(
                placeholder="ie 34.0522", min_value=-90, max_value=90, is_decimal_allowed=True
            ),
            optional=False,
        ),
        blocks.InputBlock(
            label="Longitude",
            block_id=CALENDAR_ADD_LOCATION_LON,
            element=blocks.NumberInputElement(
                placeholder="ie -118.2437", min_value=-180, max_value=180, is_decimal_allowed=True
            ),
            optional=False,
        ),
        blocks.InputBlock(
            label="Location Street Address",
            block_id=CALENDAR_ADD_LOCATION_STREET,
            element=blocks.PlainTextInputElement(placeholder="ie 123 Main St."),
            optional=True,
        ),
        blocks.InputBlock(
            label="Location Address Line 2",
            block_id=CALENDAR_ADD_LOCATION_STREET2,
            element=blocks.PlainTextInputElement(placeholder="ie Suite 200"),
            optional=True,
        ),
        blocks.InputBlock(
            label="Location City",
            block_id=CALENDAR_ADD_LOCATION_CITY,
            element=blocks.PlainTextInputElement(placeholder="ie Los Angeles"),
            optional=True,
        ),
        blocks.InputBlock(
            label="Location State",
            block_id=CALENDAR_ADD_LOCATION_STATE,
            element=blocks.PlainTextInputElement(placeholder="ie CA"),
            optional=True,
        ),
        blocks.InputBlock(
            label="Location Zip",
            block_id=CALENDAR_ADD_LOCATION_ZIP,
            element=blocks.PlainTextInputElement(placeholder="ie 90210"),
            optional=True,
        ),
        blocks.InputBlock(
            label="Location Country",
            block_id=CALENDAR_ADD_LOCATION_COUNTRY,
            element=blocks.PlainTextInputElement(placeholder="ie USA"),
            optional=True,
            hint="If outside the US, please enter the country name.",
        ),
    ]
)
