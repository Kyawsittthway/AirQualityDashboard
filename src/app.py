# src/app.py
from dash import Dash

from dataloader import load_data
from layout import create_layout
from callbacks import register_callbacks


def create_app() -> Dash:
    app = Dash(__name__)

    # Load data (wide + long)
    wales_df, wales_df_long = load_data()

    # Set layout
    app.layout = create_layout(wales_df_long)

    # Register callbacks
    register_callbacks(app, wales_df, wales_df_long)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=8052)