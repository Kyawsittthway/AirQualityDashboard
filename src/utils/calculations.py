"""
Integrated Utility Functions
Combines Rosie's exceedance logic + Charles' completeness calculations
"""

import pandas as pd
import numpy as np


LIMITS = {
    'UK': {
        'PM2.5': {'annual': 20},
        'PM10': {'daily': 50, 'annual': 40, 'annual_allowed': 35},
        'NO2': {'hourly': 200, 'annual_allowed': 18, 'annual': 40},
        'SO2': {'daily': 125, 'annual_allowed': 3},
        'O3': {'8h': 120, 'annual_allowed': 10}
    },
    'WHO': {
        'PM2.5': {'daily': 15},
        'PM10': {'daily': 45},
        'O3': {'8h': 100},
        'NO2': {'daily': 25},
        'SO2': {'daily': 40}
    }
}

POLLUTANT_DISPLAY_NAMES = {
    'NO2': 'NO₂',
    'PM2.5': 'PM₂.₅',
    'PM10': 'PM₁₀',
    'O3': 'O₃',
    'SO2': 'SO₂'
}

def calculate_exceedance(df, pollutant, threshold_type='UK'):
    """
    Calculate exceedances using Rosie's sophisticated logic.
    
    Args:
        df: Filtered DataFrame (wide format)
        pollutant: Pollutant name (e.g., 'NO2', 'PM2.5')
        threshold_type: 'UK' or 'WHO'
    
    Returns:
        dict: {
            'value': exceedance count or mean,
            'limit': threshold value,
            'label': description of what's being measured,
            'type': 'count' or 'mean'
        }
    """
    if df.empty or pollutant not in df.columns:
        return {
            'value': 0,
            'limit': 0,
            'label': 'No data available',
            'type': 'none'
        }
    
    # PM2.5: Annual mean (UK) or daily exceedances (WHO)
    if pollutant == 'PM2.5':
        if threshold_type == 'WHO':
            daily_mean = df.groupby(df['date'].dt.date)[pollutant].mean()
            value = (daily_mean > LIMITS['WHO']['PM2.5']['daily']).sum()
            return {
                'value': int(value),
                'limit': LIMITS['WHO']['PM2.5']['daily'],
                'label': f'Days exceeding {LIMITS["WHO"]["PM2.5"]["daily"]} μg/m³',
                'type': 'count'
            }
        else:
            value = df[pollutant].mean()
            limit = LIMITS['UK']['PM2.5']['annual']
            return {
                'value': round(value, 1),
                'limit': limit,
                'label': f'Annual mean (limit: {limit} μg/m³)',
                'type': 'mean'
            }
    
    # PM10: Daily exceedances
    elif pollutant == 'PM10':
        daily_mean = df.groupby(df['date'].dt.date)[pollutant].mean()
        limit = LIMITS[threshold_type]['PM10']['daily']
        value = (daily_mean > limit).sum()
        annual_allowed = LIMITS['UK']['PM10']['annual_allowed']
        return {
            'value': int(value),
            'limit': annual_allowed,
            'label': f'Days exceeding {limit} μg/m³ (max {annual_allowed}/year)',
            'type': 'count'
        }
    
    # NO2: Hourly exceedances (UK) or daily exceedances (WHO)
    elif pollutant == 'NO2':
        if threshold_type == 'WHO':
            daily_max = df.groupby(df['date'].dt.date)[pollutant].max()
            value = (daily_max > LIMITS['WHO']['NO2']['daily']).sum()
            return {
                'value': int(value),
                'limit': LIMITS['WHO']['NO2']['daily'],
                'label': f'Days exceeding {LIMITS["WHO"]["NO2"]["daily"]} μg/m³',
                'type': 'count'
            }
        else:
            value = (df[pollutant] > LIMITS['UK']['NO2']['hourly']).sum()
            annual_allowed = LIMITS['UK']['NO2']['annual_allowed']
            return {
                'value': int(value),
                'limit': annual_allowed,
                'label': f'Hours exceeding {LIMITS["UK"]["NO2"]["hourly"]} μg/m³ (max {annual_allowed}/year)',
                'type': 'count'
            }
    
    # SO2: Daily exceedances
    elif pollutant == 'SO2':
        daily_mean = df.groupby(df['date'].dt.date)[pollutant].mean()
        limit = LIMITS[threshold_type]['SO2']['daily']
        value = (daily_mean > limit).sum()
        annual_allowed = LIMITS['UK']['SO2']['annual_allowed']
        return {
            'value': int(value),
            'limit': annual_allowed,
            'label': f'Days exceeding {limit} μg/m³ (max {annual_allowed}/year)',
            'type': 'count'
        }
    
    # O3: 8-hour rolling mean exceedances
    elif pollutant == 'O3':
        df_sorted = df.sort_values('date')
        df_sorted['8h_mean'] = df_sorted[pollutant].rolling(window=8, min_periods=8).mean()
        daily_max = df_sorted.groupby(df_sorted['date'].dt.date)['8h_mean'].max()
        limit = LIMITS[threshold_type]['O3']['8h']
        value = (daily_max > limit).sum()
        annual_allowed = LIMITS['UK']['O3']['annual_allowed']
        return {
            'value': int(value),
            'limit': annual_allowed,
            'label': f'Days exceeding 8h mean {limit} μg/m³ (max {annual_allowed}/year)',
            'type': 'count'
        }
    
    return {
        'value': 0,
        'limit': 0,
        'label': 'Unknown pollutant',
        'type': 'none'
    }




def calculate_completeness(df, pollutant, date_col='date'):
    """
    Calculate data completeness percentage.
    
    Args:
        df: DataFrame with date and pollutant data
        pollutant: Pollutant column name
        date_col: Name of date column
    
    Returns:
        float: Percentage completeness (0-100)
    """
    if df.empty or pollutant not in df.columns or date_col not in df.columns:
        return 0.0
    
    expected = df[date_col].nunique()
    if expected == 0:
        return 0.0
    
    actual = df[pollutant].notna().sum()
    completeness = (actual / len(df)) * 100
    
    return round(completeness, 1)


def calculate_completeness_by_site(df, sites, pollutant):
    """
    Calculate completeness for each site.
    
    Args:
        df: DataFrame with site and pollutant data
        sites: List of site names
        pollutant: Pollutant column name
    
    Returns:
        list: [{site, completeness, status}]
    """
    if df.empty or 'site' not in df.columns or pollutant not in df.columns:
        return []
    
    results = []
    
    for site in sites:
        site_df = df[df['site'] == site]
        if not site_df.empty:
            expected = len(site_df)
            valid = site_df[pollutant].notna().sum()
            completeness = round((valid / expected) * 100, 1) if expected > 0 else 0.0
            
            # Status classification
            if completeness >= 85:
                status = 'high'
            elif completeness >= 75:
                status = 'mid'
            else:
                status = 'low'
            
            results.append({
                'site': site,
                'completeness': completeness,
                'status': status
            })
    
    return results


def calculate_summary_stats(filtered_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate site-level summary statistics from filtered long-format data.
    Returns:
        DataFrame with columns: Site, Mean, Median, Min, Max, Std, Observations
    """
    if filtered_df.empty or "site" not in filtered_df.columns or "value" not in filtered_df.columns:
        return pd.DataFrame(columns=["Site", "Mean", "Median", "Min", "Max", "Std", "Observations"])

    summary = (
        filtered_df.groupby("site")["value"]
        .agg(
            Mean="mean",
            Median="median",
            Min="min",
            Max="max",
            Std="std",
            Observations="count",
        )
        .reset_index()
        .rename(columns={"site": "Site"})
    )

    for col in ["Mean", "Median", "Min", "Max", "Std"]:
        summary[col] = summary[col].round(2)

    summary["Observations"] = summary["Observations"].astype(int)

    return summary



def get_status_class(value, limit, is_exceedance=True):
    """
    Determine status class for color coding.
    
    Args:
        value: Current value
        limit: Threshold limit
        is_exceedance: True if higher is worse, False if higher is better
    
    Returns:
        str: 'good', 'warning', or 'danger'
    """
    if value == '--' or value is None:
        return 'good'
    
    if is_exceedance:
        if value == 0:
            return 'good'
        elif value <= limit * 0.5:
            return 'warning'
        else:
            return 'danger'
    else:
        # For completeness (higher is better)
        if value >= 85:
            return 'good'
        elif value >= 75:
            return 'warning'
        else:
            return 'danger'


def format_date_range(start_date, end_date):
    """
    Format date range for display.
    
    Args:
        start_date: Start date
        end_date: End date
    
    Returns:
        str: Formatted date range
    """
    if not start_date or not end_date:
        return "--"
    
    try:
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        
        if start.year == end.year:
            return f"{start.strftime('%b')} – {end.strftime('%b %Y')}"
        else:
            return f"{start.strftime('%b %Y')} – {end.strftime('%b %Y')}"
    except:
        return "--"


def hex_to_rgba(hex_color, alpha=0.12):
    """Convert hex color to rgba for backgrounds."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"
