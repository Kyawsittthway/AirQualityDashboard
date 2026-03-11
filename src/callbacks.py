# src/callbacks.py

from dash import (
    Dash,
    html,
    dcc,
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
from components.kpi_tiles import create_kpi_tiles
from components.station_cards import create_station_cards_section, create_circular_gauge
from utils.calculations import (
    calculate_exceedance_rosie,
    calculate_completeness,
    calculate_completeness_by_site,
    calculate_summary_stats,
    get_status_class,
    format_date_range,
    LIMITS,
    POLLUTANT_DISPLAY_NAMES,
)
from dataloader import load_data

wales_df, wales_df_long = load_data()


@callback(
    Output("toggle-uk", "className"),
    Output("toggle-who", "className"),
    Output("threshold-store", "data"),
    Input("toggle-uk", "n_clicks"),
    Input("toggle-who", "n_clicks"),
    State("threshold-store", "data"),
)
def toggle_threshold(uk_clicks, who_clicks, current):
    """Handle WHO/UK threshold toggle."""
    if not uk_clicks and not who_clicks:
        return "toggle-option active", "toggle-option", "UK"

    ctx = callback_context
    if not ctx.triggered:
        return "toggle-option active", "toggle-option", "UK"

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

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
    State("theme-store", "data"),
)
def toggle_theme(dark_clicks, light_clicks, current):
    """Handle dark/light theme toggle."""
    if not dark_clicks and not light_clicks:
        return "toggle-option active", "toggle-option", "dark", "dark"

    ctx = callback_context
    if not ctx.triggered:
        return "toggle-option active", "toggle-option", "dark", "dark"

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "toggle-dark":
        return "toggle-option active", "toggle-option", "dark", "dark"
    else:
        return "toggle-option", "toggle-option active", "light", "light"


def register_callbacks(app, wales_df, wales_df_long):
    # Precomputed maps to reduce repetition and increase dashboard's speed

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

    all_sites = sorted(wales_df_long["site"].unique())
    all_pollutants = sorted(wales_df_long["pollutants"].unique())
    global_min = wales_df_long["date"].min().date()
    global_max = wales_df_long["date"].max().date()

    def has_full_date_range(start_date, end_date):
        return bool(start_date) and bool(end_date)

    # Function to compute intersection window (date-only) for current selection
    def compute_allowed_bounds(sites, pollutant):
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

    # 1) Update site dropdown OPTIONS based on pollutant + date range

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
            # Date range active (with or without pollutant)
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

    # 2) Update pollutant dropdown OPTIONS based on sites + date range

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

    # 3) Reset dropdown VALUES

    @app.callback(
        Output("site_drop", "value"),
        Output("pol_drop", "value"),
        Input("reset_btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def reset_dropdowns(n_clicks):
        return [], None

        # 4) Sync filter_store with current UI values

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

    # 5) Update ONLY date_range bounds from store

    @app.callback(
        Output("date_range", "min_date_allowed"),
        Output("date_range", "max_date_allowed"),
        Input("filter_store", "data"),
    )
    def update_date_bounds(store):
        if not store:
            return global_min, global_max

        sites = store.get("sites", []) or []
        pollutant = store.get("pollutant")

        min_allowed, max_allowed = compute_allowed_bounds(sites, pollutant)

        if min_allowed is None or max_allowed is None:
            # Keep DatePicker usable even if no overlap — user can change selection
            return global_min, global_max

        return min_allowed, max_allowed

    # 6) Manage date selection
    #    - Reset clears selected dates
    #    - Changing sites/pollutant clears selected dates if they become invalid

    @app.callback(
        Output("date_range", "start_date"),
        Output("date_range", "end_date"),
        Input("reset_btn", "n_clicks"),
        Input("site_drop", "value"),
        Input("pol_drop", "value"),
        State("date_range", "start_date"),
        State("date_range", "end_date"),
    )
    def manage_date_selection(n_clicks, sites, pollutant, start_date, end_date):
        triggered = callback_context.triggered_id
        sites = sites or []

        # Reset always clears date selection
        if triggered == "reset_btn":
            return None, None

        min_allowed, max_allowed = compute_allowed_bounds(sites, pollutant)

        # If no overlap or no valid ranges, clear date selection
        if min_allowed is None or max_allowed is None:
            return None, None

        # If user hasn't chosen both dates yet
        if not has_full_date_range(start_date, end_date):
            return no_update, no_update

        # If current selection is outside allowed bounds, clear it
        try:
            cs = pd.to_datetime(start_date).date()
            ce = pd.to_datetime(end_date).date()
        except Exception:
            return None, None

        if cs < min_allowed or cs > max_allowed or ce < min_allowed or ce > max_allowed:
            return None, None

        return no_update, no_update
        # 7) Warning banner

    @app.callback(
        Output("filter_warning", "children"),
        Output("filter_warning", "style"),
        Input("site_drop", "value"),
        Input("pol_drop", "value"),
        Input("date_range", "start_date"),
        Input("date_range", "end_date"),
    )
    def show_filter_warning(sites, pollutant, start_date, end_date):
        hidden = {"display": "none"}
        visible = {
            "color": "#856404",
            "backgroundColor": "#fff3cd",
            "border": "1px solid #ffc107",
            "borderRadius": "4px",
            "padding": "10px 16px",
            "margin": "8px 0",
            "display": "block",
        }

        sites = sites or []
        date_active = has_full_date_range(start_date, end_date)

        if not sites or not pollutant:
            return "", hidden

        # Sites that don't measure the pollutant
        sites_missing_pollutant = [
            s for s in sites if pollutant not in site_to_pollutants.get(s, set())
        ]
        if sites_missing_pollutant:
            return (
                f"⚠️ The following sites do not measure {pollutant} and will not "
                f"appear on the graph: {', '.join(sites_missing_pollutant)}",
                visible,
            )

        # If the date intersection for the selected sites is empty, tell user that there is no overlapping time period
        min_allowed, max_allowed = compute_allowed_bounds(sites, pollutant)
        if min_allowed is None or max_allowed is None:
            return (
                "⚠️ No overlapping time period exists across the selected sites "
                "(and pollutant). Try fewer sites or remove the pollutant filter.",
                visible,
            )

        if date_active:
            start_d = pd.to_datetime(start_date).date()
            end_d = pd.to_datetime(end_date).date()

            # Sites with no data for (site, pollutant) in selected date range
            sites_no_data = [
                s
                for s in sites
                if (s, pollutant) not in site_pol_to_dates
                or site_pol_to_dates[(s, pollutant)][1] < start_d
                or site_pol_to_dates[(s, pollutant)][0] > end_d
            ]

            if sites_no_data:
                return (
                    f"⚠️ No {pollutant} data in the selected date range for: "
                    f"{', '.join(sites_no_data)}. Try expanding the date range.",
                    visible,
                )

        return "", hidden

    # 8) HOURLY Graph

    @app.callback(
        Output("time-series-chart", "figure"),
        Input("site_drop", "value"),
        Input("pol_drop", "value"),
        Input("date_range", "start_date"),
        Input("date_range", "end_date"),
    )
    def update_graph(selected_sites, pollutant, start_date, end_date):
        selected_sites = selected_sites or []

        if (
            not selected_sites
            or not pollutant
            or not has_full_date_range(start_date, end_date)
        ):
            fig = px.line(title="Select sites, a pollutant, and a date range")
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=400,
            )
            return fig

        start_dt = pd.to_datetime(start_date)
        end_dt = (
            pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        )

        df = wales_df[
            (wales_df["site"].isin(selected_sites))
            & (wales_df["date"] >= start_dt)
            & (wales_df["date"] <= end_dt)
        ].copy()

        if df.empty:
            fig = px.line(title="No data for this selection")
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=400,
            )
            return fig

        df = df.sort_values(["site", "date"])

        fig = px.line(df, x="date", y=pollutant, color="site")
        fig.update_traces(connectgaps=False)

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=400,
            xaxis_title="Date/Time",
            yaxis_title=f"{pollutant} (µg/m³)",
            legend_title="Site",
            margin=dict(t=60),
        )
        return fig


@callback(
    Output("meta-stations", "children"),
    Output("meta-pollutant", "children"),
    Output("meta-period", "children"),
    Input("site_drop", "value"),
    Input("pol_drop", "value"),
    Input("date_range", "start_date"),
    Input("date_range", "end_date"),
)
def update_topbar(sites, pollutant, start_date, end_date):
    """Update topbar metadata."""
    stations_text = f"{len(sites)}" if sites else "--"
    pollutant_text = (
        POLLUTANT_DISPLAY_NAMES.get(pollutant, pollutant) if pollutant else "--"
    )
    period_text = format_date_range(start_date, end_date)

    return stations_text, pollutant_text, period_text


@callback(
    Output("kpi-no2-value", "children"),
    Output("kpi-no2-subtitle", "children"),
    Output("kpi-no2-container", "className"),
    # Output("kpi-pm25-value", "children"),
    # Output("kpi-pm25-subtitle", "children"),
    # Output("kpi-pm25-container", "className"),
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
    Input("threshold-store", "data"),
)
def update_kpi_tiles(sites, pollutant, start_date, end_date, threshold_type):
    """Update all KPI tiles."""
    if not sites or not pollutant or not start_date or not end_date:
        return (
            "--",
            "Select data to view",
            "kpi-tile status-good",
            # "--",
            # "Select data to view",
            # "kpi-tile status-good",
            "--",
            "days/hours",
            "Select data to view",
            "kpi-tile status-good",
            "--",
            "Select data to view",
            "kpi-tile status-good",
        )

    df_filtered = wales_df[
        (wales_df["site"].isin(sites))
        & (wales_df["date"] >= start_date)
        & (wales_df["date"] <= end_date)
    ]

    if df_filtered.empty:
        return (
            "--",
            "No data available",
            "kpi-tile status-good",
            # "--",
            # "No data available",
            # "kpi-tile status-good",
            "--",
            "days/hours",
            "No data available",
            "kpi-tile status-good",
            "--",
            "No data available",
            "kpi-tile status-good",
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
    exceed_val = exceed_result["value"]
    exceed_unit = "count" if exceed_result["type"] == "count" else "μg/m³"
    exceed_subtitle = exceed_result["label"]

    # Determine status
    if exceed_result["type"] == "count":
        exceed_status = get_status_class(
            exceed_val, exceed_result["limit"], is_exceedance=True
        )
    else:
        exceed_status = "warning"

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
        no2_mean,
        no2_subtitle,
        no2_class,
        # pm25_mean,
        # pm25_subtitle,
        # pm25_class,
        exceed_val,
        exceed_unit,
        exceed_subtitle,
        exceed_class,
        completeness_val,
        completeness_subtitle,
        completeness_class,
    )


@callback(
    Output("stats_container", "children"),
    Input("site_drop", "value"),
    Input("pol_drop", "value"),
    Input("date_range", "start_date"),
    Input("date_range", "end_date"),
)
def update_summary_stats(sites, pollutant, start_date, end_date):
    if not sites or not pollutant or not start_date or not end_date:
        return html.Div(
            "Please select site(s), a pollutant, and a date range to generate statistics.",
            className="text-muted italic",
        )

    mask = (
        wales_df_long["site"].isin(sites)
        & (wales_df_long["pollutants"] == pollutant)
        & (wales_df_long["date"] >= pd.to_datetime(start_date))
        & (wales_df_long["date"] <= pd.to_datetime(end_date))
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
                "padding": "12px 10px",
                "fontFamily": "Inter, sans-serif",
                "fontSize": "14px",
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
                "fontSize": "12px",
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
        className="stats-table",
    )


@callback(
    Output("completeness-overall", "children"),
    Output("completeness-bars", "children"),
    Input("site_drop", "value"),
    Input("pol_drop", "value"),
    Input("date_range", "start_date"),
    Input("date_range", "end_date"),
)
def update_completeness(sites, pollutant, start_date, end_date):
    """Update completeness panel."""
    if not sites or not pollutant or not start_date or not end_date:
        return "--", []

    df_filtered = wales_df[
        (wales_df["site"].isin(sites))
        & (wales_df["date"] >= start_date)
        & (wales_df["date"] <= end_date)
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


@callback(
    Output("station-cards-container", "children"),
    Input("site_drop", "value"),
    Input("pol_drop", "value"),
    Input("date_range", "start_date"),
    Input("date_range", "end_date"),
    Input("threshold-store", "data"),
)
def update_station_cards(sites, pollutant, start_date, end_date, threshold_type):
    """Update station cards with gauges."""
    if not sites or not pollutant or not start_date or not end_date:
        return html.Div(
            "Select stations and pollutant to view details",
            style={
                "textAlign": "center",
                "color": "var(--text-tertiary)",
                "padding": "40px",
            },
        )

    cards = []

    for site in sites:
        site_df = wales_df[
            (wales_df["site"] == site)
            & (wales_df["date"] >= start_date)
            & (wales_df["date"] <= end_date)
        ]

        if site_df.empty:
            continue

        # Calculate metrics
        exceed_result = calculate_exceedance_rosie(site_df, pollutant, threshold_type)
        completeness = calculate_completeness(site_df, pollutant)

        # Determine colors
        if exceed_result["type"] == "count":
            exceed_color = (
                "#EF4444"
                if exceed_result["value"] > exceed_result["limit"]
                else "#10B981"
            )
        else:
            exceed_color = "#F59E0B"

        comp_color = (
            "#10B981"
            if completeness >= 85
            else "#F59E0B" if completeness >= 75 else "#EF4444"
        )

        cards.append(
            html.Div(
                className="station-card",
                children=[
                    html.Div(
                        className="station-info",
                        children=[
                            html.Div(site, className="station-name"),
                            html.Div(
                                f"{len(site_df)} observations", className="station-meta"
                            ),
                        ],
                    ),
                    html.Div(
                        className="gauge-container",
                        children=[
                            html.Div(
                                children=[
                                    dcc.Graph(
                                        figure=create_circular_gauge(
                                            exceed_result["value"],
                                            (
                                                exceed_result["limit"]
                                                if exceed_result["limit"] > 0
                                                else 100
                                            ),
                                            exceed_color,
                                            60,
                                        ),
                                        config={"displayModeBar": False},
                                        style={"height": "60px", "width": "60px"},
                                    ),
                                    html.Div(
                                        POLLUTANT_DISPLAY_NAMES.get(
                                            pollutant, pollutant
                                        ),
                                        className="gauge-label",
                                    ),
                                ]
                            ),
                            html.Div(
                                children=[
                                    dcc.Graph(
                                        figure=create_circular_gauge(
                                            completeness, 100, comp_color, 60
                                        ),
                                        config={"displayModeBar": False},
                                        style={"height": "60px", "width": "60px"},
                                    ),
                                    html.Div("Complete", className="gauge-label"),
                                ]
                            ),
                        ],
                    ),
                ],
            )
        )

    if not cards:
        return html.Div(
            "No data available for selected filters",
            style={
                "textAlign": "center",
                "color": "var(--text-tertiary)",
                "padding": "40px",
            },
        )

    return html.Div(className="station-grid", children=cards)
