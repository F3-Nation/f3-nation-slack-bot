import base64
import json

from flask import Request, Response

from scripts import calendar_images


def handle(request: Request) -> Response:
    decoded_data = request.data.decode()
    data_dict = json.loads(decoded_data)
    event_message = base64.b64decode(data_dict["message"]["data"]).decode()
    try:
        if event_message == "hourly":
            calendar_images.generate_calendar_images()
            return Response("Calendar images generated", status=200)
    except Exception as e:
        print(f"Error generating calendar images: {e}")
        return Response(f"Error: {e}", status=200)
