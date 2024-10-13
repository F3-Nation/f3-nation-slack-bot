import base64
import json

from flask import Request, Response

from scripts import backblast_reminders, calendar_images, preblast_reminders, update_special_events


def handle(request: Request) -> Response:
    decoded_data = request.data.decode()
    data_dict = json.loads(decoded_data)
    event_message = base64.b64decode(data_dict["message"]["data"]).decode()
    print(f"Event message: {event_message}")
    try:
        if event_message == "hourly":
            print("Running hourly scripts")
            calendar_images.generate_calendar_images()
            return Response("Hourly scripts complete", status=200)
        elif event_message == "daily":
            backblast_reminders.send_backblast_reminders()
            preblast_reminders.send_preblast_reminders()
            update_special_events.update_special_events()
            return Response("Daily scripts complete", status=200)
        else:
            return Response(f"Event message not used: {event_message}", status=200)
    except Exception as e:
        print(f"Error running scripts: {e}")
        return Response(f"Error: {e}", status=200)
