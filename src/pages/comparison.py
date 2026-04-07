import dash
from dash import html,dcc


dash.register_page("pages.comparison", path="/comparison", name="Wales Air Quality | Comparative Analysis")


layout = html.Div(
    className="content",
    children=[
        html.Div(
            className="page-header comparison-page-header",
            children=[
                # html.H1("Comparative Analysis", className="page-title"),
                html.P(
                    "Compare how pollutant concentration relates to temperature, "
                    "cross-variable correlations, and wind-direction patterns across selected sites.",
                    className="page-subtitle",
                ),
            ],
        ),

        html.Div(
            className="comparison-grid",
            children=[
                html.Div(
                    className="card comparison-card comparison-card-full",
                    children=[
                        html.Div(
                            className="card-header comparison-card-header",
                            children=[
                                html.Div(
                                    children=[
                                        html.Div("Temperature vs Pollutant", className="card-title"),
                                        html.Div(
                                            "Shows how pollutant concentration varies with temperature across the selected site(s). Colours distinguish sites; relationships should be interpreted within each site.",
                                            id="temp_scatter_subtitle",
                                            className="card-subtitle",
                                        ),
                                    ]
                                )
                            ],
                        ),
                        html.Div(
                            className="card-body",
                            children=[
                                html.Div(id="temp_scatter_container")
                            ],
                        ),
                        html.Div(
                                    id = 'temp_scatter_insight'
                        ),
                    ],
                ),

                html.Div(
                    className="card comparison-card comparison-card-full",
                    children=[
                        html.Div(
                            className="card-header comparison-card-header",
                            children=[
                                html.Div(
                                    children=[
                                        html.Div("Correlation Matrices", className="card-title"),
                                        html.Div(
                                            "Site-level view of pollutant and temperature relationships. "
                                            "Values near 1 indicate strong positive relationships; values near -1 indicate strong inverse relationships.",
                                            className="card-subtitle",
                                        ),
                                    ]
                                ),
                            ],
                        ),
                        html.Div(
                            className="card-body",
                            children=[
                                html.Div(
                                    id="correlation_heatmap_container",
                                    className="pollution-rose-grid",
                                )
                            ],
                        ),
                        html.Div(id = "correlation_heatmap_insights"),
                    ],
                ),

                html.Div(
                    className="card comparison-card comparison-card-full",
                    children=[
                        html.Div(
                            className="card-header comparison-card-header",
                            children=[
                                html.Div(
                                    children=[
                                        html.Div("Pollution Roses", className="card-title"),
                                        html.Div(
                                            "Site-level wind-direction analysis. Shows how pollutant concentrations are distributed by wind direction, helping identify potential source directions associated with elevated levels.",
                                            className="card-subtitle",
                                        ),
                                    ]
                                )
                            ],
                        ),
                        html.Div(
                            className="card-body",
                            children=[
                                html.Div(
                                    id="pollution_rose_container",
                                    className="pollution-rose-grid",
                                ),
                                html.Div(
                                    id = 'pollution_rose_insights'
                                )
                            ],
                        ),
                    ],
                ),
            ],
        ),
    ],
)

