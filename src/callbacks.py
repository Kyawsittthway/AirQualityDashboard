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
    calculate_exceedance_rosie,
    calculate_completeness,
    calculate_completeness_by_site,
    calculate_summary_stats,
    get_status_class,
    format_date_range,
    LIMITS,
    POLLUTANT_DISPLAY_NAMES,
)
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

    pol_to_sites = wales_df_long.groupby(
        "pollutants")["site"].apply(set).to_dict()

    all_sites = sorted(wales_df_long["site"].unique())
    all_pollutants = sorted(wales_df_long["pollutants"].unique())
    global_min = wales_df_long["date"].min().date()
    global_max = wales_df_long["date"].max().date()

    def has_full_date_range(start_date, end_date):
        return bool(start_date) and bool(end_date)

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
            start_dt = pd.to_datetime(
                start_date).date() if date_active else None
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
        n_clicks, sites, pollutant,
        yday, last_week, last_month,
        dq,
        start_date, end_date,
        stored_dates,
    ):
        triggered = callback_context.triggered_id
        sites = sites or []

        if triggered == "reset_btn":
            return None, None

        today = date.today()

        if triggered == "yday":
            yesterday = today - timedelta(days=1)
            end = min(yesterday, RATIFIED_CUTOFF.date()
                      ) if dq == "Ratified" else yesterday
            return yesterday, end
        elif triggered == "last_week":
            start = today - timedelta(days=7)
            end = min(today, RATIFIED_CUTOFF.date()
                      ) if dq == "Ratified" else today
            return start, end
        elif triggered == "last_month":
            start = today - timedelta(days=30)
            end = min(today, RATIFIED_CUTOFF.date()
                      ) if dq == "Ratified" else today
            return start, end

        min_allowed, max_allowed = compute_allowed_bounds(sites, pollutant)

        if min_allowed is None or max_allowed is None:
            return None, None

        if dq == "Ratified":
            max_allowed = min(max_allowed, RATIFIED_CUTOFF.date())

        effective_start = stored_dates["start"] if stored_dates else start_date
        effective_end = stored_dates["end"] if stored_dates else end_date

        if dq == "Ratified" and effective_end:
            effective_end = str(min(
                pd.to_datetime(effective_end).date(),
                RATIFIED_CUTOFF.date()
            ))

        if not has_full_date_range(effective_start, effective_end):
            return no_update, no_update

        try:
            cs = pd.to_datetime(effective_start).date()
            ce = pd.to_datetime(effective_end).date()
        except Exception:
            return None, None

        if (
            cs < min_allowed
            or cs > max_allowed
            or ce < min_allowed
            or ce > max_allowed
        ):
            return None, None

        return effective_start, effective_end

    # ─────────────────────────────────────────────────────────────
    # 8) Warning banner
    # ─────────────────────────────────────────────────────────────

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

        sites_missing_pollutant = [
            s for s in sites if pollutant not in site_to_pollutants.get(s, set())
        ]
        if sites_missing_pollutant:
            return (
                f"⚠️ The following sites do not measure {pollutant} and will not "
                f"appear on the graph: {', '.join(sites_missing_pollutant)}",
                visible,
            )

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

    # ─────────────────────────────────────────────────────────────
    # 9) Hourly graph
    # ─────────────────────────────────────────────────────────────

    @app.callback(
        Output("time-series-chart", "figure"),
        Input("site_drop", "value"),
        Input("pol_drop", "value"),
        Input("date_range", "start_date"),
        Input("date_range", "end_date"),
        Input("dq_store", "data"),
    )
    def update_graph(selected_sites, pollutant, start_date, end_date, dq):
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
        end_dt = pd.to_datetime(end_date) + \
            pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        start_dt, end_dt = apply_dq_cap(start_dt, end_dt, dq)

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

    # ─────────────────────────────────────────────────────────────
    # 10) Topbar metadata
    # ─────────────────────────────────────────────────────────────

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
            POLLUTANT_DISPLAY_NAMES.get(
                pollutant, pollutant) if pollutant else "--"
        )
        period_text = format_date_range(start_date, end_date)
        return stations_text, pollutant_text, period_text

    # ─────────────────────────────────────────────────────────────
    # 11) Summary statistics table
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
        end_dt = pd.to_datetime(end_date) + \
            pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
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
                columns=[{"name": col, "id": col}
                         for col in summary_df.columns],
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

    # ─────────────────────────────────────────────────────────────
    # 12) Data completeness panel
    # ─────────────────────────────────────────────────────────────

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
        end_dt = pd.to_datetime(end_date) + \
            pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        start_dt, end_dt = apply_dq_cap(start_dt, end_dt, dq)

        df_filtered = wales_df[
            (wales_df["site"].isin(sites))
            & (wales_df["date"] >= start_dt)
            & (wales_df["date"] <= end_dt)
        ]

        overall = calculate_completeness(df_filtered, pollutant)
        overall_text = f"{overall}%"

        site_results = calculate_completeness_by_site(
            df_filtered, sites, pollutant)

        bars = []
        for result in site_results:
            bars.append(
                html.Div(
                    className="completeness-item",
                    children=[
                        html.Div(result["site"],
                                 className="completeness-label"),
                        html.Div(
                            className="completeness-bar-track",
                            children=[
                                html.Div(
                                    className=f"completeness-bar-fill status-{result['status']}",
                                    style={
                                        "width": f"{result['completeness']}%"},
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

    # ─────────────────────────────────────────────────────────────
    # 13) Quick select button active glow
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
