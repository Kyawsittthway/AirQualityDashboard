"""
AirLens Dashboard v2
UK Air Quality Analysis Dashboard
"""

from dash import Dash, html, dcc, callback, Output, Input, State, no_update, callback_context, clientside_callback
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from components.sidebar import create_sidebar
from components.kpi_tiles import create_kpi_tiles
from components.station_cards import create_station_cards_section, create_circular_gauge
from utils.calculations import (
    calculate_exceedance,
    calculate_completeness,
    calculate_completeness_by_site,
    calculate_summary_stats,
    get_status_class,
    format_date_range,
    LIMITS,
    POLLUTANT_DISPLAY_NAMES
)


wales_df = pd.read_csv("wales_air_quality_data_16.csv")
wales_df["date"] = pd.to_datetime(wales_df["date"], errors="coerce")

pollutant_cols = ["NO2", "PM2.5", "PM10", "O3", "SO2"]

# long format for filtering
wales_df_long = wales_df.copy()
wales_df_long = wales_df_long.melt(
    id_vars=["date", "site", "site_id", "code"],
    value_vars=pollutant_cols,
    var_name="pollutants",
    value_name="value"
)
wales_df_long = wales_df_long.dropna(subset=["value"])


app = Dash(__name__, suppress_callback_exceptions=True)
app.title = "AirLens · UK Air Quality"


app.layout = html.Div(
    id="app-container",
    **{"data-theme": "dark"},
    children=[
        # Sidebar
        create_sidebar(),
        
        # Main Content
        html.Div(
            id="main-content",
            children=[
                # Top Bar
                html.Div(
                    className="topbar",
                    children=[
                        html.Div(
                            className="topbar-title",
                            children=[
                                "Wales Air Quality Dashboard",
                                html.Span("DEFRA", className="topbar-badge")
                            ]
                        ),
                        html.Div(
                            className="topbar-meta",
                            children=[
                                html.Div(
                                    className="meta-pill",
                                    children=["Stations:", html.Strong("--", id="meta-stations")]
                                ),
                                html.Div(
                                    className="meta-pill",
                                    children=["Pollutant:", html.Strong("--", id="meta-pollutant")]
                                ),
                                html.Div(
                                    className="meta-pill",
                                    children=["Period:", html.Strong("--", id="meta-period")]
                                )
                            ]
                        )
                    ]
                ),
                
                # Content Area
                html.Div(
                    className="content",
                    children=[
                        # KPI Tiles
                        create_kpi_tiles(),
                        
                        # Time Series Chart
                        html.Div(
                            className="card",
                            children=[
                                html.Div(
                                    className="card-header",
                                    children=[
                                        html.Div("Pollutant Concentration Over Time", className="card-title")
                                    ]
                                ),
                                html.Div(
                                    className="card-body",
                                    children=[
                                        dcc.Graph(
                                            id="time-series-chart",
                                            figure={},
                                            config={'displayModeBar': True, 'displaylogo': False}
                                        )
                                    ]
                                )
                            ]
                        ),
                        
                        # Bottom Row: Stats + Completeness
                        html.Div(
                            style={"display": "grid", "gridTemplateColumns": "1.5fr 1fr", "gap": "24px"},
                            children=[
                                # Summary Statistics
                                html.Div(
                                    className="card",
                                    children=[
                                        html.Div(
                                            className="card-header",
                                            children=[
                                                html.Div("Summary Statistics", className="card-title")
                                            ]
                                        ),
                                        html.Div(
                                            className="card-body",
                                            children=[
                                                html.Div(
                                                    className="stats-grid",
                                                    children=[
                                                        # Mean
                                                        html.Div(
                                                            className="stat-cell",
                                                            children=[
                                                                html.Div("Mean", className="stat-label"),
                                                                html.Div("--", className="stat-value", id="stat-mean"),
                                                                html.Div("μg/m³", className="stat-unit")
                                                            ]
                                                        ),
                                                        # Median
                                                        html.Div(
                                                            className="stat-cell",
                                                            children=[
                                                                html.Div("Median", className="stat-label"),
                                                                html.Div("--", className="stat-value", id="stat-median"),
                                                                html.Div("μg/m³", className="stat-unit")
                                                            ]
                                                        ),
                                                        # Std Dev
                                                        html.Div(
                                                            className="stat-cell",
                                                            children=[
                                                                html.Div("Std Dev", className="stat-label"),
                                                                html.Div("--", className="stat-value", id="stat-std"),
                                                                html.Div("μg/m³", className="stat-unit")
                                                            ]
                                                        ),
                                                        # Min
                                                        html.Div(
                                                            className="stat-cell",
                                                            children=[
                                                                html.Div("Min", className="stat-label"),
                                                                html.Div("--", className="stat-value", id="stat-min"),
                                                                html.Div("μg/m³", className="stat-unit")
                                                            ]
                                                        ),
                                                        # Max
                                                        html.Div(
                                                            className="stat-cell",
                                                            children=[
                                                                html.Div("Max", className="stat-label"),
                                                                html.Div("--", className="stat-value", id="stat-max"),
                                                                html.Div("μg/m³", className="stat-unit")
                                                            ]
                                                        ),
                                                        # IQR
                                                        html.Div(
                                                            className="stat-cell",
                                                            children=[
                                                                html.Div("IQR", className="stat-label"),
                                                                html.Div("--", className="stat-value", id="stat-iqr"),
                                                                html.Div("μg/m³", className="stat-unit")
                                                            ]
                                                        )
                                                    ]
                                                )
                                            ]
                                        )
                                    ]
                                ),
                                
                                # Data Completeness
                                html.Div(
                                    className="card",
                                    children=[
                                        html.Div(
                                            className="card-header",
                                            children=[
                                                html.Div("Data Completeness", className="card-title")
                                            ]
                                        ),
                                        html.Div(
                                            className="card-body",
                                            children=[
                                                # Overall percentage
                                                html.Div(
                                                    style={"textAlign": "center", "marginBottom": "24px"},
                                                    children=[
                                                        html.Div(
                                                            "--",
                                                            id="completeness-overall",
                                                            style={
                                                                "fontSize": "56px",
                                                                "fontWeight": "800",
                                                                "background": "linear-gradient(135deg, var(--sage-300), var(--sage-500))",
                                                                "WebkitBackgroundClip": "text",
                                                                "WebkitTextFillColor": "transparent",
                                                                "backgroundClip": "text",
                                                                "letterSpacing": "-2px"
                                                            }
                                                        ),
                                                        html.Div(
                                                            "Overall Completeness",
                                                            style={
                                                                "fontSize": "12px",
                                                                "color": "var(--text-tertiary)",
                                                                "textTransform": "uppercase",
                                                                "letterSpacing": "0.5px",
                                                                "fontWeight": "600",
                                                                "marginTop": "8px"
                                                            }
                                                        )
                                                    ]
                                                ),
                                                # Per-station bars
                                                html.Div(
                                                    className="completeness-list",
                                                    id="completeness-bars"
                                                )
                                            ]
                                        )
                                    ]
                                )
                            ]
                        ),
                        
                        # Station Cards
                        html.Div(
                            className="card",
                            style={"marginTop": "24px"},
                            children=[
                                html.Div(
                                    className="card-header",
                                    children=[
                                        html.Div("Station Details", className="card-title")
                                    ]
                                ),
                                html.Div(
                                    className="card-body",
                                    children=[
                                        create_station_cards_section()
                                    ]
                                )
                            ]
                        )
                    ]
                )
            ]
        )
    ]
)


@callback(
    Output("toggle-uk", "className"),
    Output("toggle-who", "className"),
    Output("threshold-store", "data"),
    Input("toggle-uk", "n_clicks"),
    Input("toggle-who", "n_clicks"),
    State("threshold-store", "data")
)
def toggle_threshold(uk_clicks, who_clicks, current):
    """Handle WHO/UK threshold toggle."""
    if not uk_clicks and not who_clicks:
        return "toggle-option active", "toggle-option", "UK"
    
    ctx = callback_context
    if not ctx.triggered:
        return "toggle-option active", "toggle-option", "UK"
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if button_id == "toggle-uk":
        return "toggle-option active", "toggle-option", "UK"
    else:
        return "toggle-option", "toggle-option active", "WHO"

@callback(
    Output("toggle-dark", "className"),
    Output("toggle-light", "className"),
    Output("theme-store", "data"),
    Output("app-container", "data-theme"),
    Input("toggle-dark", "n_clicks"),
    Input("toggle-light", "n_clicks"),
    State("theme-store", "data")
)
def toggle_theme(dark_clicks, light_clicks, current):
    """Handle dark/light theme toggle."""
    if not dark_clicks and not light_clicks:
        return "toggle-option active", "toggle-option", "dark", "dark"
    
    ctx = callback_context
    if not ctx.triggered:
        return "toggle-option active", "toggle-option", "dark", "dark"
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if button_id == "toggle-dark":
        return "toggle-option active", "toggle-option", "dark", "dark"
    else:
        return "toggle-option", "toggle-option active", "light", "light"


@callback(
    Output("site_drop", "value"),
    Output("pol_drop", "value"),
    Output("date_range", "start_date"),
    Output("date_range", "end_date"),
    Input("reset_btn", "n_clicks"),
    prevent_initial_call=True
)
def reset_filters(n):
    """Reset all filters."""
    return [], None, None, None


@callback(
    Output("site_drop", "options"),
    Input("pol_drop", "value"),
    Input("date_range", "start_date"),
    Input("date_range", "end_date")
)
def update_site_dropdown(pollutant, start_date, end_date):
    """Update available sites."""
    df_filtered = wales_df_long.copy()
    if pollutant:
        df_filtered = df_filtered[df_filtered["pollutants"] == pollutant]
    if start_date and end_date:
        df_filtered = df_filtered[
            (df_filtered["date"] >= start_date) & (df_filtered["date"] <= end_date)
        ]
    return sorted(df_filtered["site"].unique())


@callback(
    Output("pol_drop", "options"),
    Input("site_drop", "value"),
    Input("date_range", "start_date"),
    Input("date_range", "end_date")
)
def update_pollutant_dropdown(sites, start_date, end_date):
    """Update available pollutants."""
    df_filtered = wales_df_long.copy()
    if sites:
        df_filtered = df_filtered[df_filtered["site"].isin(sites)]
    if start_date and end_date:
        df_filtered = df_filtered[
            (df_filtered["date"] >= start_date) & (df_filtered["date"] <= end_date)
        ]
    return sorted(df_filtered["pollutants"].unique())


@callback(
    Output("date_range", "min_date_allowed"),
    Output("date_range", "max_date_allowed"),
    Input("site_drop", "value"),
    Input("pol_drop", "value")
)
def update_date_picker(sites, pollutant):
    """Update date picker range."""
    df_filtered = wales_df_long.copy()
    if sites:
        df_filtered = df_filtered[df_filtered["site"].isin(sites)]
    if pollutant:
        df_filtered = df_filtered[df_filtered["pollutants"] == pollutant]
    
    if df_filtered.empty:
        return wales_df_long["date"].min().date(), wales_df_long["date"].max().date()
    
    return df_filtered["date"].min().date(), df_filtered["date"].max().date()

@callback(
    Output("meta-stations", "children"),
    Output("meta-pollutant", "children"),
    Output("meta-period", "children"),
    Input("site_drop", "value"),
    Input("pol_drop", "value"),
    Input("date_range", "start_date"),
    Input("date_range", "end_date")
)
def update_topbar(sites, pollutant, start_date, end_date):
    """Update topbar metadata."""
    stations_text = f"{len(sites)}" if sites else "--"
    pollutant_text = POLLUTANT_DISPLAY_NAMES.get(pollutant, pollutant) if pollutant else "--"
    period_text = format_date_range(start_date, end_date)
    
    return stations_text, pollutant_text, period_text

@callback(
    Output("time-series-chart", "figure"),
    Input("site_drop", "value"),
    Input("pol_drop", "value"),
    Input("date_range", "start_date"),
    Input("date_range", "end_date"),
    Input("threshold-store", "data")
)
def update_time_series(sites, pollutant, start_date, end_date, threshold_type):
    """Update time series chart with dark theme."""
    if not sites or not pollutant or not start_date or not end_date:
        # Empty state
        fig = go.Figure()
        fig.add_annotation(
            text="Select stations, pollutant, and date range",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=15, color="rgba(255,255,255,0.4)")
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=400,
            margin=dict(l=60, r=40, t=20, b=60)
        )
        return fig

    df_filtered = wales_df[
        (wales_df["site"].isin(sites)) &
        (wales_df[pollutant].notna()) &
        (wales_df["date"] >= start_date) &
        (wales_df["date"] <= end_date)
    ]

    if df_filtered.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=15, color="rgba(255,255,255,0.4)")
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=400
        )
        return fig

    # Create chart
    fig = px.line(
        df_filtered,
        x="date",
        y=pollutant,
        color="site",
        color_discrete_sequence=["#8FB569", "#A855F7", "#F59E0B", "#4ADE80", "#38BDF8"]
    )

    # Add threshold line
    threshold_source = LIMITS.get(threshold_type, {}).get(pollutant, {})
    threshold_val = threshold_source.get('daily') or threshold_source.get('hourly') or threshold_source.get('annual')
    
    if threshold_val:
        fig.add_hline(
            y=threshold_val,
            line_dash="dash",
            line_color="#EF4444",
            opacity=0.6,
            annotation_text=f"{threshold_type}: {threshold_val} μg/m³",
            annotation_position="right",
            annotation_font_size=11,
            annotation_font_color="#EF4444"
        )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={'color': '#FFFFFF', 'family': 'Inter'},
        height=400,
        margin=dict(l=60, r=40, t=20, b=60),
        xaxis_title="Date",
        yaxis_title=f"{POLLUTANT_DISPLAY_NAMES.get(pollutant, pollutant)} (μg/m³)",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        hovermode='x unified',
        xaxis=dict(gridcolor="rgba(255,255,255,0.1)", showgrid=True),
        yaxis=dict(gridcolor="rgba(255,255,255,0.1)", showgrid=True)
    )

    fig.update_traces(line=dict(width=2.5))

    return fig


@callback(
    Output("kpi-no2-value", "children"),
    Output("kpi-no2-subtitle", "children"),
    Output("kpi-no2-container", "className"),
    Output("kpi-pm25-value", "children"),
    Output("kpi-pm25-subtitle", "children"),
    Output("kpi-pm25-container", "className"),
    Output("kpi-exceed-value", "children"),
    Output("kpi-exceed-unit", "children"),
    Output("kpi-exceed-subtitle", "children"),
    Output("kpi-exceed-container", "className"),
    Output("kpi-complete-value", "children"),
    Output("kpi-complete-subtitle", "children"),
    Output("kpi-complete-container", "className"),
    Input("site_drop", "value"),
    Input("pol_drop", "value"),
    Input("date_range", "start_date"),
    Input("date_range", "end_date"),
    Input("threshold-store", "data")
)
def update_kpi_tiles(sites, pollutant, start_date, end_date, threshold_type):
    """Update all KPI tiles."""
    if not sites or not pollutant or not start_date or not end_date:
        return (
            "--", "Select data to view", "kpi-tile status-good",
            "--", "Select data to view", "kpi-tile status-good",
            "--", "days/hours", "Select data to view", "kpi-tile status-good",
            "--", "Select data to view", "kpi-tile status-good"
        )

    df_filtered = wales_df[
        (wales_df["site"].isin(sites)) &
        (wales_df["date"] >= start_date) &
        (wales_df["date"] <= end_date)
    ]

    if df_filtered.empty:
        return (
            "--", "No data available", "kpi-tile status-good",
            "--", "No data available", "kpi-tile status-good",
            "--", "days/hours", "No data available", "kpi-tile status-good",
            "--", "No data available", "kpi-tile status-good"
        )

    # NO2 Mean
    no2_mean = "--"
    no2_subtitle = "Not measured"
    no2_class = "kpi-tile status-good"
    if "NO2" in df_filtered.columns:
        no2_data = df_filtered["NO2"].dropna()
        if len(no2_data) > 0:
            no2_mean = round(no2_data.mean(), 1)
            no2_subtitle = f"n = {len(no2_data)} observations"
            no2_class = "kpi-tile status-good"

    # PM2.5 Mean
    pm25_mean = "--"
    pm25_subtitle = "Not measured"
    pm25_class = "kpi-tile status-good"
    if "PM2.5" in df_filtered.columns:
        pm25_data = df_filtered["PM2.5"].dropna()
        if len(pm25_data) > 0:
            pm25_mean = round(pm25_data.mean(), 1)
            pm25_subtitle = f"n = {len(pm25_data)} observations"
            pm25_class = "kpi-tile status-warning"

    # Calculate exceedance values
    exceed_result = calculate_exceedance_rosie(df_filtered, pollutant, threshold_type)
    exceed_val = exceed_result['value']
    exceed_unit = "count" if exceed_result['type'] == 'count' else "μg/m³"
    exceed_subtitle = exceed_result['label']
    
    # Determine status
    if exceed_result['type'] == 'count':
        exceed_status = get_status_class(exceed_val, exceed_result['limit'], is_exceedance=True)
    else:
        exceed_status = 'warning'
    
    exceed_class = f"kpi-tile status-{exceed_status}"

    # Completeness
    completeness = calculate_completeness(df_filtered, pollutant)
    completeness_val = f"{completeness}%"
    completeness_status = get_status_class(completeness, 100, is_exceedance=False)
    
    if completeness >= 85:
        completeness_subtitle = "Excellent data quality"
    elif completeness >= 75:
        completeness_subtitle = "Acceptable quality"
    else:
        completeness_subtitle = "Significant gaps"
    
    completeness_class = f"kpi-tile status-{completeness_status}"

    return (
        no2_mean, no2_subtitle, no2_class,
        pm25_mean, pm25_subtitle, pm25_class,
        exceed_val, exceed_unit, exceed_subtitle, exceed_class,
        completeness_val, completeness_subtitle, completeness_class
    )


@callback(
    Output("stat-mean", "children"),
    Output("stat-median", "children"),
    Output("stat-std", "children"),
    Output("stat-min", "children"),
    Output("stat-max", "children"),
    Output("stat-iqr", "children"),
    Input("site_drop", "value"),
    Input("pol_drop", "value"),
    Input("date_range", "start_date"),
    Input("date_range", "end_date")
)
def update_summary_stats(sites, pollutant, start_date, end_date):
    """Update summary statistics."""
    if not sites or not pollutant or not start_date or not end_date:
        return "--", "--", "--", "--", "--", "--"

    df_filtered = wales_df[
        (wales_df["site"].isin(sites)) &
        (wales_df["date"] >= start_date) &
        (wales_df["date"] <= end_date)
    ]

    stats = calculate_summary_stats(df_filtered, pollutant)
    
    return (
        stats['mean'],
        stats['median'],
        stats['std'],
        stats['min'],
        stats['max'],
        stats['iqr']
    )

@callback(
    Output("completeness-overall", "children"),
    Output("completeness-bars", "children"),
    Input("site_drop", "value"),
    Input("pol_drop", "value"),
    Input("date_range", "start_date"),
    Input("date_range", "end_date")
)
def update_completeness(sites, pollutant, start_date, end_date):
    """Update completeness panel."""
    if not sites or not pollutant or not start_date or not end_date:
        return "--", []

    df_filtered = wales_df[
        (wales_df["site"].isin(sites)) &
        (wales_df["date"] >= start_date) &
        (wales_df["date"] <= end_date)
    ]

    # Overall
    overall = calculate_completeness(df_filtered, pollutant)
    overall_text = f"{overall}%"

    # Per-site
    site_results = calculate_completeness_by_site(df_filtered, sites, pollutant)
    
    bars = []
    for result in site_results:
        bars.append(
            html.Div(
                className="completeness-item",
                children=[
                    html.Div(result['site'], className="completeness-label"),
                    html.Div(
                        className="completeness-bar-track",
                        children=[
                            html.Div(
                                className=f"completeness-bar-fill status-{result['status']}",
                                style={"width": f"{result['completeness']}%"}
                            )
                        ]
                    ),
                    html.Div(f"{result['completeness']}%", className="completeness-percentage")
                ]
            )
        )

    return overall_text, bars

@callback(
    Output("station-cards-container", "children"),
    Input("site_drop", "value"),
    Input("pol_drop", "value"),
    Input("date_range", "start_date"),
    Input("date_range", "end_date"),
    Input("threshold-store", "data")
)
def update_station_cards(sites, pollutant, start_date, end_date, threshold_type):
    """Update station cards with gauges."""
    if not sites or not pollutant or not start_date or not end_date:
        return html.Div(
            "Select stations and pollutant to view details",
            style={"textAlign": "center", "color": "var(--text-tertiary)", "padding": "40px"}
        )

    cards = []
    
    for site in sites:
        site_df = wales_df[
            (wales_df["site"] == site) &
            (wales_df["date"] >= start_date) &
            (wales_df["date"] <= end_date)
        ]
        
        if site_df.empty:
            continue
        
        # Calculate metrics
        exceed_result = calculate_exceedance_rosie(site_df, pollutant, threshold_type)
        completeness = calculate_completeness(site_df, pollutant)
        
        # Determine colors
        if exceed_result['type'] == 'count':
            exceed_color = "#EF4444" if exceed_result['value'] > exceed_result['limit'] else "#10B981"
        else:
            exceed_color = "#F59E0B"
        
        comp_color = "#10B981" if completeness >= 85 else "#F59E0B" if completeness >= 75 else "#EF4444"
        
        cards.append(
            html.Div(
                className="station-card",
                children=[
                    html.Div(
                        className="station-info",
                        children=[
                            html.Div(site, className="station-name"),
                            html.Div(
                                f"{len(site_df)} observations",
                                className="station-meta"
                            )
                        ]
                    ),
                    html.Div(
                        className="gauge-container",
                        children=[
                            html.Div(
                                children=[
                                    dcc.Graph(
                                        figure=create_circular_gauge(
                                            exceed_result['value'],
                                            exceed_result['limit'] if exceed_result['limit'] > 0 else 100,
                                            exceed_color,
                                            60
                                        ),
                                        config={'displayModeBar': False},
                                        style={"height": "60px", "width": "60px"}
                                    ),
                                    html.Div(
                                        POLLUTANT_DISPLAY_NAMES.get(pollutant, pollutant),
                                        className="gauge-label"
                                    )
                                ]
                            ),
                            html.Div(
                                children=[
                                    dcc.Graph(
                                        figure=create_circular_gauge(
                                            completeness,
                                            100,
                                            comp_color,
                                            60
                                        ),
                                        config={'displayModeBar': False},
                                        style={"height": "60px", "width": "60px"}
                                    ),
                                    html.Div("Complete", className="gauge-label")
                                ]
                            )
                        ]
                    )
                ]
            )
        )
    
    if not cards:
        return html.Div(
            "No data available for selected filters",
            style={"textAlign": "center", "color": "var(--text-tertiary)", "padding": "40px"}
        )
    
    return html.Div(className="station-grid", children=cards)


if __name__ == "__main__":
    app.run(debug=True, port=8052)
