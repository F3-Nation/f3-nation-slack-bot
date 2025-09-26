import plotly.graph_objects as go
import plotly.io as pio

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
neon_green = "#39FF14"
fig = go.Figure(
    go.Bar(
        x=values,
        y=categories,
        orientation="h",
        marker={
            "color": neon_green,
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
            "x": 0.5,  # left edge of bar
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

fig.show()
