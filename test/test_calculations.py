import pandas as pd
import numpy as np
import pytest

from utils.calculations import (
    calculate_exceedance,
    exceedance_summary,
    calculate_completeness,
    calculate_completeness_by_site,
    calculate_summary_stats,
    get_status_class,
    format_date_range,
    hex_to_rgba,
)


def test_pm25_who_exceedance():
    data = {
        "date": pd.date_range("2024-01-01", periods=3, freq="D"),
        "PM2.5": [10, 20, 30],  # only 20 and 30 exceed WHO daily (15)
    }
    df = pd.DataFrame(data)

    result = calculate_exceedance(df, "PM2.5", "WHO")

    assert result["value"] == 2
    assert result["type"] == "count"


def test_no2_uk_hourly_exceedance():
    data = {
        "date": pd.date_range("2024-01-01", periods=5, freq="h"),
        "NO2": [100, 210, 220, 150, 300],
    }
    df = pd.DataFrame(data)

    result = calculate_exceedance(df, "NO2", "UK")

    assert result["value"] == 3  # >200


def test_completeness():
    df = pd.DataFrame(
        {"date": pd.date_range("2024-01-01", periods=4), "NO2": [1, None, 3, 4]}
    )

    result = calculate_completeness(df, "NO2")

    assert result == 75.0  # 3/4 valid


def test_completeness_by_site():
    df = pd.DataFrame({"site": ["A", "A", "B", "B"], "NO2": [1, None, 2, 3]})

    result = calculate_completeness_by_site(df, ["A", "B"], "NO2")

    assert result[0]["completeness"] == 50.0
    assert result[1]["completeness"] == 100.0


def test_summary_stats():
    df = pd.DataFrame({"site": ["A", "A", "B"], "value": [10, 20, 30]})

    result = calculate_summary_stats(df)

    assert result.loc[result["Site"] == "A", "Mean"].values[0] == 15
    assert result.loc[result["Site"] == "B", "Mean"].values[0] == 30


def test_status_class():
    assert get_status_class(0, 10) == "good"
    assert get_status_class(3, 10) == "warning"
    assert get_status_class(10, 10) == "danger"


def test_format_date_range():
    result = format_date_range("2024-01-01", "2024-03-01")
    assert result == "Jan – Mar 2024"


def test_hex_to_rgba():
    result = hex_to_rgba("#ff0000", 0.5)
    assert result == "rgba(255,0,0,0.5)"


def test_exceedance_summary_basic():
    df = pd.DataFrame(
        {
            "site": ["A"] * 5,
            "year": [2024] * 5,
            "pollutants": ["NO2"] * 5,
            "value": [100, 210, 220, 150, 300],
            "date": pd.date_range("2024-01-01", periods=5, freq="h"),
        }
    )

    result = exceedance_summary(df)

    assert not result.empty
    assert result.iloc[0]["Site"] == "A"
