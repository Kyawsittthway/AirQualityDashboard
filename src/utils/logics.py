import plotly.graph_objects as go


def toggle_threshold_logic(button_id, uk_clicks, who_clicks):
    if not uk_clicks and not who_clicks:
        return "toggle-option active", "toggle-option", "UK"

    if button_id == "toggle-uk":
        return "toggle-option active", "toggle-option", "UK"
    else:
        return "toggle-option", "toggle-option active", "WHO"


def toggle_theme_logic(dark_clicks, light_clicks, button_id):
    if not dark_clicks and not light_clicks:
        return "toggle-option active", "toggle-option", "dark", "dark"

    if button_id == "toggle-dark":
        return "toggle-option active", "toggle-option", "dark", "dark"
    else:
        return "toggle-option", "toggle-option active", "light", "light"


def update_year_logic(
    sites,
    pollutant,
    current_years,
    all_years,
    site_to_years,
    pollutant_to_years,
    site_pollutant_to_years,
):
    """
    Pure logic for year dropdown update

    Args:
        sites: Selected sites (None or list)
        pollutant: Selected pollutant (None or str)
        current_years: Currently selected years (None or list)
        all_years: All available years (list)
        site_to_years: Lookup dict {site: set(years)}
        pollutant_to_years: Lookup dict {pollutant: set(years)}
        site_pollutant_to_years: Lookup dict {(site, pol): set(years)}

    Returns:
        List of dicts with 'label' and 'value' for dropdown
    """
    # if nothing is selected then use empty lists
    if sites is None:
        sites = []
    if current_years is None:
        current_years = []

    # if nothing selected then show all years
    if not sites and not pollutant:
        valid = all_years
    # if sites but no pollutant are chosen show all years common to those sites
    elif sites and not pollutant:
        sites_pol = [site_to_years.get(s, set()) for s in sites]
        valid = sorted(set.intersection(*sites_pol)) if sites_pol else []
    # if pollutant but no sites selected then show all years common for that pollutant
    elif not sites and pollutant:
        valid = sorted(pollutant_to_years.get(pollutant, set()))
    # if both site and pollutant chosen then just show the years that match both
    else:
        sites_pol = [site_pollutant_to_years.get((s, pollutant), set()) for s in sites]
        valid = sorted(set.intersection(*sites_pol)) if sites_pol else []

    # keep the years already chosen in the dropdown
    if current_years:
        valid = sorted(set(valid) | set(current_years))

    return [{"label": y, "value": y} for y in valid if y < 2026]


# Filter exceedance logics


def filter_exceedance_data(df, selected_sites, pollutant, selected_years):
    if isinstance(selected_sites, str):
        selected_sites = [selected_sites]

    return df[
        (df["Site"].isin(selected_sites))
        & (df["pollutant"] == pollutant)
        & (df["Year"].isin(selected_years))
    ].copy()


def apply_standard(df, standard):
    who_toggle = standard == "WHO"

    if who_toggle:
        df["Value"] = df["who_value"]
        df["Limit"] = df["who_limit"]
        df["exceeds"] = df["who_exceeds"]
    else:
        df["Value"] = df["uk_value"]
        df["Limit"] = df["uk_limit"]
        df["exceeds"] = df["uk_exceeds"]

    return df


def prepare_chart_data(df):
    df = df.sort_values(["Site", "Year"]).reset_index(drop=True)

    df["label"] = df["Value"].apply(lambda x: "0" if x == 0 else "")
    df["hover_label"] = df["Value"].astype(str)

    df["color"] = df["exceeds"].map({"Above": "red", "Within": "green"}).fillna("grey")

    return df


def build_exceedance_chart(df, pollutant, y_label):
    fig = go.Figure()

    x_axis = [df["Site"], df["Year_str"]]

    fig.add_trace(
        go.Bar(
            x=x_axis,
            y=df["Value"],
            marker_color=df["color"],
            text=df["label"],
            textposition="outside",
            hovertext=df["hover_label"],
            hovertemplate="Site: %{x[0]}<br>Year: %{x[1]}<br>Value:%{hovertext}<extra></extra>",
            showlegend=False,
        )
    )

    # legend
    fig.add_trace(go.Bar(x=[None], y=[None], marker_color="red", name="Above Limit"))
    fig.add_trace(go.Bar(x=[None], y=[None], marker_color="green", name="Within Limit"))

    # limit line
    unique_limits = df["Limit"].dropna().unique()
    if len(unique_limits) == 1 and unique_limits[0] != 0:
        fig.add_hline(y=unique_limits[0], line_dash="dash", line_color="red")

    fig.update_layout(
        title=f"{pollutant} Exceedance for Selected Sites",
        barmode="group",
        yaxis_title=y_label,
    )

    return fig
