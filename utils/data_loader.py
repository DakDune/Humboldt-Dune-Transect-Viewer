from pathlib import Path
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString
import streamlit as st


# -----------------------------
# CONFIG
# -----------------------------
DATA_PATH = Path("data/MasterTransects.xlsx")

# Your CRS
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
        .str.replace(" ", "_", regex=False)
    )

    # Handle duplicate column names
    df = df.loc[:, ~df.columns.duplicated()]

    return df


# -----------------------------
# SPLIT INTO SURVEYS
# -----------------------------
def split_surveys(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["station"] = pd.to_numeric(df["station"], errors="coerce")

    # New survey begins when station resets to 0
    df["new_survey"] = df["station"] == 0
    df["survey_id"] = df["new_survey"].cumsum()

    return df


# -----------------------------
# GET LONGEST SURVEY
# -----------------------------
def get_longest_survey(df: pd.DataFrame) -> pd.DataFrame:
    grouped = df.groupby("survey_id")
    survey_lengths = grouped["station"].max()
    best_id = survey_lengths.idxmax()
    return grouped.get_group(best_id)


# -----------------------------
# BUILD LINESTRING
# -----------------------------
def build_linestring(df: pd.DataFrame) -> LineString:
    df = df.dropna(subset=["easting", "northing"]).copy()
    coords = list(zip(df["easting"], df["northing"]))

    if len(coords) < 2:
        raise ValueError("Not enough valid coordinates to build LineString.")

    return LineString(coords)


# -----------------------------
# PARSE TRANSECT SUMMARY SHEET
# -----------------------------
def parse_transect_summary(xls: pd.ExcelFile) -> pd.DataFrame:
    sheet_name = None
    for s in xls.sheet_names:
        if s.strip().lower() == "transect_per_survey":
            sheet_name = s
            break

    if sheet_name is None:
        return pd.DataFrame()

    df = xls.parse(sheet_name)
    df = clean_columns(df)

    # Standardize transect id
    if "transect" in df.columns:
        df["transect_id"] = df["transect"].astype(str).str.strip()
    elif "transect_id" in df.columns:
        df["transect_id"] = df["transect_id"].astype(str).str.strip()
    else:
        return pd.DataFrame()

    # Standardize date
    if "date" in df.columns:
        df["survey_date"] = pd.to_datetime(df["date"], errors="coerce")
    elif "date_recorded" in df.columns:
        df["survey_date"] = pd.to_datetime(df["date_recorded"], errors="coerce")
    else:
        df["survey_date"] = pd.NaT

    numeric_cols = [
        "toe_station_m",
        "toe_elev_m",
        "toe_easting",
        "toe_northing",
        "shoreline_station_m",
        "shoreline_easting",
        "shoreline_northing",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    keep_cols = ["transect_id", "survey_date"] + [c for c in numeric_cols if c in df.columns]
    return df[keep_cols].copy()


# -----------------------------
# MAIN LOADER
# -----------------------------
@st.cache_data
def load_transect_data():
    """
    Returns:
        transects_gdf: GeoDataFrame (one line per transect)
        survey_dict: dict with survey data per transect
        transect_summary_df: DataFrame from transect_per_survey
    """
    xls = pd.ExcelFile(DATA_PATH)

    transect_records = []
    survey_dict = {}

    # Parse summary sheet once
    transect_summary_df = parse_transect_summary(xls)

    for sheet in xls.sheet_names:
        if sheet.strip().lower() == "transect_per_survey":
            continue

        df = xls.parse(sheet)
        df = clean_columns(df)

        # Skip non-profile sheets
        if "station" not in df.columns:
            continue

        df = split_surveys(df)

        # -------------------------
        # GEOMETRY (longest survey)
        # -------------------------
        try:
            longest = get_longest_survey(df)
            line = build_linestring(longest)

            transect_records.append(
                {
                    "transect_id": sheet,
                    "geometry": line,
                }
            )
        except Exception as e:
            print(f"Skipping {sheet}: {e}")
            continue

        # -------------------------
        # STORE SURVEY DATA
        # -------------------------
        survey_dict[sheet] = {}

        for sid, group in df.groupby("survey_id"):
            if group["station"].isna().all():
                continue

            date_val = None
            if "date" in group.columns:
                date_val = group["date"].iloc[0]
            elif "date_recorded" in group.columns:
                date_val = group["date_recorded"].iloc[0]

            survey_dict[sheet][sid] = {
                "date": date_val,
                "station": group["station"].values,
                "elev": group["elev_m"].values if "elev_m" in group.columns else None,
            }

    transects_gdf = gpd.GeoDataFrame(
        transect_records,
        geometry="geometry",
        crs=CRS_UTM,
    )

    transects_gdf = transects_gdf.to_crs(CRS_WGS84)

    return transects_gdf, survey_dict, transect_summary_df