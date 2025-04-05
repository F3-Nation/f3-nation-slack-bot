import copy
import json
import os
from datetime import date, datetime
from logging import Logger
from typing import List

import pytz
from cryptography.fernet import Fernet
from f3_data_models.models import (
    Attendance,
    Attendance_x_AttendanceType,
    AttendanceType,
    EventInstance,
    EventType_x_EventInstance,
    Org,
    SlackUser,
)
from f3_data_models.utils import DbManager
from pillow_heif import register_heif_opener
from slack_sdk.web import WebClient
from sqlalchemy import not_

from features import backblast_legacy
from utilities import constants, sendmail
from utilities.database.orm import SlackSettings
from utilities.database.special_queries import event_attendance_query, get_user_permission_list
from utilities.helper_functions import (
    get_channel_names,
    get_pax,
    get_user,
    parse_rich_block,
    remove_keys_from_dict,
    replace_user_channel_ids,
    safe_convert,
    safe_get,
    upload_files_to_storage,
)
from utilities.slack import actions, forms
from utilities.slack import orm as slack_orm

register_heif_opener()


def add_custom_field_blocks(form: slack_orm.BlockView, region_record: SlackSettings) -> slack_orm.BlockView:
    output_form = copy.deepcopy(form)
    for custom_field in (region_record.custom_fields or {}).values():
        if safe_get(custom_field, "enabled"):
            output_form.add_block(
                slack_orm.InputBlock(
                    element=forms.CUSTOM_FIELD_TYPE_MAP[custom_field["type"]],
                    action=actions.CUSTOM_FIELD_PREFIX + custom_field["name"],
                    label=custom_field["name"],
                    optional=True,
                )
            )
            if safe_get(custom_field, "type") == "Dropdown":
                output_form.set_options(
                    {
                        actions.CUSTOM_FIELD_PREFIX + custom_field["name"]: slack_orm.as_selector_options(
                            names=custom_field["options"],
                            values=custom_field["options"],
                        )
                    }
                )
    return output_form


def backblast_middleware(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
):
    if region_record.org_id is None:
        backblast_legacy.build_backblast_form(body, client, logger, context, region_record)
    else:
        user = get_user(safe_get(body, "user", "id") or safe_get(body, "user_id"), region_record, client, logger)
        user_id = user.user_id
        event_records = event_attendance_query(
            attendance_filter=[
                Attendance.user_id == user_id,
                Attendance.is_planned,
                Attendance.attendance_types.any(AttendanceType.id.in_([2, 3])),
            ],
            event_filter=[
                EventInstance.start_date < date.today(),
                EventInstance.backblast_ts.is_(None),
                EventInstance.is_active,
            ],
        )

        if event_records:
            select_block = slack_orm.InputBlock(
                label="Select a past Q",
                action=actions.BACKBLAST_FILL_SELECT,
                dispatch_action=True,
                element=slack_orm.StaticSelectElement(
                    placeholder="Select an event",
                    options=slack_orm.as_selector_options(
                        names=[
                            f"{r.start_date} {r.org.name} {' / '.join([t.name for t in r.event_types])}"
                            for r in event_records
                        ],
                        values=[str(r.id) for r in event_records],
                    ),
                ),
            )
        else:
            select_block = slack_orm.SectionBlock(label="No past events for you to send a backblast for!")

        blocks = [
            select_block,
            slack_orm.ActionsBlock(
                elements=[
                    slack_orm.ButtonElement(
                        label=":heavy_plus_sign: New Unscheduled Event", action=actions.BACKBLAST_NEW_BLANK_BUTTON
                    ),
                    slack_orm.ButtonElement(label=":calendar: Open Calendar", action=actions.OPEN_CALENDAR_BUTTON),
                ]
            ),
        ]
        form = slack_orm.BlockView(blocks=blocks)
        form.update_modal(
            client=client,
            view_id=safe_get(body, actions.LOADING_ID),
            callback_id=actions.BACKBLAST_SELECT_CALLBACK_ID,
            title_text="Select Backblast",
            submit_button_text="None",
        )


def build_backblast_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    """
    Args:
        body (dict): Slack request body
        client (WebClient): Slack WebClient object
        logger (Logger): Logger object
        context (dict): Slack request context
        region_record (Region): Region record for the requesting region
    """

    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    trigger_id = safe_get(body, "trigger_id")
    backblast_metadata = safe_get(body, "message", "metadata", "event_payload") or {}
    action_id = safe_get(body, "actions", 0, "action_id")
    if action_id == actions.BACKBLAST_FILL_SELECT:
        event_instance_id = safe_convert(safe_get(body, "actions", 0, "selected_option", "value"), int)
    elif action_id == actions.MSG_EVENT_BACKBLAST_BUTTON:
        event_instance_id = safe_convert(safe_get(body, "actions", 0, "value"), int)
    else:
        event_instance_id = safe_get(backblast_metadata, "event_instance_id")

    update_view_id = safe_get(body, actions.LOADING_ID) or safe_get(body, "view", "id")

    if safe_get(backblast_metadata, actions.BACKBLAST_TITLE):
        initial_backblast_data = backblast_metadata
        moleskin_block = safe_get(body, "message", "blocks", 1)
        moleskin_block = remove_keys_from_dict(moleskin_block, ["display_team_id", "display_url"])
        initial_backblast_data[actions.BACKBLAST_MOLESKIN] = moleskin_block
    elif event_instance_id:
        event_record: EventInstance = DbManager.get(EventInstance, event_instance_id, joinedloads="all")
        already_posted = event_record.backblast_ts is not None
        attendance_records: List[Attendance] = DbManager.find_records(
            Attendance,
            [Attendance.event_instance_id == event_instance_id, Attendance.is_planned != already_posted],
            joinedloads="all",
        )
        initial_backblast_data = {
            actions.BACKBLAST_TITLE: event_record.name,
            actions.BACKBLAST_INFO: f"""
*AO:* {event_record.org.name}
*DATE:* {event_record.start_date.strftime("%Y-%m-%d")}
*EVENT TYPE:* {" / ".join([t.name for t in event_record.event_types])}
""",
            # actions.BACKBLAST_DATE: event_record.start_date.strftime("%Y-%m-%d"),
            # actions.BACKBLAST_AO: event_record.org.meta["slack_channel_id"],
            actions.BACKBLAST_Q: safe_get(
                [a.slack_user.slack_id for a in attendance_records if 2 in [t.id for t in a.attendance_types]], 0
            ),
            actions.BACKBLAST_COQ: [
                a.slack_user.slack_id for a in attendance_records if 3 in [t.id for t in a.attendance_types]
            ],
            actions.BACKBLAST_PAX: [a.slack_user.slack_id for a in attendance_records],
            actions.BACKBLAST_MOLESKIN: region_record.backblast_moleskin_template,
            # actions.BACKBLAST_EVENT_TYPE: str(event_record.event_types[0].id),  # picking the first for now
        }
        backblast_metadata["event_instance_id"] = event_instance_id
    else:
        initial_backblast_data = {
            actions.BACKBLAST_Q: user_id,
            actions.BACKBLAST_DATE: datetime.now(pytz.timezone("US/Central")).strftime("%Y-%m-%d"),
            actions.BACKBLAST_MOLESKIN: region_record.backblast_moleskin_template,
        }

    org_event_types: Org = DbManager.get(Org, region_record.org_id, joinedloads=[Org.event_types])
    event_type_options = slack_orm.as_selector_options(
        [r.name for r in org_event_types.event_types], [str(r.id) for r in org_event_types.event_types]
    )

    backblast_form = copy.deepcopy(forms.BACKBLAST_FORM)
    backblast_form.set_options({actions.BACKBLAST_EVENT_TYPE: event_type_options})
    backblast_form.set_initial_values(initial_backblast_data)
    backblast_form = add_custom_field_blocks(backblast_form, region_record)

    if (region_record.email_enabled or 0) == 0 or (region_record.email_option_show or 0) == 0:
        backblast_form.delete_block(actions.BACKBLAST_EMAIL_SEND)
    # backblast_metadata = None
    if action_id == actions.BACKBLAST_EDIT_BUTTON:
        callback_id = actions.BACKBLAST_EDIT_CALLBACK_ID
        backblast_metadata["channel_id"] = safe_get(body, "container", "channel_id")
        backblast_metadata["message_ts"] = safe_get(body, "container", "message_ts")
        backblast_metadata["files"] = safe_get(backblast_metadata, actions.BACKBLAST_FILE) or []
    else:
        callback_id = actions.BACKBLAST_CALLBACK_ID

    if update_view_id:
        backblast_form.update_modal(
            client=client,
            view_id=update_view_id,
            callback_id=callback_id,
            title_text="Backblast",
            parent_metadata=backblast_metadata,
        )
    else:
        backblast_form.post_modal(
            client=client,
            trigger_id=trigger_id,
            callback_id=callback_id,
            title_text="Backblast",
            parent_metadata=backblast_metadata,
        )


def handle_backblast_post(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    create_or_edit = "create" if safe_get(body, "view", "callback_id") == actions.BACKBLAST_CALLBACK_ID else "edit"

    backblast_form = copy.deepcopy(forms.BACKBLAST_FORM)
    backblast_form = add_custom_field_blocks(backblast_form, region_record)
    backblast_data: dict = backblast_form.get_selected_values(body)
    logger.debug(f"Backblast data: {backblast_data}")

    metadata = json.loads(safe_get(body, "view", "private_metadata") or "{}")
    if safe_get(metadata, "event_instance_id"):
        event: EventInstance = DbManager.get(EventInstance, safe_get(metadata, "event_instance_id"), joinedloads="all")

    title = safe_get(backblast_data, actions.BACKBLAST_TITLE)
    the_date = safe_get(backblast_data, actions.BACKBLAST_DATE) or event.start_date.strftime("%Y-%m-%d")
    the_ao = safe_get(backblast_data, actions.BACKBLAST_AO) or event.org.meta["slack_channel_id"]
    the_q = safe_get(backblast_data, actions.BACKBLAST_Q)
    the_coq = safe_get(backblast_data, actions.BACKBLAST_COQ)
    pax = safe_get(backblast_data, actions.BACKBLAST_PAX)
    non_slack_pax = safe_get(backblast_data, actions.BACKBLAST_NONSLACK_PAX)
    fngs = safe_get(backblast_data, actions.BACKBLAST_FNGS)
    count = safe_get(backblast_data, actions.BACKBLAST_COUNT)
    moleskin = safe_get(backblast_data, actions.BACKBLAST_MOLESKIN)
    email_send = safe_get(backblast_data, actions.BACKBLAST_EMAIL_SEND)
    # ao = safe_get(backblast_data, actions.BACKBLAST_AO)
    event_type = safe_convert(safe_get(backblast_data, actions.BACKBLAST_EVENT_TYPE), int) or event.event_types[0].id
    files = safe_get(backblast_data, actions.BACKBLAST_FILE) or []

    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    file_list, file_send_list = upload_files_to_storage(files=files, logger=logger, client=client)
    event_instance_id = safe_get(metadata, "event_instance_id")
    if (
        region_record.default_backblast_destination == constants.CONFIG_DESTINATION_SPECIFIED["value"]
        and region_record.backblast_destination_channel
    ):
        destination_channel = region_record.backblast_destination_channel
    else:
        destination_channel = the_ao

    if create_or_edit == "edit":
        message_channel = safe_get(metadata, "channel_id")
        message_ts = safe_get(metadata, "message_ts")
        file_list = safe_get(metadata, "files") if not file_list else file_list
    else:
        message_channel = None
        message_ts = None

    all_pax = list(set([the_q] + (the_coq or []) + pax))
    db_users: List[SlackUser] = [get_user(p, region_record, client, logger) for p in all_pax]
    auto_count = len(all_pax)
    pax_names_list = [user.user_name for user in db_users]

    pax_formatted = get_pax(pax)
    pax_full_list = [pax_formatted]
    fngs_formatted = fngs
    fng_count = 0
    if non_slack_pax:
        pax_full_list.append(non_slack_pax)
        pax_names_list.append(non_slack_pax)
        auto_count += non_slack_pax.count(",") + 1
    if fngs:
        pax_full_list.append(fngs)
        pax_names_list.append(fngs)
        fng_count = fngs.count(",") + 1
        fngs_formatted = str(fng_count) + " " + fngs
        auto_count += fngs.count(",") + 1
    pax_formatted = ", ".join(pax_full_list)
    pax_names = ", ".join(pax_names_list)

    if the_coq is None:
        the_coqs_formatted = ""
        the_coqs_names = ""
    else:
        the_coqs_formatted = get_pax(the_coq)
        the_coqs_full_list = [the_coqs_formatted]
        the_coqs_users = [get_user(c, region_record, client, logger) for c in the_coq]
        the_coqs_names_list = [user.user_name for user in the_coqs_users]
        the_coqs_formatted = ", " + ", ".join(the_coqs_full_list)
        the_coqs_names = ", " + ", ".join(the_coqs_names_list)

    ao_name = get_channel_names([the_ao], logger, client)[0]
    q_user = get_user(the_q, region_record, client, logger)
    q_name = q_user.user_name
    q_url = q_user.avatar_url
    count = count or auto_count

    post_msg = f"""*Backblast! {title}*
*DATE*: {the_date}
*AO*: <#{the_ao}>
*Q*: <@{the_q}>{the_coqs_formatted}
*PAX*: {pax_formatted}
*FNGs*: {fngs_formatted}
*COUNT*: {count}"""

    custom_fields = {}
    for field, value in backblast_data.items():
        if (field[: len(actions.CUSTOM_FIELD_PREFIX)] == actions.CUSTOM_FIELD_PREFIX) and value:
            post_msg += f"\n*{field[len(actions.CUSTOM_FIELD_PREFIX) :]}*: {str(value)}"
            custom_fields[field[len(actions.CUSTOM_FIELD_PREFIX) :]] = value

    if file_list:
        custom_fields["files"] = file_list

    msg_block = slack_orm.SectionBlock(label=post_msg)

    backblast_data.pop(actions.BACKBLAST_MOLESKIN, None)
    backblast_data[actions.BACKBLAST_FILE] = file_list
    backblast_data[actions.BACKBLAST_OP] = user_id
    backblast_data["event_instance_id"] = event_instance_id

    edit_block = slack_orm.ActionsBlock(
        elements=[
            slack_orm.ButtonElement(
                label=":pencil: Edit this backblast",
                action=actions.BACKBLAST_EDIT_BUTTON,
                value=json.dumps(backblast_data),
            ),
            slack_orm.ButtonElement(
                label=":heavy_plus_sign: New backblast",
                action=actions.BACKBLAST_NEW_BUTTON,
                value="new",
            ),
        ]
    )

    if region_record.strava_enabled:
        edit_block.elements.append(
            slack_orm.ButtonElement(
                label=":runner: Connect to Strava",
                action=actions.BACKBLAST_STRAVA_BUTTON,
                value="strava",
            )
        )

    blocks = [msg_block.as_form_field(), moleskin]
    for file in file_list or []:
        blocks.append(
            slack_orm.ImageBlock(
                alt_text=title,
                image_url=file,
            ).as_form_field()
        )
    blocks.append(edit_block.as_form_field())

    moleskin_text = parse_rich_block(moleskin)
    moleskin_text_w_names = replace_user_channel_ids(
        moleskin_text, region_record, client, logger
    )  # check this for efficiency

    if create_or_edit == "create":
        text = (f"{moleskin_text_w_names}\n\nUse the 'New Backblast' button to create a new backblast")[:1500]
        res = client.chat_postMessage(
            channel=destination_channel,
            text=text,
            username=f"{q_name} (via F3 Nation)",
            icon_url=q_url,
            blocks=blocks,
            metadata={"event_type": "backblast", "event_payload": backblast_data},
        )
        print(json.dumps({"event_type": "successful_slack_post", "team_name": region_record.workspace_name}))
        if (email_send and email_send == "yes") or (email_send is None and region_record.email_enabled == 1):
            moleskin_msg = moleskin_text_w_names

            if region_record.postie_format:
                subject = f"[{ao_name}] {title}"
                moleskin_msg += f"\n\nTags: {ao_name}, {pax_names}"
            else:
                subject = title

            email_msg = f"""Date: {the_date}
AO: {ao_name}
Q: {q_name} {the_coqs_names}
PAX: {pax_names}
FNGs: {fngs_formatted}
COUNT: {count}
{moleskin_msg}
            """

            try:
                # Decrypt password
                fernet = Fernet(os.environ[constants.PASSWORD_ENCRYPT_KEY].encode())
                email_password_decrypted = fernet.decrypt(region_record.email_password.encode()).decode()
                sendmail.send(
                    subject=subject,
                    body=email_msg,
                    email_server=region_record.email_server,
                    email_server_port=region_record.email_server_port,
                    email_user=region_record.email_user,
                    email_password=email_password_decrypted,
                    email_to=region_record.email_to,
                    attachments=file_send_list,
                )
                logger.debug("\nEmail Sent! \n{}".format(email_msg))
                print(
                    json.dumps(
                        {
                            "event_type": "successful_email_sent",
                            "team_name": region_record.workspace_name,
                        }
                    )
                )
            except Exception as sendmail_err:
                logger.error("Error with sendmail: {}".format(sendmail_err))
                logger.debug("\nEmail Sent! \n{}".format(email_msg))
                print(json.dumps({"event_type": "failed_email", "team_name": region_record.workspace_name}))

    elif create_or_edit == "edit":
        text = (f"{moleskin_text_w_names}\n\nUse the 'New Backblast' button to create a new backblast")[:1500]
        res = client.chat_update(
            channel=message_channel,
            ts=message_ts,
            text=text,
            username=f"{q_name} (via F3 Nation)",
            icon_url=q_url,
            blocks=blocks,
            metadata={"event_type": "backblast", "event_payload": backblast_data},
        )
        logger.debug("\nBackblast updated in Slack! \n{}".format(post_msg))
        print(json.dumps({"event_type": "successful_slack_edit", "team_name": region_record.workspace_name}))

        if event_instance_id:
            DbManager.delete_records(
                Attendance,
                filters=[
                    Attendance.event_instance_id == event_instance_id,
                    not_(Attendance.is_planned),
                ],
            )
        logger.debug("\nBackblast deleted from database! \n{}".format(post_msg))
        print(json.dumps({"event_type": "successful_db_delete", "team_name": region_record.workspace_name}))

    # res_link = client.chat_getPermalink(channel=chan or message_channel, message_ts=res["ts"])

    backblast_parsed = f"""Backblast! {title}
Date: {the_date}
AO: {ao_name}
Q: {q_name} {the_coqs_names}
PAX: {pax_names}
FNGs: {fngs_formatted}
COUNT: {count}
{moleskin_text_w_names}
"""
    rich_blocks: list = res["message"]["blocks"]
    rich_blocks.pop(-1)

    if event_instance_id:
        event: EventInstance = DbManager.get(EventInstance, event_instance_id, joinedloads="all")
        db_fields = {
            EventInstance.start_date: the_date,
            EventInstance.org_id: event.org.id,
            # Event.event_type_id: event_type, # TODO: update event_type records
            EventInstance.backblast_ts: res["ts"],
            EventInstance.backblast: backblast_parsed,
            EventInstance.backblast_rich: res["message"]["blocks"],
            EventInstance.name: title,
            EventInstance.pax_count: count,
            EventInstance.fng_count: fng_count,
            EventInstance.meta: custom_fields,
            EventInstance.is_active: True,
            EventInstance.highlight: EventInstance.highlight,
        }
        DbManager.update_record(EventInstance, event_instance_id, fields=db_fields)
        DbManager.update_records(
            EventType_x_EventInstance,
            [EventType_x_EventInstance.event_instance_id == event_instance_id],
            fields={EventType_x_EventInstance.event_type_id: event_type},
        )  # TODO: handle multiple event types
    else:
        db_fields = {k.key: v for k, v in db_fields.items()}
        event = DbManager.create_record(EventInstance(**db_fields))
        event_instance_id = event.id
        DbManager.create_record(
            EventType_x_EventInstance(event_instance_id=event_instance_id, event_type_id=event_type)
        )

    attendance_types = [2 if u.slack_id == the_q else 3 if u.slack_id in (the_coq or []) else 1 for u in db_users]
    attendance_records = [
        Attendance(
            event_instance_id=event_instance_id,
            user_id=user.user_id,
            attendance_x_attendance_types=[Attendance_x_AttendanceType(attendance_type_id=attendance_type)],
            is_planned=False,
        )
        for user, attendance_type in zip(db_users, attendance_types)
    ]
    DbManager.create_records(attendance_records)
    print(
        json.dumps(
            {
                "event_type": "successful_db_insert",
                "team_name": region_record.workspace_name,
            }
        )
    )

    for file in file_send_list:
        try:
            os.remove(file["filepath"])
        except Exception as e:
            logger.error(f"Error removing file: {e}")


def handle_backblast_edit_button(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    channel_id = safe_get(body, "channel_id") or safe_get(body, "channel", "id")

    slack_user = get_user(user_id, region_record, client, logger)
    user_permissions = [p.name for p in get_user_permission_list(slack_user.user_id, region_record.org_id)]
    user_is_admin = constants.PERMISSIONS[constants.ALL_PERMISSIONS] in user_permissions

    backblast_data = safe_get(body, "message", "metadata", "event_payload") or json.loads(
        safe_get(body, "actions", 0, "value") or "{}"
    )

    if region_record.editing_locked == 1:
        allow_edit: bool = (
            user_is_admin
            or (user_id == backblast_data[actions.BACKBLAST_Q])
            or (user_id in backblast_data[actions.BACKBLAST_COQ] or [])
            or (user_id in backblast_data[actions.BACKBLAST_OP])
        )
    else:
        allow_edit = True

    if allow_edit:
        build_backblast_form(
            body=body,
            client=client,
            logger=logger,
            context=context,
            region_record=region_record,
        )
    else:
        client.chat_postEphemeral(
            text="Editing this backblast is only allowed for the Q(s), the original poster, or your local Slack admins."
            "Please contact one of them to make changes.",
            channel=channel_id,
            user=user_id,
        )
