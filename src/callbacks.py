# src/callbacks.py

from dash import Input, Output, State, no_update, callback_context
import pandas as pd
import plotly.express as px


def register_callbacks(app, wales_df, wales_df_long):
    # Precomputed maps to reduce repetition and increase dashboard's speed

    site_to_pollutants = (
        wales_df_long.groupby("site")["pollutants"]
        .apply(set)
        .to_dict()
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

    pol_to_sites = (
        wales_df_long.groupby("pollutants")["site"]
        .apply(set)
        .to_dict()
    )

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

            candidates = pol_to_sites.get(pollutant, set(
                all_sites)) if pollutant else set(all_sites)

            valid = sorted([
                site for site in candidates
                if site in site_to_dates
                and site_to_dates[site][0] <= end_dt
                and site_to_dates[site][1] >= start_dt
            ])

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
            start_dt = pd.to_datetime(
                start_date).date() if date_active else None
            end_dt = pd.to_datetime(end_date).date() if date_active else None

            if not sites:
                valid = all_pollutants
                if date_active:
                    valid = sorted(
                        p for p, (p_min, p_max) in pol_to_dates.items()
                        if p_min <= end_dt and p_max >= start_dt
                    )
            else:
                common = set.intersection(*[
                    site_to_pollutants[s] for s in sites if s in site_to_pollutants
                ]) if sites else set(all_pollutants)

                if date_active:
                    common = {
                        p for p in common
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
            s for s in sites
            if pollutant not in site_to_pollutants.get(s, set())
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
                s for s in sites
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
        Output("controls-and-graph", "figure"),
        Input("site_drop", "value"),
        Input("pol_drop", "value"),
        Input("date_range", "start_date"),
        Input("date_range", "end_date"),
    )
    def update_graph(selected_sites, pollutant, start_date, end_date):
        selected_sites = selected_sites or []

        if not selected_sites or not pollutant or not has_full_date_range(start_date, end_date):
            return px.line(title="Select sites, a pollutant, and a date range")

        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date) + \
            pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

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
            xaxis_title="Date/Time",
            yaxis_title=f"{pollutant} (µg/m³)",
            legend_title="Site",
            margin=dict(t=60),
        )
        return fig
