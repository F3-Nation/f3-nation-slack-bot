import base64
import json

from flask import Request, Response

from scripts import calendar_images


def handle(request: Request) -> Response:
    decoded_data = request.data.decode()
    data_dict = json.loads(decoded_data)
    event_message = base64.b64decode(data_dict["message"]["data"]).decode()
    if event_message == "hourly":
        calendar_images.generate_calendar_images()
    return Response("Event received", status=200)
