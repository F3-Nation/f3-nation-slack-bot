import base64
import json

from flask import Request, Response

from features import canvas
from scripts import auto_preblast_send, backblast_reminders, calendar_images, preblast_reminders, q_lineups


def handle(request: Request) -> Response:
    decoded_data = request.data.decode()
    data_dict = json.loads(decoded_data)
    event_message = base64.b64decode(data_dict["message"]["data"]).decode()

    try:
        if event_message == "hourly":
            print("Running hourly scripts")
            print("Running calendar images")
            calendar_images.generate_calendar_images()
            print("Running backblast reminders")
            backblast_reminders.send_backblast_reminders()
            print("Running preblast reminders")
            preblast_reminders.send_preblast_reminders()
            print("Running automated preblast send")
            auto_preblast_send.send_automated_preblasts()
            # update_special_events.update_special_events()
            print("Running canvas updates")
            canvas.update_all_canvases()
            print("Running Q lineups")
            q_lineups.send_lineups()
            return Response("Hourly scripts complete", status=200)
        else:
            return Response(f"Event message not used: {event_message}", status=200)
    except Exception as e:
        print(f"Error running scripts: {e}")
        return Response(f"Error: {e}", status=200)
