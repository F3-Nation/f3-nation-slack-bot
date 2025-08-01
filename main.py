# import json
import json
import logging
import re
import time
import traceback
from typing import Callable, Tuple

import functions_framework
from flask import Request, Response
from google.cloud.logging_v2.handlers import StructuredLogHandler, setup_logging
from slack_bolt import App
from slack_bolt.adapter.google_cloud_functions import SlackRequestHandler

import scripts
from features import strava
from features.calendar import series
from utilities.builders import add_loading_form, send_error_response
from utilities.constants import LOCAL_DEVELOPMENT
from utilities.database.orm import SlackSettings
from utilities.helper_functions import (
    get_oauth_settings,
    get_region_record,
    get_request_type,
    safe_get,
    update_local_region_records,
)
from utilities.routing import MAIN_MAPPER
from utilities.slack.actions import LOADING_ID

logging_level = logging.INFO
if LOCAL_DEVELOPMENT:
    logger = logging.getLogger()
    logger.setLevel(logging_level)
    handler = logging.StreamHandler()
    logger.addHandler(handler)
else:
    handler = StructuredLogHandler()
    setup_logging(handler, log_level=logging_level)


app = App(
    process_before_response=not LOCAL_DEVELOPMENT,
    oauth_settings=get_oauth_settings(),
)


@functions_framework.http
def handler(request: Request):
    if request.path == "/":
        return Response("Service is running", status=200)
    elif request.path == "/gcp_event":
        logging.info("GCP Event")
        return scripts.handle(request)
    elif request.path == "/exchange_token":
        return strava.strava_exchange_token(request)
    elif request.path[:6] == "/slack":
        slack_handler = SlackRequestHandler(app=app)
        return slack_handler.handle(request)
    elif request.path == "/map-update":
        return series.update_from_map(request)
    else:
        return Response(f"Invalid path: {request.path}", status=404)


def main_response(body, logger: logging.Logger, client, ack, context):
    # ack()
    if LOCAL_DEVELOPMENT:
        logger.info(json.dumps(body, indent=4))
    else:
        logger.info(body)
    team_id = safe_get(body, "team_id") or safe_get(body, "team", "id")
    try:
        region_record: SlackSettings = get_region_record(team_id, body, context, client, logger)
    except Exception as exc:
        logger.warning(f"Error getting region record: {exc}")
        region_record = SlackSettings(team_id="T00000000")

    request_type, request_id = get_request_type(body)
    lookup: Tuple[Callable, bool] = safe_get(safe_get(MAIN_MAPPER, request_type), request_id)
    if lookup:
        run_function, add_loading = lookup
        if add_loading:
            body[LOADING_ID] = add_loading_form(body=body, client=client)
        try:
            # time the call
            start_time = time.time()
            resp = run_function(
                body=body,
                client=client,
                logger=logger,
                context=context,
                region_record=region_record,
            )
            if resp and request_type == "block_suggestion":
                ack(options=resp)
            else:
                ack()
            end_time = time.time()
            logger.info(f"Function {run_function.__name__} took {end_time - start_time:.2f} seconds to run.")
        except Exception as exc:
            tb_str = "".join(traceback.format_exception(None, exc, exc.__traceback__))
            send_error_response(body=body, client=client, error=str(exc)[:3000])
            logger.error(tb_str)
    else:
        logger.warning(
            f"no handler for path: "
            f"{safe_get(safe_get(MAIN_MAPPER, request_type), request_id) or request_type + ', ' + request_id}"
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
app.options(MATCH_ALL_PATTERN)(*ARGS, **LAZY_KWARGS)
app.shortcut(MATCH_ALL_PATTERN)(*ARGS, **LAZY_KWARGS)

if __name__ == "__main__":
    port = 3000 if LOCAL_DEVELOPMENT else 8080
    app.start(port=port)
    update_local_region_records()