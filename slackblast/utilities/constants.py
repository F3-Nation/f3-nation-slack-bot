import os

SLACK_BOT_TOKEN = "SLACK_BOT_TOKEN"
SLACK_STATE_S3_BUCKET_NAME = "ENV_SLACK_STATE_S3_BUCKET_NAME"
SLACK_INSTALLATION_S3_BUCKET_NAME = "ENV_SLACK_INSTALLATION_S3_BUCKET_NAME"
SLACK_CLIENT_ID = "ENV_SLACK_CLIENT_ID"
SLACK_CLIENT_SECRET = "ENV_SLACK_CLIENT_SECRET"
SLACK_SCOPES = "ENV_SLACK_SCOPES"
PASSWORD_ENCRYPT_KEY = "PASSWORD_ENCRYPT_KEY"

DATABASE_HOST = "DATABASE_HOST"
ADMIN_DATABASE_USER = "ADMIN_DATABASE_USER"
ADMIN_DATABASE_PASSWORD = "ADMIN_DATABASE_PASSWORD"
ADMIN_DATABASE_SCHEMA = "ADMIN_DATABASE_SCHEMA"
STRAVA_CLIENT_ID = "STRAVA_CLIENT_ID"
STRAVA_CLIENT_SECRET = "STRAVA_CLIENT_SECRET"

LOCAL_DEVELOPMENT = os.environ.get(SLACK_BOT_TOKEN, "123") != "123"

SLACK_STATE_S3_BUCKET_NAME = "ENV_SLACK_STATE_S3_BUCKET_NAME"
SLACK_INSTALLATION_S3_BUCKET_NAME = "ENV_SLACK_INSTALLATION_S3_BUCKET_NAME"
SLACK_CLIENT_ID = "ENV_SLACK_CLIENT_ID"
SLACK_CLIENT_SECRET = "ENV_SLACK_CLIENT_SECRET"
SLACK_SCOPES = "ENV_SLACK_SCOPES"

CONFIG_DESTINATION_AO = {"name": "The AO Channel", "value": "ao_channel"}
CONFIG_DESTINATION_CURRENT = {"name": "Current Channel", "value": "current_channel"}

DEFAULT_BACKBLAST_MOLESKINE_TEMPLATE = "\n*WARMUP:* \n*THE THANG:* \n*MARY:* \n*ANNOUNCEMENTS:* \n*COT:* "

STATE_METADATA = "STATE_METADATA"

AWS_ACCESS_KEY_ID = "AWS_ACCESS_KEY_ID"
AWS_SECRET_ACCESS_KEY = "AWS_SECRET_ACCESS_KEY"

MAX_HEIC_SIZE = 1000
