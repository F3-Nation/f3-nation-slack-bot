import os
import sys
from typing import List

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import random
from datetime import datetime, timedelta

import boto3
import pytz
from f3_data_models.models import (
    Attendance,
    Attendance_x_AttendanceType,
    AttendanceType,
    EventInstance,
    EventTag,
    EventTag_x_EventInstance,
    EventType,
    EventType_x_EventInstance,
    Org,
    Org_Type,
    Org_x_SlackSpace,
    SlackSpace,
    User,
)

# import dataframe_image as dfi
from f3_data_models.utils import DbManager, get_session
from slack_sdk import WebClient
from slack_sdk.models import blocks
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import aliased, joinedload

from utilities.constants import EVENT_TAG_COLORS, GCP_IMAGE_URL, LOCAL_DEVELOPMENT, S3_IMAGE_URL
from utilities.helper_functions import current_date_cst, safe_get, update_local_region_records
from utilities.slack import actions


def time_int_to_str(time: int) -> str:
    return f"{time // 100:02d}{time % 100:02d}"


def highlight_cells(s, color_dict):
    import pandas as pd

    highlight_cells_list = []
    for cell in s:
        cell_str = str(cell)
        tags = cell_str.split("\n")
        found = False
        if tags:
            for tag in tags:
                if tag in color_dict.keys():
                    highlight_cells_list.append(f"background-color: {EVENT_TAG_COLORS[color_dict[tag]][0]}")
                    found = True
                    break
        if not found:
            highlight_cells_list.append("background-color: #000000")
    return pd.Series(highlight_cells_list)


def set_text_color(s, color_dict):
    text_color_list = []
    for cell in s:
        cell_str = str(cell)
        tags = cell_str.split("\n")
        found = False
        if tags:
            for tag in tags:
                if tag in color_dict.keys():
                    text_color_list.append(f"color: {EVENT_TAG_COLORS[color_dict[tag]][1]}")
                    found = True
                    break
        if not found:
            text_color_list.append("color: #F0FFFF")
    return text_color_list


def generate_calendar_images(force: bool = False):
    import dataframe_image as dfi
    import pandas as pd

    with get_session() as session:
        tomorrow_day_of_week = (current_date_cst() + timedelta(days=1)).weekday()
        current_week_start = current_date_cst() + timedelta(days=-tomorrow_day_of_week + 1)
        current_week_end = current_date_cst() + timedelta(days=7 - tomorrow_day_of_week + 1)
        next_week_start = current_week_start + timedelta(weeks=1)
        next_week_end = current_week_end + timedelta(weeks=1)

        firstq_subquery = (
            select(
                Attendance.event_instance_id,
                User.f3_name.label("q_name"),
                func.row_number()
                .over(partition_by=Attendance.event_instance_id, order_by=Attendance.created)
                .label("rn"),
            )
            .select_from(Attendance)
            .join(Attendance_x_AttendanceType, Attendance.id == Attendance_x_AttendanceType.attendance_id)
            .join(Attendance.user)
            .filter(Attendance_x_AttendanceType.attendance_type_id == 2)
            .alias()
        )

        attendance_subquery = (
            select(
                Attendance.event_instance_id,
                func.max(
                    case(
                        (Attendance.attendance_types.any(AttendanceType.id == 2), Attendance.updated),
                    )
                ).label("q_last_updated"),
            )
            .select_from(Attendance)
            .options(joinedload(Attendance.attendance_types))
            .group_by(Attendance.event_instance_id)
            .alias()
        )

        RegionOrg = aliased(Org)

        query = (
            session.query(
                EventInstance.start_date,
                EventInstance.start_time,
                EventInstance.updated.label("event_updated"),
                EventInstance.pax_count,
                EventTag.name.label("event_tag"),
                EventTag.color.label("event_tag_color"),
                EventType.name.label("event_type"),
                EventType.acronym.label("event_acronym"),
                Org.name.label("ao_name"),
                Org.description.label("ao_description"),
                Org.parent_id.label("ao_parent_id"),
                firstq_subquery.c.q_name,
                attendance_subquery.c.q_last_updated,
                RegionOrg.name.label("region_name"),
                RegionOrg.id.label("region_id"),
            )
            .select_from(EventInstance)
            .outerjoin(EventTag_x_EventInstance, EventInstance.id == EventTag_x_EventInstance.event_instance_id)
            .outerjoin(EventTag, EventTag_x_EventInstance.event_tag_id == EventTag.id)
            .join(EventType_x_EventInstance, EventInstance.id == EventType_x_EventInstance.event_instance_id)
            .join(EventType, EventType_x_EventInstance.event_type_id == EventType.id)
            .join(Org, EventInstance.org_id == Org.id)
            .join(RegionOrg, RegionOrg.id == Org.parent_id)
            .outerjoin(
                firstq_subquery,
                and_(EventInstance.id == firstq_subquery.c.event_instance_id, firstq_subquery.c.rn == 1),
            )
            .outerjoin(attendance_subquery, EventInstance.id == attendance_subquery.c.event_instance_id)
            .filter(
                (EventInstance.start_date >= current_week_start),
                (EventInstance.start_date < next_week_end),
                (EventInstance.is_active),
                # (EventInstance.series_id.is_not(None)),
                or_(EventTag.name.is_(None), EventTag.name != "Off-The-Books"),
            )
        )

        results = query.all()
        df_all = pd.DataFrame(results)

        event_tags = session.query(EventTag).all()

        region_org_records = (
            session.query(Org, Org_x_SlackSpace, SlackSpace)
            .select_from(Org)
            .join(Org_x_SlackSpace, Org.id == Org_x_SlackSpace.org_id)
            .join(SlackSpace, Org_x_SlackSpace.slack_space_id == SlackSpace.id)
            .filter(Org.org_type == Org_Type.region)
            .all()
        )

        for region_id in df_all["region_id"].unique():
            try:
                region_id = int(region_id)
                df_full = df_all[df_all["region_id"] == region_id].copy()
                region_name = df_full["region_name"].iloc[0]
                region_org_record = safe_get([r for r in region_org_records if r[0].id == region_id], 0)
                if region_org_record:
                    slack_app_settings: dict = region_org_record[2].settings
                    print(f"Running for {region_name}")

                    color_dict = {
                        t.name: t.color
                        for t in event_tags
                        if t.specific_org_id == region_id or t.specific_org_id is None
                    }
                    # if "Open" in color_dict:
                    #     color_dict["OPEN!"] = color_dict.pop("Open")
                    color_dict["OPEN!"] = "Green"
                    calendar_updated = False

                    for week in ["current", "next"]:
                        if week == "current":
                            df = df_full[
                                (df_full["start_date"] >= current_week_start)
                                & (df_full["start_date"] < current_week_end)
                            ].copy()
                        else:
                            df = df_full[
                                (df_full["start_date"] >= next_week_start) & (df_full["start_date"] < next_week_end)
                            ].copy()

                        max_event_updated = (
                            datetime(year=1900, month=1, day=1)
                            if df["event_updated"].isnull().all()
                            else df["event_updated"].max()
                        )
                        max_q_last_updated = (
                            datetime(year=1900, month=1, day=1)
                            if df["q_last_updated"].isnull().all()
                            else df["q_last_updated"].max()
                        )
                        max_changed = max(max_event_updated, max_q_last_updated)
                        max_changed = datetime(year=1900, month=1, day=1) if pd.isnull(max_changed) else max_changed
                        now_cst = datetime.now(pytz.timezone("US/Central"))
                        first_sunday_run = now_cst.weekday() == 6 and now_cst.hour < 1

                        if (
                            (max_changed > datetime.now() - timedelta(hours=1))
                            or first_sunday_run
                            or LOCAL_DEVELOPMENT
                            or force
                        ):
                            # convert start_date from date to string
                            df.loc[:, "event_date"] = pd.to_datetime(df["start_date"])
                            df.loc[:, "event_date_fmt"] = df["event_date"].dt.strftime("%m/%d")
                            df.loc[:, "event_time"] = df["start_time"]
                            df.loc[df["q_name"].isna(), "q_name"] = "OPEN!"
                            df.loc[:, "q_name"] = df["q_name"].str.replace(r"\s\(([\s\S]*?\))", "", regex=True)

                            # if pax_count is not null then second line is pax_count otherwise event_acronym + event_time # noqa
                            df.loc[:, "label"] = df["q_name"] + "\n" + df["event_acronym"] + " " + df["event_time"]
                            df.loc[df["pax_count"].notna(), "label"] = (
                                df["q_name"] + "\nPAX: " + df["pax_count"].astype(str).str.replace(".0", "")
                            )

                            df.loc[(df["event_tag"].notnull()), ("label")] = (
                                df["q_name"] + "\n" + df["event_tag"] + "\n" + df["event_time"]
                            )
                            df.loc[(df["pax_count"].notna()) & (df["event_tag"].notnull()), ("label")] = (
                                df["q_name"]
                                + "\n"
                                + df["event_tag"]
                                + "\nPAX: "
                                + df["pax_count"].astype(str).str.replace(".0", "")
                            )
                            df.loc[:, "AO\nLocation"] = df["ao_name"]  # + "\n" + df["ao_description"]
                            df.loc[df["ao_description"].notnull(), "AO\nLocation"] = (
                                df["ao_name"] + "\n" + df["ao_description"]
                            )
                            df.loc[:, "AO\nLocation2"] = df["AO\nLocation"].str.replace("The ", "")
                            df.loc[:, "event_day_of_week"] = df["event_date"].dt.day_name()

                            # Combine cells for days / AOs with more than one event
                            df.sort_values(["ao_name", "event_date", "event_time"], ignore_index=True, inplace=True)
                            prior_date = ""
                            prior_label = ""
                            prior_ao = ""
                            include_list = []
                            for i in range(len(df)):
                                row2 = df.loc[i]
                                if (row2["event_date_fmt"] == prior_date) & (row2["ao_name"] == prior_ao):
                                    df.loc[i, "label"] = prior_label + "\n" + df.loc[i, "label"]
                                    prior_label = df.loc[i, "label"]
                                    include_list.append(False)
                                else:
                                    if prior_label != "":
                                        include_list.append(True)
                                    prior_date = row2["event_date_fmt"]
                                    prior_ao = row2["ao_name"]
                                    prior_label = row2["label"]

                            include_list.append(True)

                            # filter out duplicate dates
                            df = df[include_list]

                            # Reshape to wide format by date
                            df2 = df.pivot(
                                index="AO\nLocation",
                                columns=["event_day_of_week", "event_date_fmt"],
                                values="label",
                            ).fillna("")

                            # Sort and enforce word wrap on labels
                            df2.sort_index(axis=1, level=["event_date_fmt"], inplace=True)
                            df2.columns = df2.columns.map("\n".join).str.strip("\n")
                            df2.reset_index(inplace=True)

                            # Take out "The " for sorting
                            df2["AO\nLocation2"] = df2["AO\nLocation"].str.replace("The ", "")
                            df2.sort_values(by=["AO\nLocation2"], axis=0, inplace=True)
                            df2.drop(["AO\nLocation2"], axis=1, inplace=True)
                            df2.reset_index(inplace=True, drop=True)

                            # Set CSS properties for th elements in dataframe
                            th_props = [
                                ("font-size", "15px"),
                                ("text-align", "center"),
                                ("font-weight", "bold"),
                                ("color", "#F0FFFF"),
                                ("background-color", "#000000"),
                                ("white-space", "pre-wrap"),
                                ("border", "1px solid #F0FFFF"),
                            ]

                            # Set CSS properties for td elements in dataframe
                            td_props = [
                                ("font-size", "15px"),
                                ("text-align", "center"),
                                ("white-space", "pre-wrap"),
                                # ('background-color', '#000000'),
                                # ("color", "#F0FFFF"),
                                ("border", "1px solid #F0FFFF"),
                            ]

                            # Set table styles
                            styles = [
                                {"selector": "th", "props": th_props},
                                {"selector": "td", "props": td_props},
                            ]

                            # set style and export png
                            # df_styled = df2.style.set_table_styles(styles).apply(highlight_cells).hide_index()
                            # apply styles, hide the index
                            df_styled = (
                                df2.style.set_table_styles(styles)
                                .apply(highlight_cells, color_dict=color_dict)
                                .hide(axis="index")
                            )
                            df_styled = df_styled.apply(set_text_color, color_dict=color_dict, axis=1)

                            # create calendar image
                            random_chars = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=10))
                            filename = f"{region_id}-{week}-{random_chars}.png"
                            if LOCAL_DEVELOPMENT:
                                dfi.export(df_styled, filename, table_conversion="playwright")
                            else:
                                dfi.export(df_styled, f"/mnt/calendar-images/{filename}", table_conversion="playwright")

                            # upload to s3 and remove local file
                            slack_app_settings = region_org_record[2].settings
                            existing_file = slack_app_settings.get(f"calendar_image_{week}")

                            if LOCAL_DEVELOPMENT:  # TODO: upload to GCP
                                s3_client = boto3.client("s3")
                                with open(filename, "rb") as f:
                                    s3_client.upload_fileobj(
                                        f, "slackblast-images", filename, ExtraArgs={"ContentType": "image/png"}
                                    )
                                try:
                                    if existing_file:
                                        s3_client.delete_object(Bucket="slackblast-images", Key=existing_file)
                                    os.remove(filename)
                                except Exception as e:
                                    print(f"Error deleting old file {existing_file} from S3: {e}")
                            else:
                                if existing_file:
                                    try:
                                        os.remove(f"/mnt/calendar-images/{existing_file}")
                                    except Exception as e:
                                        print(f"Error deleting old file {existing_file} from local storage: {e}")
                            slack_app_settings[f"calendar_image_{week}"] = filename
                            calendar_updated = True

                    # post to slack channel if enabled
                    if (
                        slack_app_settings.get("q_image_posting_enabled")
                        and slack_app_settings.get("q_image_posting_channel")
                        and slack_app_settings.get("bot_token")
                        and calendar_updated
                    ):
                        print("Posting to Slack channel")
                        client = WebClient(token=slack_app_settings["bot_token"])
                        if LOCAL_DEVELOPMENT:
                            IMAGE_URL = S3_IMAGE_URL
                        else:
                            IMAGE_URL = GCP_IMAGE_URL
                        block_list = [blocks.HeaderBlock(text=":calendar: Q Calendar")]
                        if slack_app_settings.get("calendar_image_current"):
                            block_list.append(
                                blocks.ImageBlock(
                                    image_url=IMAGE_URL.format(
                                        bucket="f3nation-calendar-images",
                                        image_name=slack_app_settings["calendar_image_current"],
                                    ),
                                    alt_text="This Week's Q Sheet",
                                )
                            )
                        if slack_app_settings.get("calendar_image_next"):
                            block_list.append(
                                blocks.ImageBlock(
                                    image_url=IMAGE_URL.format(
                                        bucket="f3nation-calendar-images",
                                        image_name=slack_app_settings["calendar_image_next"],
                                    ),
                                    alt_text="Next Week's Q Sheet",
                                )
                            )
                        block_list.append(
                            blocks.ActionsBlock(
                                elements=[
                                    blocks.ButtonElement(
                                        text=":calendar: Open Full Calendar",
                                        action_id=actions.OPEN_CALENDAR_BUTTON,
                                    ),
                                ]
                            )
                        )
                        block_list.extend(create_special_events_blocks(slack_app_settings))
                        try:
                            if slack_app_settings.get("q_image_posting_ts") and (not first_sunday_run):
                                try:
                                    client.chat_update(
                                        channel=slack_app_settings["q_image_posting_channel"],
                                        ts=slack_app_settings["q_image_posting_ts"],
                                        blocks=block_list,
                                        text="Q Sheet",
                                    )
                                except Exception as e:
                                    print(f"Error updating Slack message, posting new message: {e}")
                                    response = client.chat_postMessage(
                                        channel=slack_app_settings["q_image_posting_channel"],
                                        text="Q Sheet",
                                        blocks=block_list,
                                    )
                                    if response["ok"]:
                                        slack_app_settings["q_image_posting_ts"] = response["ts"]
                            else:
                                response = client.chat_postMessage(
                                    channel=slack_app_settings["q_image_posting_channel"],
                                    text="Q Sheet",
                                    blocks=block_list,
                                )
                                if response["ok"]:
                                    slack_app_settings["q_image_posting_ts"] = response["ts"]
                        except Exception as e:
                            print(f"Error posting to Slack channel: {e}")
                        # update org record with new filename
                    print(f"Updating Slack app settings for region {region_name} with {slack_app_settings}")
                    session.query(SlackSpace).filter(SlackSpace.team_id == slack_app_settings["team_id"]).update(
                        {"settings": slack_app_settings}
                    )
                    session.commit()

            except Exception as e:
                print(f"Error processing region {region_id}: {e}")
    update_local_region_records()


def create_special_events_text(events: List[EventInstance], slack_settings_dict: dict, max_events: int = 10) -> str:
    text = ""
    for i, event in enumerate(events[:max_events]):
        text += f"{i + 1}. *{event.name}* - {event.start_date.strftime('%A, %B %d')} - {event.start_time} @ {event.org.name}\n"  # noqa

        if event.preblast_ts:
            # TODO: need to make this work for region-level events
            if slack_settings_dict.get("default_preblast_destination") == "specified_channel":
                channel_id = slack_settings_dict.get("preblast_destination_channel")
            else:
                channel_id = event.org.meta.get("slack_channel_id")

            if channel_id:
                text += f"<slack://channel?team={slack_settings_dict.get('team_id')}&id={channel_id}&ts={event.preblast_ts}|Click here to go to the preblast thread!>\n"  # noqa

    return text


def create_special_events_blocks(slack_settings_dict: dict) -> blocks.Block:
    blocks_list = []
    # list special events
    special_events: List[EventInstance] = DbManager.find_records(
        cls=EventInstance,
        filters=[
            or_(
                EventInstance.org_id == slack_settings_dict.get("org_id"),
                EventInstance.org.has(Org.parent_id == slack_settings_dict.get("org_id")),
            ),
            EventInstance.start_date >= current_date_cst(),
            EventInstance.start_date
            <= current_date_cst() + timedelta(days=slack_settings_dict.get("special_events_post_days") or 60),
            EventInstance.is_active,
            EventInstance.highlight,
        ],
        joinedloads=[EventInstance.org],
    )
    if len(special_events) > 0:
        blocks_list.append(blocks.HeaderBlock(text=":tada: Special Events:"))
        msg = create_special_events_text(special_events, slack_settings_dict)
        blocks_list.append(blocks.SectionBlock(text=blocks.MarkdownTextObject(text=msg)))
    return blocks_list


if __name__ == "__main__":
    generate_calendar_images()
