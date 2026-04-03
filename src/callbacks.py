# src/callbacks.py

from dash import (
    Dash,
    html,
    dcc,
    ctx,
    callback,
    Output,
    Input,
    State,
    no_update,
    callback_context,
    clientside_callback,
    dash_table,
)
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from components.sidebar import create_sidebar
from utils.calculations import (
    calculate_exceedance,
    calculate_completeness,
    calculate_completeness_by_site,
    calculate_summary_stats,
    get_status_class,
    format_date_range,
    exceedance_summary,
    LIMITS,
    POLLUTANT_DISPLAY_NAMES,
)
from utils.logics import toggle_theme_logic, toggle_threshold_logic, update_year_logic
from datetime import date, timedelta

RATIFIED_CUTOFF = pd.Timestamp("2025-09-30 00:00:00")

# Reusable style dicts for quick-select button states
_BTN_BASE = {
    "background": "var(--bg-tertiary)",
    "borderColor": "var(--border-primary)",
    "color": "var(--text-secondary)",
    "boxShadow": "none",
    "transform": "scale(1)",
}
_BTN_ACTIVE = {
    "background": "rgba(143, 181, 105, 0.15)",
    "borderColor": "var(--sage-500)",
    "color": "var(--sage-300)",
    "boxShadow": "0 0 0 3px rgba(143, 181, 105, 0.15), 0 0 16px rgba(143, 181, 105, 0.35)",
    "transform": "scale(1.02)",
}


def get_threshold_info(pollutant, standard):
    if not pollutant or standard not in LIMITS or pollutant not in LIMITS[standard]:
        return None

    pollutant_limits = LIMITS[standard][pollutant]

    for metric in ["daily", "hourly", "8h", "annual"]:
        if metric in pollutant_limits:
            return {
                "metric": metric,
                "value": pollutant_limits[metric],
            }

    return None


@callback(
    Output("toggle-uk", "className"),
    Output("toggle-who", "className"),
    Output("threshold-store", "data"),
    Input("toggle-uk", "n_clicks"),
    Input("toggle-who", "n_clicks"),
    State("threshold-store", "data"),
)
def toggle_threshold(uk_clicks, who_clicks, current):
    ctx = callback_context

    if not ctx.triggered:
        return "toggle-option active", "toggle-option", "UK"

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    return toggle_threshold_logic(button_id, uk_clicks, who_clicks)


@callback(
    Output("toggle-dark", "className"),
    Output("toggle-light", "className"),
    Output("theme-store", "data"),
    Output("app-container", "data-theme"),
    Input("toggle-dark", "n_clicks"),
    Input("toggle-light", "n_clicks"),
    State("theme-store", "data"),
)
def toggle_theme(dark_clicks, light_clicks, current):

    ctx = callback_context
    if not ctx.triggered:
        return "toggle-option active", "toggle-option", "dark", "dark"

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    return toggle_theme_logic(dark_clicks, light_clicks, button_id)


@callback(
    Output("toggle-all", "className"),
    Output("toggle-ratified", "className"),
    Output("dq_store", "data"),
    Input("toggle-all", "n_clicks"),
    Input("toggle-ratified", "n_clicks"),
    State("dq_store", "data"),
)
def toggle_data_quality(all_clicks, ratified_clicks, current):
    """Handle All/Ratified data quality toggle."""
    if not all_clicks and not ratified_clicks:
        return "toggle-option active", "toggle-option", "All"

    triggered = callback_context.triggered
    if not triggered:
        return "toggle-option active", "toggle-option", "All"

    button_id = triggered[0]["prop_id"].split(".")[0]

    if button_id == "toggle-all":
        return "toggle-option active", "toggle-option", "All"
    else:
        return "toggle-option", "toggle-option active", "Ratified"


def register_callbacks(app, wales_df, wales_df_long):

    # Precomputed maps to reduce repetition and increase dashboard speed
    site_to_pollutants = (
        wales_df_long.groupby("site")["pollutants"].apply(set).to_dict()
    )

    site_to_dates = (
        wales_df_long.groupby("site")["date"]
        .agg(["min", "max"])
        .apply(lambda r: (r["min"].date(), r["max"].date()), axis=1)
        .to_dict()
    )

    pol_to_dates = (
        wales_df_long.groupby("pollutants")["date"]
        .agg(["min", "max"])
        .apply(lambda r: (r["min"].date(), r["max"].date()), axis=1)
        .to_dict()
    )

    site_pol_to_dates = (
        wales_df_long.groupby(["site", "pollutants"])["date"]
        .agg(["min", "max"])
        .apply(lambda r: (r["min"].date(), r["max"].date()), axis=1)
        .to_dict()
    )

    pol_to_sites = wales_df_long.groupby("pollutants")["site"].apply(set).to_dict()
    valid_rows = wales_df_long.dropna(subset=["value"]).copy()

    # get the available years for each site
    site_to_years = valid_rows.groupby("site")["year"].apply(set).to_dict()
    # get available years for each pollutant
    pollutant_to_years = valid_rows.groupby("pollutants")["year"].apply(set).to_dict()
    # get available years for each site and pollutant combo
    site_pollutant_to_years = (
        valid_rows.groupby(["site", "pollutants"])["year"].apply(set).to_dict()
    )

    # get all the unique sites and pollutants from the dataset
    all_years = sorted(y for y in valid_rows["year"].dropna().unique() if y < 2026)
    all_sites = sorted(wales_df_long["site"].unique())
    all_pollutants = sorted(wales_df_long["pollutants"].unique())

    global_min = wales_df_long["date"].min().date()
    global_max = wales_df_long["date"].max().date()
    exceedance_data = exceedance_summary(valid_rows)

    def has_full_date_range(start_date, end_date):
        return bool(start_date) and bool(end_date)

    @app.callback(
        Output("year_drop", "options"),
        Input("site_drop", "value"),
        Input("pol_drop", "value"),
        State("year_drop", "value"),
    )
    def update_year(sites, pollutant, current_years):
        return update_year_logic(
            sites,
            pollutant,
            current_years,
            all_years,
            site_to_years,
            pollutant_to_years,
            site_pollutant_to_years,
        )

    @app.callback(
        Output("exceedance_chart", "figure"),
        Input("site_drop", "value"),
        Input("pol_drop", "value"),
        Input("year_drop", "value"),
        Input("threshold-store", "data"),
    )
    def exceedance_bar(selected_sites, pollutant, selected_years, threshold_standard):
        # check if who limits selected
        who_toggle = threshold_standard == "WHO"
        # if no selection is made tell the user to select
        if not selected_sites or not pollutant or not selected_years:
            return px.bar(title="Select site, pollutant and year")
        # make sure sites are in a list
        if isinstance(selected_sites, str):
            selected_sites = [selected_sites]
        results_data = exceedance_data[
            (exceedance_data["Site"].isin(selected_sites))
            & (exceedance_data["pollutant"] == pollutant)
            & (exceedance_data["Year"].isin(selected_years))
        ].copy()
        if results_data.empty:
            return px.bar(title="No data available")
        # choose the correct columns based on uk or who limits
        if who_toggle:
            results_data["Value"] = results_data["who_value"]
            results_data["Limit"] = results_data["who_limit"]
            results_data["exceeds"] = results_data["who_exceeds"]
        else:
            results_data["Value"] = results_data["uk_value"]
            results_data["Limit"] = results_data["uk_limit"]
            results_data["exceeds"] = results_data["uk_exceeds"]
        fig = go.Figure()
        results_data = results_data.sort_values(["Site", "Year"]).reset_index(drop=True)
        # use both site and year on the axis
        x_axis = [results_data["Site"], results_data["Year_str"]]
        colours = [
            (
                "red"
                if exceeds_limit == "Above"
                else "green" if exceeds_limit == "Within" else "grey"
            )
            for exceeds_limit in results_data["exceeds"]
        ]
        # show 0 label when value is 0 as its hard to see
        results_data["label"] = results_data["Value"].apply(
            lambda x: "0" if x == 0 else ""
        )
        results_data["hover_label"] = results_data["Value"].astype(str)
        trace = go.Bar(
            x=x_axis,
            y=results_data["Value"],
            marker_color=colours,
            text=results_data["label"],
            textposition="outside",
            hovertext=results_data["hover_label"],
            hovertemplate="Site: %{x[0]}<br>Year: %{x[1]}<br>Value:%{hovertext}<extra></extra>",
        )
        trace.showlegend = False  # dont print the legend out for each individual trace
        fig.add_trace(trace)
        # add legends to state what the colours mean
        # fig.update_layout(hovermode='closest')
        fig.add_trace(
            go.Bar(x=[None], y=[None], marker_color="red", name="Above Limit")
        )
        fig.add_trace(
            go.Bar(x=[None], y=[None], marker_color="green", name="Within Limit")
        )
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="lines",
                line=dict(color="red", dash="dash"),
                name="Limit",
            )
        )
        # put the y axis labels for each pollutant which vary depending on which one is selected
        pollutant_labels_uk = {
            "PM2.5": "PM2.5 annual mean (µg/m³)",
            "PM10": f"PM10 days exceeding {LIMITS['UK']['PM10']['daily']}(µg/m³)",
            "NO2": f"NO2 hours exceeding {LIMITS['UK']['NO2']['hourly']}(µg/m³)",
            "SO2": f"SO2 days exceeding {LIMITS['UK']['SO2']['daily']}(µg/m³)",
            "O3": f"O3 days exceeding {LIMITS['UK']['O3']['8h']}(µg/m³)",
        }
        pollutant_labels_who = {
            "PM2.5": "PM2.5 annual mean (µg/m³)",
            "PM10": "PM10 annual mean (µg/m³)",
            "NO2": "NO2 annual mean(µg/m³)",
            "SO2": f"SO2 days exceeding {LIMITS['WHO']['SO2']['daily']}(µg/m³)",
            "O3": "O3 seasonal peak mean(6 months) (µg/m³)",
        }
        # choose correct y axis label depending on toggle
        if who_toggle:
            y_label = pollutant_labels_who.get(pollutant, "Value")
        else:
            y_label = pollutant_labels_uk.get(pollutant, "Value")

        fig.update_layout(
            title=f"{pollutant} Exceedance for Selected Sites",
            barmode="group",  # want a bar for each year
            yaxis_title=y_label,
        )
        unique_limits = results_data["Limit"].dropna().unique()
        if len(unique_limits) == 1 and unique_limits[0] != 0:
            fig.add_hline(y=unique_limits[0], line_dash="dash", line_color="red")
        return fig

    @app.callback(
        Output("nav-home", "className"),
        Output("nav-comparison", "className"),
        Output("nav-exceedance", "className"),
        Input("url", "pathname"),
    )
    def highlight_nav(pathname):
        # Highlights the active page in the sidebar navigation based on the current URL pathname
        pathname = pathname or "/"

        def nav_class(link_path: str) -> str:
            return "nav-link active" if pathname == link_path else "nav-link"

        return (
            nav_class("/"),
            nav_class("/comparison"),
            nav_class("/exceedance"),
        )

    # Function to compute intersection window (date-only) for current selection
    def compute_allowed_bounds(sites, pollutant):
        """Compute intersection window (date-only) for current selection."""
        sites = sites or []

        if not sites:
            if pollutant:
                return pol_to_dates.get(pollutant, (global_min, global_max))
            return global_min, global_max

        ranges = []
        for s in sites:
            if pollutant:
                key = (s, pollutant)
                if key in site_pol_to_dates:
                    ranges.append(site_pol_to_dates[key])
            else:
                if s in site_to_dates:
                    ranges.append(site_to_dates[s])

        if not ranges:
            return None, None

        min_allowed = max(r[0] for r in ranges)
        max_allowed = min(r[1] for r in ranges)

        if min_allowed > max_allowed:
            return None, None

        return min_allowed, max_allowed

    def apply_dq_cap(start_dt, end_dt, dq):
        """Cap end_dt to ratified cutoff if Ratified mode is active."""
        if dq == "Ratified":
            end_dt = min(end_dt, RATIFIED_CUTOFF)
        return start_dt, end_dt

    def filter_df(wales_df_long, sites, pollutant, start_date, end_date):
        # Filter the long-format DataFrame based on selected sites, pollutant, and date range
        dff = wales_df_long.copy()

        if sites:
            dff = dff[dff["site"].isin(sites)]

        if pollutant:
            dff = dff[dff["pollutants"] == pollutant]

        if start_date:
            dff = dff[dff["date"] >= pd.to_datetime(start_date)]

        if end_date:
            end_dt = (
                pd.to_datetime(end_date)
                + pd.Timedelta(days=1)
                - pd.Timedelta(seconds=1)
            )
            dff = dff[dff["date"] <= end_dt]

        return dff.sort_values("date")

    def get_days(start_date, end_date):
        if not start_date or not end_date:
            return None
        return max((pd.to_datetime(end_date) - pd.to_datetime(start_date)).days + 1, 1)

    def get_mode(days):
        if days <= 1:
            return "day"
        if days < 30:
            return "short"
        if days < 180:
            return "medium"
        return "long"

    def make_kpi(title, value, subtitle):
        # Helper function to create a KPI card with consistent styling
        return html.Div(
            [
                html.Div(title, className="kpi-label"),
                html.Div(value, className="kpi-value"),
                html.Div(subtitle, className="kpi-subtitle"),
            ]
        )

    def format_site_value_lines(series, decimals=2, suffix=""):
        # Helper function to format lines for each site, displaying the value with specified decimal places and suffix, or "--" if data is missing
        if series.empty:
            return "--"

        return html.Div(
            [
                html.Div(
                    f"{site}: {('--' if pd.isna(val) else f'{val:.{decimals}f}{suffix}')}",
                    className="kpi-site-line",
                )
                for site, val in series.items()
            ]
        )

    def format_site_exceedance_lines(site_exceedance):
        # Helper function to format exceedance lines for each site, displaying how much each site is above or below the threshold, or "--" if data is missing
        if not site_exceedance:
            return "--"

        return html.Div(
            [
                html.Div(
                    f"{row['site']}: {row['value']}",
                    className="kpi-site-line",
                )
                for row in site_exceedance
            ]
        )

    def format_with_units(value, decimals=2, units="µg/m³"):
        # Helper function to format a numeric value with specified decimal places and units
        if value is None or pd.isna(value):
            return "--"
        return f"{value:.{decimals}f} {units}"

    # Helper function to generate a subtitle comparing the current value to a threshold, indicating how much it is above or below the threshold
    def threshold_comparison_subtitle(
        value,
        threshold_value,
        threshold_metric=None,
        threshold_standard=None,
        units="µg/m³",
    ):
        if (
            value is None
            or pd.isna(value)
            or threshold_value is None
            or pd.isna(threshold_value)
        ):
            return "No threshold available"

        diff = value - threshold_value

        if threshold_standard and threshold_metric:
            metric_label = f"{threshold_standard} {threshold_metric} threshold"
        elif threshold_metric:
            metric_label = f"{threshold_metric} threshold"
        elif threshold_standard:
            metric_label = f"{threshold_standard} threshold"
        else:
            metric_label = "threshold"

        if diff > 0:
            return html.Span(
                f"{abs(diff):.2f} {units} above {metric_label}",
                className="kpi-subtitle-danger",
            )
        elif diff < 0:
            return html.Span(
                f"{abs(diff):.2f} {units} below {metric_label}",
                className="kpi-subtitle-good",
            )
        else:
            return html.Span(
                f"Equal to {metric_label}",
                className="kpi-subtitle-neutral",
            )

    # Helper function that generates lines comparing each site's value to a threshold, indicating how much each site is above or below the threshold
    def format_site_threshold_comparison_lines(
        series,
        threshold_value,
        threshold_metric=None,
        threshold_standard=None,
        decimals=2,
        units="µg/m³",
    ):
        if series.empty:
            return "--"

        if threshold_standard and threshold_metric:
            metric_label = f"{threshold_standard} {threshold_metric} threshold"
        elif threshold_metric:
            metric_label = f"{threshold_metric} threshold"
        elif threshold_standard:
            metric_label = f"{threshold_standard} threshold"
        else:
            metric_label = "threshold"

        lines = []
        for site, val in series.items():
            if threshold_value is None or pd.isna(val):
                lines.append(html.Div(f"{site}: --", className="kpi-site-line"))
                continue

            if val > threshold_value:
                line_class = "kpi-site-line danger"
                text = f"{site}: {abs(val - threshold_value):.{decimals}f} {units} above {metric_label}"
            elif val < threshold_value:
                line_class = "kpi-site-line good"
                text = f"{site}: {abs(val - threshold_value):.{decimals}f} {units} below {metric_label}"
            else:
                line_class = "kpi-site-line neutral"
                text = f"{site}: Equal to {metric_label}"

            lines.append(html.Div(text, className=line_class))

        return html.Div(lines)

    def build_overview_chart(
        dff,
        pollutant_label,
        start_date,
        end_date,
        threshold_value=None,
        threshold_metric=None,
        threshold_standard=None,
    ):
        # Build the overview line chart for the selected pollutant and date range, with threshold annotation
        start_str = pd.to_datetime(start_date).strftime("%d %b %Y")
        end_str = pd.to_datetime(end_date).strftime("%d %b %Y")

        n_sites = dff["site"].nunique()

        if n_sites > 1:
            fig = px.line(
                dff,
                x="date",
                y="value",
                color="site",
                # markers=True,
            )
        else:
            fig = px.line(
                dff,
                x="date",
                y="value",
                # markers=True,
            )

            peak_idx = dff["value"].idxmax()
            peak_row = dff.loc[peak_idx]

            fig.add_trace(
                go.Scatter(
                    x=[peak_row["date"]],
                    y=[peak_row["value"]],
                    mode="markers+text",
                    name="Peak",
                    text=["Peak"],
                    textposition="top center",
                )
            )

        if threshold_value is not None:
            if threshold_standard and threshold_metric:
                annotation = f"{threshold_standard} {threshold_metric} threshold"
            elif threshold_standard:
                annotation = f"{threshold_standard} threshold"
            elif threshold_metric:
                annotation = f"{threshold_metric} threshold"
            else:
                annotation = "Threshold"

            fig.add_hline(
                y=threshold_value,
                line_dash="dash",
                annotation_text=annotation,
            )

        fig.update_layout(
            title=f"{pollutant_label} Concentration ({start_str} – {end_str})",
            height=400,
            title_font=dict(family="Inter, sans-serif", size=16, color="#d1e0c2"),
            xaxis_title="Date",
            yaxis_title=f"{pollutant_label} (µg/m³)",
            xaxis_title_font=dict(family="Inter, sans-serif", size=13, color="#acb5c0"),
            yaxis_title_font=dict(family="Inter, sans-serif", size=13, color="#acb5c0"),
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend_title="Site" if n_sites > 1 else None,
        )

        return fig

    def build_trend_chart(dff, days, pollutant_label):
        # Build the trend line chart, adjusting aggregation level (daily/weekly/monthly) based on the length of the date range
        if days <= 31:
            freq = "D"
            title = f"Daily {pollutant_label} Concentration"
        elif days < 180:
            freq = "W"
            title = f"Weekly {pollutant_label} Concentration"
        else:
            freq = "ME"
            title = f"Monthly {pollutant_label} Concentration"

        agg = (
            dff.set_index("date")
            .groupby("site")["value"]
            .resample(freq)
            .mean()
            .reset_index()
        )

        n_sites = dff["site"].nunique()

        fig = px.line(
            agg,
            x="date",
            y="value",
            color="site" if n_sites > 1 else None,
            markers=True,
            title=title,
        )

        fig.update_layout(
            height=400,
            title_font=dict(family="Inter, sans-serif", size=16, color="#829a67"),
            xaxis_title="Date",
            yaxis_title=f"{pollutant_label} (µg/m³)",
            xaxis_title_font=dict(family="Inter, sans-serif", size=13, color="#acb5c0"),
            yaxis_title_font=dict(family="Inter, sans-serif", size=13, color="#acb5c0"),
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend_title="Site" if n_sites > 1 else None,
        )
        return fig

    def build_distribution_chart(dff, days, pollutant_label):
        # Build the distribution box plot, adjusting x-axis grouping (day/month) based on the length of the date range
        temp = dff.copy()

        if days <= 31:
            temp["bucket"] = temp["date"].dt.strftime("%Y-%m-%d")
            title = f"{pollutant_label} Distribution by Day"
            x_title = "Day"
        else:
            temp["bucket"] = temp["date"].dt.strftime("%Y-%m")
            title = f"{pollutant_label} Distribution by Month"
            x_title = "Month"

        n_sites = dff["site"].nunique()

        fig = px.box(
            temp,
            x="bucket",
            y="value",
            color="site" if n_sites > 1 else None,
            title=title,
        )

        fig.update_layout(
            height=400,
            title_font=dict(family="Inter, sans-serif", size=16, color="#d1e0c2"),
            xaxis_title=x_title,
            yaxis_title=f"{pollutant_label} (µg/m³)",
            xaxis_title_font=dict(family="Inter, sans-serif", size=13, color="#acb5c0"),
            yaxis_title_font=dict(family="Inter, sans-serif", size=13, color="#acb5c0"),
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend_title="Site" if n_sites > 1 else None,
        )
        return fig

    def build_seasonality_chart(dff, days, pollutant_label):
        # Build the seasonality chart, adjusting grouping (hour of day, weekday, month) based on the length of the date range
        required_cols = {"date", "value"}
        if dff is None or dff.empty or not required_cols.issubset(dff.columns):
            fig = go.Figure()
            fig.update_layout(
                title="No data available for seasonality analysis",
                height=360,
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            return fig

        temp = dff.copy()
        temp["date"] = pd.to_datetime(temp["date"], errors="coerce")
        temp = temp.dropna(subset=["date", "value"])

        if temp.empty:
            fig = go.Figure()
            fig.update_layout(
                title="No valid data available for seasonality analysis",
                height=400,
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            return fig

        if "site" not in temp.columns:
            temp["site"] = "Selected site"

        temp["site"] = temp["site"].fillna("Unknown site").astype(str)
        n_sites = temp["site"].nunique()

        def apply_layout(fig, title, x_title, y_title, height=360):
            fig.update_layout(
                title=title,
                height=height,
                title_font=dict(
                    family="Inter, sans-serif",
                    size=16,
                    color="#d1e0c2",
                ),
                xaxis_title=x_title,
                yaxis_title=y_title,
                xaxis_title_font=dict(
                    family="Inter, sans-serif",
                    size=13,
                    color="#acb5c0",
                ),
                yaxis_title_font=dict(
                    family="Inter, sans-serif",
                    size=13,
                    color="#acb5c0",
                ),
                font=dict(
                    family="Inter, sans-serif",
                    size=12,
                    color="#acb5c0",
                ),
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend_title="Site" if n_sites > 1 else None,
                margin=dict(l=30, r=20, t=50, b=40),
            )
            return fig

        if days <= 1:
            temp["hour"] = temp["date"].dt.hour

            grouped = (
                temp.groupby(["site", "hour"], as_index=False)["value"]
                .mean()
                .rename(columns={"value": "mean_value"})
            )

            fig = px.line(
                grouped,
                x="hour",
                y="mean_value",
                color="site" if n_sites > 1 else None,
                markers=True,
                title=f"Hourly Profile of {pollutant_label}",
            )
            fig.update_xaxes(dtick=1)

            return apply_layout(
                fig,
                f"Hourly Profile of {pollutant_label}",
                "Hour of Day",
                f"Average {pollutant_label} (µg/m³)",
                height=360,
            )

        elif days <= 45:
            weekday_order = [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]

            temp["weekday"] = temp["date"].dt.day_name()

            grouped = (
                temp.groupby(["site", "weekday"], as_index=False)["value"]
                .mean()
                .rename(columns={"value": "mean_value"})
            )

            grouped["weekday"] = pd.Categorical(
                grouped["weekday"],
                categories=weekday_order,
                ordered=True,
            )
            grouped = grouped.sort_values(["site", "weekday"])

            fig = px.bar(
                grouped,
                x="weekday",
                y="mean_value",
                color="site" if n_sites > 1 else None,
                barmode="group" if n_sites > 1 else "relative",
                title=f"Average {pollutant_label} by Day of Week",
            )

            return apply_layout(
                fig,
                f"Average {pollutant_label} by Day of Week",
                "Weekday",
                f"Average {pollutant_label} (µg/m³)",
                height=380,
            )

        else:
            month_order = [
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            ]

            temp["month"] = temp["date"].dt.month_name()

            grouped = (
                temp.groupby(["site", "month"], as_index=False)["value"]
                .mean()
                .rename(columns={"value": "mean_value"})
            )

            grouped["month"] = pd.Categorical(
                grouped["month"],
                categories=month_order,
                ordered=True,
            )
            grouped = grouped.sort_values(["site", "month"])

            fig = px.line(
                grouped,
                x="month",
                y="mean_value",
                color="site" if n_sites > 1 else None,
                markers=True,
                title=f"Seasonal Profile of {pollutant_label}",
            )

            return apply_layout(
                fig,
                f"Seasonal Profile of {pollutant_label}",
                "Month",
                f"Average {pollutant_label} (µg/m³)",
                height=360,
            )

    def get_site_exceedance_summary(dff, pollutant, threshold_standard):
        results = []

        dff = dff.copy()
        dff["date"] = pd.to_datetime(dff["date"], errors="coerce")
        dff["value"] = pd.to_numeric(dff["value"], errors="coerce")

        for site, site_df in dff.groupby("site"):
            if site_df.empty:
                results.append(
                    {
                        "site": site,
                        "value": 0,
                        "label": "No data available",
                    }
                )
                continue

            site_wide = (
                site_df[["date", "pollutants", "value"]]
                .dropna(subset=["date", "value"])
                .pivot(index="date", columns="pollutants", values="value")
                .reset_index()
                .sort_values("date")
            )
            print(f"Site: {site}, rows: {len(site_wide)}")
            print(
                f"Calling calculate_exceedance with pollutant={pollutant}, standard={threshold_standard}"
            )

            exceedance_info = calculate_exceedance(
                site_wide,
                pollutant,
                threshold_standard,
            )
            print(f"Result: {exceedance_info}")
            if pollutant not in site_wide.columns:
                results.append(
                    {
                        "site": site,
                        "value": 0,
                        "label": "No data available",
                    }
                )
                continue

            exceedance_info = calculate_exceedance(
                site_wide,
                pollutant,
                threshold_standard,
            )

            results.append(
                {
                    "site": site,
                    "value": exceedance_info["value"],
                    "label": exceedance_info["label"],
                }
            )

        return sorted(results, key=lambda x: str(x["site"]))

    # ─────────────────────────────────────────────────────────────
    # 1) Update site dropdown OPTIONS based on pollutant + date range
    # ─────────────────────────────────────────────────────────────

    @app.callback(
        Output("site_drop", "options"),
        Input("pol_drop", "value"),
        Input("date_range", "start_date"),
        Input("date_range", "end_date"),
        State("site_drop", "value"),
    )
    def update_site_dropdown(pollutant, start_date, end_date, currently_selected):
        date_active = has_full_date_range(start_date, end_date)

        if not pollutant and not date_active:
            valid = all_sites

        elif pollutant and not date_active:
            valid = sorted(pol_to_sites.get(pollutant, set()))

        else:
            start_dt = pd.to_datetime(start_date).date()
            end_dt = pd.to_datetime(end_date).date()

            candidates = (
                pol_to_sites.get(pollutant, set(all_sites))
                if pollutant
                else set(all_sites)
            )

            valid = sorted(
                [
                    site
                    for site in candidates
                    if site in site_to_dates
                    and site_to_dates[site][0] <= end_dt
                    and site_to_dates[site][1] >= start_dt
                ]
            )

        if currently_selected:
            valid = sorted(set(valid) | set(currently_selected))

        return valid

    # ─────────────────────────────────────────────────────────────
    # 2) Update pollutant dropdown OPTIONS based on sites + date range
    # ─────────────────────────────────────────────────────────────

    @app.callback(
        Output("pol_drop", "options"),
        Input("site_drop", "value"),
        Input("date_range", "start_date"),
        Input("date_range", "end_date"),
        State("pol_drop", "value"),
    )
    def update_pollutant_dropdown(sites, start_date, end_date, currently_selected):
        sites = sites or []
        date_active = has_full_date_range(start_date, end_date)

        if not sites and not date_active:
            valid = all_pollutants

        else:
            start_dt = pd.to_datetime(start_date).date() if date_active else None
            end_dt = pd.to_datetime(end_date).date() if date_active else None

            if not sites:
                valid = all_pollutants
                if date_active:
                    valid = sorted(
                        p
                        for p, (p_min, p_max) in pol_to_dates.items()
                        if p_min <= end_dt and p_max >= start_dt
                    )
            else:
                common = (
                    set.intersection(
                        *[
                            site_to_pollutants[s]
                            for s in sites
                            if s in site_to_pollutants
                        ]
                    )
                    if sites
                    else set(all_pollutants)
                )

                if date_active:
                    common = {
                        p
                        for p in common
                        if any(
                            (s, p) in site_pol_to_dates
                            and site_pol_to_dates[(s, p)][0] <= end_dt
                            and site_pol_to_dates[(s, p)][1] >= start_dt
                            for s in sites
                        )
                    }

                valid = sorted(common)

        if currently_selected and currently_selected not in valid:
            valid = sorted(set(valid) | {currently_selected})

        return valid

    # ─────────────────────────────────────────────────────────────
    # 3) Reset dropdown VALUES
    # ─────────────────────────────────────────────────────────────

    @app.callback(
        Output("site_drop", "value"),
        Output("pol_drop", "value"),
        Input("reset_btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def reset_dropdowns(n_clicks):
        return [], None

    # ─────────────────────────────────────────────────────────────
    # 4) Sync filter_store with current UI values
    # ─────────────────────────────────────────────────────────────

    @app.callback(
        Output("filter_store", "data"),
        Input("site_drop", "value"),
        Input("pol_drop", "value"),
        Input("date_range", "start_date"),
        Input("date_range", "end_date"),
    )
    def sync_filter_store(sites, pollutant, start_date, end_date):
        return {
            "sites": sites or [],
            "pollutant": pollutant,
            "start_date": start_date,
            "end_date": end_date,
        }

    # ─────────────────────────────────────────────────────────────
    # 5) Update date_range bounds — also respects ratified cap
    # ─────────────────────────────────────────────────────────────

    @app.callback(
        Output("date_range", "min_date_allowed"),
        Output("date_range", "max_date_allowed"),
        Input("filter_store", "data"),
        Input("dq_store", "data"),
    )
    def update_date_bounds(store, dq):
        if not store:
            max_allowed = RATIFIED_CUTOFF.date() if dq == "Ratified" else global_max
            return global_min, max_allowed

        sites = store.get("sites", []) or []
        pollutant = store.get("pollutant")

        min_allowed, max_allowed = compute_allowed_bounds(sites, pollutant)

        if min_allowed is None or max_allowed is None:
            max_allowed = RATIFIED_CUTOFF.date() if dq == "Ratified" else global_max
            return global_min, max_allowed

        if dq == "Ratified":
            max_allowed = min(max_allowed, RATIFIED_CUTOFF.date())

        return min_allowed, max_allowed

    # ─────────────────────────────────────────────────────────────
    # 6) Save quick-select dates to store so they survive
    #    site/pollutant dropdown changes
    # ─────────────────────────────────────────────────────────────

    @app.callback(
        Output("date-store", "data"),
        Input("yday", "n_clicks"),
        Input("last_week", "n_clicks"),
        Input("last_month", "n_clicks"),
        prevent_initial_call=True,
    )
    def save_quick_date(yday, last_week, last_month):
        today = date.today()
        triggered = callback_context.triggered_id
        if triggered == "yday":
            d = today - timedelta(days=1)
            return {"start": str(d), "end": str(d)}
        elif triggered == "last_week":
            return {"start": str(today - timedelta(days=7)), "end": str(today)}
        elif triggered == "last_month":
            return {"start": str(today - timedelta(days=30)), "end": str(today)}
        return no_update

    # ─────────────────────────────────────────────────────────────
    # 7) Manage date selection
    #    - Reset clears dates
    #    - Quick buttons set and persist dates to store
    #    - Changing sites/pollutant/dq restores from store if valid
    #    - Ratified mode caps selected end date to cutoff
    # ─────────────────────────────────────────────────────────────

    @app.callback(
        Output("date_range", "start_date"),
        Output("date_range", "end_date"),
        Input("reset_btn", "n_clicks"),
        Input("site_drop", "value"),
        Input("pol_drop", "value"),
        Input("yday", "n_clicks"),
        Input("last_week", "n_clicks"),
        Input("last_month", "n_clicks"),
        Input("dq_store", "data"),
        State("date_range", "start_date"),
        State("date_range", "end_date"),
        State("date-store", "data"),
    )
    def manage_date_selection(
        n_clicks,
        sites,
        pollutant,
        yday,
        last_week,
        last_month,
        dq,
        start_date,
        end_date,
        stored_dates,
    ):
        triggered = callback_context.triggered_id
        sites = sites or []

        if triggered == "reset_btn":
            return None, None

        today = date.today()

        if triggered == "yday":
            yesterday = today - timedelta(days=1)
            end = (
                min(yesterday, RATIFIED_CUTOFF.date())
                if dq == "Ratified"
                else yesterday
            )
            return yesterday, end
        elif triggered == "last_week":
            start = today - timedelta(days=7)
            end = min(today, RATIFIED_CUTOFF.date()) if dq == "Ratified" else today
            return start, end
        elif triggered == "last_month":
            start = today - timedelta(days=30)
            end = min(today, RATIFIED_CUTOFF.date()) if dq == "Ratified" else today
            return start, end

        min_allowed, max_allowed = compute_allowed_bounds(sites, pollutant)

        if min_allowed is None or max_allowed is None:
            return None, None

        if dq == "Ratified":
            max_allowed = min(max_allowed, RATIFIED_CUTOFF.date())

        effective_start = stored_dates["start"] if stored_dates else start_date
        effective_end = stored_dates["end"] if stored_dates else end_date

        if dq == "Ratified" and effective_end:
            effective_end = str(
                min(pd.to_datetime(effective_end).date(), RATIFIED_CUTOFF.date())
            )

        if not has_full_date_range(effective_start, effective_end):
            return no_update, no_update

        try:
            cs = pd.to_datetime(effective_start).date()
            ce = pd.to_datetime(effective_end).date()
        except Exception:
            return None, None

        if cs < min_allowed or cs > max_allowed or ce < min_allowed or ce > max_allowed:
            return None, None

        return effective_start, effective_end

    # Topbar metadata
    @app.callback(
        Output("meta-stations", "children"),
        Output("meta-pollutant", "children"),
        Output("meta-period", "children"),
        Input("site_drop", "value"),
        Input("pol_drop", "value"),
        Input("date_range", "start_date"),
        Input("date_range", "end_date"),
    )
    def update_topbar(sites, pollutant, start_date, end_date):
        stations_text = f"{len(sites)}" if sites else "--"
        pollutant_text = (
            POLLUTANT_DISPLAY_NAMES.get(pollutant, pollutant) if pollutant else "--"
        )
        period_text = format_date_range(start_date, end_date)
        return stations_text, pollutant_text, period_text

    # ─────────────────────────────────────────────────────────────
    # Summary statistics table
    # ─────────────────────────────────────────────────────────────

    @app.callback(
        Output("stats_container", "children"),
        Input("site_drop", "value"),
        Input("pol_drop", "value"),
        Input("date_range", "start_date"),
        Input("date_range", "end_date"),
        Input("dq_store", "data"),
    )
    def update_summary_stats(sites, pollutant, start_date, end_date, dq):
        if not sites or not pollutant or not start_date or not end_date:
            return html.Div(
                "Please select site(s), a pollutant, and a date range to generate statistics.",
                className="text-muted italic",
            )

        start_dt = pd.to_datetime(start_date)
        end_dt = (
            pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        )
        start_dt, end_dt = apply_dq_cap(start_dt, end_dt, dq)

        mask = (
            wales_df_long["site"].isin(sites)
            & (wales_df_long["pollutants"] == pollutant)
            & (wales_df_long["date"] >= start_dt)
            & (wales_df_long["date"] <= end_dt)
        )

        filtered_df = wales_df_long.loc[mask].copy()

        if filtered_df.empty:
            return html.Div(
                f"No {pollutant} data available for the selected sites in this timeframe."
            )

        summary_df = calculate_summary_stats(filtered_df)

        if summary_df.empty:
            return html.Div("No statistics available for the current filters.")

        return html.Div(
            dash_table.DataTable(
                data=summary_df.to_dict("records"),
                columns=[{"name": col, "id": col} for col in summary_df.columns],
                sort_action="native",
                page_size=10,
                style_table={
                    "overflowX": "auto",
                    "width": "100%",
                    "backgroundColor": "transparent",
                },
                style_cell={
                    "textAlign": "center",
                    "padding": "8px 8px",
                    "fontFamily": "Inter, sans-serif",
                    "fontSize": "13px",
                    "color": "var(--text-primary)",
                    "backgroundColor": "var(--bg-secondary)",
                    "border": "none",
                },
                style_header={
                    "fontWeight": "700",
                    "color": "var(--sage-500)",
                    "backgroundColor": "var(--bg-tertiary)",
                    "borderBottom": "1px solid rgba(255, 255, 255, 0.08)",
                    "textTransform": "uppercase",
                    "letterSpacing": "0.4px",
                    "fontSize": "11px",
                    "padding": "8px 8px",
                },
                style_data={
                    "backgroundColor": "var(--bg-secondary)",
                    "color": "var(--text-primary)",
                    "borderBottom": "1px solid rgba(255, 255, 255, 0.06)",
                },
                style_data_conditional=[
                    {
                        "if": {"row_index": "odd"},
                        "backgroundColor": "var(--bg-tertiary)",
                    },
                    {
                        "if": {"state": "active"},
                        "backgroundColor": "rgba(159, 212, 181, 0.12)",
                        "border": "1px solid var(--sage-500)",
                    },
                    {
                        "if": {"state": "selected"},
                        "backgroundColor": "rgba(159, 212, 181, 0.18)",
                        "border": "1px solid var(--sage-500)",
                    },
                ],
                style_as_list_view=True,
            ),
            # className="stats-table",
        )

    # Data Completeness
    @app.callback(
        Output("completeness-overall", "children"),
        Output("completeness-bars", "children"),
        Input("site_drop", "value"),
        Input("pol_drop", "value"),
        Input("date_range", "start_date"),
        Input("date_range", "end_date"),
        Input("dq_store", "data"),
    )
    def update_completeness(sites, pollutant, start_date, end_date, dq):
        """Update completeness panel."""
        if not sites or not pollutant or not start_date or not end_date:
            return "--", []

        start_dt = pd.to_datetime(start_date)
        end_dt = (
            pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        )
        start_dt, end_dt = apply_dq_cap(start_dt, end_dt, dq)

        df_filtered = wales_df[
            (wales_df["site"].isin(sites))
            & (wales_df["date"] >= start_dt)
            & (wales_df["date"] <= end_dt)
        ]

        overall = calculate_completeness(df_filtered, pollutant)
        overall_text = f"{overall}%"

        site_results = calculate_completeness_by_site(df_filtered, sites, pollutant)

        bars = []
        for result in site_results:
            bars.append(
                html.Div(
                    className="completeness-item",
                    children=[
                        html.Div(result["site"], className="completeness-label"),
                        html.Div(
                            className="completeness-bar-track",
                            children=[
                                html.Div(
                                    className=f"completeness-bar-fill status-{result['status']}",
                                    style={"width": f"{result['completeness']}%"},
                                )
                            ],
                        ),
                        html.Div(
                            f"{result['completeness']}%",
                            className="completeness-percentage",
                        ),
                    ],
                )
            )

        return overall_text, bars

    #  Trends KPIs, chart, and insights

    @app.callback(
        Output("trends-kpi-avg", "children"),
        Output("trends-kpi-max", "children"),
        Output("trends-kpi-exceed", "children"),
        Output("trends-kpi-var", "children"),
        Output("trends-warning", "children"),
        Output("trends-warning", "style"),
        Output("trends-chart-container", "children"),
        Output("trends-insight-box", "children"),
        Input("trends-tabs", "value"),
        Input("site_drop", "value"),
        Input("pol_drop", "value"),
        Input("date_range", "start_date"),
        Input("date_range", "end_date"),
        Input("threshold-store", "data"),
        Input("dq_store", "data"),
    )
    def update_trends(
        tab,
        selected_sites,
        selected_pollutant,
        start_date,
        end_date,
        threshold_standard,
        dq,
    ):
        df = wales_df_long.copy()

        effective_end_date = end_date
        if dq == "Ratified" and end_date:
            effective_end_date = str(
                min(pd.to_datetime(end_date).date(), RATIFIED_CUTOFF.date())
            )

        days = get_days(start_date, effective_end_date)

        if days is None:
            empty_fig = go.Figure()
            empty_fig.update_layout(
                title="Select a date range to begin",
                title_font=dict(family="Inter, sans-serif", size=16, color="#d1e0c2"),
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=300,
            )
            return (
                make_kpi("Average", "--", "Awaiting filters"),
                make_kpi("Peak", "--", "Awaiting filters"),
                make_kpi("Exceedances", "--", "Awaiting filters"),
                make_kpi("Variability", "--", "Awaiting filters"),
                "",
                {"display": "none"},
                dcc.Graph(
                    figure=empty_fig,
                    config={"displayModeBar": True, "displaylogo": False},
                ),
                html.Div(
                    html.P(
                        [
                            html.Strong("Insights: "),
                            "Select a start and end date to generate a temporal analysis summary.",
                        ],
                        className="insight-inline",
                    ),
                    className="insight-box",
                ),
            )

        dff = filter_df(
            df, selected_sites, selected_pollutant, start_date, effective_end_date
        )

        if dff.empty or not selected_pollutant:
            empty_fig = go.Figure()
            empty_fig.update_layout(
                title="No data available for selected filters",
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=300,
            )
            return (
                make_kpi("Average", "--", "No data"),
                make_kpi("Peak", "--", "No data"),
                make_kpi("Exceedances", "--", "No data"),
                make_kpi("Variability", "--", "No data"),
                "No matching data was found for the current selection.",
                {"display": "block"},
                dcc.Graph(
                    figure=empty_fig,
                    config={"displayModeBar": True, "displaylogo": False},
                ),
                html.Div(
                    [
                        html.H4("No Data Available", className="insight-inline"),
                        html.P("Try adjusting the site, pollutant, or date range."),
                    ]
                ),
            )

        pollutant_label = POLLUTANT_DISPLAY_NAMES.get(
            selected_pollutant, selected_pollutant
        )
        threshold_info = get_threshold_info(
            selected_pollutant, threshold_standard or "UK"
        )
        threshold_value = threshold_info["value"] if threshold_info else None
        threshold_metric = threshold_info["metric"] if threshold_info else None
        selected_standard = threshold_standard or "UK"

        site_count = dff["site"].nunique()
        site_avg = dff.groupby("site")["value"].mean().sort_index()
        site_max = dff.groupby("site")["value"].max().sort_index()
        site_std = dff.groupby("site")["value"].std().sort_index()

        site_exceedance = get_site_exceedance_summary(
            dff,
            selected_pollutant,
            selected_standard,
        )

        avg_val = dff["value"].mean()
        max_val = dff["value"].max()
        mode = get_mode(days)

        warning_text = ""
        warning_style = {"display": "none"}

        if tab == "overview":
            fig = build_overview_chart(
                dff,
                pollutant_label,
                start_date,
                effective_end_date,
                threshold_value,
                threshold_metric,
                selected_standard,
            )
        elif tab == "trend":
            fig = build_trend_chart(dff, days, pollutant_label)
        elif tab == "distribution":
            fig = build_distribution_chart(dff, days, pollutant_label)
        elif tab == "seasonality":
            fig = build_seasonality_chart(dff, days, pollutant_label)
        else:
            fig = go.Figure()

        peak_row = dff.loc[dff["value"].idxmax()]
        peak_time = peak_row["date"].strftime("%Y-%m-%d")

        if site_count == 1:
            exceedance_info = (
                site_exceedance[0]
                if site_exceedance
                else {"value": "--", "label": "No data"}
            )

            avg_value = site_avg.iloc[0]
            max_value = site_max.iloc[0]
            std_value = 0 if pd.isna(site_std.iloc[0]) else site_std.iloc[0]

            avg_kpi = make_kpi(
                "Average",
                format_with_units(avg_value),
                threshold_comparison_subtitle(
                    avg_value,
                    threshold_value,
                    threshold_metric,
                    selected_standard,
                ),
            )

            max_kpi = make_kpi(
                "Peak",
                format_with_units(max_value),
                threshold_comparison_subtitle(
                    max_value,
                    threshold_value,
                    threshold_metric,
                    selected_standard,
                ),
            )

            exceed_kpi = make_kpi(
                "Exceedance",
                f"{exceedance_info['value']}",
                exceedance_info["label"],
            )

            var_kpi = make_kpi(
                "Variability",
                format_with_units(std_value),
                "Standard deviation",
            )

        else:
            avg_kpi = make_kpi(
                "Average",
                format_site_value_lines(site_avg, decimals=2, suffix=" µg/m³"),
                format_site_threshold_comparison_lines(
                    site_avg,
                    threshold_value,
                    threshold_metric,
                    selected_standard,
                ),
            )

            max_kpi = make_kpi(
                "Peak",
                format_site_value_lines(site_max, decimals=2, suffix=" µg/m³"),
                format_site_threshold_comparison_lines(
                    site_max,
                    threshold_value,
                    threshold_metric,
                    selected_standard,
                ),
            )

            exceed_kpi = make_kpi(
                "Exceedance",
                format_site_exceedance_lines(site_exceedance),
                site_exceedance[0]["label"] if site_exceedance else "No data",
            )

            var_kpi = make_kpi(
                "Variability",
                format_site_value_lines(
                    site_std.fillna(0), decimals=2, suffix=" µg/m³"
                ),
                "Standard deviation by site",
            )

        if mode == "day":
            insight = (
                f"This selection focuses on a very short window. Average {pollutant_label} is {avg_val:.2f} µg/m³, "
                f"with a peak of {max_val:.2f} on {peak_time}. At this range, local variation and unusual values matter "
                f"more than seasonal interpretation."
            )
        elif mode == "short":
            insight = (
                f"This {days}-day window supports short-term monitoring. Average {pollutant_label} is {avg_val:.2f} µg/m³, "
                f"with a maximum of {max_val:.2f} on {peak_time}. Daily trend movement and weekday structure are the most useful views here."
            )
        else:
            insight = (
                f"This {days}-day window supports broader temporal interpretation. Average {pollutant_label} is {avg_val:.2f} µg/m³, "
                f"with a maximum of {max_val:.2f} on {peak_time}. Seasonal structure and longer trend behaviour can now be interpreted more confidently."
            )

        return (
            avg_kpi,
            max_kpi,
            exceed_kpi,
            var_kpi,
            warning_text,
            warning_style,
            dcc.Graph(
                figure=fig, config={"displayModeBar": True, "displaylogo": False}
            ),
            html.Div(
                html.P(
                    [html.Strong("Insights: "), insight], className="insight-inline"
                ),
                className="insight-box",
            ),
        )

    # ────────────────────────────────────────────────────────────
    # Quick select button active glow
    # ─────────────────────────────────────────────────────────────
    _BTN_BASE = {
        "background": "var(--bg-tertiary)",
        "borderColor": "var(--border-primary)",
        "color": "var(--text-secondary)",
        "boxShadow": "none",
        "transform": "scale(1)",
    }
    _BTN_ACTIVE = {
        "background": "rgba(143, 181, 105, 0.15)",
        "borderColor": "var(--sage-500)",
        "color": "var(--sage-300)",
        "boxShadow": "0 0 0 3px rgba(143, 181, 105, 0.15), 0 0 16px rgba(143, 181, 105, 0.35)",
        "transform": "scale(1.02)",
    }

    @app.callback(
        Output("yday", "className"),
        Output("yday", "style"),
        Output("last_week", "className"),
        Output("last_week", "style"),
        Output("last_month", "className"),
        Output("last_month", "style"),
        Input("yday", "n_clicks"),
        Input("last_week", "n_clicks"),
        Input("last_month", "n_clicks"),
        Input("reset_btn", "n_clicks"),
        Input("date_range", "start_date"),
    )
    def update_quick_btn_active(yday, last_week, last_month, reset, start_date):
        triggered = callback_context.triggered_id
        base_cls = "quick-date-btn"
        active_cls = "quick-date-btn active"

        # Reset or manual calendar pick — clear all
        if triggered in ("reset_btn", "date_range") or not triggered:
            return base_cls, _BTN_BASE, base_cls, _BTN_BASE, base_cls, _BTN_BASE

        if triggered == "yday":
            return active_cls, _BTN_ACTIVE, base_cls, _BTN_BASE, base_cls, _BTN_BASE
        elif triggered == "last_week":
            return base_cls, _BTN_BASE, active_cls, _BTN_ACTIVE, base_cls, _BTN_BASE
        elif triggered == "last_month":
            return base_cls, _BTN_BASE, base_cls, _BTN_BASE, active_cls, _BTN_ACTIVE

        return base_cls, _BTN_BASE, base_cls, _BTN_BASE, base_cls, _BTN_BASE

    @app.callback(
        Output("date-controls", "style"),
        Output("year-wrapper", "style"),
        Input("url", "pathname"),
    )
    def toggle_side_bar_page(pathname):
        # if user is on the exceedance page then hide the date picker and show the year drop down
        if pathname == "/exceedance":
            return {"visibility": "hidden", "height": 0, "overflow": "hidden"}, {
                "display": "block"
            }
        return {"display": "block"}, {"display": "none"}
