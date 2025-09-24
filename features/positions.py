import copy
import json
from logging import Logger

from slack_sdk.models import blocks
from slack_sdk.web import WebClient

from application.org.command_handlers import OrgCommandHandler
from application.org.commands import AddPosition, ReplacePositionAssignments
from infrastructure.persistence.sqlalchemy.org_repository import SqlAlchemyOrgRepository
from utilities.database.orm import SlackSettings
from utilities.database.special_queries import get_position_users
from utilities.helper_functions import get_user, safe_convert, safe_get
from utilities.slack import forms
from utilities.slack.sdk_orm import SdkBlockView, as_selector_options

# Local copies of Slack action constants used in this module to avoid importing utilities.slack.actions
# Values mirror those defined in utilities/slack/actions.py
SLT_LEVEL_SELECT = "slt-level-select"
SLT_SELECT = "slt-select"
CONFIG_NEW_POSITION = "new_position"
CONFIG_SLT_CALLBACK_ID = "config-slt-id"
NEW_POSITION_CALLBACK_ID = "new-position-id"
CONFIG_NEW_POSITION_NAME = "new_position_name"
CONFIG_NEW_POSITION_DESCRIPTION = "new_position_description"


def build_config_slt_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
    update_view_id: str | None = None,
    selected_org_id: int | None = None,
):
    if safe_get(body, "actions", 0, "action_id") == SLT_LEVEL_SELECT:
        org_id = safe_convert(safe_get(body, "actions", 0, "selected_option", "value"), int)
        org_id = org_id if org_id != 0 else region_record.org_id
        update_view_id = safe_get(body, "view", "id")
    else:
        org_id = selected_org_id or region_record.org_id

    position_users = get_position_users(org_id, region_record.org_id, slack_team_id=region_record.team_id)
    # Fetch AOs via repository (DDD)
    repo = SqlAlchemyOrgRepository()
    aos = repo.list_children(region_record.org_id, include_inactive=False)
    level_options = {"names": ["Region"], "values": ["0"]}
    for a in aos:
        level_options["names"].append(a.name)
        level_options["values"].append(str(int(a.id)))

    block_list = [
        blocks.InputBlock(
            label="Select the SLT positions for...",
            block_id=SLT_LEVEL_SELECT,
            element=blocks.StaticSelectElement(
                options=as_selector_options(**level_options),
                initial_value="0" if org_id == region_record.org_id else str(org_id),
                action_id=SLT_LEVEL_SELECT,
            ),
            dispatch_action=True,
        ),
    ]

    for p in position_users:
        block_list.append(
            blocks.InputBlock(
                label=p.position.name,
                block_id=SLT_SELECT + str(p.position.id),
                optional=True,
                element=blocks.UserMultiSelectElement(
                    placeholder="Select SLT Members...",
                    initial_value=[u.slack_id for u in p.slack_users if u is not None],
                    action_id=SLT_SELECT + str(p.position.id),
                ),
                hint=p.position.description,
            )
        )

    block_list.append(
        blocks.ActionsBlock(
            elements=[
                blocks.ButtonElement(text=":heavy_plus_sign: New Position", action_id=CONFIG_NEW_POSITION),
                # Future: possible button to clone from global catalog (global positions already appear in list)
            ]
        )
    )

    form = SdkBlockView(blocks=block_list)
    if update_view_id:
        form.update_modal(
            client=client,
            view_id=update_view_id,
            callback_id=CONFIG_SLT_CALLBACK_ID,
            title_text="SLT Members",
        )
    else:
        form.post_modal(
            client=client,
            trigger_id=safe_get(body, "trigger_id"),
            callback_id=CONFIG_SLT_CALLBACK_ID,
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
            SLT_LEVEL_SELECT,
            SLT_LEVEL_SELECT,
            "selected_option",
            "value",
        ),
        int,
    )
    selected_org_id = selected_org_id if selected_org_id != 0 else region_record.org_id

    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        callback_id=NEW_POSITION_CALLBACK_ID,
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
    org_type_str = "region" if selected_org_id == region_record.org_id else "ao"

    position_name = safe_get(form_data, CONFIG_NEW_POSITION_NAME)
    position_description = safe_get(form_data, CONFIG_NEW_POSITION_DESCRIPTION)

    if not position_name:
        logger.warning("Position name missing; ignoring new position submission")
    else:
        try:
            repo = SqlAlchemyOrgRepository()
            handler = OrgCommandHandler(repo)
            handler.handle(
                AddPosition(
                    org_id=int(region_record.org_id),
                    name=position_name,
                    description=position_description,
                    org_type=org_type_str,
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
    org_id = safe_convert(safe_get(form_data, SLT_LEVEL_SELECT, SLT_LEVEL_SELECT, "selected_option", "value"), int)
    org_id = org_id if org_id != 0 else region_record.org_id
    # Gather desired assignments
    new_assignments: list[tuple[int, int]] = []  # (position_id, user_id)

    for key, value in form_data.items():
        if key.startswith(SLT_SELECT):
            position_id = int(key.replace(SLT_SELECT, ""))
            users = [get_user(u, region_record, client, logger) for u in value[key]["selected_users"]]

            for u in users:
                if u:
                    new_assignments.append((position_id, int(u.user_id)))

    # DDD path: for each position, gather user IDs and dispatch ReplacePositionAssignments
    try:
        repo = SqlAlchemyOrgRepository()
        handler = OrgCommandHandler(repo)
        # Build mapping position_id -> list[user_id]
        mapping: dict[int, list[int]] = {}
        for pos_id, user_id in new_assignments:
            mapping.setdefault(int(pos_id), []).append(int(user_id))
        # For positions with zero selected users we still need to clear assignments
        # Identify all position ids present in the form (even if zero users selected)
        form_position_ids: list[int] = []
        for key in form_data.keys():
            if key.startswith(SLT_SELECT):
                form_position_ids.append(int(key.replace(SLT_SELECT, "")))
        for pid in form_position_ids:
            assignment = ReplacePositionAssignments(
                org_id=int(region_record.org_id),
                position_id=pid,
                user_ids=mapping.get(pid, []),
            )
            print(f"Dispatching assignment update: {assignment}")
            handler.handle(assignment)
    except ValueError as e:
        logger.error(f"Failed to update position assignments via DDD path: {e}")
