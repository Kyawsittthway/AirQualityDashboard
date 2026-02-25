"""
Station Cards Component
Shows each station with circular gauge indicators (like Rooms in reference)
"""

from dash import html, dcc
import plotly.graph_objects as go


def create_circular_gauge(value, max_val, color, size=60):
    """
    Create a simple circular gauge using Plotly.
    
    Args:
        value: Current value
        max_val: Maximum value for the gauge
        color: Color for the ring
        size: Size in pixels
    
    Returns:
        Plotly figure
    """
    percentage = (value / max_val * 100) if max_val > 0 else 0
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={'font': {'size': 14, 'color': '#FFFFFF'}},
        gauge={
            'axis': {'range': [0, max_val], 'visible': False},
            'bar': {'color': color, 'thickness': 0.7},
            'bgcolor': 'rgba(255,255,255,0.1)',
            'borderwidth': 0,
            'steps': [{'range': [0, max_val], 'color': 'rgba(255,255,255,0.05)'}],
        }
    ))
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': '#FFFFFF', 'family': 'Inter'},
        height=size,
        width=size,
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False
    )
    
    return fig


def create_station_cards_section():
    """
    Creates station cards grid (populated dynamically by callback).
    Returns container div that will be filled by callback.
    """
    return html.Div(
        id="station-cards-container",
        children=[
            html.Div(
                "Select stations and pollutant to view details",
                style={
                    "textAlign": "center",
                    "color": "var(--text-tertiary)",
                    "padding": "40px",
                    "fontSize": "15px"
                }
            )
        ]
    )
