import os
import re
from io import BytesIO

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

from utils.data_loader import load_transect_data


# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(layout="wide", page_title="Dune Transect Viewer")


# -----------------------------
# STYLING
# -----------------------------
st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(180deg, #eef6fb 0%, #f8fbfd 100%);
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #e7f1f8 0%, #f7fbfe 100%);
        border-right: 1px solid #d6e4ee;
    }

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }

    h1, h2, h3 {
        color: #1f4e79;
    }

    .trend-box {
        background: #ffffff;
        border: 1px solid #d9e6ef;
        border-left: 6px solid #2c6da4;
        border-radius: 10px;
        padding: 0.9rem 1rem;
        margin: 0.8rem 0 1rem 0;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }

    .trend-label {
        font-size: 0.8rem;
        color: #5a6c7d;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 0.2rem;
    }

    .trend-value {
        font-size: 1.2rem;
        color: #173a59;
        font-weight: 700;
    }

    .trend-note {
        font-size: 0.9rem;
        color: #4f6272;
        margin-top: 0.2rem;
    }

    .stDownloadButton > button {
        background-color: #2c6da4;
        color: white;
        border: none;
        border-radius: 8px;
    }

    .stDownloadButton > button:hover {
        background-color: #235781;
        color: white;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    "<h1 style='text-align:center; margin-bottom: 0.2rem;'>Dune Transect Viewer</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align:center; color:#5f7386; margin-top:0;'>Interactive Humboldt dune transect profiles and shoreline context</p>",
    unsafe_allow_html=True,
)


# -----------------------------
# MAPBOX TOKEN
# -----------------------------
os.environ["MAPBOX_API_KEY"] = st.secrets["MAPBOX_API_KEY"]


# -----------------------------
# LOAD DATA
# -----------------------------
gdf, survey_dict, transect_summary_df = load_transect_data()


# -----------------------------
# HELPERS
# -----------------------------
def sort_key(x):
    match = re.match(r"T(\d+)", str(x))
    if match:
        return (0, int(match.group(1)))
    return (1, str(x))


def compute_shoreline_trend(summary_df: pd.DataFrame, transect_id: str):
    if summary_df.empty:
        return None

    df = summary_df[summary_df["transect_id"].astype(str) == str(transect_id)].copy()

    required_cols = {"survey_date", "shoreline_station_m"}
    if not required_cols.issubset(df.columns):
        return None

    df = df.dropna(subset=["survey_date", "shoreline_station_m"]).sort_values("survey_date")

    if len(df) < 2:
        return None

    decimal_year = (
        df["survey_date"].dt.year
        + (df["survey_date"].dt.dayofyear - 1) / 365.25
    )

    slope, intercept = np.polyfit(decimal_year, df["shoreline_station_m"], 1)

    start_year = int(df["survey_date"].dt.year.min())
    end_year = int(df["survey_date"].dt.year.max())

    return {
        "slope_m_per_yr": slope,
        "start_year": start_year,
        "end_year": end_year,
        "n_surveys": len(df),
    }


# -----------------------------
# TRANSECT SORTING
# -----------------------------
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
    index=transect_ids.index(st.session_state.selected_transect),
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
        clean_date = pd.to_datetime(raw_date).strftime("%Y-%m-%d")
    except Exception:
        clean_date = str(raw_date)
    date_records.append((clean_date, sid))

date_records = sorted(date_records, key=lambda x: x[0])

date_options = [d[0] for d in date_records]
survey_lookup = {d[0]: d[1] for d in date_records}

selected_dates = st.sidebar.multiselect(
    "Select Survey Dates",
    date_options,
    default=date_options[-1:] if date_options else [],
)


# -----------------------------
# MAP STYLING
# -----------------------------
gdf["color"] = gdf["transect_id"].apply(
    lambda x: [217, 72, 72] if x == selected_transect else [30, 136, 168]
)

gdf["width"] = gdf["transect_id"].apply(
    lambda x: 60 if x == selected_transect else 16
)

gdf["coordinates"] = gdf.geometry.apply(lambda geom: list(map(list, geom.coords)))


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

st.pydeck_chart(deck, use_container_width=True)


# -----------------------------
# SHORELINE TREND BOX
# -----------------------------
trend_result = compute_shoreline_trend(transect_summary_df, selected_transect)

if trend_result is not None:
    slope = trend_result["slope_m_per_yr"]
    slope_str = f"{slope:+.2f} m/yr"
    year_label = f"{trend_result['start_year']}–{trend_result['end_year']}"

    st.markdown(
        f"""
        <div class="trend-box">
            <div class="trend-label">Shoreline trend</div>
            <div class="trend-value">{year_label}: {slope_str}</div>
            <div class="trend-note">
                Computed from shoreline_station_m in transect_per_survey
                using {trend_result['n_surveys']} surveys.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------
# PROFILE PLOT
# -----------------------------
if selected_dates:
    fig, ax = plt.subplots(figsize=(9, 5.2))

    colors = plt.cm.cividis(np.linspace(0.12, 0.92, len(selected_dates)))

    all_station = []
    all_elev = []

    for i, d in enumerate(selected_dates):
        sid = survey_lookup[d]
        data = transect_surveys[sid]

        station = np.asarray(data["station"], dtype=float)
        elev = np.asarray(data["elev"], dtype=float)

        valid = np.isfinite(station) & np.isfinite(elev)
        station = station[valid]
        elev = elev[valid]

        if len(station) == 0:
            continue

        ax.plot(
            station,
            elev,
            label=d,
            color=colors[i],
            linewidth=2.1,
        )

        all_station.extend(station.tolist())
        all_elev.extend(elev.tolist())

    if all_station and all_elev:
        ax.set_xlim(min(all_station), max(all_station))
        ax.set_ylim(min(all_elev), max(all_elev))

    ax.set_xlabel("Cross-shore Distance (m)")
    ax.set_ylabel("Elevation (m)")
    ax.set_title(f"Transect {selected_transect}", fontsize=13, color="#173a59")

    ax.grid(True, linestyle="--", alpha=0.28)
    ax.set_facecolor("#fcfeff")
    for spine in ax.spines.values():
        spine.set_color("#b8cad6")

    # Shoreline trend annotation inside plot
    if trend_result is not None:
        slope = trend_result["slope_m_per_yr"]
        year_label = f"{trend_result['start_year']}–{trend_result['end_year']}"
        annotation = f"{year_label} shoreline trend: {slope:+.2f} m/yr"

        ax.text(
            0.015,
            0.97,
            annotation,
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=9.5,
            color="#173a59",
            bbox=dict(
                boxstyle="round,pad=0.3",
                facecolor="white",
                edgecolor="#c6d7e2",
                alpha=0.95,
            ),
        )

    if len(selected_dates) <= 8:
        ax.legend(fontsize=8, frameon=False)
    else:
        ax.legend(fontsize=7, ncol=2, frameon=False)

    st.pyplot(fig, use_container_width=True)

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    buf.seek(0)

    st.download_button(
        label="Download Plot as PNG",
        data=buf,
        file_name=f"{selected_transect}_profiles.png",
        mime="image/png",
    )


# -----------------------------
# FOOTER
# -----------------------------
st.markdown(
    """
    <hr>
    <div style="text-align:center; font-size:12px; color:#5c7080;">
        By Dakota Fee | dakotafee@ucsb.edu
    </div>
    """,
    unsafe_allow_html=True,
)