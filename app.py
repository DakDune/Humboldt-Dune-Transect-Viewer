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
# FORCE BACKGROUND + STYLE
# -----------------------------
def apply_styling(image_path):
    if image_path.exists():
        with open(image_path, "rb") as img_file:
            b64 = base64.b64encode(img_file.read()).decode()

        background_css = f"""
        <style>

        /* TRUE ROOT BACKGROUND */
        .stApp {{
            background-image: linear-gradient(
                rgba(240, 248, 255, 0.75),
                rgba(240, 248, 255, 0.75)
            ), url("data:image/jpg;base64,{b64}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}

        /* MAIN CONTENT CARD */
        [data-testid="stAppViewContainer"] {{
            background: transparent;
        }}

        .block-container {{
            background-color: rgba(255, 255, 255, 0.85);
            padding: 2rem;
            border-radius: 12px;
        }}

        /* SIDEBAR */
        section[data-testid="stSidebar"] {{
            background: linear-gradient(
                to bottom,
                #f0f6ff,
                #ffffff
            );
            border-right: 1px solid #d6e4f0;
        }}

        /* TITLE */
        h1 {{
            color: #1f4e79;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}

        /* SUBHEADERS */
        h2, h3 {{
            color: #2c6da4;
        }}

        /* BUTTON */
        .stDownloadButton > button {{
            background-color: #2c6da4;
            color: white;
            border-radius: 6px;
            border: none;
        }}

        </style>
        """
        st.markdown(background_css, unsafe_allow_html=True)

# Apply styling
apply_styling(Path("assets/background.jpg"))

# -----------------------------
# TITLE
# -----------------------------
st.markdown(
    "<h1 style='text-align:center;'>Humboldt Dunes Cross Shore Profile Viewer</h1>",
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
    try:
        clean_date = pd.to_datetime(data["date"]).strftime("%Y-%m-%d")
    except:
        clean_date = str(data["date"])
    date_records.append((clean_date, sid))

date_records = sorted(date_records)

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
    lambda x: [255, 80, 80] if x == selected_transect else [0, 160, 200]
)

gdf["width"] = gdf["transect_id"].apply(
    lambda x: 60 if x == selected_transect else 15
)

gdf["coordinates"] = gdf.geometry.apply(
    lambda geom: list(map(list, geom.coords))
)

# -----------------------------
# AUTO-ZOOM
# -----------------------------
geom = gdf[gdf["transect_id"] == selected_transect].geometry.iloc[0]
centroid = geom.centroid

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
)

deck = pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    map_style="mapbox://styles/mapbox/satellite-v9",
    tooltip={"text": "Transect: {transect_id}"}
)

st.pydeck_chart(deck)

# -----------------------------
# PLOT
# -----------------------------
if selected_dates:

    fig, ax = plt.subplots(figsize=(9, 5))

    colors = plt.cm.cividis(np.linspace(0, 1, len(selected_dates)))

    all_s, all_e = [], []

    for i, d in enumerate(selected_dates):
        sid = survey_lookup[d]
        data = transect_surveys[sid]

        s = data["station"]
        e = data["elev"]

        ax.plot(s, e, color=colors[i], linewidth=2, label=d)

        all_s.extend(s)
        all_e.extend(e)

    ax.set_xlim(min(all_s), max(all_s))
    ax.set_ylim(min(all_e), max(all_e))

    ax.set_xlabel("Cross-shore Distance (m)")
    ax.set_ylabel("Elevation (m)")
    ax.set_title(f"Transect {selected_transect}")

    ax.grid(True, linestyle="--", alpha=0.3)

    if len(selected_dates) <= 8:
        ax.legend(frameon=False, fontsize=8)
    else:
        ax.legend(frameon=False, fontsize=7, ncol=2)

    st.pyplot(fig)

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    buf.seek(0)

    st.download_button(
        "Download Plot",
        buf,
        f"{selected_transect}.png",
        "image/png"
    )

# -----------------------------
# FOOTER
# -----------------------------
st.markdown(
    "<hr><div style='text-align:center;color:#555;font-size:12px;'>By Dakota Fee | dakotafee@ucsb.edu</div>",
    unsafe_allow_html=True
)