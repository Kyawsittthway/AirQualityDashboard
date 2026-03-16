import rdata
import requests
import pyreadr
import pandas as pd
from datetime import datetime, timedelta
import shutil
import os
import warnings
warnings.filterwarnings(
    "ignore", message='Missing constructor for R class "POSIXct".*')
warnings.filterwarnings(
    "ignore", message='Missing constructor for R class "POSIXt".*')


# CONFIG

COLS_TO_KEEP = ['date', 'site', 'site_id', 'NO2', 'PM10', 'SO2', 'O3', 'PM2.5', 'wd',
                'ws', 'temp']


WALES_ACTIVE_SITE_IDS = ['AH', 'CARD', 'CNPR', 'CHP', 'CWMC', 'CAEB', 'PEMB', 'NPT3', 'PT4',
                         'SWA1', 'WREX']

URL_BASE = "https://uk-air.defra.gov.uk/openair/R_data/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

DATA_DIR = "data"
METADATA_FILE = os.path.join(DATA_DIR, "AURN_metadata.RData")
BASE_FILE = os.path.join(DATA_DIR, "base_air_quality.parquet")
LIVE_FILE = os.path.join(DATA_DIR, "live_air_quality.parquet")


# HELPERS

def ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def get_yesterday_end() -> pd.Timestamp:
    """Returns the last hour of yesterday, e.g. 2026-03-13 23:00:00."""
    return pd.Timestamp(datetime.now().date() - timedelta(days=1)).replace(hour=23, minute=0)


def normalise_date_column(df: pd.DataFrame) -> pd.DataFrame:
    """Parse date column to datetime, preserving hourly timestamps."""
    if "date" not in df.columns:
        return df

    try:
        df["date"] = pd.to_datetime(df["date"], unit="s", origin="unix")
    except Exception:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    return df


# METADATA

def load_metadata() -> pd.DataFrame:
    ensure_data_dir()

    if not os.path.exists(METADATA_FILE):
        metadata_url = f"{URL_BASE}AURN_metadata.RData"
        response = requests.get(metadata_url, headers=HEADERS, timeout=30)
        response.raise_for_status()

        with open(METADATA_FILE, "wb") as f:
            f.write(response.content)

    metadata = pyreadr.read_r(METADATA_FILE)
    metadata_df = metadata["AURN_metadata"]

    return metadata_df


def get_site_name_map(metadata_df: pd.DataFrame) -> dict:
    if "site_name" in metadata_df.columns:
        return (
            metadata_df[["site_id", "site_name"]]
            .drop_duplicates()
            .set_index("site_id")["site_name"]
            .to_dict()
        )
    if "site" in metadata_df.columns:
        return (
            metadata_df[["site_id", "site"]]
            .drop_duplicates()
            .set_index("site_id")["site"]
            .to_dict()
        )
    return {}


# LIVE FILE MANAGEMENT

def load_or_create_live_file() -> pd.DataFrame:
    ensure_data_dir()

    if os.path.exists(LIVE_FILE):
        df = pd.read_parquet(LIVE_FILE)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df

    if os.path.exists(BASE_FILE):
        shutil.copy(BASE_FILE, LIVE_FILE)
        df = pd.read_parquet(LIVE_FILE)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df

    return pd.DataFrame(columns=COLS_TO_KEEP)


# DATE LOGIC

def get_missing_info(existing_df: pd.DataFrame) -> tuple[pd.Timestamp | None, list[int]]:
    """
    Returns (cutoff_datetime, years_needed).
    - cutoff_datetime: the max datetime already in the dataset; fetch everything after this.
    - years_needed: list of years to download from DEFRA.
    Returns (None, []) if the dataset is already up to date.
    """
    yesterday_end = get_yesterday_end()

    if existing_df.empty or "date" not in existing_df.columns:
        return None, [yesterday_end.year]

    dates = pd.to_datetime(existing_df["date"], errors="coerce").dropna()
    if dates.empty:
        return None, [yesterday_end.year]

    max_dt = dates.max()

    if max_dt >= yesterday_end:
        return None, []  # already up to date

    years_needed = list(range(max_dt.year, yesterday_end.year + 1))
    return max_dt, years_needed


# DEFRA FETCHING

def looks_like_html(content: bytes) -> bool:
    sample = content[:500].lower()
    return b"<html" in sample or b"<!doctype html" in sample


def fetch_site_year_rdata(site_id: str, year: int) -> pd.DataFrame | None:
    """
    Download and parse one DEFRA site-year RData file using rdata.
    """
    fn = f"{site_id}_{year}.RData"
    url = f"{URL_BASE}{fn}"

    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()

        content = response.content
        if not content:
            print(f"Empty response for {fn}")
            return None

        if looks_like_html(content):
            print(
                f"{fn} is not an RData file (HTML returned instead). Check site_id.")
            return None

        parsed = rdata.parser.parse_data(content)
        converted = rdata.conversion.convert(parsed)

        key = fn.replace(".RData", "")
        if key not in converted:
            print(
                f"{key} not found inside {fn}. Available keys: {list(converted.keys())}")
            return None

        df = converted[key]
        df["site_id"] = site_id
        return df

    except Exception as e:
        print(f"Error processing {fn}: {e}")
        return None


def fetch_dates_from_defra(
    metadata_df: pd.DataFrame,
    cutoff_dt: pd.Timestamp | None,
    years_needed: list[int]
) -> pd.DataFrame:
    """
    Fetch all hourly rows after cutoff_dt and up to end of yesterday.
    If cutoff_dt is None, fetches all rows up to end of yesterday.
    """
    if not years_needed:
        return pd.DataFrame(columns=COLS_TO_KEEP)

    yesterday_end = get_yesterday_end()
    site_name_map = get_site_name_map(metadata_df)
    dfs = []

    for site_id in WALES_ACTIVE_SITE_IDS:
        for year in years_needed:
            df = fetch_site_year_rdata(site_id, year)
            if df is None or df.empty:
                continue

            if "site" not in df.columns:
                df["site"] = site_name_map.get(site_id)

            df = normalise_date_column(df)

            if "date" not in df.columns:
                continue

            # Filter: strictly after the cutoff hour, up to end of yesterday
            if cutoff_dt is not None:
                df = df[df["date"] > cutoff_dt]
            df = df[df["date"] <= yesterday_end]

            if df.empty:
                continue

            df = df[[c for c in COLS_TO_KEEP if c in df.columns]]
            dfs.append(df)

    if not dfs:
        return pd.DataFrame(columns=COLS_TO_KEEP)

    return pd.concat(dfs, ignore_index=True)


# MERGING

def merge_new_data(
    existing_df: pd.DataFrame,
    new_df: pd.DataFrame,
    cutoff_dt: pd.Timestamp | None
) -> pd.DataFrame:
    """
    Keep existing rows up to and including cutoff_dt, then append new rows.
    """
    if existing_df.empty:
        merged = new_df.copy()
    else:
        existing_df = existing_df.copy()
        existing_df["date"] = pd.to_datetime(
            existing_df["date"], errors="coerce")
        if cutoff_dt is not None:
            # Retain everything up to and including the cutoff point
            existing_df = existing_df[existing_df["date"] <= cutoff_dt]
        merged = pd.concat([existing_df, new_df], ignore_index=True)

    dedupe_cols = [c for c in ["date", "site_id", "code"]
                   if c in merged.columns]
    if dedupe_cols:
        merged = merged.drop_duplicates(subset=dedupe_cols, keep="last")

    sort_cols = [c for c in ["date", "site_id"] if c in merged.columns]
    if sort_cols:
        merged = merged.sort_values(sort_cols).reset_index(drop=True)

    return merged


# MAIN

def refresh_live_data() -> pd.DataFrame:
    ensure_data_dir()

    metadata_df = load_metadata()
    existing_df = load_or_create_live_file()
    cutoff_dt, years_needed = get_missing_info(existing_df)

    if not years_needed:
        print("Live dataset is up to date.")
        return existing_df

    print(f"Fetching data after: {cutoff_dt} for years: {years_needed}")

    new_df = fetch_dates_from_defra(metadata_df, cutoff_dt, years_needed)

    # if no new data, dont update
    if new_df.empty:
        print("No new rows were fetched. Keeping existing live dataset unchanged.")
        return existing_df

    updated_df = merge_new_data(existing_df, new_df, cutoff_dt)
    updated_df.to_parquet(LIVE_FILE, index=False)
    print(f"Updated live dataset saved to: {LIVE_FILE}")

    return updated_df
