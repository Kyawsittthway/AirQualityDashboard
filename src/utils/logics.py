from dash import html
import plotly.graph_objects as go
import pandas as pd
from datetime import date
import plotly.express as px
from utils.calculations import calculate_exceedance


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


# ─────────────────────────────────────────────────────────────
# Date helpers
# ─────────────────────────────────────────────────────────────


def has_full_date_range(start_date, end_date) -> bool:
    """Return True only when BOTH dates are present (non-empty, non-None)."""
    return bool(start_date) and bool(end_date)


def get_days(start_date, end_date):
    """
    Return the inclusive number of days between two date strings.
    Returns None if either date is missing.
    Minimum return value is 1 (same-day selection).
    """
    if not start_date or not end_date:
        return None
    return max((pd.to_datetime(end_date) - pd.to_datetime(start_date)).days + 1, 1)


def get_mode(days: int) -> str:
    """
    Classify a date-range length into a display mode.

    day    : exactly 1 day  → hourly charts make sense
    short  : < 30 days      → daily/weekday charts make sense
    medium : < 180 days     → weekly aggregation makes sense
    long   : 180+ days      → monthly aggregation makes sense
    """
    if days <= 1:
        return "day"
    if days < 30:
        return "short"
    if days < 180:
        return "medium"
    return "long"


def apply_dq_cap(start_dt, end_dt, dq: str, ratified_cutoff):
    """
    Cap end_dt to ratified_cutoff when data-quality mode is 'Ratified'.
    start_dt is passed through unchanged.

    Parameters
    ----------
    start_dt        : datetime-like
    end_dt          : datetime-like
    dq              : str  — 'Ratified' or anything else
    ratified_cutoff : datetime-like — the hard ceiling for ratified data
    """
    if dq == "Ratified":
        end_dt = min(end_dt, ratified_cutoff)
    return start_dt, end_dt


# ─────────────────────────────────────────────────────────────
# DataFrame filtering
# ─────────────────────────────────────────────────────────────


def filter_df(df: pd.DataFrame, sites, pollutant, start_date, end_date) -> pd.DataFrame:
    """
    Filter the long-format DataFrame by site list, pollutant, and date range.
    Any argument can be None / empty to skip that filter.
    Always returns a copy sorted by date.
    """
    dff = df.copy()

    if sites:
        dff = dff[dff["site"].isin(sites)]

    if pollutant:
        dff = dff[dff["pollutants"] == pollutant]

    if start_date:
        dff = dff[dff["date"] >= pd.to_datetime(start_date)]

    if end_date:
        end_dt = (
            pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        )
        dff = dff[dff["date"] <= end_dt]

    return dff.sort_values("date").reset_index(drop=True)


# ─────────────────────────────────────────────────────────────
# Allowed date-range bounds
# ─────────────────────────────────────────────────────────────


def compute_allowed_bounds(
    sites,
    pollutant,
    pol_to_dates: dict,
    site_to_dates: dict,
    site_pol_to_dates: dict,
    global_min: date,
    global_max: date,
):
    """
    Compute the intersection of valid date ranges across all selected sites
    and the chosen pollutant.

    Logic:
    - No sites, no pollutant  → return the global dataset bounds
    - No sites, pollutant     → return the pollutant's own date range
    - Sites + pollutant       → intersect each (site, pollutant) range
    - Sites, no pollutant     → intersect each site's range

    Returns (None, None) when the intersection is empty (no overlap).
    """
    sites = sites or []

    if not sites:
        if pollutant:
            return pol_to_dates.get(pollutant, (global_min, global_max))
        return global_min, global_max

    ranges = []
    for s in sites:
        if pollutant:
            key = (s, pollutant)
            if key in site_pol_to_dates:
                ranges.append(site_pol_to_dates[key])
        else:
            if s in site_to_dates:
                ranges.append(site_to_dates[s])

    if not ranges:
        return None, None

    min_allowed = max(r[0] for r in ranges)
    max_allowed = min(r[1] for r in ranges)

    if min_allowed > max_allowed:
        return None, None

    return min_allowed, max_allowed


# ─────────────────────────────────────────────────────────────
# Formatting helpers
# ─────────────────────────────────────────────────────────────


def format_with_units(value, decimals: int = 2, units: str = "µg/m³") -> str:
    """
    Format a numeric value to a fixed number of decimal places with units.
    Returns '--' for None or NaN.
    """
    if value is None or pd.isna(value):
        return "--"
    return f"{value:.{decimals}f} {units}"


def threshold_comparison_subtitle(
    value,
    threshold_value,
    threshold_metric=None,
    threshold_standard=None,
    units: str = "µg/m³",
):
    """
    Return a plain string describing how 'value' sits relative to 'threshold_value'.

    NOTE: In the original Dash code this returns an html.Span; here we return a
    plain string so the function can be tested without Dash installed.
    The original behaviour is preserved via the 'status' key alongside the text.

    Returns a dict:
        {"text": str, "status": "danger" | "good" | "neutral" | "unavailable"}
    """
    if (
        value is None
        or pd.isna(value)
        or threshold_value is None
        or pd.isna(threshold_value)
    ):
        return {"text": "No threshold available", "status": "unavailable"}

    diff = value - threshold_value

    if threshold_standard and threshold_metric:
        metric_label = f"{threshold_standard} {threshold_metric} threshold"
    elif threshold_metric:
        metric_label = f"{threshold_metric} threshold"
    elif threshold_standard:
        metric_label = f"{threshold_standard} threshold"
    else:
        metric_label = "threshold"

    if diff > 0:
        return {
            "text": f"{abs(diff):.2f} {units} above {metric_label}",
            "status": "danger",
        }
    elif diff < 0:
        return {
            "text": f"{abs(diff):.2f} {units} below {metric_label}",
            "status": "good",
        }
    else:
        return {"text": f"Equal to {metric_label}", "status": "neutral"}


def format_site_value_lines(series, decimals=2, suffix=""):
    # Helper function to format lines for each site, displaying the value with specified decimal places and suffix, or "--" if data is missing
    if series.empty:
        return "--"

    return html.Div(
        [
            html.Div(
                f"{site}: {('--' if pd.isna(val) else f'{val:.{decimals}f}{suffix}')}",
                className="kpi-site-line",
            )
            for site, val in series.items()
        ]
    )


def format_site_exceedance_lines(site_exceedance):
    # Helper function to format exceedance lines for each site, displaying how much each site is above or below the threshold, or "--" if data is missing
    if not site_exceedance:
        return "--"

    return html.Div(
        [
            html.Div(
                f"{row['site']}: {row['value']}",
                className="kpi-site-line",
            )
            for row in site_exceedance
        ]
    )


def format_site_threshold_comparison_lines(
    series,
    threshold_value,
    threshold_metric=None,
    threshold_standard=None,
    decimals=2,
    units="µg/m³",
):
    if series.empty:
        return "--"

    if threshold_standard and threshold_metric:
        metric_label = f"{threshold_standard} {threshold_metric} threshold"
    elif threshold_metric:
        metric_label = f"{threshold_metric} threshold"
    elif threshold_standard:
        metric_label = f"{threshold_standard} threshold"
    else:
        metric_label = "threshold"

    lines = []
    for site, val in series.items():
        if threshold_value is None or pd.isna(val):
            lines.append(html.Div(f"{site}: --", className="kpi-site-line"))
            continue

        if val > threshold_value:
            line_class = "kpi-site-line danger"
            text = f"{site}: {abs(val - threshold_value):.{decimals}f} {units} above {metric_label}"
        elif val < threshold_value:
            line_class = "kpi-site-line good"
            text = f"{site}: {abs(val - threshold_value):.{decimals}f} {units} below {metric_label}"
        else:
            line_class = "kpi-site-line neutral"
            text = f"{site}: Equal to {metric_label}"

        lines.append(html.Div(text, className=line_class))

    return html.Div(lines)


def build_overview_chart(
    dff,
    pollutant_label,
    start_date,
    end_date,
    threshold_value=None,
    threshold_metric=None,
    threshold_standard=None,
):
    # Build the overview line chart for the selected pollutant and date range, with threshold annotation
    start_str = pd.to_datetime(start_date).strftime("%d %b %Y")
    end_str = pd.to_datetime(end_date).strftime("%d %b %Y")

    n_sites = dff["site"].nunique()

    if n_sites > 1:
        fig = px.line(
            dff,
            x="date",
            y="value",
            color="site",
            # markers=True,
        )
    else:
        fig = px.line(
            dff,
            x="date",
            y="value",
            # markers=True,
        )

        peak_idx = dff["value"].idxmax()
        peak_row = dff.loc[peak_idx]

        fig.add_trace(
            go.Scatter(
                x=[peak_row["date"]],
                y=[peak_row["value"]],
                mode="markers+text",
                name="Peak",
                text=["Peak"],
                textposition="top center",
            )
        )

    if threshold_value is not None:
        if threshold_standard and threshold_metric:
            annotation = f"{threshold_standard} {threshold_metric} threshold"
        elif threshold_standard:
            annotation = f"{threshold_standard} threshold"
        elif threshold_metric:
            annotation = f"{threshold_metric} threshold"
        else:
            annotation = "Threshold"

        fig.add_hline(
            y=threshold_value,
            line_dash="dash",
            annotation_text=annotation,
        )

    fig.update_layout(
        title=f"{pollutant_label} Concentration ({start_str} – {end_str})",
        height=400,
        title_font=dict(family="Inter, sans-serif", size=16, color="#d1e0c2"),
        xaxis_title="Date",
        yaxis_title=f"{pollutant_label} (µg/m³)",
        xaxis_title_font=dict(family="Inter, sans-serif", size=13, color="#acb5c0"),
        yaxis_title_font=dict(family="Inter, sans-serif", size=13, color="#acb5c0"),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_title="Site" if n_sites > 1 else None,
    )

    return fig


def build_trend_chart(dff, days, pollutant_label):
    # Build the trend line chart, adjusting aggregation level (daily/weekly/monthly) based on the length of the date range
    if days <= 31:
        freq = "D"
        title = f"Daily {pollutant_label} Concentration"
    elif days < 180:
        freq = "W"
        title = f"Weekly {pollutant_label} Concentration"
    else:
        freq = "ME"
        title = f"Monthly {pollutant_label} Concentration"

    agg = (
        dff.set_index("date")
        .groupby("site")["value"]
        .resample(freq)
        .mean()
        .reset_index()
    )

    n_sites = dff["site"].nunique()

    fig = px.line(
        agg,
        x="date",
        y="value",
        color="site" if n_sites > 1 else None,
        markers=True,
        title=title,
    )

    fig.update_layout(
        height=400,
        title_font=dict(family="Inter, sans-serif", size=16, color="#829a67"),
        xaxis_title="Date",
        yaxis_title=f"{pollutant_label} (µg/m³)",
        xaxis_title_font=dict(family="Inter, sans-serif", size=13, color="#acb5c0"),
        yaxis_title_font=dict(family="Inter, sans-serif", size=13, color="#acb5c0"),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_title="Site" if n_sites > 1 else None,
    )
    return fig


def build_distribution_chart(dff, days, pollutant_label):
    # Build the distribution box plot, adjusting x-axis grouping (day/month) based on the length of the date range
    temp = dff.copy()

    if days <= 31:
        temp["bucket"] = temp["date"].dt.strftime("%Y-%m-%d")
        title = f"{pollutant_label} Distribution by Day"
        x_title = "Day"
    else:
        temp["bucket"] = temp["date"].dt.strftime("%Y-%m")
        title = f"{pollutant_label} Distribution by Month"
        x_title = "Month"

    n_sites = dff["site"].nunique()

    fig = px.box(
        temp,
        x="bucket",
        y="value",
        color="site" if n_sites > 1 else None,
        title=title,
    )

    fig.update_layout(
        height=400,
        title_font=dict(family="Inter, sans-serif", size=16, color="#d1e0c2"),
        xaxis_title=x_title,
        yaxis_title=f"{pollutant_label} (µg/m³)",
        xaxis_title_font=dict(family="Inter, sans-serif", size=13, color="#acb5c0"),
        yaxis_title_font=dict(family="Inter, sans-serif", size=13, color="#acb5c0"),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_title="Site" if n_sites > 1 else None,
    )
    return fig


def build_seasonality_chart(dff, days, pollutant_label):
    # Build the seasonality chart, adjusting grouping (hour of day, weekday, month) based on the length of the date range
    required_cols = {"date", "value"}
    if dff is None or dff.empty or not required_cols.issubset(dff.columns):
        fig = go.Figure()
        fig.update_layout(
            title="No data available for seasonality analysis",
            height=360,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        return fig

    temp = dff.copy()
    temp["date"] = pd.to_datetime(temp["date"], errors="coerce")
    temp = temp.dropna(subset=["date", "value"])

    if temp.empty:
        fig = go.Figure()
        fig.update_layout(
            title="No valid data available for seasonality analysis",
            height=400,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        return fig

    if "site" not in temp.columns:
        temp["site"] = "Selected site"

    temp["site"] = temp["site"].fillna("Unknown site").astype(str)
    n_sites = temp["site"].nunique()

    def apply_layout(fig, title, x_title, y_title, height=360):
        fig.update_layout(
            title=title,
            height=height,
            title_font=dict(
                family="Inter, sans-serif",
                size=16,
                color="#d1e0c2",
            ),
            xaxis_title=x_title,
            yaxis_title=y_title,
            xaxis_title_font=dict(
                family="Inter, sans-serif",
                size=13,
                color="#acb5c0",
            ),
            yaxis_title_font=dict(
                family="Inter, sans-serif",
                size=13,
                color="#acb5c0",
            ),
            font=dict(
                family="Inter, sans-serif",
                size=12,
                color="#acb5c0",
            ),
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend_title="Site" if n_sites > 1 else None,
            margin=dict(l=30, r=20, t=50, b=40),
        )
        return fig

    if days <= 1:
        temp["hour"] = temp["date"].dt.hour

        grouped = (
            temp.groupby(["site", "hour"], as_index=False)["value"]
            .mean()
            .rename(columns={"value": "mean_value"})
        )

        fig = px.line(
            grouped,
            x="hour",
            y="mean_value",
            color="site" if n_sites > 1 else None,
            markers=True,
            title=f"Hourly Profile of {pollutant_label}",
        )
        fig.update_xaxes(dtick=1)

        return apply_layout(
            fig,
            f"Hourly Profile of {pollutant_label}",
            "Hour of Day",
            f"Average {pollutant_label} (µg/m³)",
            height=360,
        )

    elif days <= 45:
        weekday_order = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        temp["weekday"] = temp["date"].dt.day_name()

        grouped = (
            temp.groupby(["site", "weekday"], as_index=False)["value"]
            .mean()
            .rename(columns={"value": "mean_value"})
        )

        grouped["weekday"] = pd.Categorical(
            grouped["weekday"],
            categories=weekday_order,
            ordered=True,
        )
        grouped = grouped.sort_values(["site", "weekday"])

        fig = px.bar(
            grouped,
            x="weekday",
            y="mean_value",
            color="site" if n_sites > 1 else None,
            barmode="group" if n_sites > 1 else "relative",
            title=f"Average {pollutant_label} by Day of Week",
        )

        return apply_layout(
            fig,
            f"Average {pollutant_label} by Day of Week",
            "Weekday",
            f"Average {pollutant_label} (µg/m³)",
            height=380,
        )

    else:
        month_order = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]

        temp["month"] = temp["date"].dt.month_name()

        grouped = (
            temp.groupby(["site", "month"], as_index=False)["value"]
            .mean()
            .rename(columns={"value": "mean_value"})
        )

        grouped["month"] = pd.Categorical(
            grouped["month"],
            categories=month_order,
            ordered=True,
        )
        grouped = grouped.sort_values(["site", "month"])

        fig = px.line(
            grouped,
            x="month",
            y="mean_value",
            color="site" if n_sites > 1 else None,
            markers=True,
            title=f"Seasonal Profile of {pollutant_label}",
        )

        return apply_layout(
            fig,
            f"Seasonal Profile of {pollutant_label}",
            "Month",
            f"Average {pollutant_label} (µg/m³)",
            height=360,
        )


def get_site_exceedance_summary(dff, pollutant, threshold_standard):
    results = []

    dff = dff.copy()
    dff["date"] = pd.to_datetime(dff["date"], errors="coerce")
    dff["value"] = pd.to_numeric(dff["value"], errors="coerce")

    for site, site_df in dff.groupby("site"):
        if site_df.empty:
            results.append(
                {
                    "site": site,
                    "value": 0,
                    "label": "No data available",
                }
            )
            continue

        site_wide = (
            site_df[["date", "pollutants", "value"]]
            .dropna(subset=["date", "value"])
            .pivot(index="date", columns="pollutants", values="value")
            .reset_index()
            .sort_values("date")
        )
        print(f"Site: {site}, rows: {len(site_wide)}")
        print(
            f"Calling calculate_exceedance with pollutant={pollutant}, standard={threshold_standard}"
        )

        exceedance_info = calculate_exceedance(
            site_wide,
            pollutant,
            threshold_standard,
        )
        print(f"Result: {exceedance_info}")
        if pollutant not in site_wide.columns:
            results.append(
                {
                    "site": site,
                    "value": 0,
                    "label": "No data available",
                }
            )
            continue

        exceedance_info = calculate_exceedance(
            site_wide,
            pollutant,
            threshold_standard,
        )

        results.append(
            {
                "site": site,
                "value": exceedance_info["value"],
                "label": exceedance_info["label"],
            }
        )

    return sorted(results, key=lambda x: str(x["site"]))
