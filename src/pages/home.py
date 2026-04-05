import dash
from dash import html, dcc


dash.register_page(__name__, path="/", name="Wales Air Quality | Overview")


layout = html.Div(
            # Main content area
            className="content",
            children=[
                # Warning banner for data issues
                html.Div(
                    id="trends-warning",
                    className="warning-banner",
                    style={"display": "none"},
                        ),
                html.Div(
                    className="home-page",
                    children=[
                        html.Div(
                            className="kpi-grid",
                            children=[
                                # KPIs
                                html.Div(id="trends-kpi-avg", className="kpi-card"),
                                html.Div(id="trends-kpi-max", className="kpi-card"),
                                html.Div(id="trends-kpi-exceed", className="kpi-card"),
                                html.Div(id="trends-kpi-var", className="kpi-card"),
                            ],
                        ),
                        html.Div(
                            className="card",
                            children=[
                                # Tabs for temporal trends
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

                        # Bottom Row: Stats + Completeness
                        html.Div(
                            className="analytics-row",
                            children=[
                                # Site Summary Statistics Table
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
                                                html.Div(id="stats_container")
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
                                                html.Div(
                                                    "Data Completeness", className="card-title")
                                            ]
                                        ),
                                        html.Div(
                                            className="card-body",
                                            children=[
                                                # Overall percentage
                                                html.Div(
                                                    style={
                                                        "textAlign": "center", "marginBottom": "24px"},
                                                    children=[
                                                        html.Div(
                                                            "--",
                                                            id="completeness-overall",
                                                            style={
                                                                "fontSize": "24px",
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
                    ],
                ),
            ]
        )
    
