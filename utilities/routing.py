from features import (
    backblast,
    canvas,
    config,
    connect,
    custom_fields,
    db_admin,
    preblast,
    region,
    special_events,
    strava,
    weaselbot,
    welcome,
)
from features.calendar import ao, event_preblast, event_type, home, location, series
from features.calendar import config as calendar_config
from utilities import announcements, builders
from utilities.slack import actions

# Required arguments for handler functions:
#     body: dict
#     client: WebClient
#     logger: Logger
#     context: dict

# The mappers define the function to be called for each event
# The boolean value indicates whether a loading modal should be triggered before running the function

global COMMAND_MAPPER, VIEW_MAPPER, ACTION_MAPPER, VIEW_CLOSED_MAPPER, EVENT_MAPPER, MAIN_MAPPER

COMMAND_MAPPER = {
    "/backblast": (backblast.backblast_middleware, True),
    "/preblast": (event_preblast.build_event_preblast_select_form, True),
    "/f3-nation-settings": (config.build_config_form, True),
    "/tag-achievement": (weaselbot.build_achievement_form, True),
    "/send-announcement": (announcements.send, False),
    "/calendar": (home.build_home_form, True),
}

VIEW_MAPPER = {
    actions.BACKBLAST_CALLBACK_ID: (backblast.handle_backblast_post, False),
    actions.BACKBLAST_EDIT_CALLBACK_ID: (backblast.handle_backblast_post, False),
    actions.PREBLAST_CALLBACK_ID: (preblast.handle_preblast_post, False),
    actions.PREBLAST_EDIT_CALLBACK_ID: (preblast.handle_preblast_post, False),
    actions.WELCOME_MESSAGE_CONFIG_CALLBACK_ID: (welcome.handle_welcome_message_config_post, False),
    actions.CONFIG_GENERAL_CALLBACK_ID: (config.handle_config_general_post, False),
    actions.CONFIG_EMAIL_CALLBACK_ID: (config.handle_config_email_post, False),
    actions.STRAVA_MODIFY_CALLBACK_ID: (strava.handle_strava_modify, False),
    actions.CUSTOM_FIELD_ADD_CALLBACK_ID: (custom_fields.handle_custom_field_add, False),
    actions.CUSTOM_FIELD_MENU_CALLBACK_ID: (custom_fields.handle_custom_field_menu, False),
    actions.ACHIEVEMENT_CALLBACK_ID: (weaselbot.handle_achievements_tag, False),
    actions.WEASELBOT_CONFIG_CALLBACK_ID: (weaselbot.handle_config_form, False),
    actions.ADD_LOCATION_CALLBACK_ID: (location.handle_location_add, False),
    actions.ADD_AO_CALLBACK_ID: (ao.handle_ao_add, False),
    actions.ADD_SERIES_CALLBACK_ID: (series.handle_series_add, False),
    actions.EVENT_PREBLAST_CALLBACK_ID: (event_preblast.handle_event_preblast_edit, False),
    actions.CALENDAR_ADD_EVENT_TYPE_CALLBACK_ID: (event_type.handle_event_type_add, False),
    actions.EVENT_PREBLAST_POST_CALLBACK_ID: (event_preblast.handle_event_preblast_edit, False),
    actions.REGION_CALLBACK_ID: (region.handle_region_edit, False),
    actions.SPECIAL_EVENTS_CALLBACK_ID: (special_events.handle_special_settings_edit, False),
    actions.CONFIG_SLT_CALLBACK_ID: (config.handle_config_slt_post, False),
    actions.NEW_POSITION_CALLBACK_ID: (config.handle_new_position_post, False),
    connect.CONNECT_EXISTING_REGION_CALLBACK_ID: (connect.handle_existing_region_selection, False),
    connect.CREATE_NEW_REGION_CALLBACK_ID: (connect.handle_new_region_creation, False),
}

ACTION_MAPPER = {
    actions.BACKBLAST_EDIT_BUTTON: (backblast.handle_backblast_edit_button, True),
    actions.BACKBLAST_NEW_BUTTON: (backblast.backblast_middleware, True),
    actions.BACKBLAST_STRAVA_BUTTON: (strava.build_strava_form, True),
    actions.STRAVA_ACTIVITY_BUTTON: (strava.build_strava_modify_form, False),
    actions.STRAVA_CONNECT_BUTTON: (builders.ignore_event, False),
    actions.CONFIG_CUSTOM_FIELDS: (custom_fields.build_custom_field_menu, False),
    actions.CUSTOM_FIELD_ADD: (custom_fields.build_custom_field_add_edit, False),
    actions.CUSTOM_FIELD_EDIT: (custom_fields.build_custom_field_add_edit, False),
    actions.CUSTOM_FIELD_DELETE: (custom_fields.delete_custom_field, False),
    actions.PREBLAST_NEW_BUTTON: (preblast.build_preblast_form, True),
    actions.PREBLAST_EDIT_BUTTON: (preblast.handle_preblast_edit_button, True),
    actions.CONFIG_WEASELBOT: (weaselbot.build_config_form, False),
    actions.CONFIG_WELCOME_MESSAGE: (welcome.build_welcome_message_form, False),
    actions.CONFIG_EMAIL: (config.build_config_email_form, False),
    actions.CONFIG_GENERAL: (config.build_config_general_form, False),
    actions.CONFIG_WELCOME_MESSAGE: (welcome.build_welcome_config_form, False),
    actions.CONFIG_CALENDAR: (calendar_config.build_calendar_config_form, False),
    actions.CALENDAR_ADD_SERIES_AO: (series.build_series_add_form, False),
    actions.SERIES_EDIT_DELETE: (series.handle_series_edit_delete, False),
    actions.LOCATION_EDIT_DELETE: (location.handle_location_edit_delete, False),
    actions.AO_EDIT_DELETE: (ao.handle_ao_edit_delete, False),
    actions.CALENDAR_ADD_EVENT_AO: (series.build_series_add_form, False),
    actions.CALENDAR_MANAGE_LOCATIONS: (location.manage_locations, False),
    actions.CALENDAR_MANAGE_AOS: (ao.manage_aos, False),
    actions.CALENDAR_MANAGE_SERIES: (series.manage_series, False),
    actions.CALENDAR_MANAGE_EVENTS: (series.manage_series, False),
    actions.CALENDAR_MANAGE_EVENT_TYPES: (event_type.build_event_type_form, False),
    actions.CALENDAR_ADD_AO_NEW_LOCATION: (location.build_location_add_form, False),
    actions.CALENDAR_HOME_EVENT: (home.handle_home_event, False),
    actions.CALENDAR_HOME_AO_FILTER: (home.build_home_form, False),
    actions.CALENDAR_HOME_Q_FILTER: (home.build_home_form, False),
    actions.CALENDAR_HOME_DATE_FILTER: (home.build_home_form, False),
    actions.CALENDAR_HOME_EVENT_TYPE_FILTER: (home.build_home_form, False),
    actions.EVENT_PREBLAST_HC: (event_preblast.handle_event_preblast_action, False),
    actions.EVENT_PREBLAST_UN_HC: (event_preblast.handle_event_preblast_action, False),
    actions.EVENT_PREBLAST_TAKE_Q: (event_preblast.handle_event_preblast_action, False),
    actions.EVENT_PREBLAST_REMOVE_Q: (event_preblast.handle_event_preblast_action, False),
    actions.EVENT_PREBLAST_HC_UN_HC: (event_preblast.handle_event_preblast_action, False),
    actions.EVENT_PREBLAST_EDIT: (event_preblast.handle_event_preblast_action, False),
    actions.EVENT_PREBLAST_SELECT: (event_preblast.handle_event_preblast_select, False),
    actions.EVENT_PREBLAST_NEW_BUTTON: (home.handle_event_preblast_select_button, False),
    actions.OPEN_CALENDAR_BUTTON: (home.handle_event_preblast_select_button, False),
    actions.MSG_EVENT_PREBLAST_BUTTON: (event_preblast.handle_event_preblast_action, False),
    actions.MSG_EVENT_BACKBLAST_BUTTON: (backblast.build_backblast_form, False),
    actions.BACKBLAST_FILL_SELECT: (backblast.build_backblast_form, False),
    actions.BACKBLAST_NEW_BLANK_BUTTON: (backblast.build_backblast_form, False),
    actions.REGION_INFO_BUTTON: (region.build_region_form, False),
    actions.CONFIG_SPECIAL_EVENTS: (special_events.build_special_settings_form, False),
    actions.DB_ADMIN_UPGRADE: (db_admin.handle_db_admin_upgrade, False),
    actions.DB_ADMIN_RESET: (db_admin.handle_db_admin_reset, False),
    actions.SECRET_MENU_CALENDAR_IMAGES: (db_admin.handle_calendar_image_refresh, False),
    actions.SECRET_MENU_PAXMINER_MIGRATION: (db_admin.handle_paxminer_migration, False),
    actions.CONFIG_SLT: (config.build_config_slt_form, False),
    actions.SLT_LEVEL_SELECT: (config.build_config_slt_form, False),
    actions.CONFIG_NEW_POSITION: (config.build_new_position_form, False),
    actions.SECRET_MENU_PAXMINER_MIGRATION_ALL: (db_admin.handle_paxminer_migration_all, False),
    actions.CONFIG_CONNECT: (connect.build_connect_options_form, False),
    connect.CONNECT_EXISTING_REGION: (connect.build_existing_region_form, False),
    connect.CREATE_NEW_REGION: (connect.build_new_region_form, False),
    actions.SECRET_MENU_UPDATE_CANVAS: (canvas.update_canvas, False),
    actions.SECRET_MENU_MAKE_ADMIN: (db_admin.handle_make_admin, False),
}

VIEW_CLOSED_MAPPER = {
    actions.CUSTOM_FIELD_ADD_FORM: (builders.ignore_event, False),
    actions.STRAVA_MODIFY_CALLBACK_ID: (strava.handle_strava_modify, False),
}

EVENT_MAPPER = {
    "team_join": (welcome.handle_team_join, False),
}

MAIN_MAPPER = {
    "command": COMMAND_MAPPER,
    "block_actions": ACTION_MAPPER,
    "view_submission": VIEW_MAPPER,
    "view_closed": VIEW_CLOSED_MAPPER,
    "event_callback": EVENT_MAPPER,
}
