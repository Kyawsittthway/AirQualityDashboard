from dash import html, dcc

def create_layout(wales_df_long):
    return [
        html.Div(children="TEAM 16 UK-AIR DASHBOARD"),
        html.Button("Reset filters", id="reset_btn", n_clicks=0),

        dcc.Dropdown(
            options=wales_df_long['site'].unique(),
            value=None,
            multi=True,
            id="site_drop",
            placeholder="Choose site.."
        ),

        dcc.Dropdown(
            options=wales_df_long["pollutants"].unique(),
            value=None,
            id='pol_drop',
            placeholder="Choose pollutant..."
        ),

        dcc.DatePickerRange(id="date_range"),
        dcc.Graph(figure={}, id="controls-and-graph")
    ]