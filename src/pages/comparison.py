import dash
from dash import html,dcc


dash.register_page("pages.comparison", path="/comparison", name="Comparison")

layout = html.Div(
    className = 'content',
    children=[
        html.Div(
            className="home-page",
            children=[
                 html.Div(
                    className = 'card',
                    children = [
                        html.Div('Scatter Plot',className = 'card-title')
                    ]
                ),
                html.Div(
                    className = 'card',
                    children = [
                        html.Div('Heat Map',className = 'card-title')
                    ]
                ),
                html.Div(
                    className="card",
                    children=[
                        html.Div('Pollution Rose', className="card-title")
                    ],
                ),
                html.Div(
                    className = 'card-body',
                    children = [
                        html.Div(
                            id = 'pollution_rose_container',
                            style = {
                                'display':'grid',
                                'gridTemplateColumns':'repeat(auto-fit,minmax(320px,1fr))',
                                'gap':'16px'
                            }
                        )
                    ]
                ),
            
            ],
        )
    ],
)