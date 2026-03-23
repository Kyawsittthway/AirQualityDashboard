# src/app.py
from dash import Dash
from dataloader import load_data
from layout import create_layout
from callbacks import register_callbacks


def create_app() -> Dash:
    """Initialise the Dash app, load data, set layout, and register callbacks."""
    app = Dash(__name__, use_pages=True, suppress_callback_exceptions=True)

    # Load raw wide-format data and the reshaped long-format version
    wales_df, wales_df_long = load_data()

    # Build and assign the dashboard layout using the long-format data for dropdown options
    app.layout = create_layout(wales_df_long)
       
    # Wire up all interactivity — dropdowns, date picker, reset button, and graph
    register_callbacks(app, wales_df, wales_df_long)

    return app


if __name__ == "__main__":
    # Run the development server — disable debug=True in production
    app = create_app()
    app.run(debug=True, use_reloader=False, port=8055)
