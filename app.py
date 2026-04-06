import streamlit as st
import pydeck as pdk
from utils.data_loader import load_transect_data
import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from io import BytesIO

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(layout="wide")
st.title("Dune Transect Viewer")

# -----------------------------
# MAPBOX TOKEN
# -----------------------------
os.environ["MAPBOX_API_KEY"] = st.secrets["MAPBOX_API_KEY"]

# -----------------------------
# LOAD DATA
# -----------------------------
gdf, survey_dict = load_transect_data()

# -----------------------------
# SIDEBAR - TRANSECT
# -----------------------------
st.sidebar.header("Transect Selection")

transect_ids = sorted(gdf["transect_id"].tolist())

selected_transect = st.sidebar.selectbox(
    "Select Transect",
    transect_ids
)

# -----------------------------
# SIDEBAR - DATE SELECTION
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

# SORT DATES
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

center_lat = centroid.y
center_lon = centroid.x

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
    latitude=center_lat,
    longitude=center_lon,
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

    # PROFESSIONAL COLOR SCHEME (muted, publication-style)
    colors = plt.cm.viridis(np.linspace(0, 1, len(selected_dates)))

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

    # Fixed axes
    ax.set_xlim(min(all_station), max(all_station))
    ax.set_ylim(min(all_elev), max(all_elev))

    # Labels
    ax.set_xlabel("Cross-shore Distance (m)", fontsize=11)
    ax.set_ylabel("Elevation (m)", fontsize=11)
    ax.set_title(f"Transect {selected_transect}", fontsize=13)

    # Clean grid
    ax.grid(True, linestyle="--", alpha=0.3)

    # Cleaner legend
    if len(selected_dates) <= 8:
        ax.legend(fontsize=8, frameon=False)
    else:
        ax.legend(fontsize=7, ncol=2, frameon=False)

    st.pyplot(fig)

    # -----------------------------
    # DOWNLOAD BUTTON (PNG)
    # -----------------------------
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    buf.seek(0)

    st.download_button(
        label="Download Plot as PNG",
        data=buf,
        file_name=f"{selected_transect}_profiles.png",
        mime="image/png"
    )