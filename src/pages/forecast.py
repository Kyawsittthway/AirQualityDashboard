
import dash
from dash import html, dcc

dash.register_page("pages.forecast", path="/forecast",
                   name="Forecast", title="AQI Forecast")

SITES = [
    "Aston Hill",
    "Cardiff Centre",
    "Cardiff Newport Road",
    "Chepstow A48",
    "Cwmbran Crownbridge",
    "Hafod-yr-ynys Hill Roadside",
    "Narberth",
    "Newport",
    "Port Talbot Margam",
    "Swansea Roadside",
    "Wrexham",
]

# ── AQI band colour helpers ───────────────────────────────────────────────────


def aqi_band_colour(band: int) -> str:
    if band <= 3:
        return "#4caf7d"   # green  – Low
    if band <= 6:
        return "#e0a920"   # amber  – Moderate
    if band <= 9:
        return "#e05a20"   # orange – High
    return "#c93030"       # red    – Very High


def aqi_band_label(band: int) -> str:
    if band <= 3:
        return "Low"
    if band <= 6:
        return "Moderate"
    if band <= 9:
        return "High"
    return "Very High"


# ── Reusable sub-components ───────────────────────────────────────────────────

def _empty_state(message: str) -> html.Div:
    return html.Div(
        className="empty-panel",
        children=[
            html.Div(message, className="empty-panel-text"),
        ],
    )


def _day_card_placeholder(day_label: str) -> html.Div:
    """Skeleton day card rendered before predictions load."""
    return html.Div(
        className="forecast-day-card forecast-day-card--skeleton",
        children=[
            html.Div(day_label, className="forecast-day-label"),
            html.Div(className="forecast-day-badge forecast-day-badge--skeleton"),
            html.Div("—", className="forecast-day-aqi-num"),
            html.Div("—", className="forecast-day-band-label"),
        ],
    )


def _pollutant_bar_row(pollutant: str, unit: str = "µg/m³") -> html.Div:
    """Skeleton pollutant breakdown row."""
    return html.Div(
        className="forecast-poll-row",
        children=[
            html.Span(pollutant, className="forecast-poll-name"),
            html.Div(className="forecast-poll-bar-wrap",
                     children=[html.Div(className="forecast-poll-bar", id=f"poll-bar-{pollutant.lower().replace('.', '')}")]),
            html.Span("—", className="forecast-poll-val",
                      id=f"poll-val-{pollutant.lower().replace('.', '')}", ),
            html.Span("—", className="forecast-poll-band",
                      id=f"poll-band-{pollutant.lower().replace('.', '')}", ),
        ],
    )


# ── Page layout ───────────────────────────────────────────────────────────────

layout = html.Div(
    id="forecast-page",
    className="forecast-page",
    children=[

        # ── Page header ───────────────────────────────────────────────────────
        html.Div(
            className="forecast-page-header",
            children=[
                html.Div(
                    className="forecast-header-left",
                    children=[
                        html.H1("7-Day AQI Forecast",
                                className="forecast-title"),
                        html.P(
                            "Daily air quality index predictions powered by site-level XGBoost models. "
                            "Weather data sourced from Open-Meteo.",
                            className="forecast-subtitle",
                        ),
                    ],
                ),
            ],
        ),

        # ── Status / warning banner ─────────────────────
        html.Div(
            id="forecast-warning",
            className="forecast-warning",
            style={"display": "none"},
        ),

        # ── Summary strip ─────────────────────────────────────────────────────
        html.Div(
            className="forecast-summary-strip",
            children=[
                html.Div(
                    className="forecast-summary-card",
                    children=[
                        html.Div(
                            "Site type", className="forecast-summary-label"),
                        html.Div("—", className="forecast-summary-value",
                                 id="fc-meta-type"),
                    ],
                ),
                html.Div(
                    className="forecast-summary-card",
                    children=[
                        html.Div("Forecast from",
                                 className="forecast-summary-label"),
                        html.Div("—", className="forecast-summary-value",
                                 id="fc-meta-start"),
                    ],
                ),
                html.Div(
                    className="forecast-summary-card",
                    children=[
                        html.Div("Peak AQI (7d)",
                                 className="forecast-summary-label"),
                        html.Div(
                            "—", className="forecast-summary-value forecast-summary-value--aqi", id="fc-meta-peak"),
                    ],
                ),
                html.Div(
                    className="forecast-summary-card",
                    children=[
                        html.Div("Worst pollutant",
                                 className="forecast-summary-label"),
                        html.Div("—", className="forecast-summary-value",
                                 id="fc-meta-worst"),
                    ],
                ),
                html.Div(
                    className="forecast-summary-card",
                    children=[
                        html.Div("Avg AQI (7d)",
                                 className="forecast-summary-label"),
                        html.Div(
                            "—", className="forecast-summary-value", id="fc-meta-avg"),
                    ],
                ),
            ],
        ),

        # ── 7-day card strip ──────────────────────────────────────────────────
        html.Div(
            className="forecast-section",
            children=[
                html.Div(
                    className="forecast-section-header",
                    children=[
                        html.H2("Daily Forecast",
                                className="forecast-section-title"),
                        html.Span(
                            "Click a day to inspect per-pollutant breakdown",
                            className="forecast-section-hint",
                        ),
                    ],
                ),
                html.Div(
                    id="forecast-day-grid",
                    className="forecast-day-grid",
                    children=[
                        _day_card_placeholder(d)
                        for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                    ],
                ),
            ],
        ),
        dcc.Store(id="forecast-store"),
        dcc.Store(id="forecast-active-day", data=0),
        html.Div(
            className="forecast-section",
            children=[
                html.Div(
                    className="forecast-section-header",
                    children=[
                        html.H2("AI Insight",
                                className="forecast-section-title"),
                        html.Span("Powered by Gemini",
                                  className="forecast-section-hint"),
                    ],
                ),
                dcc.Loading(
                    id="gemini-loading",
                    type="default",
                    color="#829a67",
                    children=[html.Div(
                        id="forecast-gemini-insight",
                        className="insight-box",
                        children=[
                            html.P(
                                "Select a site to generate an AI summary.",
                                className="insight-inline",
                            )
                        ],
                    )]),
            ],
        ),

        # ── Detail + chart row ────────────────────────────────────────────────
        html.Div(
            className="forecast-detail-row",
            children=[

                # Left: pollutant breakdown for selected day
                html.Div(
                    className="forecast-detail-card",
                    children=[
                        html.Div(
                            className="forecast-detail-header",
                            children=[
                                html.H3(
                                    "—", className="forecast-detail-title", id="fc-detail-title"),
                                html.Span(
                                    "—", className="forecast-detail-badge", id="fc-detail-badge"),
                            ],
                        ),
                        html.Div(
                            id="fc-detail-body",
                            className="forecast-detail-body",
                            children=[_pollutant_bar_row(p) for p in [
                                "NO2", "O3", "SO2", "PM10", "PM2.5"]],
                        ),
                        html.Div(
                            id="fc-detail-weather",
                            className="forecast-detail-weather",
                            children=[
                                html.Div(
                                    className="forecast-weather-item",
                                    children=[
                                        html.Span(
                                            "Temp", className="forecast-weather-label"),
                                        html.Span(
                                            "—", className="forecast-weather-val", id="fc-weather-temp"),
                                    ],
                                ),
                                html.Div(
                                    className="forecast-weather-item",
                                    children=[
                                        html.Span(
                                            "Wind speed", className="forecast-weather-label"),
                                        html.Span(
                                            "—", className="forecast-weather-val", id="fc-weather-ws"),
                                    ],
                                ),
                                html.Div(
                                    className="forecast-weather-item",
                                    children=[
                                        html.Span(
                                            "Wind dir", className="forecast-weather-label"),
                                        html.Span(
                                            "—", className="forecast-weather-val", id="fc-weather-wd"),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),

                # Right: AQI trend chart over 7 days
                html.Div(
                    className="forecast-chart-card",
                    children=[
                        html.Div(
                            className="forecast-section-header",
                            children=[
                                html.H3("AQI Trend",
                                        className="forecast-section-title"),
                            ],
                        ),
                        dcc.Graph(
                            id="forecast-trend-chart",
                            className="forecast-chart",
                            config={"displayModeBar": False,
                                    "displaylogo": False},
                            style={"height": "320px"},
                        ),
                    ],
                ),
            ],
        ),

        # ── Pollutant concentration chart ─────────────────────────────────────
        html.Div(
            className="forecast-section",
            children=[
                html.Div(
                    className="forecast-section-header",
                    children=[
                        html.H2("Pollutant Concentrations",
                                className="forecast-section-title")]),
                dcc.Graph(
                    id="forecast-poll-chart",
                    className="forecast-chart",
                    config={"displayModeBar": False,
                            "displaylogo": False},
                    style={"height": "300px"},
                ),
            ],
        ),

    ],
)
