# src/callbacks.py
from dash import Input, Output, no_update
import pandas as pd
import plotly.express as px


def register_callbacks(app, wales_df, wales_df_long):
    """
    Register all Dash callbacks.

    Parameters
    ----------
    app : dash.Dash
        Your Dash app instance.
    wales_df : pd.DataFrame
        Original wide dataframe (columns include pollutants like 'NO2', 'O3', etc.)
    wales_df_long : pd.DataFrame
        Long dataframe with columns: date, site, site_id, code, pollutants, value
    """

    @app.callback(
        Output("site_drop", "value"),
        Output("pol_drop", "value"),
        Output("date_range", "start_date"),
        Output("date_range", "end_date"),
        Input("reset_btn", "n_clicks"),
        prevent_initial_call=True
    )
    def reset_filters(n):
        # Clear all selections
        return [], None, None, None

    @app.callback(
        Output("site_drop", "options"),
        Input("pol_drop", "value"),
        Input("date_range", "start_date"),
        Input("date_range", "end_date"),
    )
    def update_site_dropdown(pollutant, start_date, end_date):
        df = wales_df_long.copy()

        if pollutant:
            df = df[df["pollutants"] == pollutant]

        if start_date and end_date:
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            df = df[(df["date"] >= start_dt) & (df["date"] <= end_dt)]

        return sorted(df["site"].unique())

    @app.callback(
        Output("pol_drop", "options"),
        Input("site_drop", "value"),
        Input("date_range", "start_date"),
        Input("date_range", "end_date"),
    )
    def update_pollutant_dropdown(sites, start_date, end_date):
        df = wales_df_long.copy()

        if sites:
            df = df[df["site"].isin(sites)]

        if start_date and end_date:
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            df = df[(df["date"] >= start_dt) & (df["date"] <= end_dt)]

        return sorted(df["pollutants"].unique())

    @app.callback(
        Output("date_range", "min_date_allowed"),
        Output("date_range", "max_date_allowed"),
        Input("site_drop", "value"),
        Input("pol_drop", "value"),
    )
    def update_date_picker(sites, pollutant):
        df = wales_df_long.copy()

        if sites:
            df = df[df["site"].isin(sites)]

        if pollutant:
            df = df[df["pollutants"] == pollutant]

        if df.empty:
            return (
                wales_df_long["date"].min().date(),
                wales_df_long["date"].max().date(),
            )

        return (
            df["date"].min().date(),
            df["date"].max().date(),
        )

    @app.callback(
        Output("controls-and-graph", "figure"),
        Input("site_drop", "value"),
        Input("pol_drop", "value"),
        Input("date_range", "start_date"),
        Input("date_range", "end_date"),
    )
    def update_graph(selected_sites, pollutant, start_date, end_date):
        if not selected_sites or not pollutant or not start_date or not end_date:
            return px.line(title="Select sites and date range")

        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)

        df = wales_df[
            (wales_df["site"].isin(selected_sites)) &
            (wales_df["date"] >= start_dt) &
            (wales_df["date"] <= end_dt)
        ].copy()

        if df.empty:
            return px.line(title="No data for this selection")

        df = df.sort_values(["site", "date"])

        fig = px.line(df, x="date", y=pollutant, color="site")
        fig.update_traces(connectgaps=False)
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title=f"{pollutant} (µg/m³)",
        )
        return fig