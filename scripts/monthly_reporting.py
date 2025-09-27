from typing import List

import plotly.graph_objects as go
import plotly.io as pio
from f3_data_models.models import Org, Org_x_SlackSpace, SlackSpace
from f3_data_models.utils import DbManager

from utilities.database.orm import SlackSettings

pio.renderers.default = "browser"
pio.templates.default = "plotly_dark"

# Data for the horizontal bar chart
categories = ["Moneyball", "PAX2", "PAX3"]
values = [10, 20, 15]
images = [
    "https://cdn.icon-icons.com/icons2/2699/PNG/512/slack_tile_logo_icon_168820.png",  # Replace with your image URLs
    "https://cdn.icon-icons.com/icons2/2699/PNG/512/slack_tile_logo_icon_168820.png",
    "https://cdn.icon-icons.com/icons2/2699/PNG/512/slack_tile_logo_icon_168820.png",
]

# Create the horizontal bar chart (dark + neon styling)
# neon_colors = ["#00F5D4", "#7B2FF7", "#F72585"]  # aqua, purple, magenta
NEON_GREEN = "#39FF14"


def cycle_all_orgs():
    records = DbManager.find_join_records3(Org_x_SlackSpace, Org, SlackSpace, filters=[True])
    region_orgs: List[Org] = [r[1] for r in records]
    slack_spaces: List[SlackSpace] = [r[2] for r in records]

    for org, slack in zip(region_orgs, slack_spaces):
        settings = SlackSettings(**slack.settings)
        if settings.reporting_region_leaderboard_enabled and settings.reporting_region_leaderboard_channel:
            print(f"Org: {org.name}, Channel: {settings.reporting_region_leaderboard_channel}")


def create_post_leaders_chart(categories, values, images):
    fig = go.Figure(
        go.Bar(
            x=values,
            y=categories,
            orientation="h",
            marker={
                "color": NEON_GREEN,
                # "line": {"color": "#00E5FF", "width": 2},  # cyan edge for a subtle neon outline
            },
            hovertemplate="%{y}: %{x}<extra></extra>",
        )
    )

    # Add images to the chart
    for i, img_url in enumerate(images):
        fig.add_layout_image(
            {
                "source": img_url,
                # center image on each bar using its value
                "x": 2,  # left edge of bar
                "y": categories[i],
                "xref": "x",
                "yref": "y",
                "sizex": max(values[i] / 3, 1),  # keep a minimum size
                "sizey": 0.5,
                "xanchor": "center",
                "yanchor": "middle",
                "opacity": 0.95,
                "layer": "above",
            }
        )

    # Update layout for better appearance
    fig.update_layout(
        template="plotly_dark",
        title={
            "text": "Monthly Post Leaders",
            "font": {"color": "#FFFFFF", "size": 30},
            "x": 0.5,
            "xanchor": "center",
        },
        xaxis={
            "title": {"text": "Posts", "font": {"color": "#A0AEC0", "size": 18}},
            "gridcolor": "rgba(0,245,212,0.15)",
            "zerolinecolor": "rgba(0,245,212,0.25)",
            "tickfont": {"color": "#E2E8F0", "size": 18},
        },
        yaxis={
            # "title": {"text": "Categories", "font": {"color": "#A0AEC0"}},
            "gridcolor": "rgba(123,47,247,0.12)",
            "tickfont": {"color": "#E2E8F0", "size": 18},
        },
        paper_bgcolor="#0B1220",
        plot_bgcolor="#0B1220",
        height=420,
        margin={"l": 90, "r": 30, "t": 60, "b": 50},
    )

    # fig.show()
    fig.write_image("monthly_post_leaders.png", scale=3)
