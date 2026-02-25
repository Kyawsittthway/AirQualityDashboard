from dash import html, dcc


def create_layout(wales_df_long):
    return [
        # Dashboard title
        html.Div(children="TEAM 16 UK-AIR DASHBOARD"),

        # Resets all filters back to their default state
        html.Button("Reset filters", id="reset_btn", n_clicks=0),

        # Multi-select dropdown for monitoring sites —
        # options are dynamically filtered by the selected pollutant and date range
        dcc.Dropdown(
            options=wales_df_long['site'].unique(),
            value=None,
            multi=True,
            id="site_drop",
            placeholder="Choose site.."
        ),

        # Single-select dropdown for pollutant —
        # options are dynamically filtered to only those measured by all selected sites
        dcc.Dropdown(
            options=wales_df_long["pollutants"].unique(),
            value=None,
            id='pol_drop',
            placeholder="Choose pollutant..."
        ),

        # Date range picker — min/max bounds update based on selected sites and pollutant,
        # restricting selection to the overlapping period where all sites have data
        dcc.DatePickerRange(id="date_range"),

        # warning banner for when site(s) selected doesn't have data for the filtered range
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
        dcc.Store(id="filter_store"),

        # Main time series chart — updates when any filter changes
        dcc.Graph(figure={}, id="controls-and-graph")
    ]
