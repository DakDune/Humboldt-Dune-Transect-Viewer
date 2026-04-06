from pathlib import Path
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString
import streamlit as st


# -----------------------------
# CONFIG
# -----------------------------
DATA_PATH = Path("data/MasterTransects.xlsx")

# Your CRS (UTM Zone 10N)
CRS_UTM = "EPSG:6339"
CRS_WGS84 = "EPSG:4326"


# -----------------------------
# COLUMN CLEANING
# -----------------------------
def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    # handle duplicates like "transect"
    df = df.loc[:, ~df.columns.duplicated()]

    return df


# -----------------------------
# SPLIT INTO SURVEYS
# -----------------------------
def split_surveys(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Ensure numeric
    df["station"] = pd.to_numeric(df["station"], errors="coerce")

    # New survey when station == 0
    df["new_survey"] = df["station"] == 0
    df["survey_id"] = df["new_survey"].cumsum()

    return df


# -----------------------------
# GET LONGEST SURVEY (FOR GEOMETRY)
# -----------------------------
def get_longest_survey(df: pd.DataFrame) -> pd.DataFrame:
    grouped = df.groupby("survey_id")

    # Choose survey with max station extent (better than count)
    survey_lengths = grouped["station"].max()

    best_id = survey_lengths.idxmax()

    return grouped.get_group(best_id)


# -----------------------------
# BUILD LINESTRING
# -----------------------------
def build_linestring(df: pd.DataFrame) -> LineString:
    # Drop NaNs just in case
    df = df.dropna(subset=["easting", "northing"])

    coords = list(zip(df["easting"], df["northing"]))

    return LineString(coords)


# -----------------------------
# MAIN LOADER
# -----------------------------
@st.cache_data
def load_transect_data():
    """
    Returns:
        transects_gdf: GeoDataFrame (one line per transect)
        survey_dict: dict with survey data per transect
    """

    xls = pd.ExcelFile(DATA_PATH)

    transect_records = []
    survey_dict = {}

    for sheet in xls.sheet_names:

        df = xls.parse(sheet)

        df = clean_columns(df)

        # Skip empty sheets
        if "station" not in df.columns:
            continue

        df = split_surveys(df)

        # -------------------------
        # GEOMETRY (longest survey)
        # -------------------------
        try:
            longest = get_longest_survey(df)
            line = build_linestring(longest)

            transect_records.append({
                "transect_id": sheet,
                "geometry": line
            })
        except Exception as e:
            print(f"Skipping {sheet}: {e}")
            continue

        # -------------------------
        # STORE SURVEY DATA
        # -------------------------
        survey_dict[sheet] = {}

        for sid, group in df.groupby("survey_id"):

            # Skip empty junk
            if group["station"].isna().all():
                continue

            # Date handling (robust)
            date_val = None
            if "date" in group.columns:
                date_val = group["date"].iloc[0]
            elif "date_recorded" in group.columns:
                date_val = group["date_recorded"].iloc[0]

            survey_dict[sheet][sid] = {
                "date": date_val,
                "station": group["station"].values,
                "elev": group["elev_m"].values
            }

    # -----------------------------
    # BUILD GEODATAFRAME
    # -----------------------------
    transects_gdf = gpd.GeoDataFrame(
        transect_records,
        geometry="geometry",
        crs=CRS_UTM
    )

    # Convert to lat/lon for map
    transects_gdf = transects_gdf.to_crs(CRS_WGS84)

    return transects_gdf, survey_dict