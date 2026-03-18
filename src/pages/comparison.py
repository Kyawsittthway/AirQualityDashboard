import dash
from dash import html


dash.register_page(__name__, path="/comparison", name="Comparison")

layout = html.Div(
    id="app-container",
    **{"data-theme": "dark"},
    children=[
        html.Div(
            className="content",
            children=[
                html.Div(
                    className="comparison-page",
                    children=[
                        html.Div('Comparison page coming soon!', className="coming-soon")
                    ],
                )
            ],
        )
    ],
)