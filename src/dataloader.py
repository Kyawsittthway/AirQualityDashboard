import pandas as pd

def load_data():
    wales_df = pd.read_csv("wales_air_quality_data_16.csv")
    wales_df["date"] = pd.to_datetime(wales_df["date"], errors="coerce")

    pollutant_cols = ["NO2", "PM2.5", "PM10", "O3", "SO2"]

    wales_df_long = wales_df.copy().melt(
        id_vars=["date", "site", "site_id", "code"],
        value_vars=pollutant_cols,
        var_name="pollutants",
        value_name="value"
    )

    wales_df_long = wales_df_long.dropna(subset=["value"])

    return wales_df, wales_df_long