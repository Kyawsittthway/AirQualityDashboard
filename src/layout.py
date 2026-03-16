from dash import html, page_container
from components.sidebar import create_sidebar


def create_layout(wales_df_long):
    return html.Div(
        id="app-container",
        **{"data-theme": "dark"},
        children=[
            # Sidebar
            create_sidebar(),

            # Main Content
            html.Div(
                id="main-content",
                children=[
                    # Global Top Bar
                    html.Div(
                        className="topbar",
                        children=[
                            html.Div(
                                className="topbar-title",
                                children=[
                                    "Wales Air Quality Dashboard",
                                    html.Span("DEFRA", className="topbar-badge"),
                                ],
                            ),
                            html.Div(
                                className="topbar-meta",
                                children=[
                                    html.Div(
                                        className="meta-pill",
                                        children=["Stations:", html.Strong("--", id="meta-stations")],
                                    ),
                                    html.Div(
                                        className="meta-pill",
                                        children=["Pollutant:", html.Strong("--", id="meta-pollutant")],
                                    ),
                                    html.Div(
                                        className="meta-pill",
                                        children=["Period:", html.Strong("--", id="meta-period")],
                                    ),
                                ],
                            ),
                        ],
                    ),

                    # Routed page content
                    page_container,
                ],
            ),
        ],
    )