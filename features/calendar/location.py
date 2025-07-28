import copy
import json
from logging import Logger
from typing import List

from f3_data_models.models import Location, Org
from f3_data_models.utils import DbManager
from slack_sdk.web import WebClient

from features.calendar import ao
from utilities.database.orm import SlackSettings
from utilities.helper_functions import safe_convert, safe_get, trigger_map_revalidation
from utilities.slack import actions, orm


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
    edit_location: Location = None,
):
    form = copy.deepcopy(LOCATION_FORM)
    action_id = safe_get(body, "actions", 0, "action_id")

    if edit_location:
        form.set_initial_values(
            {
                actions.CALENDAR_ADD_LOCATION_NAME: edit_location.name,
                actions.CALENDAR_ADD_LOCATION_DESCRIPTION: edit_location.description,
                actions.CALENDAR_ADD_LOCATION_STREET: edit_location.address_street,
                actions.CALENDAR_ADD_LOCATION_STREET2: edit_location.address_street2,
                actions.CALENDAR_ADD_LOCATION_CITY: edit_location.address_city,
                actions.CALENDAR_ADD_LOCATION_STATE: edit_location.address_state,
                actions.CALENDAR_ADD_LOCATION_ZIP: edit_location.address_zip,
                actions.CALENDAR_ADD_LOCATION_COUNTRY: edit_location.address_country,
            }
        )
        if edit_location.latitude and edit_location.longitude:
            form.set_initial_values(
                {
                    actions.CALENDAR_ADD_LOCATION_LAT: edit_location.latitude,
                    actions.CALENDAR_ADD_LOCATION_LON: edit_location.longitude,
                }
            )
        title_text = "Edit Location"
    else:
        title_text = "Add a Location"

    parent_metadata = (
        {"update_view_id": safe_get(body, "view", "id")} if action_id == actions.CALENDAR_ADD_AO_NEW_LOCATION else {}
    )
    parent_metadata = {}
    if action_id == actions.CALENDAR_ADD_AO_NEW_LOCATION:
        parent_metadata["update_view_id"] = safe_get(body, "view", "id")
        form_data = ao.AO_FORM.get_selected_values(body)
        parent_metadata.update(form_data)
    if edit_location:
        parent_metadata["location_id"] = edit_location.id

    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text=title_text,
        callback_id=actions.ADD_LOCATION_CALLBACK_ID,
        new_or_add="add",
        parent_metadata=parent_metadata,
    )


def handle_location_add(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    form_data = LOCATION_FORM.get_selected_values(body)
    metadata = safe_convert(safe_get(body, "view", "private_metadata"), json.loads)

    latitude = safe_convert(safe_get(form_data, actions.CALENDAR_ADD_LOCATION_LAT), float)
    longitude = safe_convert(safe_get(form_data, actions.CALENDAR_ADD_LOCATION_LON), float)

    # TODO: some kind of validation of either lat/long or address?

    location: Location = Location(
        name=safe_get(form_data, actions.CALENDAR_ADD_LOCATION_NAME),
        description=safe_get(form_data, actions.CALENDAR_ADD_LOCATION_DESCRIPTION),
        is_active=True,
        latitude=latitude,
        longitude=longitude,
        address_street=safe_get(form_data, actions.CALENDAR_ADD_LOCATION_STREET),
        address_street2=safe_get(form_data, actions.CALENDAR_ADD_LOCATION_STREET2),
        address_city=safe_get(form_data, actions.CALENDAR_ADD_LOCATION_CITY),
        address_state=safe_get(form_data, actions.CALENDAR_ADD_LOCATION_STATE),
        address_zip=safe_get(form_data, actions.CALENDAR_ADD_LOCATION_ZIP),
        address_country=safe_get(form_data, actions.CALENDAR_ADD_LOCATION_COUNTRY),
        org_id=region_record.org_id,
    )

    if safe_get(metadata, "location_id"):
        # location_id is passed in the metadata if this is an edit
        update_dict = location.__dict__
        update_dict.pop("_sa_instance_state")
        DbManager.update_record(Location, metadata["location_id"], fields=update_dict)
    else:
        location = DbManager.create_record(location)
    trigger_map_revalidation()

    if safe_get(metadata, "update_view_id"):
        update_metadata = {
            actions.CALENDAR_ADD_AO_NAME: safe_get(metadata, actions.CALENDAR_ADD_AO_NAME),
            actions.CALENDAR_ADD_AO_DESCRIPTION: safe_get(metadata, actions.CALENDAR_ADD_AO_DESCRIPTION),
            actions.CALENDAR_ADD_AO_CHANNEL: safe_get(metadata, actions.CALENDAR_ADD_AO_CHANNEL),
            actions.CALENDAR_ADD_AO_LOCATION: str(location.id),
            actions.CALENDAR_ADD_AO_TYPE: safe_get(metadata, actions.CALENDAR_ADD_AO_TYPE),
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
    # find locations whose org_id points to the region
    location_records: List[Location] = DbManager.find_records(
        Location, [Location.org_id == region_record.org_id, Location.is_active]
    )

    # also find locations whose org_id points to AOs of that region
    location_records2 = DbManager.find_join_records2(
        Location,
        Org,
        [Location.org_id == Org.id, Org.parent_id == region_record.org_id, Location.is_active],
    )
    location_records.extend(record[0] for record in location_records2)

    blocks = [
        orm.SectionBlock(
            label=s.name,
            action=f"{actions.LOCATION_EDIT_DELETE}_{s.id}",
            element=orm.StaticSelectElement(
                placeholder="Edit or Delete",
                options=orm.as_selector_options(names=["Edit", "Delete"]),
                confirm=orm.ConfirmObject(
                    title="Are you sure?",
                    text="Are you sure you want to edit / delete this location? This cannot be undone.",  # noqa
                    confirm="Yes, I'm sure",
                    deny="Whups, never mind",
                ),
            ),
        )
        for s in location_records
    ]

    # TODO: add a "next page" button if there are more than 50 locations

    form = orm.BlockView(blocks=blocks)
    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text="Edit/Delete a Location",
        callback_id=actions.EDIT_DELETE_LOCATION_CALLBACK_ID,
        submit_button_text="None",
        new_or_add="add",
    )


def handle_location_edit_delete(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    location_id = safe_convert(safe_get(body, "actions", 0, "action_id").split("_")[1], int)
    action = safe_get(body, "actions", 0, "selected_option", "value")

    if action == "Edit":
        location = DbManager.get(Location, location_id)
        build_location_add_form(body, client, logger, context, region_record, location)
    elif action == "Delete":
        DbManager.update_record(Location, location_id, fields={"is_active": False})
        trigger_map_revalidation()


LOCATION_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="Location Name",
            action=actions.CALENDAR_ADD_LOCATION_NAME,
            element=orm.PlainTextInputElement(placeholder="ie Central Park - Main Entrance"),
            optional=False,
            hint="Use the actual name of the location, ie park name, etc. You will define the F3 AO name when you create AOs.",  # noqa
        ),
        orm.InputBlock(
            label="Description",
            action=actions.CALENDAR_ADD_LOCATION_DESCRIPTION,
            element=orm.PlainTextInputElement(
                placeholder="Notes about the meetup spot, ie 'Meet at the flagpole near the entrance'",  # noqa
                multiline=True,
            ),
        ),
        orm.InputBlock(
            label="Latitude",
            action=actions.CALENDAR_ADD_LOCATION_LAT,
            element=orm.NumberInputElement(
                placeholder="ie 34.0522", min_value=-90, max_value=90, is_decimal_allowed=True
            ),
            optional=False,
        ),
        orm.InputBlock(
            label="Longitude",
            action=actions.CALENDAR_ADD_LOCATION_LON,
            element=orm.NumberInputElement(
                placeholder="ie -118.2437", min_value=-180, max_value=180, is_decimal_allowed=True
            ),
            optional=False,
        ),
        orm.InputBlock(
            label="Location Street Address",
            action=actions.CALENDAR_ADD_LOCATION_STREET,
            element=orm.PlainTextInputElement(placeholder="ie 123 Main St."),
            optional=True,
        ),
        orm.InputBlock(
            label="Location Address Line 2",
            action=actions.CALENDAR_ADD_LOCATION_STREET2,
            element=orm.PlainTextInputElement(placeholder="ie Suite 200"),
            optional=True,
        ),
        orm.InputBlock(
            label="Location City",
            action=actions.CALENDAR_ADD_LOCATION_CITY,
            element=orm.PlainTextInputElement(placeholder="ie Los Angeles"),
            optional=True,
        ),
        orm.InputBlock(
            label="Location State",
            action=actions.CALENDAR_ADD_LOCATION_STATE,
            element=orm.PlainTextInputElement(placeholder="ie CA"),
            optional=True,
        ),
        orm.InputBlock(
            label="Location Zip",
            action=actions.CALENDAR_ADD_LOCATION_ZIP,
            element=orm.PlainTextInputElement(placeholder="ie 90210"),
            optional=True,
        ),
        orm.InputBlock(
            label="Location Country",
            action=actions.CALENDAR_ADD_LOCATION_COUNTRY,
            element=orm.PlainTextInputElement(placeholder="ie USA"),
            optional=True,
            hint="If outside the US, please enter the country name.",
        ),
    ]
)
