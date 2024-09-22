# import json
import base64
import json
import logging
import re
import traceback
from typing import Callable, Tuple

import functions_framework
from flask import Request, Response
from google.cloud.logging.handlers import CloudLoggingHandler
from google.cloud.logging_v2.handlers import setup_logging
from slack_bolt import App
from slack_bolt.adapter.google_cloud_functions import SlackRequestHandler

from features import strava
from utilities.builders import add_loading_form, send_error_response
from utilities.constants import LOCAL_DEVELOPMENT
from utilities.database.orm import SlackSettings
from utilities.helper_functions import (
    # get_oauth_flow,
    get_region_record,
    get_request_type,
    safe_get,
    update_local_region_records,
)
from utilities.routing import MAIN_MAPPER
from utilities.slack.actions import LOADING_ID

# SlackRequestHandler.clear_all_log_handlers()
logger = logging.getLogger()
logger.setLevel(logging.INFO)
if LOCAL_DEVELOPMENT:
    handler = logging.StreamHandler()
    logger.addHandler(handler)
else:
    handler = CloudLoggingHandler()
    setup_logging(handler)
    logger.addHandler(handler)

app = App(
    process_before_response=not LOCAL_DEVELOPMENT,
    # process_before_response=not LOCAL_DEVELOPMENT,
    # oauth_flow=get_oauth_flow(),
    # oauth_settings=SlackSettings,
)


def gcp_event_handler(request: Request):
    decoded_data = request.data.decode()
    data_dict = json.loads(decoded_data)
    event_message = base64.b64decode(data_dict["message"]["data"]).decode()
    print(event_message)
    return Response("Event received", status=200)


@functions_framework.http
def handler(request: Request):
    if request.path == "/":
        return Response("Service is running", status=200)
    elif request.path == "/gcp_event":
        gcp_event_handler(request)
    elif request.path == "/exchange_token":
        return strava.strava_exchange_token(request)
    elif request.path == "/slack/events":
        slack_handler = SlackRequestHandler(app=app)
        return slack_handler.handle(request)


def main_response(body, logger, client, ack, context):
    ack()
    if LOCAL_DEVELOPMENT:
        logger.info(json.dumps(body, indent=4))
    else:
        logger.info(body)
    team_id = safe_get(body, "team_id") or safe_get(body, "team", "id")
    region_record: SlackSettings = get_region_record(team_id, body, context, client, logger)

    request_type, request_id = get_request_type(body)
    lookup: Tuple[Callable, bool] = safe_get(safe_get(MAIN_MAPPER, request_type), request_id)
    if lookup:
        run_function, add_loading = lookup
        if add_loading:
            body[LOADING_ID] = add_loading_form(body=body, client=client)
        try:
            run_function(
                body=body,
                client=client,
                logger=logger,
                context=context,
                region_record=region_record,
            )
        except Exception as exc:
            logger.info("sending error response")
            tb_str = "".join(traceback.format_exception(None, exc, exc.__traceback__))
            send_error_response(body=body, client=client, error=str(exc)[:3000])
            logger.error(tb_str)
    else:
        logger.error(
            f"no handler for path: "
            f"{safe_get(safe_get(MAIN_MAPPER, request_type), request_id) or request_type+', '+request_id}"
        )


ARGS = [main_response]
LAZY_KWARGS = {}

# if LOCAL_DEVELOPMENT:
#     ARGS = [main_response]
#     LAZY_KWARGS = {}
# else:
#     ARGS = []
#     LAZY_KWARGS = {
#         "ack": lambda ack: ack(),
#         "lazy": [main_response],
#     }


MATCH_ALL_PATTERN = re.compile(".*")
app.action(MATCH_ALL_PATTERN)(*ARGS, **LAZY_KWARGS)
app.view(MATCH_ALL_PATTERN)(*ARGS, **LAZY_KWARGS)
app.command(MATCH_ALL_PATTERN)(*ARGS, **LAZY_KWARGS)
app.view_closed(MATCH_ALL_PATTERN)(*ARGS, **LAZY_KWARGS)
app.event(MATCH_ALL_PATTERN)(*ARGS, **LAZY_KWARGS)

if __name__ == "__main__":
    port = 3000 if LOCAL_DEVELOPMENT else 8080
    app.start(port=port)
    update_local_region_records()
