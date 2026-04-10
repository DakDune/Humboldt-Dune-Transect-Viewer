import streamlit as st
import pydeck as pdk
from utils.data_loader import load_transect_data
import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from io import BytesIO
import re
import base64
from pathlib import Path

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(layout="wide")

# -----------------------------
# BACKGROUND + STYLING
# -----------------------------
def set_background(image_path):
    with open(image_path, "rb") as img_file:
        b64_string = base64.b64encode(img_file.read()).decode()

    st.markdown(
        f"""
        <style>

        /* FULL PAGE BACKGROUND */
        html, body, [data-testid="stAppViewContainer"] {{
            background: url("data:image/jpg;base64,{b64_string}") no-repeat center center fixed;
            background-size: cover;
        }}

        /* MAIN CONTENT OVERLAY */
        [data-testid="stAppViewContainer"] > .main {{
            background-color: rgba(255, 255, 255, 0.85);
            padding: 1.5rem;
            border-radius: 10px;
        }}

        /* SIDEBAR */
        section[data-testid="stSidebar"] {{
            background-color: rgba(245, 250, 255, 0.95);
            border-right: 1px solid #ddd;
        }}

        /* TITLE */
        h1 {{
            color: #1f4e79;
            font-weight: 600;
        }}

        /* GENERAL TEXT */
        body {{
            color: #222;
        }}

        </style>
        """,
        unsafe_allow_html=True
    )

# Apply background
bg_path = Path("assets/background.jpg")
if bg_path.exists():
    set_background(bg_path)

# -----------------------------
# TITLE
# -----------------------------
st.markdown(
    "<h1 style='text-align: center;'>Dune Transect Viewer</h1>",
    unsafe_allow_html=True
)

# -----------------------------
# MAPBOX TOKEN
# -----------------------------
os.environ["MAPBOX_API_KEY"] = st.secrets["MAPBOX_API_KEY"]

# -----------------------------
# LOAD DATA
# -----------------------------
gdf, survey_dict = load_transect_data()

# -----------------------------
# SORT TRANSECTS
# -----------------------------
def sort_key(x):
    match = re.match(r"T(\d+)", x)
    if match:
        return (0, int(match.group(1)))
    else:
        return (1, x)

transect_ids = sorted(gdf["transect_id"].tolist(), key=sort_key)

# -----------------------------
# SESSION STATE
# -----------------------------
if "selected_transect" not in st.session_state:
    st.session_state.selected_transect = transect_ids[0]

# -----------------------------
# SIDEBAR
# -----------------------------
st.sidebar.header("Transect Selection")

selected_transect = st.sidebar.selectbox(
    "Select Transect",
    transect_ids,
    index=transect_ids.index(st.session_state.selected_transect)
)

st.session_state.selected_transect = selected_transect

# -----------------------------
# DATE SELECTION
# -----------------------------
transect_surveys = survey_dict[selected_transect]

date_records = []

for sid, data in transect_surveys.items():
    raw_date = data["date"]

    try:
        dt = pd.to_datetime(raw_date)
        clean_date = dt.strftime("%Y-%m-%d")
    except:
        clean_date = str(raw_date)

    date_records.append((clean_date, sid))

date_records = sorted(date_records, key=lambda x: x[0])

date_options = [d[0] for d in date_records]
survey_lookup = {d[0]: d[1] for d in date_records}

selected_dates = st.sidebar.multiselect(
    "Select Survey Dates",
    date_options,
    default=date_options[-1:]
)

# -----------------------------
# STYLE TRANSECTS
# -----------------------------
gdf["color"] = gdf["transect_id"].apply(
    lambda x: [220, 60, 60] if x == selected_transect else [0, 180, 220]
)

gdf["width"] = gdf["transect_id"].apply(
    lambda x: 50 if x == selected_transect else 12
)

gdf["coordinates"] = gdf.geometry.apply(
    lambda geom: list(map(list, geom.coords))
)

# -----------------------------
# AUTO-ZOOM
# -----------------------------
selected_geom = gdf[gdf["transect_id"] == selected_transect].geometry.iloc[0]
centroid = selected_geom.centroid

# -----------------------------
# MAP
# -----------------------------
layer = pdk.Layer(
    "PathLayer",
    data=gdf,
    get_path="coordinates",
    get_width="width",
    get_color="color",
    pickable=True,
)

view_state = pdk.ViewState(
    latitude=centroid.y,
    longitude=centroid.x,
    zoom=14,
    pitch=0,
)

deck = pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    map_style="mapbox://styles/mapbox/satellite-v9",
    tooltip={"text": "Transect: {transect_id}"},
)

st.pydeck_chart(deck)

# -----------------------------
# PROFILE PLOT
# -----------------------------
if selected_dates:

    fig, ax = plt.subplots(figsize=(9, 5))

    colors = plt.cm.cividis(np.linspace(0, 1, len(selected_dates)))

    all_station = []
    all_elev = []

    for i, d in enumerate(selected_dates):
        sid = survey_lookup[d]
        data = transect_surveys[sid]

        station = data["station"]
        elev = data["elev"]

        ax.plot(
            station,
            elev,
            label=d,
            color=colors[i],
            linewidth=2
        )

        all_station.extend(station)
        all_elev.extend(elev)

    ax.set_xlim(min(all_station), max(all_station))
    ax.set_ylim(min(all_elev), max(all_elev))

    ax.set_xlabel("Cross-shore Distance (m)")
    ax.set_ylabel("Elevation (m)")
    ax.set_title(f"Transect {selected_transect}")

    ax.grid(True, linestyle="--", alpha=0.3)

    if len(selected_dates) <= 8:
        ax.legend(fontsize=8, frameon=False)
    else:
        ax.legend(fontsize=7, ncol=2, frameon=False)

    st.pyplot(fig)

    # DOWNLOAD
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    buf.seek(0)

    st.download_button(
        label="Download Plot as PNG",
        data=buf,
        file_name=f"{selected_transect}_profiles.png",
        mime="image/png"
    )

# -----------------------------
# FOOTER
# -----------------------------
st.markdown(
    """
    <hr>
    <div style="text-align: center; font-size: 12px; color: #555;">
        By Dakota Fee | dakotafee@ucsb.edu
    </div>
    """,
    unsafe_allow_html=True
)