import copy
import json
import os
from logging import Logger
from typing import List

from f3_data_models.models import Org, Org_Type, Position_x_Org_x_User
from f3_data_models.utils import DbManager
from slack_sdk.web import WebClient

from application.org.command_handlers import OrgCommandHandler
from application.org.commands import AddPosition, ReplacePositionAssignments
from infrastructure.persistence.sqlalchemy.org_repository import SqlAlchemyOrgRepository
from utilities.database.orm import SlackSettings
from utilities.database.special_queries import get_position_users
from utilities.helper_functions import get_user, safe_convert, safe_get
from utilities.slack import actions, forms, orm

use_ddd = bool(int(os.environ.get("ORG_DDD_ENABLED", "1")))  # default on


def build_config_slt_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
    update_view_id: str | None = None,
    selected_org_id: int | None = None,
):
    if safe_get(body, "actions", 0, "action_id") == actions.SLT_LEVEL_SELECT:
        org_id = safe_convert(safe_get(body, "actions", 0, "selected_option", "value"), int)
        org_id = org_id if org_id != 0 else region_record.org_id
        update_view_id = safe_get(body, "view", "id")
    else:
        org_id = selected_org_id or region_record.org_id

    position_users = get_position_users(org_id, region_record.org_id, slack_team_id=region_record.team_id)
    aos: List[Org] = DbManager.find_records(
        cls=Org,
        filters=[Org.parent_id == region_record.org_id],
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
        blocks.append(
            orm.InputBlock(
                label=p.position.name,
                action=actions.SLT_SELECT + str(p.position.id),
                optional=True,
                element=orm.MultiUsersSelectElement(
                    placeholder="Select SLT Members...",
                    initial_value=[u.slack_id for u in p.slack_users if u is not None],
                ),
                hint=p.position.description,
            )
        )

    blocks.append(
        orm.ActionsBlock(
            elements=[
                orm.ButtonElement(label=":heavy_plus_sign: New Position", action=actions.CONFIG_NEW_POSITION),
                # Future: possible button to clone from global catalog (global positions already appear in list)
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
    selected_org_id = metadata.get("org_id")
    org_type_level = Org_Type.region if selected_org_id == region_record.org_id else Org_Type.ao

    position_name = safe_get(form_data, actions.CONFIG_NEW_POSITION_NAME)
    position_description = safe_get(form_data, actions.CONFIG_NEW_POSITION_DESCRIPTION)

    if not position_name:
        logger.warning("Position name missing; ignoring new position submission")
    else:
        if not use_ddd:
            # Legacy path persists under region org scope
            from f3_data_models.models import Position  # local import only for legacy path

            DbManager.create_record(
                Position(
                    name=position_name,
                    description=position_description,
                    org_id=region_record.org_id,
                    org_type=org_type_level,
                )
            )
        else:
            try:
                repo = SqlAlchemyOrgRepository()
                handler = OrgCommandHandler(repo)
                handler.handle(
                    AddPosition(
                        org_id=int(region_record.org_id),
                        name=position_name,
                        description=position_description,
                        org_type=org_type_level.name.lower() if org_type_level is not None else None,
                    )
                )
            except ValueError as e:
                logger.error(f"Failed to add position via DDD path: {e}")

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
    org_id = safe_convert(
        safe_get(form_data, actions.SLT_LEVEL_SELECT, actions.SLT_LEVEL_SELECT, "selected_option", "value"), int
    )
    org_id = org_id if org_id != 0 else region_record.org_id
    new_assignments: List[Position_x_Org_x_User] = []

    for key, value in form_data.items():
        if key.startswith(actions.SLT_SELECT):
            position_id = int(key.replace(actions.SLT_SELECT, ""))
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

    if not use_ddd:
        # Legacy direct persistence for assignments
        DbManager.delete_records(Position_x_Org_x_User, filters=[Position_x_Org_x_User.org_id == org_id])
        if new_assignments:
            DbManager.create_records(new_assignments)
    else:
        # DDD path: for each position, gather user IDs and dispatch ReplacePositionAssignments
        try:
            repo = SqlAlchemyOrgRepository()
            handler = OrgCommandHandler(repo)
            # Build mapping position_id -> list[user_id]
            mapping: dict[int, list[int]] = {}
            for pa in new_assignments:
                mapping.setdefault(int(pa.position_id), []).append(int(pa.user_id))
            # For positions with zero selected users we still need to clear assignments
            # Identify all position ids present in the form (even if zero users selected)
            form_position_ids = []
            for key in form_data.keys():
                if key.startswith(actions.SLT_SELECT):
                    form_position_ids.append(int(key.replace(actions.SLT_SELECT, "")))
            for pid in form_position_ids:
                handler.handle(
                    ReplacePositionAssignments(
                        org_id=int(region_record.org_id),
                        position_id=pid,
                        user_ids=mapping.get(pid, []),
                    )
                )
        except ValueError as e:
            logger.error(f"Failed to update position assignments via DDD path: {e}")
