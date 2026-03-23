import pandas as pd
from utils.updater import refresh_live_data


def load_data():
    # Load the raw air quality data from CSV
    wales_df = refresh_live_data()

    # Parse the date column, coercing any unparseable values to NaT
    wales_df["date"] = pd.to_datetime(wales_df["date"], errors="coerce")

    # Pollutant columns to unpivot from wide to long format
    pollutant_cols = ["NO2", "PM2.5", "PM10", "O3", "SO2"]

    # Reshape from wide (one column per pollutant) to long format
    # (one row per site-date-pollutant combination) for easier filtering
    wales_df_long = wales_df.copy().melt(
        id_vars=["date", "site", "site_id", "wd", "ws", "temp"],
        value_vars=pollutant_cols,
        var_name="pollutants",
        value_name="value"
    )

    # Drop rows where the pollutant has no recorded measurement
    wales_df_long = wales_df_long.dropna(subset=["value"])
    #year for the exceedance calculations
    wales_df_long['year'] = wales_df_long['date'].dt.year
    return wales_df, wales_df_long
