import copy
import json
from logging import Logger
from typing import List

from f3_data_models.models import Org, Org_Type, Position, Position_x_Org_x_User
from f3_data_models.utils import DbManager
from slack_sdk.web import WebClient

from utilities.database.orm import SlackSettings
from utilities.database.special_queries import get_position_users
from utilities.helper_functions import (
    get_user,
    safe_convert,
    safe_get,
)
from utilities.slack import actions, forms, orm


def build_config_slt_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
    update_view_id: str = None,
    selected_org_id: int = None,
):
    if safe_get(body, "actions", 0, "action_id") == actions.SLT_LEVEL_SELECT:
        org_id = safe_convert(safe_get(body, "actions", 0, "selected_option", "value"), int)
        org_id = org_id if org_id != 0 else region_record.org_id
        update_view_id = safe_get(body, "view", "id")
    else:
        update_view_id = safe_get(body, actions.LOADING_ID)
        print(f"update_view_id: {update_view_id}")
        org_id = selected_org_id or region_record.org_id

    position_users = get_position_users(org_id, region_record.org_id, slack_team_id=region_record.team_id)
    aos: List[Org] = DbManager.find_records(
        cls=Org,
        filters=[Org.parent_id == region_record.org_id, Org.is_active],
    )
    level_options = [orm.SelectorOption(name="Region", value="0")]
    for a in aos:
        level_options.append(orm.SelectorOption(name=a.name, value=str(a.id)))

    blocks = [
        orm.InputBlock(
            label="Select the SLT positions for...",
            action=actions.SLT_LEVEL_SELECT,
            element=orm.StaticSelectElement(
                options=level_options,
                initial_value="0" if org_id == region_record.org_id else str(org_id),
            ),
            dispatch_action=True,
        ),
    ]

    for p in position_users:
        slack_user_ids = [u.slack_id for u in p.slack_users if u is not None]
        blocks.append(
            orm.InputBlock(
                label=p.position.name,
                action=actions.SLT_SELECT + str(p.position.id) + "_" + str(org_id),
                optional=True,
                element=orm.MultiUsersSelectElement(
                    placeholder="Select SLT Members...",
                ),
                hint=p.position.description,
            )
        )
        if slack_user_ids:
            blocks[-1].element.initial_value = slack_user_ids

    blocks.append(
        orm.ActionsBlock(
            elements=[
                orm.ButtonElement(
                    label=":heavy_plus_sign: New Position",
                    action=actions.CONFIG_NEW_POSITION,
                ),
                orm.ButtonElement(
                    label=":pencil2: Edit Positions",
                    action=actions.CONFIG_EDIT_POSITIONS,
                ),
            ]
        )
    )

    form = orm.BlockView(blocks=blocks)
    if update_view_id:
        form.update_modal(
            client=client,
            view_id=update_view_id,
            callback_id=actions.CONFIG_SLT_CALLBACK_ID,
            title_text="SLT Members",
        )
    else:
        form.post_modal(
            client=client,
            trigger_id=safe_get(body, "trigger_id"),
            callback_id=actions.CONFIG_SLT_CALLBACK_ID,
            title_text="SLT Members",
            new_or_add="add",
        )


def build_new_position_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    form = copy.deepcopy(forms.CONFIG_NEW_POSITION_FORM)
    selected_org_id = safe_convert(
        safe_get(
            body,
            "view",
            "state",
            "values",
            actions.SLT_LEVEL_SELECT,
            actions.SLT_LEVEL_SELECT,
            "selected_option",
            "value",
        ),
        int,
    )
    selected_org_id = selected_org_id if selected_org_id != 0 else region_record.org_id

    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        callback_id=actions.NEW_POSITION_CALLBACK_ID,
        title_text="New Position",
        new_or_add="add",
        parent_metadata={"org_id": selected_org_id},
    )


def handle_new_position_post(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    form_data = forms.CONFIG_NEW_POSITION_FORM.get_selected_values(body)
    metadata = json.loads(safe_get(body, "view", "private_metadata") or "{}")
    org_type = Org_Type.region if metadata.get("org_id") == region_record.org_id else Org_Type.ao

    DbManager.create_record(
        Position(
            name=safe_get(form_data, actions.CONFIG_NEW_POSITION_NAME),
            description=safe_get(form_data, actions.CONFIG_NEW_POSITION_DESCRIPTION),
            org_id=region_record.org_id,
            org_type=org_type,
        )
    )
    build_config_slt_form(
        body,
        client,
        logger,
        context,
        region_record,
        update_view_id=safe_get(body, "view", "previous_view_id"),
        selected_org_id=metadata.get("org_id"),
    )


def handle_config_slt_post(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    form_data = body["view"]["state"]["values"]
    new_assignments: List[Position_x_Org_x_User] = []

    for key, value in form_data.items():
        if key.startswith(actions.SLT_SELECT):
            position_id, org_id = map(int, key.replace(actions.SLT_SELECT, "").split("_"))
            org_id = org_id if org_id != 0 else region_record.org_id
            users = [get_user(u, region_record, client, logger) for u in value[key]["selected_users"]]

            for u in users:
                if u:
                    new_assignments.append(
                        Position_x_Org_x_User(
                            org_id=org_id,
                            position_id=position_id,
                            user_id=u.user_id,
                        )
                    )

    DbManager.delete_records(
        Position_x_Org_x_User,
        filters=[Position_x_Org_x_User.org_id == org_id],
    )

    DbManager.create_records(new_assignments)


def build_position_list_form(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    """Build a form listing custom positions that can be edited or deleted."""
    positions_all: List[Position] = DbManager.find_records(Position, [Position.is_active])
    positions_in_org = [p for p in positions_all if p.org_id == region_record.org_id]

    blocks = [
        orm.ContextBlock(
            element=orm.ContextElement(initial_value="Only region-specific positions can be edited or deleted."),
        )
    ]

    if not positions_in_org:
        blocks.append(
            orm.SectionBlock(
                label="No custom positions found. Use 'New Position' to create one.",
            )
        )
    else:
        for p in positions_in_org:
            blocks.append(
                orm.SectionBlock(
                    label=p.name,
                    action=f"{actions.POSITION_EDIT_DELETE}_{p.id}",
                    element=orm.StaticSelectElement(
                        placeholder="Edit or Delete",
                        options=orm.as_selector_options(names=["Edit", "Delete"]),
                        confirm=orm.ConfirmObject(
                            title="Are you sure?",
                            text="Are you sure you want to edit / delete this Position? This cannot be undone.",
                            confirm="Yes, I'm sure",
                            deny="Whups, never mind",
                        ),
                    ),
                )
            )

    form = orm.BlockView(blocks=blocks)

    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text="Edit/Delete Positions",
        callback_id=actions.EDIT_DELETE_POSITION_CALLBACK_ID,
        submit_button_text="None",
        new_or_add="add",
    )


def handle_position_edit_delete(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    """Handle edit or delete action for a position."""
    action = safe_get(body, "actions", 0, "selected_option", "value")
    position_id = safe_get(body, "actions", 0, "action_id").split("_")[-1]

    if action == "Edit":
        position: Position = DbManager.get(Position, position_id)
        build_edit_position_form(body, client, logger, context, region_record, position)
    elif action == "Delete":
        # Delete position assignments first, then mark position as inactive
        DbManager.delete_records(
            Position_x_Org_x_User,
            filters=[Position_x_Org_x_User.position_id == position_id],
        )
        DbManager.update_record(
            Position,
            position_id,
            fields={
                Position.is_active: False,
            },
        )


def build_edit_position_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
    position: Position,
):
    """Build a form for editing an existing position."""
    form = copy.deepcopy(forms.CONFIG_NEW_POSITION_FORM)

    form.set_initial_values(
        {
            actions.CONFIG_NEW_POSITION_NAME: position.name,
            actions.CONFIG_NEW_POSITION_DESCRIPTION: position.description or "",
        }
    )

    form.update_modal(
        client=client,
        view_id=safe_get(body, "view", "id"),
        callback_id=actions.EDIT_POSITION_CALLBACK_ID,
        title_text="Edit Position",
        parent_metadata={"position_id": position.id},
    )


def handle_edit_position_post(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    """Handle the submission of an edited position."""
    form_data = forms.CONFIG_NEW_POSITION_FORM.get_selected_values(body)
    metadata = json.loads(safe_get(body, "view", "private_metadata") or "{}")
    position_id = metadata.get("position_id")

    if position_id:
        DbManager.update_record(
            Position,
            position_id,
            fields={
                Position.name: safe_get(form_data, actions.CONFIG_NEW_POSITION_NAME),
                Position.description: safe_get(form_data, actions.CONFIG_NEW_POSITION_DESCRIPTION),
            },
        )
