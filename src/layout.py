from dash import Dash, html, dcc, callback, Output, Input, State, no_update, callback_context, clientside_callback
from components.sidebar import create_sidebar


def create_layout(wales_df_long):
    return [
        html.Div(
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
                                        html.Span(
                                            "DEFRA", className="topbar-badge")
                                    ]
                                ),
                                html.Div(
                                    className="topbar-meta",
                                    children=[
                                        html.Div(
                                            className="meta-pill",
                                            children=["Stations:", html.Strong(
                                                "--", id="meta-stations")]
                                        ),
                                        html.Div(
                                            className="meta-pill",
                                            children=["Pollutant:", html.Strong(
                                                "--", id="meta-pollutant")]
                                        ),
                                        html.Div(
                                            className="meta-pill",
                                            children=["Period:", html.Strong(
                                                "--", id="meta-period")]
                                        )
                                    ]
                                )
                            ]
                        ),

                        # Content Area
                        html.Div(
                            className="content",
                            children=[

                                # Time Series Chart
                                html.Div(
                                    className="card",
                                    children=[
                                        html.Div(
                                            className="card-header",
                                            children=[
                                                html.Div(
                                                    "Pollutant Concentration Over Time", className="card-title")
                                            ]
                                        ),
                                        html.Div(
                                            id="filter_warning",
                                            style={
                                                "color": "#856404",
                                                "backgroundColor": "#fff3cd",
                                                "border": "1px solid #ffc107",
                                                "borderRadius": "4px",
                                                "padding": "10px 16px",
                                                "margin": "8px 0",
                                                "display": "none",  # hidden by default
                                            }),
                                        html.Div(
                                            className="card-body",
                                            children=[
                                                dcc.Graph(
                                                    id="time-series-chart",
                                                    figure={},
                                                    config={
                                                        'displayModeBar': True, 'displaylogo': False}
                                                )
                                            ]
                                        )
                                    ]
                                ),

                                # Bottom Row: Stats + Completeness
                                html.Div(
                                    style={
                                        "display": "grid", "gridTemplateColumns": "1.5fr 1fr", "gap": "24px"},
                                    children=[
                                        # Summary Statistics
                                        html.Div(
                                            className="card",
                                            children=[
                                                html.Div(
                                                    className="card-header",
                                                    children=[
                                                        html.Div(
                                                            "Summary Statistics", className="card-title")
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
                                                                        html.Div(
                                                                            "Mean", className="stat-label"),
                                                                        html.Div(
                                                                            "--", className="stat-value", id="stat-mean"),
                                                                        html.Div(
                                                                            "μg/m³", className="stat-unit")
                                                                    ]
                                                                ),
                                                                # Median
                                                                html.Div(
                                                                    className="stat-cell",
                                                                    children=[
                                                                        html.Div(
                                                                            "Median", className="stat-label"),
                                                                        html.Div(
                                                                            "--", className="stat-value", id="stat-median"),
                                                                        html.Div(
                                                                            "μg/m³", className="stat-unit")
                                                                    ]
                                                                ),
                                                                # Std Dev
                                                                html.Div(
                                                                    className="stat-cell",
                                                                    children=[
                                                                        html.Div(
                                                                            "Std Dev", className="stat-label"),
                                                                        html.Div(
                                                                            "--", className="stat-value", id="stat-std"),
                                                                        html.Div(
                                                                            "μg/m³", className="stat-unit")
                                                                    ]
                                                                ),
                                                                # Min
                                                                html.Div(
                                                                    className="stat-cell",
                                                                    children=[
                                                                        html.Div(
                                                                            "Min", className="stat-label"),
                                                                        html.Div(
                                                                            "--", className="stat-value", id="stat-min"),
                                                                        html.Div(
                                                                            "μg/m³", className="stat-unit")
                                                                    ]
                                                                ),
                                                                # Max
                                                                html.Div(
                                                                    className="stat-cell",
                                                                    children=[
                                                                        html.Div(
                                                                            "Max", className="stat-label"),
                                                                        html.Div(
                                                                            "--", className="stat-value", id="stat-max"),
                                                                        html.Div(
                                                                            "μg/m³", className="stat-unit")
                                                                    ]
                                                                ),
                                                                # IQR
                                                                html.Div(
                                                                    className="stat-cell",
                                                                    children=[
                                                                        html.Div(
                                                                            "IQR", className="stat-label"),
                                                                        html.Div(
                                                                            "--", className="stat-value", id="stat-iqr"),
                                                                        html.Div(
                                                                            "μg/m³", className="stat-unit")
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
                                )
                            ]
                        )
                    ]
                )
            ]
        )
    ]
