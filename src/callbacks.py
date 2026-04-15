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
    ALL,
)
from flask import app
import pandas as pd
import numpy as np
import statsmodels.api as sm
import plotly.express as px
import plotly.graph_objects as go
from utils.gemini_insights import generate_forecast_insight
from components.sidebar import create_sidebar
from utils.calculations import (
    calculate_exceedance,
    calculate_completeness,
    calculate_completeness_by_site,
    calculate_summary_stats,
    get_status_class,
    format_date_range,
    exceedance_summary,
    degrees_to_direction,
    aqi_index,
    aqi_category,
    LIMITS,
    POLLUTANT_DISPLAY_NAMES,

)
from utils.predictor import AQIPredictor, SITE_META
from utils.weather_utils import get_weather_forecast, get_weather_fallback
from datetime import date, timedelta

RATIFIED_CUTOFF = pd.Timestamp("2025-09-30 00:00:00")


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


def _aqi_colour(band):
    if band <= 3:
        return "#4caf7d"
    if band <= 6:
        return "#e0a920"
    if band <= 9:
        return "#e05a20"
    return "#c93030"


def _aqi_label(band):
    if band <= 3:
        return "Low"
    if band <= 6:
        return "Moderate"
    if band <= 9:
        return "High"
    return "Very High"


def unpack_store(store):
    if not store:
        return None, []
    if isinstance(store, list):
        return store, ["NO2", "O3", "SO2", "PM10", "PM2.5"]
    return list(store[0])


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

    def load_history_from_df(wales_df, site, n_days=21):
        cutoff = wales_df["date"].max() - pd.Timedelta(days=n_days)
        site_df = wales_df[(wales_df["site"] == site) & (
            wales_df["date"] > cutoff)].copy()
        sdf = site_df.copy()

        if sdf.empty:
            return None
        pollutants_filtered = list(active_sites_to_pollutants.get(site, []))
        cols_to_keep = ["date"] + \
            [p for p in pollutants_filtered if p in sdf.columns]
        sdf = sdf[cols_to_keep]

        for col in pollutants_filtered:
            sdf[col] = sdf[col].clip(lower=0)

        sdf["day"] = sdf["date"].dt.date
        results = {}

        # NO2 – daily median (≥18 hourly readings)
        if "NO2" in pollutants_filtered:
            results["NO2"] = sdf.groupby("day")["NO2"].agg(
                lambda x: x.median() if x.count() >= 18 else np.nan
            )

        # O3 – daily max of 8-hour rolling mean
        if "O3" in pollutants_filtered:
            o3_temp = sdf[["date", "day", "O3"]].sort_values("date").copy()
            o3_temp["o3_8h"] = (
                o3_temp.groupby("day")["O3"]
                .transform(lambda s: s.rolling(8, min_periods=6).mean())
            )
            results["O3"] = o3_temp.groupby("day")["o3_8h"].max()

        # SO2 – daily max
        if "SO2" in pollutants_filtered:
            results["SO2"] = sdf.groupby("day")["SO2"].agg(
                lambda x: x.max() if x.count() >= 18 else np.nan
            )

        # PM10 / PM2.5 – daily mean
        if "PM10" in pollutants_filtered:
            results["PM10"] = sdf.groupby("day")["PM10"].agg(
                lambda x: x.mean() if x.count() >= 18 else np.nan
            )
        if "PM2.5" in pollutants_filtered:
            results["PM2.5"] = sdf.groupby("day")["PM2.5"].agg(
                lambda x: x.mean() if x.count() >= 18 else np.nan
            )

        daily = pd.DataFrame(results).reset_index().rename(
            columns={"day": "date"})

        daily["date"] = pd.to_datetime(daily["date"])
        daily = daily.sort_values("date").reset_index(drop=True)

        # Fill any remaining NaNs with site median so lag features never go NaN
        for col in pollutants_filtered:
            median = daily[col].median()
            daily[col] = daily[col].fillna(0.0 if np.isnan(median) else median)

        return daily

    # loading AQI predictor
    aqi_predictor = AQIPredictor(model_dir=r"src\utils")

    @app.callback(
        Output("forecast-store", "data"),
        Output("forecast-warning", "children"),
        Output("forecast-warning", "style"),
        Input("site_drop_forecast", "value"),
    )
    def run_forecast(site):
        if not site:
            return None, "", {"display": "none"}
        history = load_history_from_df(wales_df, site)
        if history is None:
            return None, f"No recent data found for {site}.", {"display": "block"}
        meta = SITE_META[site]
        start = date.today()
        try:
            weather = get_weather_forecast(meta["lat"], meta["lon"])
        except Exception:
            weather = get_weather_fallback(start)
        measured = active_sites_to_pollutants[site]
        try:
            forecast = aqi_predictor.predict(
                site=site, history=history, weather_fc=weather, start_date=start, pollutants=measured)
        except Exception as exc:
            return None, f"Forecast error: {exc}", {"display": "block"}
        for i, day in enumerate(forecast):
            day["weather"] = weather[i]
        return forecast, "", {"display": "none"}

    @app.callback(
        Output("fc-meta-type",  "children"),
        Output("fc-meta-start", "children"),
        Output("fc-meta-peak",  "children"),
        Output("fc-meta-peak",  "style"),
        Output("fc-meta-worst", "children"),
        Output("fc-meta-avg",   "children"),
        Input("forecast-store", "data"),
        Input("site_drop_forecast", "value"),
    )
    def update_forecast_summary(forecast, site):
        pollutants = list(active_sites_to_pollutants.get(site, []))
        if not forecast or not site:
            return "—", "—", "—", {}, "—", "—"
        loc_type = SITE_META.get(site, {}).get("type", "—")
        start_str = forecast[0]["date"]
        aqis = [d["aqi"] for d in forecast]
        peak = max(aqis)
        avg = round(sum(aqis) / len(aqis), 1)
        poll_avg = {
            p: sum(d["pollutants"][p]["band"] for d in forecast) / 7
            for p in pollutants
        }
        worst = max(poll_avg, key=poll_avg.get)
        poll_labels = {"NO2": "NO₂", "O3": "O₃",
                       "SO2": "SO₂", "PM10": "PM10", "PM2.5": "PM2.5"}
        peak_colour = _aqi_colour(peak)
        return (
            loc_type, start_str,
            f"{peak} – {_aqi_label(peak)}",
            {"color": peak_colour, "fontWeight": "500"},
            poll_labels.get(worst, worst),
            str(avg),
        )

    @app.callback(
        Output("forecast-day-grid", "children"),
        Input("forecast-store", "data"),
        Input("forecast-active-day", "data"),
    )
    def update_day_grid(forecast, active_day):
        _dow = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        if not forecast:
            return [
                html.Div(className="forecast-day-card forecast-day-card--skeleton",
                         children=[html.Div(d, className="forecast-day-label")])
                for d in _dow
            ]

        cards = []
        for i, day in enumerate(forecast):
            dt = pd.to_datetime(day["date"])
            aqi = day["aqi"]

            # --- CALCULATE RANGE ---
            aqi_min = max(1, aqi - 1)
            aqi_max = min(10, aqi + 1)
            confidence_text = f"Confidence Range: {aqi_min} - {aqi_max} AQI"
            # -----------------------

            colour = _aqi_colour(aqi)
            cards.append(html.Div(
                id={"type": "forecast-day-card", "index": i},
                className=f"forecast-day-card{' forecast-day-card--active' if i == active_day else ''}",
                n_clicks=0,

                # ADD TITLE HERE for the hover effect
                title=confidence_text,

                children=[
                    html.Div(_dow[dt.dayofweek],
                             className="forecast-day-label"),
                    html.Div(f"{dt.day} {dt.strftime('%b')}",
                             className="forecast-day-date"),
                    html.Div(str(aqi), className="forecast-day-badge",
                             style={"background": colour + "22", "color": colour, "borderColor": colour + "55"}),
                    html.Div(_aqi_label(aqi), className="forecast-day-band-label",
                             style={"color": colour}),
                ],
            ))
        return cards

    @app.callback(
        Output("forecast-active-day", "data", allow_duplicate=True),
        Input({"type": "forecast-day-card", "index": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def select_forecast_day(n_clicks_list):
        if not any(n_clicks_list):
            return no_update
        return int(np.argmax(n_clicks_list))

    @app.callback(
        Output("fc-detail-title",  "children"),
        Output("fc-detail-badge",  "children"),
        Output("fc-detail-badge",  "style"),
        Output("fc-detail-body",   "children"),
        Output("fc-weather-temp",  "children"),
        Output("fc-weather-ws",    "children"),
        Output("fc-weather-wd",    "children"),
        Input("forecast-store",    "data"),
        Input("forecast-active-day", "data"),
        Input("site_drop_forecast", "value")
    )
    def update_forecast_detail(forecast, active_day, forecast_site):
        poll_labels = {"NO2": "NO₂", "O3": "O₃",
                       "SO2": "SO₂", "PM10": "PM10", "PM2.5": "PM2.5"}

        poll_max = {"NO2": 120, "O3": 160, "SO2": 200, "PM10": 80, "PM2.5": 50}
        if not forecast:
            return "Select a day", "—", {}, [], "—", "—", "—"
        day = forecast[active_day]
        dt = pd.to_datetime(day["date"])
        aqi = day["aqi"]
        colour = _aqi_colour(aqi)
        rows = []
        pollutants = active_sites_to_pollutants[forecast_site]
        for p in pollutants:
            info = day["pollutants"][p]
            val = info["concentration"]
            band = info["band"]
            bc = _aqi_colour(band)
            pct = min(100, round(val / poll_max.get(p, 100) * 100))
            rows.append(html.Div(className="forecast-poll-row", children=[
                html.Span(poll_labels[p], className="forecast-poll-name"),
                html.Div(className="forecast-poll-bar-wrap", children=[
                    html.Div(className="forecast-poll-bar",
                             style={"width": f"{pct}%", "background": bc}),
                ]),
                html.Span(f"{val:.1f} µg/m³", className="forecast-poll-val"),
                html.Span(str(band), className="forecast-poll-band",
                          style={"background": bc + "22", "color": bc}),
            ]))
        w = day.get("weather", {})
        return (
            f"{dt.strftime('%A')} {dt.day} {dt.strftime('%B')}",
            f"AQI {aqi} – {_aqi_label(aqi)}",
            {"background": colour + "22", "color": colour,
                "border": f"1px solid {colour}55"},
            rows,
            f"{w['temp']:.1f} °C" if isinstance(
                w.get("temp"),   (int, float)) else "—",
            f"{w['ws']:.1f} m/s" if isinstance(w.get("ws"),
                                               (int, float)) else "—",
            f"{w['wd_deg']:.0f}°" if isinstance(
                w.get("wd_deg"), (int, float)) else "—",
        )

    @app.callback(
        Output("forecast-trend-chart", "figure"),
        Input("forecast-store", "data"),
        Input("forecast-active-day", "data"),
    )
    def update_forecast_trend(forecast, active_day):
        if not forecast:
            return empty_dark_figure("Select a site to generate forecast")

        dates = [pd.to_datetime(d["date"]) for d in forecast]
        aqis = [d["aqi"] for d in forecast]

        upper_bounds = [min(10, a + 1) for a in aqis]
        lower_bounds = [max(1, a - 1) for a in aqis]

        colours = [_aqi_colour(a) for a in aqis]
        fig = go.Figure()

        # 1. Background AQI Rectangles
        for lo, hi, col in [(1, 3, "#4caf7d"), (4, 6, "#e0a920"), (7, 9, "#e05a20"), (10, 10, "#c93030")]:
            fig.add_hrect(y0=lo-0.5, y1=hi+0.5, fillcolor=col,
                          opacity=0.04, line_width=0)

        # 2. Add the Uncertainty Band (The shaded area)
        # the top line (invisible)
        fig.add_trace(go.Scatter(
            x=dates, y=upper_bounds,
            line=dict(width=0),
            hoverinfo='skip',
            showlegend=False,
            name='Upper Bound'
        ))
        # the bottom line with the fill
        fig.add_trace(go.Scatter(
            x=dates, y=lower_bounds,
            fill='tonexty',
            fillcolor='rgba(255, 255, 255, 0.07)',
            line=dict(width=0),
            hoverinfo='skip',
            showlegend=False,
            name='Uncertainty (±1 AQI)'
        ))

        # 3. The Main Forecast Line
        fig.add_trace(go.Scatter(
            x=dates, y=aqis, mode="lines+markers",
            line=dict(color="#829a67", width=2),
            marker=dict(
                size=[14 if i == active_day else 8 for i in range(7)],
                color=colours, line=dict(color="#1a1f2e", width=2),
            ),
            hovertemplate="%{x|%a %e %b}<br>Predicted AQI: %{y}<br>Range: ±1 Index<extra></extra>",
            showlegend=False,
        ))

        # 4. Active Day Vertical Line
        fig.add_vline(x=dates[active_day], line_dash="dot",
                      line_color="#829a67", line_width=1, opacity=0.5)

        fig.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            height=320, margin=dict(l=30, r=20, t=20, b=30),
            xaxis=dict(showgrid=False, tickformat="%a",
                       tickfont=dict(family="Inter, sans-serif", size=12, color="#acb5c0")),
            yaxis=dict(title="AQI band", range=[0.5, 10.5], dtick=1, showgrid=True,
                       gridcolor="rgba(255,255,255,0.05)",
                       tickfont=dict(family="Inter, sans-serif",
                                     size=11, color="#acb5c0"),
                       title_font=dict(family="Inter, sans-serif", size=12, color="#acb5c0")),
        )

        return fig

    @app.callback(
        Output("forecast-poll-chart", "figure"),
        Input("forecast-store", "data"),
        Input("pol_drop", "value")
    )
    def update_forecast_poll_chart(forecast, pollutant):

        poll_labels = {"NO2": "NO₂", "O3": "O₃",
                       "SO2": "SO₂", "PM10": "PM10", "PM2.5": "PM2.5"}
        if not forecast or not pollutant:
            return empty_dark_figure("Select a site and pollutant")
        dates = [pd.to_datetime(d["date"]) for d in forecast]
        vals = [d["pollutants"][pollutant]["concentration"] for d in forecast]
        colours = [_aqi_colour(d["pollutants"][pollutant]["band"])
                   for d in forecast]
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=dates, y=vals, marker_color=colours,
            marker_line_color="rgba(0,0,0,0)",
            hovertemplate="%{x|%a %e %b}<br>" +
            poll_labels[pollutant] + ": %{y:.1f} µg/m³<extra></extra>",
            showlegend=False,
        ))
        fig.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            height=300, margin=dict(l=40, r=20, t=10, b=30),
            xaxis=dict(showgrid=False, tickformat="%a",
                       tickfont=dict(family="Inter, sans-serif", size=12, color="#acb5c0")),
            yaxis=dict(title=f"{poll_labels[pollutant]} (µg/m³)", showgrid=True,
                       gridcolor="rgba(255,255,255,0.05)",
                       tickfont=dict(family="Inter, sans-serif",
                                     size=11, color="#acb5c0"),
                       title_font=dict(family="Inter, sans-serif", size=12, color="#acb5c0")),
            bargap=0.35,
        )
        return fig

    # Precomputed maps to reduce repetition and increase dashboard speed

    site_to_pollutants = (
        wales_df_long.groupby("site")["pollutants"].apply(set).to_dict()
    )
    pollutants_filtered = wales_df_long[wales_df_long["date"] > pd.to_datetime(
        "2026-02-25")]
    active_sites_to_pollutants = (
        pollutants_filtered.groupby("site")["pollutants"].apply(set).to_dict()
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
    valid_rows = wales_df_long.dropna(subset=['value']).copy()

    # get the available years for each site
    site_to_years = (valid_rows.groupby('site')['year'].apply(set).to_dict())
    # get available years for each pollutant
    pollutant_to_years = (valid_rows.groupby('pollutants')[
                          'year'].apply(set).to_dict())
    # get available years for each site and pollutant combo
    site_pollutant_to_years = (valid_rows.groupby(
        ['site', 'pollutants'])['year'].apply(set).to_dict())

    # get all the unique sites and pollutants from the dataset
    all_years = sorted(
        y for y in valid_rows['year'].dropna().unique() if y < 2026)
    all_sites = sorted(wales_df_long["site"].unique())
    all_pollutants = sorted(wales_df_long["pollutants"].unique())

    global_min = wales_df_long["date"].min().date()
    global_max = wales_df_long["date"].max().date()
    exceedance_data = exceedance_summary(valid_rows)

    def has_full_date_range(start_date, end_date):
        return bool(start_date) and bool(end_date)

    def empty_dark_figure(title=None, subtitle=None, height=360):
        fig = go.Figure()
        fig.update_layout(
            title=title,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=height,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            annotations=[
                dict(
                    text=title,
                    x=0.5,
                    y=0.5,
                    xref="paper",
                    yref="paper",
                    showarrow=False,
                    font=dict(
                        family="Inter, sans-serif",
                        size=16,
                        color="#acb5c0",
                    ),
                )
            ],
        )
        return fig

    def warning_visible(message):
        return message, {"display": "block"}

    def warning_hidden():
        return "", {"display": "none"}

    def filters_missing(sites, pollutant, start_date, end_date):
        return not sites or not pollutant or not start_date or not end_date

    def ensure_list(value):
        if not value:
            return []
        if isinstance(value, str):
            return [value]
        return value

    @app.callback(
        Output('year_drop', 'options'),
        Input('site_drop', 'value'),
        Input('pol_drop', 'value'),
        State('year_drop', 'value')
    )
    def update_year(sites, pollutant, current_years):
        # if nothing is selected then use empty lists
        if sites is None:
            sites = []
        if current_years is None:
            current_years = []
        # if nothing selected then show all years
        if not sites and not pollutant:
            valid = all_years
        # if sites but no pollutant are chosen show all years common to those sites
        elif sites and not pollutant:
            sites_pol = [site_to_years.get(s, set())for s in sites]
            valid = sorted(set.intersection(*sites_pol)) if sites_pol else []
        # if pollutant but no sites selected then show all years common for that pollutant
        elif not sites and pollutant:
            valid = sorted(pollutant_to_years.get(pollutant, set()))
        # if both site and pollutant chosen then just show the years that match both
        else:
            sites_pol = [site_pollutant_to_years.get(
                (s, pollutant), set()) for s in sites]
            valid = sorted(set.intersection(*sites_pol)) if sites_pol else []
        # keep the years already chosen in the dropdown
        if current_years:
            valid = sorted(set(valid) | set(current_years))
        return [{'label': y, 'value': y} for y in valid if y < 2026]

    @app.callback(
        Output('exceedance_chart', 'figure'),
        Input('site_drop', 'value'),
        Input('pol_drop', 'value'),
        Input('year_drop', 'value'),
        Input('threshold-store', 'data')
    )
    def exceedance_bar(selected_sites, pollutant, selected_years, threshold_standard):
        # check if who limits selected
        who_toggle = threshold_standard == 'WHO'
        # if no selection is made tell the user to select
        if not selected_sites or not pollutant or not selected_years:
            return px.bar(title='Select site, pollutant and year')
        # make sure sites are in a list
        if isinstance(selected_sites, str):
            selected_sites = [selected_sites]
        results_data = exceedance_data[
            (exceedance_data['Site'].isin(selected_sites)) &
            (exceedance_data['pollutant'] == pollutant) &
            (exceedance_data['Year'].isin(selected_years))
        ].copy()
        if results_data.empty:
            return px.bar(title='No data available')
        # choose the correct columns based on uk or who limits
        if who_toggle:
            results_data['Value'] = results_data['who_value']
            results_data['Limit'] = results_data['who_limit']
            results_data['exceeds'] = results_data['who_exceeds']
        else:
            results_data['Value'] = results_data['uk_value']
            results_data['Limit'] = results_data['uk_limit']
            results_data['exceeds'] = results_data['uk_exceeds']
        fig = go.Figure()
        results_data = results_data.sort_values(
            ['Site', 'Year']).reset_index(drop=True)
        # use both site and year on the axis
        x_axis = [results_data['Site'], results_data['Year_str']]
        colours = ['red' if exceeds_limit == 'Above' else 'green' if exceeds_limit ==
                   'Within' else 'grey' for exceeds_limit in results_data['exceeds']]
        # show 0 label when value is 0 as its hard to see
        results_data['label'] = results_data['Value'].apply(
            lambda x: '0' if x == 0 else ''
        )
        results_data['hover_label'] = results_data['Value'].astype(str)
        trace = go.Bar(
            x=x_axis,
            y=results_data['Value'],
            marker_color=colours,
            text=results_data['label'],
            textposition='outside',
            hovertext=results_data['hover_label'],
            hovertemplate='Site: %{x[0]}<br>Year: %{x[1]}<br>Value:%{hovertext}<extra></extra>')
        trace.showlegend = False  # dont print the legend out for each individual trace
        fig.add_trace(trace)
        # add legends to state what the colours mean
        # fig.update_layout(hovermode='closest')
        fig.add_trace(go.Bar(
            x=[None], y=[None],
            marker_color='red',
            name='Above Limit'
        ))
        fig.add_trace(go.Bar(
            x=[None], y=[None],
            marker_color='green',
            name='Within Limit'
        ))
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode='lines',
            line=dict(color='red', dash='dash'),
            name='Limit'
        ))
        # put the y axis labels for each pollutant which vary depending on which one is selected
        pollutant_labels_uk = {
            "PM2.5": 'PM2.5 annual mean (µg/m³)',
            "PM10": f'PM10 days exceeding {LIMITS["UK"]["PM10"]["daily"]}(µg/m³)',
            "NO2": f'NO2 hours exceeding {LIMITS["UK"]["NO2"]["hourly"]}(µg/m³)',
            "SO2": f'SO2 days exceeding {LIMITS["UK"]["SO2"]["daily"]}(µg/m³)',
            "O3": f'O3 days exceeding {LIMITS["UK"]["O3"]["8h"]}(µg/m³)'
        }
        pollutant_labels_who = {
            "PM2.5": 'PM2.5 annual mean (µg/m³)',
            "PM10": 'PM10 annual mean (µg/m³)',
            "NO2": 'NO2 annual mean(µg/m³)',
            "SO2": f'SO2 days exceeding {LIMITS["WHO"]["SO2"]["daily"]}(µg/m³)',
            "O3": 'O3 seasonal peak mean(6 months) (µg/m³)'
        }
        # choose correct y axis label depending on toggle
        if who_toggle:
            y_label = pollutant_labels_who.get(pollutant, 'Value')
        else:
            y_label = pollutant_labels_uk.get(pollutant, 'Value')

        fig.update_layout(
            title=f'{pollutant} Exceedance for Selected Sites',
            barmode='group',  # want a bar for each year
            yaxis_title=y_label)
        unique_limits = results_data['Limit'].dropna().unique()
        if len(unique_limits) == 1 and unique_limits[0] != 0:
            fig.add_hline(
                y=unique_limits[0],
                line_dash='dash',
                line_color='red'
            )
        return fig

    @app.callback(
        Output("nav-home", "className"),
        Output("nav-comparison", "className"),
        Output('nav-exceedance', 'className'),
        Output("nav-forecast",   "className"),
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
            nav_class("/forecast"),
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
            end_dt = pd.to_datetime(
                end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
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
        if value is None or pd.isna(value) or threshold_value is None or pd.isna(threshold_value):
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
                lines.append(
                    html.Div(f"{site}: --", className="kpi-site-line")
                )
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
            height=360,

            title_font=dict(
                family="Inter, sans-serif",
                size=16,
                color="#d1e0c2"
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
            height=360,

            title_font=dict(
                family="Inter, sans-serif",
                size=16,
                color="#829a67"
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
            height=360,

            title_font=dict(
                family="Inter, sans-serif",
                size=16,
                color="#d1e0c2"
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
                height=360,
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

    def get_site_exceedance_summary(dff, pollutant, threshold_standard):
        results = []

        dff = dff.copy()
        dff["date"] = pd.to_datetime(dff["date"], errors="coerce")
        dff["value"] = pd.to_numeric(dff["value"], errors="coerce")

        for site, site_df in dff.groupby("site"):
            if site_df.empty:
                results.append({
                    "site": site,
                    "value": 0,
                    "label": "No data available",
                })
                continue

            site_wide = (
                site_df[["date", "pollutants", "value"]]
                .dropna(subset=["date", "value"])
                .pivot(index="date", columns="pollutants", values="value")
                .reset_index()
                .sort_values("date")
            )

            if pollutant not in site_wide.columns:
                results.append({
                    "site": site,
                    "value": 0,
                    "label": "No data available",
                })
                continue

            exceedance_info = calculate_exceedance(
                site_wide,
                pollutant,
                threshold_standard,
            )

            results.append({
                "site": site,
                "value": exceedance_info["value"],
                "label": exceedance_info["label"],
            })

        return sorted(results, key=lambda x: str(x["site"]))

    # AI Insight Callback function and decorator

    @app.callback(
        Output("forecast-gemini-insight", "children"),
        Input("forecast-store", "data"),
        Input("site_drop_forecast", "value"),
    )
    def update_gemini_insight(store, site):
        forecast = unpack_store(store)
        measured = list(active_sites_to_pollutants.get(site, []))
        if isinstance(forecast, list) and len(forecast) > 0 and isinstance(forecast[0], list):
            forecast = forecast[0]
        if not forecast or not site:
            return html.P(
                "Select a site to generate an AI summary.",
                className="insight-inline",
            )
        insight = generate_forecast_insight(site, forecast, measured)
        return html.P(
            [html.Strong("Insights: "), insight],
            className="insight-inline",
        )

    # ─────────────────────────────────────────────────────────────
    # 1) Update site dropdown OPTIONS based on pollutant + date range
    # ─────────────────────────────────────────────────────────────

    @app.callback(
        Output("site_drop", "options"),
        Output("site_drop_forecast", "options"),
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

        return valid, valid

    # ─────────────────────────────────────────────────────────────
    # 2) Update pollutant dropdown OPTIONS based on sites + date range
    # ─────────────────────────────────────────────────────────────

    @app.callback(
        Output("pol_drop", "options"),
        Input("site_drop", "value"),
        Input("date_range", "start_date"),
        Input("date_range", "end_date"),
        State("pol_drop", "value"),
        Input("site_drop_forecast", "value")
    )
    def update_pollutant_dropdown(sites, start_date, end_date, currently_selected, forecast_site):
        if forecast_site:
            active_df = wales_df_long[wales_df_long["date"]
                                      > pd.to_datetime("2026-01-01")]
            valid_series = active_df[active_df["site"]
                                     == forecast_site]["pollutants"].unique()
            valid = sorted(valid_series.tolist())

        elif not forecast_site:
            sites = sites or []
        date_active = has_full_date_range(start_date, end_date)

        if not sites and not date_active and not forecast_site:
            valid = all_pollutants

        elif sites and not forecast_site:
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
        Output("site_drop_forecast", "value"),
        Input("reset_btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def reset_dropdowns(n_clicks):
        return [], None, None

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

    # Topbar metadata
    @app.callback(
        Output("meta-stations", "children"),
        Output("meta-pollutant", "children"),
        Output("meta-period", "children"),
        Input("site_drop", "value"),           # Multi-select
        Input("site_drop_forecast", "value"),  # Single-select
        Input("pol_drop", "value"),
        Input("date_range", "start_date"),
        Input("date_range", "end_date"),
        Input("url", "pathname")
    )
    def update_topbar(sites, forecast_site, pollutant, start, end, pathname):
        # Check if we are currently on the Forecast page
        if pathname == "/forecast":
            stations_text = "1" if forecast_site else "0"

            # Override the dates for the 7-day forecast window
            f_start = pd.Timestamp.now().date()
            f_end = f_start + pd.Timedelta(days=7)
            period_text = format_date_range(f_start, f_end)

        else:
            stations_text = str(len(sites)) if sites else "0"
            period_text = format_date_range(start, end)

        pollutant_text = POLLUTANT_DISPLAY_NAMES.get(
            pollutant, pollutant) if pollutant else "--"

        return stations_text, pollutant_text, period_text

    @callback(
        Output("site_drop", "value", allow_duplicate=True),
        Output("site_drop_forecast", "value", allow_duplicate=True),
        Input("site_drop", "value"),
        Input("site_drop_forecast", "value"),
        prevent_initial_call=True

    )
    def sync_dropdowns(main_sites, forecast_site):
        triggered_id = ctx.triggered_id

        if not triggered_id:
            return no_update, no_update

        # Case 1: User changes the MULTI-select main dropdown
        if triggered_id == "site_drop":
            if not main_sites:
                return no_update, None

            # Take the LAST selected site from the list and set as forecast site
            # This feels natural to the user (the most recent click)
            latest_selection = main_sites[-1]
            return no_update, latest_selection

        # Case 2: User changes the SINGLE-select forecast dropdown
        if triggered_id == "site_drop_forecast":
            if not forecast_site:
                return no_update, no_update

            # If the forecast site is already in the main list, don't change anything
            # Otherwise, make the main list ONLY contain this one forecast site
            if main_sites and forecast_site in main_sites:
                return no_update, no_update

            return [forecast_site], no_update

        return no_update, no_update

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
                "Select site(s), a pollutant, and a date range to generate statistics.",
                className="empty-panel-text",
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
    def update_trends(tab, selected_sites, selected_pollutant, start_date, end_date, threshold_standard, dq):
        '''
        Updates the trends KPIs, chart, and insights based on the selected tab and filters. 
        Handles data filtering, KPI calculations, chart generation, and insight messaging.
        '''

        df = wales_df_long.copy()

        effective_end_date = end_date
        if dq == "Ratified" and end_date:
            effective_end_date = str(
                min(pd.to_datetime(end_date).date(), RATIFIED_CUTOFF.date())
            )

        days = get_days(start_date, effective_end_date)

        if days is None:
            return (
                make_kpi("Average", "--", "Awaiting filters"),
                make_kpi("Peak", "--", "Awaiting filters"),
                make_kpi("Exceedances", "--", "Awaiting filters"),
                make_kpi("Variability", "--", "Awaiting filters"),
                "",
                {"display": "none"},
                html.Div(
                    className="empty-panel",
                    children=[
                        html.Div(
                            "Select site(s), pollutant, and a date range to generate temporal analysis.",
                            className="empty-panel-text",
                        ),
                    ],
                ),
                html.Div(
                    html.P(
                        [
                            html.Strong("Insights: "),
                            html.Span(
                                "Select a site, pollutant, and date range to generate a temporal analysis summary.",
                                id="empty_panel_text",
                            ),
                        ],
                        className="insight-inline",
                    ),
                    className="insight-box",
                ),
            )

        dff = filter_df(df, selected_sites, selected_pollutant,
                        start_date, effective_end_date)

        if dff.empty:
            warning_text, warning_style = warning_visible(
                "No matching data was found for the current selection."
            )
            return (
                make_kpi("Average", "--", "No data"),
                make_kpi("Peak", "--", "No data"),
                make_kpi("Exceedances", "--", "No data"),
                make_kpi("Variability", "--", "No data"),
                warning_text,
                warning_style,
                html.Div(
                    className="empty-panel",
                    children=[
                        html.Div("No data available",
                                 className="empty-panel-title"),
                        html.Div(
                            "Try adjusting the selected site, pollutant, or date range.",
                            className="empty-panel-text",
                        ),
                    ],
                ),
                html.Div(
                    html.P(
                        [
                            html.Strong("Insights: "),
                            html.Span(
                                "No valid observations were available for the current filters."
                            ),
                        ],
                        className="insight-inline",
                    ),
                    className="insight-box",
                ),
            )

        pollutant_label = POLLUTANT_DISPLAY_NAMES.get(
            selected_pollutant, selected_pollutant)
        threshold_info = get_threshold_info(
            selected_pollutant, threshold_standard or "UK")
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

        warning_text, warning_style = warning_hidden()

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
            exceedance_info = site_exceedance[0] if site_exceedance else {
                "value": "--", "label": "No data"}

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
                format_site_value_lines(site_std.fillna(
                    0), decimals=2, suffix=" µg/m³"),
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
            dcc.Graph(figure=fig, config={
                      "displayModeBar": True, "displaylogo": False}),
            html.Div(
                html.P([html.Strong("Insights: "), insight],
                       className="insight-inline"),
                className="insight-box"
            ),
        )

    def calculate_pollution_rose(df, selected_sites, pollutant, start_date, end_date):
        selected_sites = selected_sites or []
        if isinstance(selected_sites, str):
            selected_sites = [selected_sites]

        if not selected_sites or not pollutant or not start_date or not end_date:
            return go.Figure()

        # filter the dataset based on site, pollutant and date range
        filtered = df[
            (df['site'].isin(selected_sites)) &
            (df['pollutants'] == pollutant) &
            (df['date'] >= pd.to_datetime(start_date)) &
            (df['date'] <= pd.to_datetime(end_date))].copy()

        # return an empty figure if no data after filtering
        if filtered.empty:
            return go.Figure()

        # convert degrees into compass directions
        filtered['wind_direction'] = filtered['wd'].apply(degrees_to_direction)
        # change pollutant values into aqi index and categories
        filtered['aqi_index'] = filtered['value'].apply(
            lambda x: aqi_index(x, pollutant))
        filtered['aqi_category'] = filtered['aqi_index'].apply(aqi_category)
        # remove rows with missing wind or aqi categories
        filtered = filtered.dropna(subset=['wind_direction', 'aqi_category'])

        if filtered.empty:
            return go.Figure()

        # working out how many times each aqi category occur in each wind direction
        direction_counts = (
            filtered.groupby(['wind_direction', 'aqi_category']).size().reset_index(name='direction_count'))
        total_observations = len(filtered)
        # counts to percentages
        direction_counts['percentage'] = 100 * \
            direction_counts['direction_count']/total_observations
        directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
        categories = ['Low', 'Moderate', 'High', 'Very High']
        colours = {
            'Low': 'green',
            'Moderate': 'yellow',
            'High': 'orange',
            'Very High': 'red'
        }

        fig = go.Figure()

        # one trace per aqi category
        for category in categories:
            category_data = direction_counts[direction_counts['aqi_category'] == category]
            # all directions present filling missing values with 0
            category_data = (
                category_data.set_index('wind_direction')['percentage'].reindex(
                    directions, fill_value=0).reset_index()
            )
            # add polar bar trace
            fig.add_trace(go.Barpolar(
                r=category_data['percentage'],
                theta=category_data['wind_direction'],
                name=category,
                marker_color=colours[category],
                marker_line_color="rgba(255,255,255,0.15)",
                marker_line_width=1,
                opacity=0.9,
                hovertemplate=(
                    "Direction: %{theta}<br>"
                    "AQI Band: " + category + "<br>"
                    "Share: %{r:.1f}%<extra></extra>"
                ),
            ))

        fig.update_layout(
            title=None,
            barmode="stack",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(size=12, family="Inter, sans-serif", color="#acb5c0"),
            legend_title_text="AQI Band",
            margin=dict(l=20, r=20, t=20, b=20),
            polar_radialaxis_showticklabels=False,
            polar_angularaxis_rotation=90

        )

        return fig

    # graph for each site

    @app.callback(
        Output("pollution_rose_container", "children"),
        Input("site_drop", "value"),
        Input("pol_drop", "value"),
        Input("date_range", "start_date"),
        Input("date_range", "end_date"),
        Input("dq_store", "data"),
    )
    def update_pollution_rose(selected_sites, pollutant, start_date, end_date, dq):
        """
        Generate a pollution rose card for each selected site based on the chosen
        pollutant and date range. Uses consistent empty-panel states when filters
        are missing or site-level data is unavailable.
        """
        selected_sites = ensure_list(selected_sites)

        if not selected_sites or not pollutant or not start_date or not end_date:
            return [
                html.Div(
                    className="empty-panel",
                    children=[
                        html.Div(
                            "Select site(s), pollutant, and a date range to generate pollution roses.",
                            className="empty-panel-text",
                        ),
                    ],
                )
            ]

        effective_end = pd.to_datetime(
            end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        if dq == "Ratified":
            effective_end = min(effective_end, RATIFIED_CUTOFF)

        pollutant_label = POLLUTANT_DISPLAY_NAMES.get(pollutant, pollutant)
        graphs = []

        for site in selected_sites:
            fig = calculate_pollution_rose(
                wales_df_long,
                [site],
                pollutant,
                start_date,
                effective_end,
            )

            if fig.data:
                fig.update_layout(
                    title=None,
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=360,
                    autosize=True,
                    margin=dict(l=20, r=20, t=20, b=20),
                    legend_title_text="AQI Band",
                    font=dict(
                        family="Inter, sans-serif",
                        size=12,
                        color="#acb5c0",
                    ),
                )

                content = dcc.Graph(
                    figure=fig,
                    className="comparison-site-graph",
                    style={"height": "360px"},
                    config={
                        "displayModeBar": True,
                        "displaylogo": False,
                        "responsive": False,
                    },
                )

                subtitle = f"Directional distribution of {pollutant_label} concentrations at {site}."

            else:
                content = html.Div(
                    className="empty-panel comparison-site-empty",
                    children=[
                        html.Div("No data available",
                                 className="empty-panel-title"),
                        html.Div(
                            f"No valid pollution rose data was available for {site} in the selected period.",
                            className="empty-panel-text",
                        ),
                    ],
                )

                subtitle = f"No {pollutant_label} directional pattern could be generated for {site}."

            graphs.append(
                html.Div(
                    className="comparison-site-card",
                    children=[
                        html.Div(
                            className="comparison-site-card-header",
                            children=[
                                html.Div(
                                    site, className="comparison-site-title"),
                                html.Div(
                                    subtitle, className="comparison-site-subtitle"),
                            ],
                        ),
                        content,
                    ],
                )
            )

        return graphs

    @app.callback(
        Output("temp_scatter_container", "children"),
        Output("temp_scatter_subtitle", "children"),
        Input("site_drop", "value"),
        Input("pol_drop", "value"),
        Input("date_range", "start_date"),
        Input("date_range", "end_date"),
        Input("dq_store", "data"),
    )
    def update_temp_scatter(sites, pollutant, start_date, end_date, dq):
        '''This callback manages the entire temperature relationship panel,
        including handling missing filters, data availability, 
        and generating the scatter plot with appropriate annotations and subtitles.'''

        if filters_missing(sites, pollutant, start_date, end_date):
            return (
                html.Div(
                    className="empty-panel",
                    children=[
                        html.Div(
                            "Select site(s), pollutant, and a date range to generate the temperature relationship overview.",
                            className="empty-panel-text",
                        ),
                    ],
                ),
                "Shows how pollutant concentration varies with temperature across the selected site(s). Colours distinguish sites; relationships should be interpreted within each site."
            )

        sites = ensure_list(sites)

        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date) + \
            pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

        if dq == "Ratified":
            end_dt = min(end_dt, RATIFIED_CUTOFF)

        dff = wales_df[
            (wales_df["site"].isin(sites)) &
            (wales_df["date"] >= start_dt) &
            (wales_df["date"] <= end_dt)
        ].copy()

        if pollutant not in dff.columns or "temp" not in dff.columns:
            return (
                html.Div(
                    className="empty-panel",
                    children=[
                        html.Div("Unavailable", className="empty-panel-title"),
                        html.Div(
                            "Temperature or pollutant columns are unavailable for the current selection.",
                            className="empty-panel-text",
                        ),
                    ],
                ),
                "Required variables are unavailable for this view.",
            )

        dff = dff.dropna(subset=[pollutant, "temp", "site"])

        if dff.empty:
            return (
                html.Div(
                    className="empty-panel",
                    children=[
                        html.Div("No data available",
                                 className="empty-panel-title"),
                        html.Div(
                            "No valid observations were found for the selected site, pollutant, and date range.",
                            className="empty-panel-text",
                        ),
                    ],
                ),
                "No matching data is available for the current filters.",
            )

        pollutant_label = POLLUTANT_DISPLAY_NAMES.get(pollutant, pollutant)

        fig = px.scatter(
            dff,
            x="temp",
            y=pollutant,
            color="site",
            trendline="ols",
            opacity=0.6,
            labels={
                "temp": "Temperature (°C)",
                pollutant: f"{pollutant_label} (µg/m³)",
                "site": "Monitoring Site",
            },
            title=f"Temperature Relationship with {pollutant_label}",
        )

        # Only show correlation annotation for single-site view
        if len(sites) == 1:
            corr_df = dff[["temp", pollutant]].dropna()
            corr = corr_df["temp"].corr(
                corr_df[pollutant]) if len(corr_df) >= 2 else None
            n = len(corr_df)

            annotation_text = f"n = {n}"
            if corr is not None and pd.notna(corr):
                annotation_text = f"r = {corr:.2f} · n = {n}"

            fig.add_annotation(
                text=annotation_text,
                xref="paper",
                yref="paper",
                x=0.99,
                y=1.12,
                xanchor="right",
                showarrow=False,
                font=dict(
                    family="Inter, sans-serif",
                    size=12,
                    color="#acb5c0",
                ),
            )

            subtitle = (
                f"Site overview of the relationship between temperature and pollutant concentration. Each point represents an observation, with a fitted trendline to indicate overall direction. Correlation coefficient (r) quantifies the strength and direction of the relationship."
            )

        else:
            site_counts = (
                dff.groupby("site")
                .size()
                .sort_values(ascending=False)
                .to_dict()
            )

            count_text = " · ".join(
                [f"{site}: n={count}" for site, count in site_counts.items()])

            subtitle = (
                f"Combined overview across {len(sites)} selected sites. "
                f"Colours indicate site-level observations. {count_text}"
            )

        fig.update_traces(
            marker=dict(size=8),
            selector=dict(mode="markers"),
        )

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=360,
            margin=dict(l=40, r=20, t=70, b=40),
            title={"x": 0.5},
            font=dict(
                family="Inter, sans-serif",
                size=12,
                color="#acb5c0",
            ),
            legend_title="Site",
        )

        return (
            dcc.Graph(
                figure=fig,
                className="chart-graph",
                config={"displayModeBar": True, "displaylogo": False},
            ),
            subtitle,
        )

    @app.callback(
        Output("correlation_heatmap_container", "children"),
        Input("site_drop", "value"),
        Input("date_range", "start_date"),
        Input("date_range", "end_date"),
        Input("dq_store", "data"),
    )
    def update_corr_heatmap(selected_sites, start_date, end_date, dq):
        """
        Generate site-level correlation heatmaps for the selected date range and
        data quality mode. Uses a more compact rendering when multiple sites are selected.
        """
        selected_sites = ensure_list(selected_sites)

        if not selected_sites or not start_date or not end_date:
            return [
                html.Div(
                    className="empty-panel",
                    children=[
                        html.Div(
                            "Select site(s) and a date range to generate site-level correlation matrices.",
                            className="empty-panel-text",
                        ),
                    ],
                )
            ]

        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date) + \
            pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

        if dq == "Ratified":
            end_dt = min(end_dt, RATIFIED_CUTOFF)

        multi_site = len(selected_sites) > 1
        children = []

        for site in selected_sites:
            dff = wales_df[
                (wales_df["site"] == site) &
                (wales_df["date"] >= start_dt) &
                (wales_df["date"] <= end_dt)
            ].copy()

            cols = ["NO2", "PM2.5", "PM10", "O3", "SO2", "temp"]
            cols = [c for c in cols if c in dff.columns]

            if len(cols) < 2:
                content = html.Div(
                    className="empty-panel comparison-site-empty",
                    children=[
                        html.Div("Insufficient variables",
                                 className="empty-panel-title"),
                        html.Div(
                            "At least two variables are required to calculate correlations.",
                            className="empty-panel-text",
                        ),
                    ],
                )
                subtitle = "Correlation matrix unavailable."

            else:
                corr_input = dff[cols].dropna(how="all")

                if corr_input.empty:
                    content = html.Div(
                        className="empty-panel comparison-site-empty",
                        children=[
                            html.Div("No data available",
                                     className="empty-panel-title"),
                            html.Div(
                                "No valid observations were available for correlation analysis.",
                                className="empty-panel-text",
                            ),
                        ],
                    )
                    subtitle = "Correlation matrix unavailable."

                else:
                    corr = corr_input.corr()

                    if corr.isna().all().all():
                        content = html.Div(
                            className="empty-panel comparison-site-empty",
                            children=[
                                html.Div("Correlation unavailable",
                                         className="empty-panel-title"),
                                html.Div(
                                    "Correlation could not be computed from the selected data.",
                                    className="empty-panel-text",
                                ),
                            ],
                        )
                        subtitle = "Correlation matrix unavailable."

                    else:
                        rename_map = {
                            **POLLUTANT_DISPLAY_NAMES, "temp": "Temp"}
                        corr = corr.rename(
                            index=rename_map, columns=rename_map)

                        show_text = ".2f"
                        graph_height = 360 if not multi_site else 300
                        font_size = 12 if not multi_site else 10
                        colorbar_thickness = 12 if not multi_site else 10

                        fig = px.imshow(
                            corr,
                            text_auto=".2f",
                            color_continuous_scale="RdBu_r",
                            zmin=-1,
                            zmax=1,
                            aspect="auto",
                            title=None,
                        )

                        fig.update_traces(
                            hovertemplate=(
                                "X: %{x}<br>"
                                "Y: %{y}<br>"
                                "Correlation: %{z:.2f}<extra></extra>"
                            ),
                            colorbar=dict(
                                title="Correlation" if not multi_site else "",
                                thickness=colorbar_thickness,
                                len=0.72,
                                y=0.5,
                            ),
                        )

                        if multi_site:
                            fig.update_coloraxes(showscale=False)

                        fig.update_layout(
                            template="plotly_dark",
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            height=graph_height,
                            margin=dict(
                                l=12 if multi_site else 24,
                                r=12 if multi_site else 24,
                                t=10,
                                b=12 if multi_site else 20,
                            ),
                            font=dict(
                                family="Inter, sans-serif",
                                size=font_size,
                                color="#acb5c0",
                            ),
                        )

                        fig.update_xaxes(
                            side="bottom",
                            tickangle=0 if multi_site else 0,
                            tickfont=dict(size=9 if multi_site else 11),
                            automargin=True,
                        )
                        fig.update_yaxes(
                            autorange="reversed",
                            tickfont=dict(size=9 if multi_site else 11),
                            automargin=True,
                        )

                        subtitle = (None if multi_site
                                    else f"Pollutant and temperature relationships within {site}."
                                    )

                        content = dcc.Graph(
                            figure=fig,
                            className="comparison-site-graph",
                            style={"height": f"{graph_height}px"},
                            responsive=True,
                            config={"displayModeBar": True,
                                    "displaylogo": False},
                        )

            children.append(
                html.Div(
                    className="comparison-site-card",
                    children=[
                        html.Div(
                            className="comparison-site-card-header",
                            children=[
                                html.Div(
                                    site, className="comparison-site-title"),
                                html.Div(
                                    subtitle, className="comparison-site-subtitle"),
                            ],
                        ),
                        content,
                    ],
                )
            )

        return children

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
        Output('date-controls', 'style'),
        Output('year-wrapper', 'style'),
        Output("main-site-wrapper", 'style'),
        Output("forecast-site-wrapper", 'style'),
        Output("threshold-toggle-wrapper", "style"),
        Output("quality-toggle-wrapper", "style"),
        Input('url', 'pathname'),
    )
    def toggle_side_bar_page(pathname):
        # Default visibility
        date_style = {'display': 'block'}
        year_style = {'display': 'none'}
        main_site_style = {'display': 'block'}
        forecast_site_style = {'display': 'none'}
        threshold_toggle = {'display': 'block'}
        quality_toggle = {'display': 'block'}

        if pathname == '/exceedance':
            date_style = {'display': 'none'}
            year_style = {'display': 'block'}

        elif pathname == '/forecast':
            date_style = {'display': 'none'}
            main_site_style = {'display': 'none'}
            forecast_site_style = {'display': 'block'}
            threshold_toggle = {'display': 'none'}
            quality_toggle = {'display': 'none'}

        return date_style, year_style, main_site_style, forecast_site_style, threshold_toggle, quality_toggle
