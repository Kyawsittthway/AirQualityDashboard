"""
Sidebar Component - Apple Style
Sage green accents, rounded dropdowns, WHO/UK toggle
"""

from dash import html, dcc
import dash_daq as daq


def create_sidebar():
    """Create Apple-style sidebar with filters."""
    return html.Div(
        id="sidebar",
        children=[
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
                    html.Div("UK Air Quality · DEFRA",
                             className="logo-subtitle"),
                ],
            ),
            # WHO / UK Toggle
            html.Div(
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
                    # Hidden store to track which is active
                    dcc.Store(id="threshold-store", data="UK"),
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
                    dcc.Store(id="theme-store", data="dark"),
                ],
            ),
            html.Div(
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
                    dcc.Store(id="dq_store", data="All"),
                ],
            ),
            # Reset Button
            html.Button(
                "↻ Reset All Filters", id="reset_btn", className="reset-btn", n_clicks=0
            ),
            # Site Selection
            html.Div(
                className="filter-section",
                children=[
                    html.Div("Monitoring Sites", className="filter-label"),
                    dcc.Dropdown(
                        className="dropdown-sidebar",
                        id="site_drop",
                        placeholder="Select stations...",
                        multi=True,
                        value=None,
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
                        value=None,
                        className="dropdown-sidebar",
                    ),
                ],
            ),


            dcc.Store(id="filter_store"),

            # Quick Date Range Buttons
            html.Div(
                className="filter-section",
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
                                        className="quick-date-btn", n_clicks=0)
                        ]
                    )
                ]
            ),
            # Date Range
            html.Div(
                className="filter-section",
                children=[
                    html.Div("Date Range", className="filter-label"),
                    dcc.DatePickerRange(
                        id="date_range",
                        display_format="DD MMM YYYY",
                        start_date_placeholder_text="Start",
                        end_date_placeholder_text="End",
                        className="dropdown-sidebar",
                    ),
                ],
            ),
        ],
    )
