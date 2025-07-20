import base64
import json

from flask import Request, Response

from features import canvas
from scripts import (
    auto_preblast_send,
    backblast_reminders,
    calendar_images,
    preblast_reminders,
    q_lineups,
    update_slack_users,
)


def handle(request: Request) -> Response:
    decoded_data = request.data.decode()
    data_dict = json.loads(decoded_data)
    event_message = base64.b64decode(data_dict["message"]["data"]).decode()

    try:
        if event_message == "hourly":
            print("Running hourly scripts")
            print("Running calendar images")
            try:
                calendar_images.generate_calendar_images()
            except Exception as e:
                print(f"Error generating calendar images: {e}")
            print("Running backblast reminders")
            try:
                backblast_reminders.send_backblast_reminders()
            except Exception as e:
                print(f"Error sending backblast reminders: {e}")
            print("Running preblast reminders")
            try:
                preblast_reminders.send_preblast_reminders()
            except Exception as e:
                print(f"Error sending preblast reminders: {e}")
            preblast_reminders.send_preblast_reminders()
            print("Running automated preblast send")
            try:
                auto_preblast_send.send_automated_preblasts()
            except Exception as e:
                print(f"Error sending automated preblasts: {e}")
            # update_special_events.update_special_events()
            print("Running canvas updates")
            try:
                canvas.update_all_canvases()
            except Exception as e:
                print(f"Error updating canvases: {e}")
            print("Running Q lineups")
            try:
                q_lineups.send_lineups()
            except Exception as e:
                print(f"Error sending Q lineups: {e}")
            try:
                update_slack_users.update_slack_users()
            except Exception as e:
                print(f"Error updating Slack users: {e}")
            return Response("Hourly scripts complete", status=200)
        else:
            return Response(f"Event message not used: {event_message}", status=200)
    except Exception as e:
        print(f"Error running scripts: {e}")
        return Response(f"Error: {e}", status=200)
