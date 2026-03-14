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


def get_yesterday() -> pd.Timestamp:
    return pd.Timestamp(datetime.now().date() - timedelta(days=1)).normalize()


def normalise_date_column(df: pd.DataFrame) -> pd.DataFrame:
    """Parse date column to datetime, preserving hourly timestamps."""
    if "date" not in df.columns:
        return df

    try:
        df["date"] = pd.to_datetime(df["date"], unit="s", origin="unix")
    except Exception:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Do NOT call .dt.normalize() — preserve the time component
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
            # Parse to datetime but preserve hourly timestamps — no .dt.normalize()
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df

    if os.path.exists(BASE_FILE):
        shutil.copy(BASE_FILE, LIVE_FILE)
        df = pd.read_parquet(LIVE_FILE)
        if "date" in df.columns:
            # Parse to datetime but preserve hourly timestamps — no .dt.normalize()
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df

    return pd.DataFrame(columns=COLS_TO_KEEP)


# DATE LOGIC

def get_missing_dates(existing_df: pd.DataFrame) -> list[pd.Timestamp]:
    yesterday = get_yesterday()

    if existing_df.empty or "date" not in existing_df.columns:
        return [yesterday]

    dates = pd.to_datetime(existing_df["date"], errors="coerce").dropna()
    if dates.empty:
        return [yesterday]

    max_date = dates.max().normalize()

    if max_date >= yesterday:
        return []

    return list(
        pd.date_range(
            start=max_date + pd.Timedelta(days=1),
            end=yesterday,
            freq="D"
        )
    )


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


def fetch_dates_from_defra(metadata_df: pd.DataFrame, dates_to_fetch: list[pd.Timestamp]) -> pd.DataFrame:
    if not dates_to_fetch:
        return pd.DataFrame(columns=COLS_TO_KEEP)

    site_name_map = get_site_name_map(metadata_df)
    years_needed = sorted({d.year for d in dates_to_fetch})
    target_dates_set = {pd.Timestamp(d).normalize() for d in dates_to_fetch}

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

            # Compare date part only — do NOT overwrite the hourly timestamp
            df = df[df["date"].dt.normalize().isin(target_dates_set)]

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
    dates_fetched: list[pd.Timestamp]
) -> pd.DataFrame:
    refresh_set = {pd.Timestamp(d).normalize() for d in dates_fetched}

    if existing_df.empty:
        merged = new_df.copy()
    else:
        existing_df = existing_df.copy()
        # Parse to datetime preserving hours — no .dt.normalize() on the column itself
        existing_df["date"] = pd.to_datetime(
            existing_df["date"], errors="coerce")
        # Use .dt.normalize() only for the comparison, not to overwrite the column
        existing_df = existing_df[~existing_df["date"].dt.normalize().isin(
            refresh_set)]
        merged = pd.concat([existing_df, new_df], ignore_index=True)

    # Dedup on date + site_id — safe now because date includes time, so hourly rows are unique
    dedupe_cols = [c for c in ["date", "site_id", "code"]
                   if c in merged.columns]
    if dedupe_cols:
        merged = merged.drop_duplicates(subset=dedupe_cols, keep="last")

    sort_cols = [c for c in ["date", "site_id"] if c in merged.columns]
    if sort_cols:
        merged = merged.sort_values(sort_cols).reset_index(drop=True)

    return merged


# Main Refresh
def refresh_live_data() -> pd.DataFrame:
    ensure_data_dir()

    metadata_df = load_metadata()
    existing_df = load_or_create_live_file()
    dates_to_fetch = get_missing_dates(existing_df)

    if not dates_to_fetch:
        print("Live dataset is up to date.")
        return existing_df

    print("Fetching missing dates:", [
          d.strftime("%Y-%m-%d") for d in dates_to_fetch])

    new_df = fetch_dates_from_defra(metadata_df, dates_to_fetch)

    # Important: do NOT overwrite good data with an empty update
    if new_df.empty:
        print("No new rows were fetched. Keeping existing live dataset unchanged.")
        return existing_df

    updated_df = merge_new_data(existing_df, new_df, dates_to_fetch)
    updated_df.to_parquet(LIVE_FILE, index=False)
    print(f"Updated live dataset saved to: {LIVE_FILE}")

    return updated_df
