import os
import ssl
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

import matplotlib.pyplot as plt
import mplcyberpunk  # noqa: F401 needed for plt.style.
import plotly.graph_objects as go
import plotly.io as pio
from f3_data_models.models import (
    AttendanceExpanded,
    EventInstanceExpanded,
    Org,
    Org_x_SlackSpace,
    SlackSpace,
)
from f3_data_models.utils import DbManager, get_session
from PIL import Image
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from sqlalchemy import and_, func, literal, select, union_all

from utilities.database.orm import SlackSettings


@dataclass
class OrgMonthlySummary:
    org_id: int
    month: datetime
    event_count: int
    total_posts: int
    total_fngs: int
    unique_pax_count: int


@dataclass
class OrgUserLeaderboard:
    basis: str  # "month" or "ytd"
    org_id: int
    org_name: str
    user_id: int
    f3_name: str
    avatar_url: str
    post_count: int
    total_qs: int


pio.renderers.default = "browser"
pio.templates.default = "plotly_dark"

# Create the horizontal bar chart (dark + neon styling)
# neon_colors = ["#00F5D4", "#7B2FF7", "#F72585"]  # aqua, purple, magenta
NEON_GREEN = "#39FF14"
# Default export size (pixels) and scale multiplier for higher DPI
DEFAULT_IMAGE_WIDTH = 800
DEFAULT_IMAGE_HEIGHT = 800
DEFAULT_IMAGE_SCALE = 3


def upload_files_to_slack(file_paths: List[str], settings: SlackSettings):
    if not settings.bot_token or not settings.reporting_region_channel or not file_paths:
        print("Slack bot token or reporting channel not configured; skipping upload")
        return

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    client = WebClient(token=settings.bot_token, ssl=ssl_context)

    file_list = []
    for fp in file_paths:
        with open(fp, "rb") as f:
            file_bytes = f.read()
        file = {
            "filename": fp,
            "file": file_bytes,
        }
        file_list.append(file)
    try:
        response = client.files_upload_v2(
            channel=settings.reporting_region_channel,
            files_upload=file_list,
            initial_comment="Here are this month's reports!",
        )
        assert response["file"]  # the uploaded file
    except SlackApiError as e:
        print(f"Error uploading file to Slack: {e.response['error']}")


def cycle_all_orgs(run_org_id: int = None):
    records = DbManager.find_join_records3(Org_x_SlackSpace, Org, SlackSpace, filters=[True])
    region_orgs: List[Org] = [r[1] for r in records]
    slack_spaces: List[SlackSpace] = [r[2] for r in records]
    org_leaderboard_dict = pull_org_leaderboard_data()
    monthly_summary_dict = pull_org_summary_data()

    if run_org_id is None:
        # Region reports
        for org, slack in zip(region_orgs, slack_spaces):
            settings = SlackSettings(**slack.settings)
            upload_files = []
            if settings.reporting_region_leaderboard_enabled and settings.reporting_region_channel:
                upload_files.append(create_post_leaders_plot(org_leaderboard_dict[org.id]))
            if settings.reporting_region_monthly_summary_enabled:
                if org.id in monthly_summary_dict:
                    upload_files.append(create_org_monthly_summary(monthly_summary_dict[org.id]))
            # Upload all files for the org
            upload_files_to_slack(upload_files, settings)
    else:
        create_post_leaders_plot(org_leaderboard_dict[run_org_id])


def pull_org_leaderboard_data() -> Dict[int, List[OrgUserLeaderboard]]:
    session = get_session()

    # Define reusable date range and month expression
    prior_month = datetime.now().month - 1 if datetime.now().month > 1 else 12
    prior_year = datetime.now().year if datetime.now().month > 1 else datetime.now().year - 1

    # Helper to build a scoped query for a given org id column
    def build_scoped_query(org_id_col, org_name_col, scope_name: str, basis: str = "month"):
        trunc_date = datetime(prior_year, prior_month, 1) if basis == "month" else datetime(prior_year, 1, 1)
        query = (
            select(
                org_id_col.label("org_id"),
                org_name_col.label("org_name"),
                literal(basis).label("basis"),
                AttendanceExpanded.user_id.label("user_id"),
                AttendanceExpanded.f3_name.label("f3_name"),
                AttendanceExpanded.avatar_url.label("avatar_url"),
                func.count(EventInstanceExpanded.id).label("post_count"),
                func.sum(AttendanceExpanded.q_ind + AttendanceExpanded.coq_ind).label("total_qs"),
            )
            .join(AttendanceExpanded, AttendanceExpanded.event_instance_id == EventInstanceExpanded.id)
            .filter(func.date_trunc(basis, EventInstanceExpanded.start_date) == trunc_date)
            .group_by(
                org_id_col,
                org_name_col,
                AttendanceExpanded.user_id,
                AttendanceExpanded.f3_name,
                AttendanceExpanded.avatar_url,
            )
            .order_by(org_id_col, func.count(EventInstanceExpanded.id).desc())
        )
        return query

    # Build queries for AO-scoped and Region-scoped orgs
    query_ao_month = build_scoped_query(
        EventInstanceExpanded.ao_org_id, EventInstanceExpanded.ao_name, "ao", basis="month"
    )
    query_region_month = build_scoped_query(
        EventInstanceExpanded.region_org_id, EventInstanceExpanded.region_name, "region", basis="month"
    )
    query_ao_ytd = build_scoped_query(
        EventInstanceExpanded.ao_org_id, EventInstanceExpanded.ao_name, "ao", basis="year"
    )
    query_region_ytd = build_scoped_query(
        EventInstanceExpanded.region_org_id, EventInstanceExpanded.region_name, "region", basis="year"
    )

    # Union both scopes so the result includes both AO and Region orgs
    final_query = union_all(query_ao_month, query_region_month, query_ao_ytd, query_region_ytd)

    results = session.execute(final_query).all()

    results_dict: Dict[int, List[OrgUserLeaderboard]] = {}
    for row in results:
        org_id = row.org_id
        if org_id not in results_dict:
            results_dict[org_id] = []
        results_dict[org_id].append(OrgUserLeaderboard(**row._asdict()))

    session.close()
    return results_dict


def create_post_leaders_plot(records: List[OrgUserLeaderboard]) -> str:
    # guard for empty input
    if not records:
        print("No records to plot")
        return

    # sort by post_count descending and take the top_n
    def create_post_leaders_chart(
        records: List[OrgUserLeaderboard],
        top_n: int = 5,
        basis: str = "month",
        value_field: str = "post_count",
        label: str = "Posts",
        bar_color: str = NEON_GREEN,
    ):
        sorted_records = [r for r in records if r.basis == basis]
        sorted_records = sorted(sorted_records, key=lambda r: getattr(r, value_field), reverse=True)[:top_n]
        categories = [r.f3_name for r in sorted_records]
        values = [getattr(r, value_field) for r in sorted_records]
        images = [r.avatar_url for r in sorted_records]

        fig = go.Figure(
            go.Bar(
                x=values,
                y=categories,
                orientation="h",
                marker={"color": bar_color},
                hovertemplate="%{y}: %{x}<extra></extra>",
            )
        )

        # Lock avatar positions using paper coordinates so they don't scale with bar length.
        # Place the category labels (user names) as annotations immediately to the right
        # of the avatar (also positioned in paper coords). Numeric labels (post counts)
        # are still placed using data x-coordinates so they line up with the bar value.
        avatar_x_paper = 0.025
        avatar_sizex_paper = 0.07
        avatar_sizey = 0.5

        # Determine maximum value to compute a small padding so numeric labels
        # don't sit flush against the end of the bar. Use a percentage of the
        # largest value but enforce a sensible minimum so very-small-value
        # series get readable padding too.
        try:
            max_value = max([float(v) if v is not None else 0.0 for v in values] + [1.0])
        except Exception:
            max_value = 1.0
        pad = max(max_value * 0.02, 0.3)

        for i, img_url in enumerate(images):
            # raw value may be int, None, or decimal.Decimal from SQL; normalize to float for math
            raw_val = values[i] if i < len(values) else 0
            try:
                numeric = float(raw_val) if raw_val is not None else 0.0
            except Exception:
                numeric = 0.0

            # Prepare a display label: prefer integer-looking values without a decimal point
            if float(numeric).is_integer():
                display_label = str(int(numeric))
            else:
                display_label = str(numeric)

            # Add avatar (fixed on the left in paper coordinates)
            if img_url:
                fig.add_layout_image(
                    {
                        "source": img_url,
                        "x": avatar_x_paper,
                        "y": categories[i],
                        "xref": "paper",
                        "yref": "y",
                        "sizex": avatar_sizex_paper,
                        "sizey": avatar_sizey,
                        "xanchor": "left",
                        "yanchor": "middle",
                        "opacity": 0.95,
                        "layer": "above",
                    }
                )

            # Add category label (user name) to the right of the avatar, also in paper coords
            name_x_paper = avatar_x_paper + avatar_sizex_paper + 0.01
            fig.add_annotation(
                x=name_x_paper,
                y=categories[i],
                xref="paper",
                yref="y",
                text=categories[i],
                showarrow=False,
                font={"color": "#0B1220", "size": 40},
                align="left",
                xanchor="left",
                yanchor="middle",
            )

            # Numeric label (post count) placed using the data x coordinate so it reflects bar length.
            # Compute a small padding (in data units) and place the label slightly inside
            # the bar end. Right-align the label so its right edge lines up with the
            # padded x position which keeps the text clear of the bar edge.
            if numeric > pad:
                numeric_x = numeric - pad
                numeric_x_anchor = "right"
            else:
                # For very small values, place the label to the right so it remains readable
                numeric_x = numeric + pad
                numeric_x_anchor = "left"
            # Ensure numeric_x is non-negative
            if numeric_x < 0:
                numeric_x = 0

            fig.add_annotation(
                x=numeric_x,
                y=categories[i],
                xref="x",
                yref="y",
                text=display_label,
                showarrow=False,
                font={"color": "#0B1220", "size": 40, "family": "Arial Bold"},
                align="left",
                xanchor=numeric_x_anchor,
                yanchor="middle",
            )

        # Update layout for better appearance
        org_name = sorted_records[0].org_name + " " if sorted_records else ""
        if basis == "year":
            prior_month_name = "YTD"
        else:
            prior_month_name = (
                datetime(datetime.now().year, datetime.now().month - 1, 1).strftime("%B")
                if datetime.now().month > 1
                else datetime(datetime.now().year - 1, 12, 1).strftime("%B")
            )
        fig.update_layout(
            template="plotly_dark",
            title={
                "text": f"{org_name}{prior_month_name} {label} Leaders",
                "font": {"color": "#FFFFFF", "size": 30},
                "x": 0.5,
                "xanchor": "center",
            },
            # Remove x-axis ticks and labels (we're showing numeric annotations on bars instead)
            xaxis={
                "showticklabels": False,
                "showgrid": False,
                "zeroline": False,
                "ticks": "",
            },
            # xaxis={
            #     "title": {"text": "Posts", "font": {"color": "#A0AEC0", "size": 18}},
            #     "gridcolor": "rgba(0,245,212,0.15)",
            #     "zerolinecolor": "rgba(0,245,212,0.25)",
            #     "tickfont": {"color": "#E2E8F0", "size": 18},
            # },
            yaxis={
                "gridcolor": "rgba(123,47,247,0.12)",
                "tickfont": {"color": "#E2E8F0", "size": 18},
                "showticklabels": False,
                "autorange": "reversed",
            },
            paper_bgcolor="#0B1220",
            plot_bgcolor="#0B1220",
            height=800,
            width=800,
            margin={"l": 30, "r": 30, "t": 70, "b": 30},
        )

        # Be explicit about export pixel dimensions — some renderers ignore layout width/height
        # unless width/height are passed directly to the image writer. `scale` multiplies
        # those pixel dimensions (use 1 for exact pixels, >1 for higher DPI).
        fig.write_image(
            f"{basis}_{label}_leaders.png",
            width=DEFAULT_IMAGE_WIDTH,
            height=DEFAULT_IMAGE_HEIGHT,
            scale=DEFAULT_IMAGE_SCALE,
        )

    create_post_leaders_chart(
        records, top_n=5, basis="month", value_field="post_count", label="Post", bar_color="#39FF14"
    )
    create_post_leaders_chart(
        records, top_n=5, basis="year", value_field="post_count", label="Post", bar_color="#14E4FF"
    )
    create_post_leaders_chart(records, top_n=5, basis="month", value_field="total_qs", label="Q", bar_color="#FF5733")
    create_post_leaders_chart(records, top_n=5, basis="year", value_field="total_qs", label="Q", bar_color="#FFBD33")

    file_name = stitch_2x2(
        [
            "month_Post_leaders.png",
            "year_Post_leaders.png",
            "month_Q_leaders.png",
            "year_Q_leaders.png",
        ],
        out_path="4up_post_leaders.png",
        bg_color=(11, 18, 32),
        padding=10,
    )
    return file_name


def stitch_2x2(
    image_paths: List[str],
    out_path: str = "4up_post_leaders.png",
    bg_color: tuple = (11, 18, 32),
    padding: int = 0,
):
    """Stitch four images into a 2x2 grid and save as a single image.

    - image_paths: list of 4 image file paths in row-major order: [TL, TR, BL, BR]
    - out_path: output file path
    - bg_color: background RGB tuple for the canvas
    - padding: pixels of padding between images

    If the input images differ in size they will be resized to the size of the
    first image to produce a uniform grid.
    """
    if len(image_paths) != 4:
        raise ValueError("image_paths must contain exactly 4 paths (row-major order)")

    imgs = [Image.open(p).convert("RGBA") for p in image_paths]

    # Normalize sizes to the first image
    base_w, base_h = imgs[0].size
    norm_imgs = []
    for im in imgs:
        if im.size != (base_w, base_h):
            im = im.resize((base_w, base_h), Image.LANCZOS)
        norm_imgs.append(im)

    total_w = base_w * 2 + padding
    total_h = base_h * 2 + padding

    canvas = Image.new("RGBA", (total_w, total_h), color=bg_color + (255,))

    # Positions: (0,0), (base_w+padding,0), (0,base_h+padding), (base_w+padding, base_h+padding)
    positions = [(0, 0), (base_w + padding, 0), (0, base_h + padding), (base_w + padding, base_h + padding)]
    for im, pos in zip(norm_imgs, positions):
        canvas.paste(im, pos, im)

    # Save as RGB (flatten alpha) for compatibility
    canvas.convert("RGB").save(out_path, dpi=(300, 300))
    return out_path


def create_org_monthly_summary(records: List[OrgMonthlySummary]):
    # Build three subplots (Posts, Unique PAX, FNGs) with paired series for current and prior year.
    # Only plot points for months that had events (use None for missing months).
    import calendar

    plt.style.use("cyberpunk")
    fig, axs = plt.subplots(nrows=3, ncols=1, figsize=(12, 10), sharex=True)

    now = datetime.now()
    current_year = now.year
    prior_year = now.year - 1

    # Month labels Jan..Dec
    month_labels = [calendar.month_name[m] for m in range(1, 13)]

    def aggregate_year(target_year: int):
        posts: List[int | None] = []
        uniques: List[int | None] = []
        fngs: List[int | None] = []
        for m in range(1, 13):
            month_event = next(
                (event for event in records if event.month.year == target_year and event.month.month == m), None
            )
            if month_event and (month_event.event_count or 0) > 0:
                posts.append(month_event.total_posts)
                uniques.append(month_event.unique_pax_count)
                fngs.append(month_event.total_fngs)
            else:
                posts.append(None)
                uniques.append(None)
                fngs.append(None)
        return posts, uniques, fngs

    posts_current, uniques_current, fngs_current = aggregate_year(current_year)
    posts_prior, uniques_prior, fngs_prior = aggregate_year(prior_year)

    # Colors per metric; prior year uses same color with transparency and dashed style
    COLOR_POSTS = "#39FF14"  # neon green
    COLOR_UNIQUES = "#FF5733"
    COLOR_FNGS = "#33D6FF"

    # Subplot 1: Total Posts
    ax = axs[0]
    ax.plot(
        month_labels,
        posts_prior,
        label=f"{prior_year}",
        color=COLOR_POSTS,
        alpha=0.25,
        marker="o",
        linestyle="--",
    )
    ax.plot(
        month_labels,
        posts_current,
        label=f"{current_year}",
        color=COLOR_POSTS,
        alpha=0.95,
        marker="o",
    )
    ax.set_title("Total Posts", fontsize=14)
    # ax.set_ylabel("Total Posts", fontsize=12)
    ax.legend(loc="upper left")
    # mplcyberpunk.add_glow_effects(ax=ax, gradient_fill=False)

    # Subplot 2: Unique PAX
    ax = axs[1]
    ax.plot(
        month_labels,
        uniques_prior,
        label=f"{prior_year}",
        color=COLOR_UNIQUES,
        alpha=0.25,
        marker="o",
        linestyle="--",
    )
    ax.plot(
        month_labels,
        uniques_current,
        label=f"{current_year}",
        color=COLOR_UNIQUES,
        alpha=0.95,
        marker="o",
    )
    ax.set_title("Unique PAX", fontsize=14)
    # ax.set_ylabel("Unique PAX", fontsize=12)
    ax.legend(loc="upper left")
    # mplcyberpunk.add_glow_effects(ax=ax, gradient_fill=False)

    # Subplot 3: FNGs
    ax = axs[2]
    ax.plot(
        month_labels,
        fngs_current,
        label=f"{current_year}",
        color=COLOR_FNGS,
        alpha=0.95,
        marker="o",
    )
    ax.plot(
        month_labels,
        fngs_prior,
        label=f"{prior_year}",
        color=COLOR_FNGS,
        alpha=0.25,
        marker="o",
        linestyle="--",
    )

    ax.set_title("FNGs", fontsize=14)
    # ax.set_ylabel("FNGs", fontsize=12)
    ax.legend(loc="upper left")
    # mplcyberpunk.add_glow_effects(ax=ax, gradient_fill=False)

    fig.suptitle(f"Monthly Attendance — {prior_year} vs {current_year}", fontsize=16)
    # axs[-1].set_xlabel("Month", fontsize=14)
    plt.setp(axs[-1].get_xticklabels(), rotation=45)
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig("org_monthly_attendance.png", dpi=300)
    plt.close()


def pull_org_summary_data() -> Dict[int, List[OrgMonthlySummary]]:
    session = get_session()

    # Define reusable date range and month expression
    start_date = datetime(datetime.now().year - 1, 1, 1)
    end_date = datetime(datetime.now().year, datetime.now().month, 1)
    month_expr = func.date_trunc("month", EventInstanceExpanded.start_date)

    # Helper to build a scoped query for a given org id column
    def build_scoped_query(org_id_col, scope_name: str):
        # Subquery of events (one row per event) to avoid duplication from Attendance joins
        events_subq = (
            select(
                org_id_col.label("org_id"),
                month_expr.label("month"),
                EventInstanceExpanded.id.label("event_id"),
                EventInstanceExpanded.pax_count.label("pax_count"),
                EventInstanceExpanded.fng_count.label("fng_count"),
            )
            .where(
                and_(
                    EventInstanceExpanded.start_date >= start_date,
                    EventInstanceExpanded.start_date < end_date,
                )
            )
            .subquery(f"events_subq_{scope_name}")
        )

        # Aggregate event-level metrics (counts and sums) from the deduplicated events
        events_agg = (
            select(
                events_subq.c.org_id,
                events_subq.c.month,
                func.count(events_subq.c.event_id).label("event_count"),
                func.sum(events_subq.c.pax_count).label("total_posts"),
                func.sum(events_subq.c.fng_count).label("total_fngs"),
            )
            .group_by(events_subq.c.org_id, events_subq.c.month)
            .subquery(f"events_agg_{scope_name}")
        )

        # Distinct attendance per org, month, user to count unique pax across all events in that month
        attendance_distinct = (
            select(
                org_id_col.label("org_id"),
                month_expr.label("month"),
                AttendanceExpanded.user_id.label("user_id"),
            )
            .select_from(EventInstanceExpanded)
            .join(AttendanceExpanded, AttendanceExpanded.event_instance_id == EventInstanceExpanded.id)
            .where(
                and_(
                    EventInstanceExpanded.start_date >= start_date,
                    EventInstanceExpanded.start_date < end_date,
                )
            )
            .distinct()
            .subquery(f"attendance_distinct_{scope_name}")
        )

        attendance_agg = (
            select(
                attendance_distinct.c.org_id,
                attendance_distinct.c.month,
                func.count().label("unique_pax_count"),
            )
            .group_by(attendance_distinct.c.org_id, attendance_distinct.c.month)
            .subquery(f"attendance_agg_{scope_name}")
        )

        # Final join of event aggregates with unique pax counts
        scoped_query = select(
            events_agg.c.org_id.label("org_id"),
            events_agg.c.month.label("month"),
            events_agg.c.event_count,
            events_agg.c.total_posts,
            events_agg.c.total_fngs,
            func.coalesce(attendance_agg.c.unique_pax_count, 0).label("unique_pax_count"),
        ).select_from(
            events_agg.outerjoin(
                attendance_agg,
                and_(
                    events_agg.c.org_id == attendance_agg.c.org_id,
                    events_agg.c.month == attendance_agg.c.month,
                ),
            )
        )
        return scoped_query

    # Build queries for AO-scoped and Region-scoped orgs
    query_ao = build_scoped_query(EventInstanceExpanded.ao_org_id, "ao")
    query_region = build_scoped_query(EventInstanceExpanded.region_org_id, "region")

    # Union both scopes so the result includes both AO and Region orgs
    final_query = union_all(query_ao, query_region)

    results = session.execute(final_query).all()

    results_dict: Dict[int, List[OrgMonthlySummary]] = {}
    for row in results:
        org_id = row.org_id
        if org_id not in results_dict:
            results_dict[org_id] = []
        results_dict[org_id].append(OrgMonthlySummary(**row._asdict()))

    session.close()
    return results_dict


def run_monthly_summaries(run_org_id: int = None):
    summary_dict = pull_org_summary_data()

    if run_org_id is not None and run_org_id in summary_dict:
        create_org_monthly_summary(summary_dict[run_org_id])
    else:
        for _, records in summary_dict.items():
            create_org_monthly_summary(records)


if __name__ == "__main__":
    # run_monthly_summaries(run_org_id=38451)
    cycle_all_orgs(run_org_id=38451)
