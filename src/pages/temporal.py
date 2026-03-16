import dash
from dash import html, dcc, callback, Input, Output
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from dataloader import load_data
from utils.calculations import LIMITS, POLLUTANT_DISPLAY_NAMES, calculate_exceedance

dash.register_page(__name__, path="/trends", name="Temporal Trends")

_, wales_df_long = load_data()


def get_df():
    df = wales_df_long.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    return df


def get_threshold_info(pollutant, standard):
    if not pollutant or standard not in LIMITS or pollutant not in LIMITS[standard]:
        return None

    pollutant_limits = LIMITS[standard][pollutant]

    for metric in ["daily", "annual", "hourly", "8h"]:
        if metric in pollutant_limits:
            return {
                "metric": metric,
                "value": pollutant_limits[metric],
            }

    return None


def filter_df(df, sites, pollutant, start_date, end_date):
    dff = df.copy()

    if sites:
        dff = dff[dff["site"].isin(sites)]

    if pollutant:
        dff = dff[dff["pollutants"] == pollutant]

    if start_date:
        dff = dff[dff["date"] >= pd.to_datetime(start_date)]

    if end_date:
        end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
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
    return html.Div(
        [
            html.Div(title, className="kpi-label"),
            html.Div(value, className="kpi-value"),
            html.Div(subtitle, className="kpi-subtitle"),
        ]
    )

def build_overview_chart(
    dff,
    pollutant_label,
    start_date,
    end_date,
    threshold_value=None,
    threshold_metric=None,
    threshold_standard=None,
):
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

        title_font=dict(
        family="Inter, sans-serif",
        size=16,
        color= "#a8c686"
        ),

        xaxis_title="Date",
        yaxis_title=f"{pollutant_label} (µg/m³)",

        xaxis_title_font=dict(
        family="Inter, sans-serif",
        size=13,
        color="#acb5c0"
        ),

        yaxis_title_font=dict(
            family="Inter, sans-serif",
            size=13,
            color="#acb5c0"
        ),

        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_title="Site" if n_sites > 1 else None,
    )

    return fig


def build_trend_chart(dff, days, pollutant_label):
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

        title_font=dict(
        family="Inter, sans-serif",
        size=16,
        color= "#829a67"
        ),

        xaxis_title="Date",
        yaxis_title=f"{pollutant_label} (µg/m³)",

        xaxis_title_font=dict(
        family="Inter, sans-serif",
        size=13,
        color="#acb5c0"
        ),

         yaxis_title_font=dict(
            family="Inter, sans-serif",
            size=13,
            color="#acb5c0"
        ),

        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_title="Site" if n_sites > 1 else None,
    )
    return fig


def build_distribution_chart(dff, days, pollutant_label):
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

        title_font=dict(
        family="Inter, sans-serif",
        size=16,
        color= "#a8c686"
        ),

        xaxis_title=x_title,
        yaxis_title=f"{pollutant_label} (µg/m³)",

        xaxis_title_font=dict(
        family="Inter, sans-serif",
        size=13,
        color="#acb5c0"
        ),

        yaxis_title_font=dict(
            family="Inter, sans-serif",
            size=13,
            color="#acb5c0"
        ),

        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_title="Site" if n_sites > 1 else None,
    )
    return fig


def build_seasonality_chart(dff, days, pollutant_label):
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
            height=360,
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
                color="#a8c686",
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
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday"
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
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
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


def format_site_kpi_lines(series, decimals=2, suffix=""):
    if series.empty:
        return "No data"

    lines = []
    for site, value in series.items():
        if pd.isna(value):
            display = "--"
        else:
            display = f"{value:.{decimals}f}{suffix}"
        lines.append(html.Div(f"{site}: {display}"))
    return html.Div(lines)


def get_site_exceedance_summary(dff, pollutant, threshold_standard):
    results = []

    for site, site_df in dff.groupby("site"):
        site_wide = (
            site_df.pivot_table(
                index="date",
                columns="pollutants",
                values="value",
                aggfunc="mean"
            )
            .reset_index()
        )

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


layout = html.Div(
    className="trends-page",
    children=[
        html.Div(
            className="kpi-grid",
            children=[
                html.Div(id="trends-kpi-avg", className="kpi-card"),
                html.Div(id="trends-kpi-max", className="kpi-card"),
                html.Div(id="trends-kpi-threshold", className="kpi-card"),
                html.Div(id="trends-kpi-exceed", className="kpi-card"),
                html.Div(id="trends-kpi-var", className="kpi-card"),
            ],
        ),
        html.Div(
            id="trends-warning",
            className="warning-banner",
            style={"display": "none"},
        ),
        html.Div(
            className="card",
            children=[
                dcc.Tabs(
                    id="trends-tabs",
                    value="overview",
                    parent_className="dash-tabs",
                    children=[
                        dcc.Tab(label="Overview", value="overview", className="tab", selected_className="tab--selected"),
                        dcc.Tab(label="Trend", value="trend", className="tab", selected_className="tab--selected"),
                        dcc.Tab(label="Distribution", value="distribution", className="tab", selected_className="tab--selected"),
                        dcc.Tab(label="Seasonality", value="seasonality", className="tab", selected_className="tab--selected"),
                    ],
                ),
                html.Div(id="trends-chart-container", style={"marginTop": "16px"}),
            ],
        ),
        html.Div(id="trends-insight-box"),
    ],
)

def format_site_value_lines(series, decimals=2, suffix=""):
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


@callback(
    Output("trends-kpi-avg", "children"),
    Output("trends-kpi-max", "children"),
    Output("trends-kpi-threshold", "children"),
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
)
def update_trends_page(tab, selected_sites, selected_pollutant, start_date, end_date, threshold_standard):
    df = get_df()
    days = get_days(start_date, end_date)

    if days is None:
        empty_fig = go.Figure()
        empty_fig.update_layout(
            title="Select a date range to begin",
            title_font=dict(
            family="Inter, sans-serif",
            size=16,
            color= "#a8c686"
            ),
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=300,
        )
        return (
            make_kpi("Average", "--", "Awaiting filters"),
            make_kpi("Peak", "--", "Awaiting filters"),
            make_kpi("Threshold", "--", "Awaiting filters"),
            make_kpi("Exceedances", "--", "Awaiting filters"),
            make_kpi("Variability", "--", "Awaiting filters"),
            "",
            {"display": "none"},
            dcc.Graph(figure=empty_fig, config={"displayModeBar": True, "displaylogo": False}),
            html.Div(
    html.P(
        [html.Strong("Insights: "), "Select a start and end date to generate a temporal analysis summary."],
        className="insight-inline"),
    className="insight-box"),
    )

    dff = filter_df(df, selected_sites, selected_pollutant, start_date, end_date)

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
            make_kpi("Threshold", "--", "No data"),
            make_kpi("Exceedances", "--", "No data"),
            make_kpi("Variability", "--", "No data"),
            "No matching data was found for the current selection.",
            {"display": "block"},
            dcc.Graph(figure=empty_fig, config={"displayModeBar": True, "displaylogo": False}),
            html.Div(
                [
                    html.H4("No Data Available", className="insight-inline"),
                    html.P("Try adjusting the site, pollutant, or date range."),
                ]
            ),
        )

    pollutant_label = POLLUTANT_DISPLAY_NAMES.get(selected_pollutant, selected_pollutant)
    threshold_info = get_threshold_info(selected_pollutant, threshold_standard or "UK")
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

    # keep overall values only for insight text if you still want one summary sentence
    avg_val = dff["value"].mean()
    max_val = dff["value"].max()
    std_val = dff["value"].std()

    mode = get_mode(days)

    warning_text = ""
    warning_style = {"display": "none"}

    # if tab == "seasonality" and days < 30:
    #     warning_text = "Monthly seasonality is not reliable below 30 days, so this view switches to weekday pattern analysis."
    #     warning_style = {"display": "block"}

    if tab == "overview":
        fig = build_overview_chart(dff, pollutant_label, start_date, end_date, threshold_value, threshold_metric, selected_standard)
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

    threshold_subtitle = (
        f"{selected_standard} {threshold_metric} guideline"
        if threshold_metric
        else "No threshold available"
    )
    threshold_display = f"{threshold_value}" if threshold_value is not None else "--"

    if site_count == 1:
        exceedance_info = site_exceedance[0] if site_exceedance else {"value": "--", "label": "No data"}

        avg_kpi = make_kpi("Average", f"{site_avg.iloc[0]:.2f}", f"Mean {pollutant_label}")
        max_kpi = make_kpi("Peak", f"{site_max.iloc[0]:.2f}", f"Max observed {pollutant_label}")
        exceed_kpi = make_kpi("Exceedance", f"{exceedance_info['value']}", exceedance_info["label"])
        var_kpi = make_kpi(
            "Variability",
            f"{0 if pd.isna(site_std.iloc[0]) else site_std.iloc[0]:.2f}",
            "Standard deviation",
        )
    else:
        avg_kpi = make_kpi(
            "Average",
            format_site_value_lines(site_avg, decimals=2),
            f"Mean {pollutant_label} by site",
        )
        max_kpi = make_kpi(
            "Peak",
            format_site_value_lines(site_max, decimals=2),
            f"Max {pollutant_label} by site",
        )
        exceed_kpi = make_kpi(
            "Exceedance",
            format_site_exceedance_lines(site_exceedance),
            "Exceedance count by site",
        )
        var_kpi = make_kpi(
            "Variability",
            format_site_value_lines(site_std.fillna(0), decimals=2),
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
        make_kpi("Threshold", threshold_display, threshold_subtitle),
        exceed_kpi,
        var_kpi,
        warning_text,
        warning_style,
        dcc.Graph(figure=fig, config={"displayModeBar": True, "displaylogo": False}),
        html.Div(
            html.P([
                html.Strong("Insights: "), insight], className="insight-inline"), className="insight-box"
                )
            )

