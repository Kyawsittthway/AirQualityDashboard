import dash 
from dash import html, dcc 
import dash_daq as daq 

dash.register_page("pages.exceedance", path="/exceedance", name="Exceedance", title='Exceedance')

layout = html.Div(
    className='content',
    children=[
        html.Div(
            className='home-page',
            children=[
                html.Div(
                    className='card',
                    children=[
                        html.Div(
                            className='card-header',
                            children=[
                                html.Div('Exceedance Analysis', className='card-title')
                            ]
                        ),
                        html.Div(
                            className='card-body',
                            children=[
                                html.Div(id='exceedance_chart_container')
                            ]
                        )
                    ]
                )
            ]
        )
    ]
)