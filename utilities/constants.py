import os

SLACK_BOT_TOKEN = "SLACK_BOT_TOKEN"
SLACK_STATE_S3_BUCKET_NAME = "ENV_SLACK_STATE_S3_BUCKET_NAME"
SLACK_INSTALLATION_S3_BUCKET_NAME = "ENV_SLACK_INSTALLATION_S3_BUCKET_NAME"
SLACK_CLIENT_ID = "ENV_SLACK_CLIENT_ID"
SLACK_CLIENT_SECRET = "ENV_SLACK_CLIENT_SECRET"
SLACK_SCOPES = "ENV_SLACK_SCOPES"
PASSWORD_ENCRYPT_KEY = "PASSWORD_ENCRYPT_KEY"
LOCAL_HOST_DOMAIN = "LOCAL_HOST_DOMAIN"

DATABASE_HOST = "DATABASE_HOST"
ADMIN_DATABASE_USER = "ADMIN_DATABASE_USER"
ADMIN_DATABASE_PASSWORD = "ADMIN_DATABASE_PASSWORD"
ADMIN_DATABASE_SCHEMA = "ADMIN_DATABASE_SCHEMA"
PAXMINER_DATABASE_HOST = "PAXMINER_DATABASE_HOST"
PAXMINER_DATABASE_USER = "PAXMINER_DATABASE_USER"
PAXMINER_DATABASE_PASSWORD = "PAXMINER_DATABASE_PASSWORD"
PAXMINER_DATABASE_SCHEMA = "PAXMINER_DATABASE_SCHEMA"
STRAVA_CLIENT_ID = "STRAVA_CLIENT_ID"
STRAVA_CLIENT_SECRET = "STRAVA_CLIENT_SECRET"

LOCAL_DEVELOPMENT = os.environ.get("LOCAL_DEVELOPMENT", "false").lower() == "true"

SLACK_STATE_S3_BUCKET_NAME = "ENV_SLACK_STATE_S3_BUCKET_NAME"
SLACK_INSTALLATION_S3_BUCKET_NAME = "ENV_SLACK_INSTALLATION_S3_BUCKET_NAME"
SLACK_CLIENT_ID = "ENV_SLACK_CLIENT_ID"
SLACK_CLIENT_SECRET = "ENV_SLACK_CLIENT_SECRET"
SLACK_SCOPES = "ENV_SLACK_SCOPES"

CONFIG_DESTINATION_AO = {"name": "The AO Channel", "value": "ao_channel"}
CONFIG_DESTINATION_CURRENT = {"name": "Current Channel", "value": "current_channel"}
CONFIG_DESTINATION_SPECIFIED = {"name": "Specified Channel:", "value": "specified_channel"}

DEFAULT_BACKBLAST_MOLESKINE_TEMPLATE = {
    "type": "rich_text",
    "elements": [
        {
            "type": "rich_text_section",
            "elements": [
                {
                    "type": "text",
                    "text": "\nWARMUP:",
                    "style": {"bold": True},
                },
                {
                    "type": "text",
                    "text": " \n",
                },
                {
                    "type": "text",
                    "text": "THE THANG:",
                    "style": {"bold": True},
                },
                {
                    "type": "text",
                    "text": " \n",
                },
                {
                    "type": "text",
                    "text": "MARY:",
                    "style": {"bold": True},
                },
                {
                    "type": "text",
                    "text": " \n",
                },
                {
                    "type": "text",
                    "text": "ANNOUNCEMENTS:",
                    "style": {"bold": True},
                },
                {
                    "type": "text",
                    "text": " \n",
                },
                {
                    "type": "text",
                    "text": "COT:",
                    "style": {"bold": True},
                },
                {
                    "type": "text",
                    "text": " ",
                },
            ],
        }
    ],
}

DEFAULT_PREBLAST_MOLESKINE_TEMPLATE = {
    "type": "rich_text",
    "elements": [
        {
            "type": "rich_text_section",
            "elements": [
                {
                    "type": "text",
                    "text": "\nWHAT:",
                    "style": {"bold": True},
                },
                {
                    "type": "text",
                    "text": " \n",
                },
                {
                    "type": "text",
                    "text": "WHY: ",
                    "style": {"bold": True},
                },
                {
                    "type": "text",
                    "text": " ",
                },
            ],
        }
    ],
}

STATE_METADATA = "STATE_METADATA"

AWS_ACCESS_KEY_ID = "AWS_ACCESS_KEY_ID"
AWS_SECRET_ACCESS_KEY = "AWS_SECRET_ACCESS_KEY"

WELCOME_MESSAGE_TEMPLATES = [
    "The man, the myth, the LEGEND, it's {user}! Welcome to {region}! We're glad you're here. Please take a moment to introduce yourself and let us know how we can help you get started. We're looking forward to seeing you in the gloom!",  # noqa: E501
    "Who's this?!? It's {user}! Welcome to {region}! We're glad you're here. Please take a moment to introduce yourself and let us know how we can help you get started. We're looking forward to seeing you in the gloom!",  # noqa: E501
    "Hey, it's {user}! Welcome to {region}, we're glad you're here. Please take a moment to introduce yourself and let us know how we can help you get started. We're looking forward to seeing you in the gloom!",  # noqa: E501
    "Sharkbait, ooh ha ha! It's {user}! Welcome to {region}, we're glad you're here. Please take a moment to introduce yourself and let us know how we can help you get started. We're looking forward to seeing you in the gloom!",  # noqa: E501
    "Could it be?!? It's {user}! Welcome to {region}, we're glad you're here. Please take a moment to introduce yourself and let us know how we can help you get started. We're looking forward to seeing you in the gloom!",  # noqa: E501
    "{user} is in the house! Welcome to {region}, we're glad you're here. Please take a moment to introduce yourself and let us know how we can help you get started. We're looking forward to seeing you in the gloom!",  # noqa: E501
]

MAX_HEIC_SIZE = 1000

ERROR_FORM_MESSAGE_TEMPLATE = ":warning: Sorry, the following error occurred:\n\n```{error}```"

PAXMINER_REPORT_DICT = {
    "send_pax_charts": "pax_charts",
    "send_ao_leaderboard": "ao_leaderboard",
    "send_q_charts": "q_charts",
    "send_region_leaderboard": "region_leaderboard",
    "send_region_stats": "region_stats",
}

FREQUENCY_OPTIONS = {
    "names": ["Week", "Month"],
    "values": ["Weekly", "Monthly"],
}
INTERVAL_OPTIONS = {
    "names": ["Every", "Every Other", "Every Third", "Every Fourth"],
    "values": ["1", "2", "3", "4"],
}

ORG_TYPES = {
    "AO": 1,
    "Region": 2,
    "Area": 3,
    "Sector": 4,
}

S3_IMAGE_URL = "https://slackblast-images.s3.amazonaws.com/{image_name}"
GCP_IMAGE_URL = "https://storage.googleapis.com/{bucket}/{image_name}"

# Define colors for event tags
# first is background color, second is text color
EVENT_TAG_COLORS = {
    "Red": ("#FF0000", "#FFFFFF"),
    "Orange": ("#FFA500", "#FFFFFF"),
    "Yellow": ("#FFFF00", "#000000"),
    "Green": ("#008000", "#FFFFFF"),
    "Blue": ("#0000FF", "#FFFFFF"),
    "Purple": ("#800080", "#FFFFFF"),
    "Pink": ("#FFC0CB", "#000000"),
    "Black": ("#000000", "#FFFFFF"),
    "White": ("#FFFFFF", "#000000"),
    "Gray": ("#808080", "#FFFFFF"),
    "Brown": ("#A52A2A", "#FFFFFF"),
    "Cyan": ("#00FFFF", "#000000"),
    "Magenta": ("#FF00FF", "#000000"),
    "Lime": ("#00FF00", "#000000"),
    "Teal": ("#008080", "#FFFFFF"),
    "Indigo": ("#4B0082", "#FFFFFF"),
    "Maroon": ("#800000", "#FFFFFF"),
    "Navy": ("#000080", "#FFFFFF"),
    "Olive": ("#808000", "#FFFFFF"),
    "Silver": ("#C0C0C0", "#000000"),
    "Sky": ("#87CEEB", "#000000"),
    "Gold": ("#FFD700", "#000000"),
    "Coral": ("#FF7F50", "#000000"),
    "Salmon": ("#FA8072", "#000000"),
    "Turquoise": ("#40E0D0", "#000000"),
    "Lavender": ("#E6E6FA", "#000000"),
    "Beige": ("#F5F5DC", "#000000"),
    "Mint": ("#98FF98", "#000000"),
    "Peach": ("#FFDAB9", "#000000"),
}

ALL_PERMISSIONS = "All"
PERMISSIONS = {
    ALL_PERMISSIONS: "All",
}
