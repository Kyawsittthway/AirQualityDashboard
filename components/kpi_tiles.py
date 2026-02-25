"""
KPI Tiles Component - Apple Style
Large numbers, sage green gradients, status indicators
"""

from dash import html


def create_kpi_tiles():
    """Create KPI tiles matching Apple aesthetic."""
    return html.Div(
        className="kpi-grid fade-in-up",
        children=[
            # Tile 1: Mean NO2
            html.Div(
                className="kpi-tile status-good",
                id="kpi-no2-container",
                children=[
                    html.Div(
                        className="kpi-header",
                        children=[
                            html.Div("Mean NO₂", className="kpi-label"),
                            html.Div("🌱", className="kpi-icon")
                        ]
                    ),
                    html.Div(
                        className="kpi-value-section",
                        children=[
                            html.Div("--", className="kpi-value", id="kpi-no2-value"),
                            html.Div("μg/m³", className="kpi-unit")
                        ]
                    ),
                    html.Div(
                        "Select data to view",
                        className="kpi-subtitle",
                        id="kpi-no2-subtitle"
                    )
                ]
            ),
            
            # Tile 2: Mean PM2.5
            html.Div(
                className="kpi-tile status-warning",
                id="kpi-pm25-container",
                children=[
                    html.Div(
                        className="kpi-header",
                        children=[
                            html.Div("Mean PM₂.₅", className="kpi-label"),
                            html.Div("💨", className="kpi-icon")
                        ]
                    ),
                    html.Div(
                        className="kpi-value-section",
                        children=[
                            html.Div("--", className="kpi-value", id="kpi-pm25-value"),
                            html.Div("μg/m³", className="kpi-unit")
                        ]
                    ),
                    html.Div(
                        "Select data to view",
                        className="kpi-subtitle",
                        id="kpi-pm25-subtitle"
                    )
                ]
            ),
            
            # Tile 3: Exceedance
            html.Div(
                className="kpi-tile status-danger",
                id="kpi-exceed-container",
                children=[
                    html.Div(
                        className="kpi-header",
                        children=[
                            html.Div("Exceedance", className="kpi-label"),
                            html.Div("⚠️", className="kpi-icon")
                        ]
                    ),
                    html.Div(
                        className="kpi-value-section",
                        children=[
                            html.Div("--", className="kpi-value", id="kpi-exceed-value"),
                            html.Div("days/hours", className="kpi-unit", id="kpi-exceed-unit")
                        ]
                    ),
                    html.Div(
                        "Select data to view",
                        className="kpi-subtitle",
                        id="kpi-exceed-subtitle"
                    )
                ]
            ),
            
            # Tile 4: Completeness
            html.Div(
                className="kpi-tile status-good",
                id="kpi-complete-container",
                children=[
                    html.Div(
                        className="kpi-header",
                        children=[
                            html.Div("Completeness", className="kpi-label"),
                            html.Div("✓", className="kpi-icon")
                        ]
                    ),
                    html.Div(
                        className="kpi-value-section",
                        children=[
                            html.Div("--", className="kpi-value", id="kpi-complete-value"),
                            html.Div("%", className="kpi-unit")
                        ]
                    ),
                    html.Div(
                        "Select data to view",
                        className="kpi-subtitle",
                        id="kpi-complete-subtitle"
                    )
                ]
            )
        ]
    )
