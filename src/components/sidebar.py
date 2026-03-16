"""
Sidebar Component - Apple Style
Sage green accents, rounded dropdowns, WHO/UK toggle
"""

from dash import html, dcc


def create_sidebar():
    """Create Apple-style sidebar with navigation and filters."""
    return html.Div(
        id="sidebar",
        children=[
            # Track current URL
            dcc.Location(id="url"),

            # Logo Header
            html.Div(
                className="sidebar-header",
                children=[
                    html.Div(
                        className="logo-section",
                        children=[
                            html.Div("AL", className="logo-icon"),
                            # html.Div("AirLens", className="logo-text"),
                        ],
                    ),
                    # html.Div("UK Air Quality · DEFRA", className="logo-subtitle"),
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
                                "Temporal Trends",
                                href="/trends",
                                id="nav-trends",
                                className="nav-link",
                            ),
                            # dcc.Link(
                            #     "Site Comparison",
                            #     href="/comparison",
                            #     id="nav-comparison",
                            #     className="nav-link",
                            # ),
                            # dcc.Link(
                            #     "Exceedance & Compliance",
                            #     href="/exceedance",
                            #     id="nav-exceedance",
                            #     className="nav-link",
                            # ),
                            # dcc.Link(
                            #     "Methods & Data Quality",
                            #     href="/methods",
                            #     id="nav-methods",
                            #     className="nav-link",
                            # ),
                        ],
                    ),
                ],
            ),

            html.Div(className="sidebar-divider"),

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
                    dcc.Store(id="threshold-store", data="UK"),
                ],
            ),

            # # Theme Toggle
            # html.Div(
            #     className="filter-section",
            #     children=[
            #         html.Div("Appearance", className="filter-label"),
            #         html.Div(
            #             className="toggle-container",
            #             children=[
            #                 html.Button(
            #                     "🌙 Dark",
            #                     id="toggle-dark",
            #                     className="toggle-option active",
            #                     n_clicks=0,
            #                 ),
            #                 html.Button(
            #                     "☀️ Light",
            #                     id="toggle-light",
            #                     className="toggle-option",
            #                     n_clicks=0,
            #                 ),
            #             ],
            #         ),
            #         dcc.Store(id="theme-store", data="dark"),
            #     ],
            # ),

            # Reset Button
            html.Button(
                "↻ Reset All Filters",
                id="reset_btn",
                className="reset-btn",
                n_clicks=0,
            ),

            # Site Selection
            html.Div(
                className="filter-section",
                children=[
                    html.Div("Monitoring Sites", className="filter-label"),
                    dcc.Dropdown(
                        id="site_drop",
                        placeholder="Select stations...",
                        multi=True,
                        value=['Aston Hill'],
                        className="dropdown-sidebar"                    
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
                        value='NO2',
                        className="dropdown-sidebar"                   
                        ),
                ],
            ),

            dcc.Store(id="filter_store"),

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
                        className="date-picker-sidebar"                  
                        ),
                ],
            ),
        ],
    )

    