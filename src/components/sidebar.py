from dash import html, dcc
from datetime import datetime, timedelta


ALL_SITES = ['Aston Hill', 'Cardiff Centre', "Cardiff Newport Road", 'Chepstow A48',
             'Cwmbran Crownbridge', 'Hafod-yr-ynys Hill Roadside', 'Narbeth', 'Newport', 'Port Talbot Margam',
             'Swansea Roadside', 'Wrexham'
             ]


def create_sidebar():
    return html.Div(
        id="sidebar",
        children=[
            # Track current URL
            dcc.Location(id="url"),

            # Stores
            dcc.Store(id="threshold-store", data="UK"),
            dcc.Store(id="theme-store", data="dark"),
            dcc.Store(id="dq_store", data="All"),
            dcc.Store(id="filter_store"),
            dcc.Store(id="date-store"),

            # Logo Header
            html.Div(
                className="sidebar-header",
                children=[
                    html.Div(
                        className="logo-section",
                        children=[
                            html.Div("AL", className="logo-icon"),
                            html.Div("AirLens", className="logo-text"),
                        ],
                    ),
                ],
            ),

            # Navigation
            html.Div(
                className="filter-section",
                children=[
                    html.Div("Navigation", className="filter-label"),
                    html.Div(
                        className="sidebar-nav",
                        children=[
                            dcc.Link(
                                "Overview",
                                href="/",
                                id="nav-home",
                                className="nav-link",
                            ),
                            dcc.Link(
                                "Comparison",
                                href="/comparison",
                                id="nav-comparison",
                                className="nav-link",
                            ),
                            dcc.Link(
                                'Exceedance',
                                href='/exceedance',
                                id='nav-exceedance',
                                className='nav-link',
                            ),
                            dcc.Link(
                                "Forecast",
                                href="/forecast",
                                id="nav-forecast",
                                className="nav-link",
                            ),
                        ],
                    ),
                ],
            ),

            html.Div(className="sidebar-divider"),

            # Site Selection
            html.Div(
                className="filter-section",
                children=[
                    html.Div("Monitoring Sites", className="filter-label"),
                    html.Div(
                        id="main-site-wrapper",
                        children=[
                            dcc.Dropdown(
                                className="dropdown-sidebar",
                                id="site_drop",
                                placeholder="Select stations...",
                                multi=True,
                                value=["Cardiff Centre", "Swansea Roadside"],
                                options=[{'label': s, 'value': s}
                                         for s in ALL_SITES],
                            ),
                        ],
                    ),
                    html.Div(
                        id="forecast-site-wrapper",
                        style={"display": "none"},
                        children=[
                            dcc.Dropdown(
                                className="dropdown-sidebar",
                                id="site_drop_forecast",
                                placeholder="Select a station",
                                multi=False,
                                value="Cardiff Centre",
                                options=[{'label': s, 'value': s}
                                         for s in ALL_SITES],
                            ),
                        ],
                    ),
                ],
            ),

            # Pollutant Selection
            html.Div(
                className="filter-section",
                children=[
                    html.Div("Pollutant", className="filter-label"),
                    dcc.Dropdown(
                        id="pol_drop",
                        placeholder="Select pollutant...",
                        value="NO2",
                        className="dropdown-sidebar",
                        options=[
                            {"label": "NO₂", "value": "NO2"},
                            {"label": "PM2.5", "value": "PM2.5"},
                            {"label": "PM10", "value": "PM10"},
                            {"label": "O₃", "value": "O3"},
                            {"label": "SO₂", "value": "SO2"},
                        ],
                    ),
                ],
            ),

            # Year Selection
            html.Div(
                className='filter-section',
                id='year-wrapper',
                style={'display': 'none'},
                children=[
                    html.Div('Year', className='filter-label'),
                    dcc.Dropdown(
                        id='year_drop',
                        multi=True,
                        placeholder='Choose years',
                        value=[2011, 2012, 2014],
                        options=[2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020,
                                 2021, 2022, 2023, 2024, 2025],
                        className='dropdown-sidebar',
                    ),
                ],
            ),

            # Quick Date Range Buttons
            html.Div(
                id='date-controls',
                children=[
                    html.Div(
                        className='filter-section',
                        children=[
                            html.Div("Quick Select", className="filter-label"),
                            html.Div(
                                className="quick-date-btns",
                                children=[
                                    html.Button("Yesterday", id="yday",
                                                className="quick-date-btn", n_clicks=0),
                                    html.Button("Last 7 days", id="last_week",
                                                className="quick-date-btn", n_clicks=0),
                                    html.Button("Last 30 days", id="last_month",
                                                className="quick-date-btn", n_clicks=0),
                                ],
                            ),
                        ],
                    ),
                    # Date Range
                    html.Div(
                        className="filter-section",
                        children=[
                            html.Div("Date Range", className="filter-label"),
                            dcc.DatePickerRange(
                                id="date_range",
                                display_format="DD MMM YYYY",
                                start_date="2026-03-01",
                                end_date="2026-03-04",
                                start_date_placeholder_text="Start",
                                end_date_placeholder_text="End",
                                className="dropdown-sidebar",
                            ),
                        ],
                    ),
                ],
            ),

            # Reset Button
            html.Button(
                "↻ Reset All Filters",
                id="reset_btn",
                className="reset-btn",
                n_clicks=0,
            ),

            # WHO / UK Toggle
            html.Div(
                id="threshold-toggle-wrapper",
                className="filter-section",
                children=[
                    html.Div("Threshold Standard", className="filter-label"),
                    html.Div(
                        className="toggle-container",
                        children=[
                            html.Button(
                                "UK Legal",
                                id="toggle-uk",
                                className="toggle-option active",
                                n_clicks=0,
                            ),
                            html.Button(
                                "WHO Advisory",
                                id="toggle-who",
                                className="toggle-option",
                                n_clicks=0,
                            ),
                        ],
                    ),
                ],
            ),

            # Theme Toggle
            html.Div(
                className="filter-section",
                children=[
                    html.Div("Appearance", className="filter-label"),
                    html.Div(
                        className="toggle-container",
                        children=[
                            html.Button(
                                "🌙 Dark",
                                id="toggle-dark",
                                className="toggle-option active",
                                n_clicks=0,
                            ),
                            html.Button(
                                "☀️ Light",
                                id="toggle-light",
                                className="toggle-option",
                                n_clicks=0,
                            ),
                        ],
                    ),
                ],
            ),

            # Data Quality Toggle
            html.Div(
                id="quality-toggle-wrapper",
                className="filter-section",
                children=[
                    html.Div("Data Quality", className="filter-label"),
                    html.Div(
                        className="toggle-container",
                        children=[
                            html.Button(
                                "All",
                                id="toggle-all",
                                className="toggle-option active",
                                n_clicks=0,
                            ),
                            html.Button(
                                ["Ratified", html.Br(), html.Span(
                                    "(Up to 30-09-2025)", style={"fontSize": "0.75em"})],
                                id="toggle-ratified",
                                className="toggle-option",
                                n_clicks=0,
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
