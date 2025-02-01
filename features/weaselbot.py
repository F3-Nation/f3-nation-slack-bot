import copy
from datetime import datetime
from logging import Logger

import pytz
from f3_data_models.models import (
    Achievement,
    Achievement_x_Org,
    Achievement_x_User,
    SlackSpace,
)
from f3_data_models.utils import DbManager
from slack_sdk.web import WebClient
from sqlalchemy.exc import ProgrammingError

from utilities.database.orm import SlackSettings
from utilities.helper_functions import (
    get_user,
    safe_convert,
    safe_get,
    update_local_region_records,
)
from utilities.slack import actions, forms
from utilities.slack import orm as slack_orm


def build_achievement_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    update_view_id = safe_get(body, actions.LOADING_ID)
    achievement_form = copy.deepcopy(forms.ACHIEVEMENT_FORM)
    callback_id = actions.ACHIEVEMENT_CALLBACK_ID

    # build achievement list
    achievement_list = []
    # gather achievements from paxminer
    achievement_list = DbManager.find_join_records2(
        Achievement, Achievement_x_Org, [Achievement_x_Org.org_id == region_record.org_id]
    )
    achievement_list: list[Achievement] = [a[0] for a in achievement_list]

    if achievement_list:
        achievement_list = slack_orm.as_selector_options(
            names=[achievement.name for achievement in achievement_list],
            values=[str(achievement.id) for achievement in achievement_list],
            descriptions=[achievement.description for achievement in achievement_list],
        )
    else:
        achievement_list = slack_orm.as_selector_options(
            names=["No achievements available"],
            values=["None"],
        )

    achievement_form.set_initial_values(
        {
            actions.ACHIEVEMENT_DATE: datetime.now(pytz.timezone("US/Central")).strftime("%Y-%m-%d"),
        }
    )
    achievement_form.set_options(
        {
            actions.ACHIEVEMENT_SELECT: achievement_list,
        }
    )

    achievement_form.update_modal(
        client=client,
        view_id=update_view_id,
        callback_id=callback_id,
        title_text="Tag achievements",
    )


def handle_achievements_tag(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    achievement_data = forms.ACHIEVEMENT_FORM.get_selected_values(body)
    achievement_pax_list = safe_get(achievement_data, actions.ACHIEVEMENT_PAX)
    achievement_pax_list = [get_user(pax, region_record, client, logger).user_id for pax in achievement_pax_list]
    achievement_id = safe_convert(safe_get(achievement_data, actions.ACHIEVEMENT_SELECT), int)
    achievement_date = datetime.strptime(safe_get(achievement_data, actions.ACHIEVEMENT_DATE), "%Y-%m-%d")

    achievement_info: Achievement = DbManager.get(Achievement, achievement_id)
    achievement_name = achievement_info.name
    achievement_verb = achievement_info.verb

    # Get all achievements for the year
    pax_awards: list[Achievement_x_User] = DbManager.find_records(
        Achievement_x_User,
        filters=[
            Achievement_x_User.user_id.in_(achievement_pax_list),
            Achievement_x_User.date_awarded >= datetime(achievement_date.year, 1, 1),
            Achievement_x_User.date_awarded <= datetime(achievement_date.year, 12, 31),
        ],
    )
    pax_awards_total = {}
    pax_awards_this_achievement = {}
    for pax in achievement_pax_list:
        pax_awards_total[pax] = 0
        pax_awards_this_achievement[pax] = 0
    for award in pax_awards:
        pax_awards_total[award.user_id] += 1
        if award.achievement_id == achievement_id:
            pax_awards_this_achievement[award.user_id] += 1

    for pax in achievement_pax_list:
        msg = f"Congrats to our man <@{pax}>! He has achieved *{achievement_name}* for {achievement_verb}!"
        msg += f" This is achievement #{pax_awards_total[pax] + 1} for him this year"
        if pax_awards_this_achievement[pax] > 0:
            msg += f" and #{pax_awards_this_achievement[pax] + 1} time this year for this achievement."
        else:
            msg += "."
        client.chat_postMessage(channel=region_record.achievement_channel, text=msg)
        DbManager.create_record(
            Achievement_x_User(
                user_id=pax,
                date_awarded=achievement_date,
                achievement_id=achievement_id,
            ),
        )


def build_config_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    # paxminer_schema = region_record.paxminer_schema
    # update_view_id = safe_get(body, actions.LOADING_ID)
    config_form = copy.deepcopy(forms.WEASELBOT_CONFIG_FORM)
    callback_id = actions.WEASELBOT_CONFIG_CALLBACK_ID
    trigger_id = safe_get(body, "trigger_id")

    try:
        weaselbot_achievements = DbManager.find_join_records2(
            Achievement,
            Achievement_x_Org,
            [Achievement_x_Org.org_id == region_record.org_id],
        )
        weaselbot_achievements = [a[0] for a in weaselbot_achievements]
    except ProgrammingError:
        weaselbot_achievements = None

    if not weaselbot_achievements:
        config_form = copy.deepcopy(forms.NO_WEASELBOT_CONFIG_FORM)
        config_form.post_modal(
            client=client,
            trigger_id=trigger_id,
            callback_id=callback_id,
            new_or_add="add",
            title_text="Achievement Settings",
            submit_button_text="None",
        )
    else:
        initial_features = []
        if region_record.send_achievements:
            initial_features.append("achievements")
        if region_record.send_aoq_reports:
            initial_features.append("kotter_reports")

        config_form.set_initial_values(
            {
                actions.WEASELBOT_ENABLE_FEATURES: initial_features,
                actions.WEASELBOT_ACHIEVEMENT_CHANNEL: region_record.achievement_channel,
                actions.WEASELBOT_KOTTER_CHANNEL: region_record.default_siteq,
                actions.WEASELBOT_KOTTER_WEEKS: region_record.NO_POST_THRESHOLD,
                actions.WEASELBOT_KOTTER_REMOVE_WEEKS: region_record.REMINDER_WEEKS,
                actions.WEASELBOT_HOME_AO_WEEKS: region_record.HOME_AO_CAPTURE,
                actions.WEASELBOT_Q_WEEKS: region_record.NO_Q_THRESHOLD_WEEKS,
                actions.WEASELBOT_Q_POSTS: region_record.NO_Q_THRESHOLD_POSTS,
            }
        )

        config_form.post_modal(
            client=client,
            trigger_id=trigger_id,
            callback_id=callback_id,
            new_or_add="add",
            title_text="Achievement Settings",
        )


def handle_config_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    config_data = forms.WEASELBOT_CONFIG_FORM.get_selected_values(body)

    region_record.send_achievements = (
        1 if "achievements" in safe_get(config_data, actions.WEASELBOT_ENABLE_FEATURES) else 0
    )
    region_record.send_aoq_reports = (
        1 if "kotter_reports" in safe_get(config_data, actions.WEASELBOT_ENABLE_FEATURES) else 0
    )
    region_record.achievement_channel = safe_get(config_data, actions.WEASELBOT_ACHIEVEMENT_CHANNEL)
    region_record.default_siteq = safe_get(config_data, actions.WEASELBOT_KOTTER_CHANNEL)
    region_record.NO_POST_THRESHOLD = safe_get(config_data, actions.WEASELBOT_KOTTER_WEEKS)
    region_record.REMINDER_WEEKS = safe_get(config_data, actions.WEASELBOT_KOTTER_REMOVE_WEEKS)
    region_record.HOME_AO_CAPTURE = safe_get(config_data, actions.WEASELBOT_HOME_AO_WEEKS)
    region_record.NO_Q_THRESHOLD_WEEKS = safe_get(config_data, actions.WEASELBOT_Q_WEEKS)
    region_record.NO_Q_THRESHOLD_POSTS = safe_get(config_data, actions.WEASELBOT_Q_POSTS)

    DbManager.update_record(SlackSpace, region_record.team_id, fields={SlackSpace.settings: region_record.__dict__})
    update_local_region_records()
