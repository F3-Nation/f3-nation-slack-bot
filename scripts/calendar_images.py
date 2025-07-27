import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import random
from datetime import datetime, timedelta

import boto3
import dataframe_image as dfi
import pandas as pd
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
from f3_data_models.utils import get_session
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import aliased, joinedload

from utilities.constants import EVENT_TAG_COLORS, LOCAL_DEVELOPMENT
from utilities.helper_functions import current_date_cst, safe_get, update_local_region_records


def time_int_to_str(time: int) -> str:
    return f"{time // 100:02d}{time % 100:02d}"


def highlight_cells(s, color_dict):
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


def generate_calendar_images():
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
            region_id = int(region_id)
            df_full = df_all[df_all["region_id"] == region_id].copy()
            region_name = df_full["region_name"].iloc[0]
            print(f"Running for {region_name}")

            color_dict = {
                t.name: t.color for t in event_tags if t.specific_org_id == region_id or t.specific_org_id is None
            }
            if "Open" in color_dict:
                color_dict["OPEN!"] = color_dict.pop("Open")

            for week in ["current", "next"]:
                if week == "current":
                    df = df_full[
                        (df_full["start_date"] >= current_week_start) & (df_full["start_date"] < current_week_end)
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
                first_sunday_run = datetime.now().weekday() == 6 and datetime.now().hour < 1

                if (max_changed > datetime.now() - timedelta(hours=1)) or first_sunday_run or LOCAL_DEVELOPMENT:
                    # convert start_date from date to string
                    df.loc[:, "event_date"] = pd.to_datetime(df["start_date"])
                    df.loc[:, "event_date_fmt"] = df["event_date"].dt.strftime("%m/%d")
                    df.loc[:, "event_time"] = df["start_time"]
                    df.loc[df["q_name"].isna(), "q_name"] = "OPEN!"
                    df.loc[:, "q_name"] = df["q_name"].str.replace(r"\s\(([\s\S]*?\))", "", regex=True)

                    df.loc[:, "label"] = df["q_name"] + "\n" + df["event_acronym"] + " " + df["event_time"]
                    df.loc[(df["event_tag"].notnull()), ("label")] = (
                        df["q_name"] + "\n" + df["event_tag"] + "\n" + df["event_time"]
                    )
                    df.loc[:, "AO\nLocation"] = df["ao_name"]  # + "\n" + df["ao_description"]
                    df.loc[df["ao_description"].notnull(), "AO\nLocation"] = df["ao_name"] + "\n" + df["ao_description"]
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
                    region_org_record = safe_get([r for r in region_org_records if r[0].id == region_id], 0)
                    if region_org_record:
                        slack_app_settings = region_org_record[2].settings
                        existing_file = slack_app_settings.get(f"calendar_image_{week}")

                        if LOCAL_DEVELOPMENT:  # TODO: upload to GCP
                            s3_client = boto3.client("s3")
                            with open(filename, "rb") as f:
                                s3_client.upload_fileobj(
                                    f, "slackblast-images", filename, ExtraArgs={"ContentType": "image/png"}
                                )

                            if existing_file:
                                s3_client.delete_object(Bucket="slackblast-images", Key=existing_file)
                            os.remove(filename)
                        else:
                            if existing_file:
                                os.remove(f"/mnt/calendar-images/{existing_file}")

                        # update org record with new filename
                        slack_app_settings[f"calendar_image_{week}"] = filename
                        session.query(SlackSpace).filter(SlackSpace.team_id == slack_app_settings["team_id"]).update(
                            {"settings": slack_app_settings}
                        )
                        session.commit()
                    else:
                        print(f"No Slack settings found for region {region_id}. Skipping upload.")

    update_local_region_records()


if __name__ == "__main__":
    generate_calendar_images()
