import sys
import os
import pytest
import pandas as pd
from datetime import date, datetime, timedelta

sys.path.append(os.path.abspath("src"))
from utils.logics import (
    toggle_threshold_logic,
    toggle_theme_logic,
    update_year_logic,
    has_full_date_range,
    get_days,
    get_mode,
    apply_dq_cap,
    filter_df,
    compute_allowed_bounds,
    format_with_units,
    threshold_comparison_subtitle,
)


# Unit Testing for toggling threshold
def test_toggle_threshold_uk():
    result = toggle_threshold_logic("toggle-uk", 1, 0)
    assert result == ("toggle-option active", "toggle-option", "UK")


def test_toggle_threshold_who():
    result = toggle_threshold_logic("toggle-who", 0, 1)
    assert result == ("toggle-option", "toggle-option active", "WHO")


def test_toggle_threshold_default():
    result = toggle_threshold_logic(None, None, None)
    assert result == ("toggle-option active", "toggle-option", "UK")


# Unit Testing for toggling themes
def test_toggle_theme_dark():
    result = toggle_theme_logic(1, 0, "toggle-dark")
    assert result == ("toggle-option active", "toggle-option", "dark", "dark")


def test_toggle_theme_light():
    result = toggle_theme_logic(0, 1, "toggle-light")
    assert result == ("toggle-option", "toggle-option active", "light", "light")


def test_toggle_theme_default():
    result = toggle_theme_logic(None, None, None)
    assert result == ("toggle-option active", "toggle-option", "dark", "dark")


# Unit Testing for updating year


# tests/test_year_dropdown.py
def test_update_year_no_selection():
    """Test when nothing selected"""
    result = update_year_logic(
        sites=None,
        pollutant=None,
        current_years=None,
        all_years=[2020, 2021, 2022, 2023, 2024, 2025],
        site_to_years={...},
        pollutant_to_years={...},
        site_pollutant_to_years={...},
    )

    assert len(result) == 6
    assert result[0]["value"] == 2020


# ═══════════════════════════════════════════════════════════════
# Shared fixtures — reusable sample data across test classes
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def sample_df():
    """
    A minimal long-format DataFrame that mirrors the real wales_df_long structure.
    Four rows: 2 sites × 2 pollutants, 2 consecutive days each.
    """
    return pd.DataFrame(
        {
            "site": ["Cardiff", "Cardiff", "Swansea", "Swansea"],
            "pollutants": ["NO2", "PM2.5", "NO2", "PM2.5"],
            "date": pd.to_datetime(
                [
                    "2024-01-01",
                    "2024-01-02",
                    "2024-01-01",
                    "2024-01-02",
                ]
            ),
            "value": [10.0, 20.0, 30.0, 40.0],
        }
    )


@pytest.fixture
def site_to_dates():
    """Pre-computed (min_date, max_date) for each site."""
    return {
        "Cardiff": (date(2023, 1, 1), date(2024, 12, 31)),
        "Swansea": (date(2022, 6, 1), date(2024, 6, 30)),
    }


@pytest.fixture
def pol_to_dates():
    """Pre-computed (min_date, max_date) for each pollutant."""
    return {
        "NO2": (date(2022, 1, 1), date(2024, 12, 31)),
        "PM2.5": (date(2023, 1, 1), date(2024, 6, 30)),
    }


@pytest.fixture
def site_pol_to_dates():
    """Pre-computed (min_date, max_date) for each (site, pollutant) pair."""
    return {
        ("Cardiff", "NO2"): (date(2023, 1, 1), date(2024, 12, 31)),
        ("Cardiff", "PM2.5"): (date(2023, 6, 1), date(2024, 6, 30)),
        ("Swansea", "NO2"): (date(2022, 6, 1), date(2024, 6, 30)),
        ("Swansea", "PM2.5"): (date(2023, 3, 1), date(2024, 3, 31)),
    }


GLOBAL_MIN = date(2022, 1, 1)
GLOBAL_MAX = date(2024, 12, 31)
RATIFIED_CUTOFF = datetime(2024, 6, 30)


# ═══════════════════════════════════════════════════════════════
# has_full_date_range
# ═══════════════════════════════════════════════════════════════


class TestHasFullDateRange:
    """
    Controls whether downstream callbacks run at all.
    Must be True only when BOTH dates are genuinely present.
    """

    def test_both_present_returns_true(self):
        # Normal case — user has picked a start and end date
        assert has_full_date_range("2024-01-01", "2024-03-01") is True

    def test_start_missing_returns_false(self):
        # User only picked an end date — range is incomplete
        assert has_full_date_range(None, "2024-03-01") is False

    def test_end_missing_returns_false(self):
        # User only picked a start date — range is incomplete
        assert has_full_date_range("2024-01-01", None) is False

    def test_both_missing_returns_false(self):
        # Nothing selected yet — page just loaded
        assert has_full_date_range(None, None) is False

    def test_empty_strings_return_false(self):
        # Dash sometimes sends "" instead of None when a picker is cleared
        assert has_full_date_range("", "") is False

    def test_one_empty_string_returns_false(self):
        assert has_full_date_range("2024-01-01", "") is False


# ═══════════════════════════════════════════════════════════════
# get_days
# ═══════════════════════════════════════════════════════════════


class TestGetDays:
    """
    Drives which chart type is shown and how aggregation is chosen.
    Must handle missing inputs gracefully (dashboard loads before user picks dates).
    """

    def test_same_day_returns_one(self):
        # Start == End means the user is looking at a single day
        assert get_days("2024-01-01", "2024-01-01") == 1

    def test_one_week_returns_seven(self):
        assert get_days("2024-01-01", "2024-01-07") == 7

    def test_full_month_january(self):
        # Jan has 31 days; inclusive count = 31
        assert get_days("2024-01-01", "2024-01-31") == 31

    def test_leap_year_february(self):
        # 2024 is a leap year: Feb 1 → Feb 29 = 29 days
        assert get_days("2024-02-01", "2024-02-29") == 29

    def test_cross_year_boundary(self):
        # Dec 31 → Jan 1 inclusive = 2 days
        assert get_days("2023-12-31", "2024-01-01") == 2

    def test_none_start_returns_none(self):
        # No start date yet — must not crash, just return None
        assert get_days(None, "2024-01-31") is None

    def test_none_end_returns_none(self):
        assert get_days("2024-01-01", None) is None

    def test_both_none_returns_none(self):
        assert get_days(None, None) is None

    def test_minimum_is_one_not_zero(self):
        # Even if someone passes identical timestamps the result should be 1
        assert get_days("2024-06-15", "2024-06-15") >= 1


# ═══════════════════════════════════════════════════════════════
# get_mode
# ═══════════════════════════════════════════════════════════════


class TestGetMode:
    """
    Determines chart granularity — wrong mode = misleading chart for the user.
    Test all four buckets AND their exact boundary values.
    """

    # ── Exact boundary values (fence-post errors are common here) ──

    def test_boundary_day_exactly_one(self):
        assert get_mode(1) == "day"

    def test_boundary_short_starts_at_two(self):
        # 2 days is NOT a single day anymore — should be "short"
        assert get_mode(2) == "short"

    def test_boundary_short_ends_at_29(self):
        assert get_mode(29) == "short"

    def test_boundary_medium_starts_at_30(self):
        # 30 days triggers weekly aggregation
        assert get_mode(30) == "medium"

    def test_boundary_medium_ends_at_179(self):
        assert get_mode(179) == "medium"

    def test_boundary_long_starts_at_180(self):
        # 180 days → monthly aggregation
        assert get_mode(180) == "long"

    # ── Mid-range sanity checks ──

    def test_mid_short(self):
        assert get_mode(15) == "short"

    def test_mid_medium(self):
        assert get_mode(90) == "medium"

    def test_mid_long(self):
        assert get_mode(365) == "long"

    def test_multi_year(self):
        assert get_mode(730) == "long"


# ═══════════════════════════════════════════════════════════════
# apply_dq_cap
# ═══════════════════════════════════════════════════════════════


class TestApplyDqCap:
    """
    Prevents provisional (un-ratified) data from appearing when the user
    has selected 'Ratified' quality mode.
    """

    def test_ratified_mode_caps_end_date(self):
        # end_dt is AFTER the cutoff → should be capped
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)  # after cutoff
        s, e = apply_dq_cap(start, end, "Ratified", RATIFIED_CUTOFF)
        assert e == RATIFIED_CUTOFF

    def test_ratified_mode_end_before_cutoff_unchanged(self):
        # end_dt is already BEFORE the cutoff → no change needed
        start = datetime(2024, 1, 1)
        end = datetime(2024, 3, 31)  # before cutoff
        s, e = apply_dq_cap(start, end, "Ratified", RATIFIED_CUTOFF)
        assert e == end

    def test_provisional_mode_end_date_unchanged(self):
        # 'Provisional' mode → cutoff must NOT be applied
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)
        s, e = apply_dq_cap(start, end, "Provisional", RATIFIED_CUTOFF)
        assert e == end

    def test_start_date_never_modified(self):
        # start_dt must pass through untouched regardless of mode
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)
        s, e = apply_dq_cap(start, end, "Ratified", RATIFIED_CUTOFF)
        assert s == start

    def test_end_exactly_on_cutoff_unchanged(self):
        # Exactly on the boundary — should stay as-is
        start = datetime(2024, 1, 1)
        end = RATIFIED_CUTOFF
        s, e = apply_dq_cap(start, end, "Ratified", RATIFIED_CUTOFF)
        assert e == RATIFIED_CUTOFF


# ═══════════════════════════════════════════════════════════════
# filter_df
# ═══════════════════════════════════════════════════════════════


class TestFilterDf:
    """
    The most critical function — every chart and KPI depends on this.
    Tests cover: single filters, combined filters, edge cases, and
    the inclusive end-date boundary (the +1 day / -1 second logic).
    """

    def test_filter_by_single_site(self, sample_df):
        result = filter_df(sample_df, ["Cardiff"], None, None, None)
        assert set(result["site"]) == {"Cardiff"}
        assert len(result) == 2

    def test_filter_by_multiple_sites(self, sample_df):
        result = filter_df(sample_df, ["Cardiff", "Swansea"], None, None, None)
        assert set(result["site"]) == {"Cardiff", "Swansea"}

    def test_filter_by_pollutant(self, sample_df):
        result = filter_df(sample_df, None, "NO2", None, None)
        assert set(result["pollutants"]) == {"NO2"}

    def test_filter_by_start_date_excludes_earlier(self, sample_df):
        # Start date = Jan 2 → Jan 1 row should be gone
        result = filter_df(sample_df, None, None, "2024-01-02", None)
        assert all(result["date"] >= pd.Timestamp("2024-01-02"))

    def test_filter_by_end_date_excludes_later(self, sample_df):
        # End date = Jan 1 → Jan 2 row should be gone
        result = filter_df(sample_df, None, None, None, "2024-01-01")
        assert all(result["date"] <= pd.Timestamp("2024-01-01 23:59:59"))

    def test_end_date_is_inclusive(self, sample_df):
        # Jan 2 rows must be INCLUDED when end_date = "2024-01-02"
        result = filter_df(sample_df, None, None, "2024-01-01", "2024-01-02")
        assert len(result) == 4  # all rows

    def test_combined_site_and_pollutant(self, sample_df):
        result = filter_df(sample_df, ["Cardiff"], "NO2", None, None)
        assert len(result) == 1
        assert result.iloc[0]["site"] == "Cardiff"
        assert result.iloc[0]["pollutants"] == "NO2"

    def test_unknown_site_returns_empty(self, sample_df):
        result = filter_df(sample_df, ["Newport"], None, None, None)
        assert result.empty

    def test_no_filters_returns_all_rows(self, sample_df):
        result = filter_df(sample_df, None, None, None, None)
        assert len(result) == len(sample_df)

    def test_empty_site_list_treated_as_no_filter(self, sample_df):
        # [] means "nothing selected" — should return all rows, not zero rows
        result = filter_df(sample_df, [], None, None, None)
        assert len(result) == len(sample_df)

    def test_result_is_sorted_by_date(self, sample_df):
        # Shuffle the input to make sure sorting is applied
        shuffled = sample_df.sample(frac=1, random_state=42)
        result = filter_df(shuffled, None, None, None, None)
        dates = result["date"].tolist()
        assert dates == sorted(dates)

    def test_returns_copy_not_original(self, sample_df):
        # Mutating the result must not affect the original
        result = filter_df(sample_df, None, None, None, None)
        result["value"] = 999
        assert sample_df["value"].tolist() != [999, 999, 999, 999]


# ═══════════════════════════════════════════════════════════════
# compute_allowed_bounds
# ═══════════════════════════════════════════════════════════════


class TestComputeAllowedBounds:
    """
    Drives the min/max of the date picker — wrong bounds = user can't select
    valid dates or accidentally picks invalid ones.

    The key behaviour:
    - Multiple sites → take the LATEST start (max of mins) and EARLIEST end (min of maxes)
      so the window only covers dates ALL sites have data for.
    - Non-overlapping sites → return (None, None) so the UI can warn the user.
    """

    def test_no_sites_no_pollutant_returns_global(
        self, pol_to_dates, site_to_dates, site_pol_to_dates
    ):
        result = compute_allowed_bounds(
            [],
            None,
            pol_to_dates,
            site_to_dates,
            site_pol_to_dates,
            GLOBAL_MIN,
            GLOBAL_MAX,
        )
        assert result == (GLOBAL_MIN, GLOBAL_MAX)

    def test_no_sites_with_pollutant_returns_pollutant_range(
        self, pol_to_dates, site_to_dates, site_pol_to_dates
    ):
        result = compute_allowed_bounds(
            [],
            "NO2",
            pol_to_dates,
            site_to_dates,
            site_pol_to_dates,
            GLOBAL_MIN,
            GLOBAL_MAX,
        )
        assert result == pol_to_dates["NO2"]

    def test_single_site_no_pollutant_returns_site_range(
        self, pol_to_dates, site_to_dates, site_pol_to_dates
    ):
        result = compute_allowed_bounds(
            ["Cardiff"],
            None,
            pol_to_dates,
            site_to_dates,
            site_pol_to_dates,
            GLOBAL_MIN,
            GLOBAL_MAX,
        )
        assert result == site_to_dates["Cardiff"]

    def test_single_site_with_pollutant_returns_site_pol_range(
        self, pol_to_dates, site_to_dates, site_pol_to_dates
    ):
        result = compute_allowed_bounds(
            ["Cardiff"],
            "NO2",
            pol_to_dates,
            site_to_dates,
            site_pol_to_dates,
            GLOBAL_MIN,
            GLOBAL_MAX,
        )
        assert result == site_pol_to_dates[("Cardiff", "NO2")]

    def test_two_overlapping_sites_returns_intersection(
        self, pol_to_dates, site_to_dates, site_pol_to_dates
    ):
        # Cardiff NO2: 2023-01-01 → 2024-12-31
        # Swansea NO2: 2022-06-01 → 2024-06-30
        # Intersection: 2023-01-01 → 2024-06-30
        result = compute_allowed_bounds(
            ["Cardiff", "Swansea"],
            "NO2",
            pol_to_dates,
            site_to_dates,
            site_pol_to_dates,
            GLOBAL_MIN,
            GLOBAL_MAX,
        )
        assert result == (date(2023, 1, 1), date(2024, 6, 30))

    def test_non_overlapping_sites_returns_none_none(
        self, pol_to_dates, site_to_dates, site_pol_to_dates
    ):
        # Manually craft two sites with no date overlap for PM2.5
        custom_site_pol = {
            ("SiteA", "NO2"): (date(2020, 1, 1), date(2021, 1, 1)),
            ("SiteB", "NO2"): (date(2023, 1, 1), date(2024, 1, 1)),
            # gap: 2021-01-01 < 2023-01-01  → no overlap
        }
        result = compute_allowed_bounds(
            ["SiteA", "SiteB"],
            "NO2",
            pol_to_dates,
            site_to_dates,
            custom_site_pol,
            GLOBAL_MIN,
            GLOBAL_MAX,
        )
        assert result == (None, None)

    def test_site_not_in_lookup_returns_none_none(
        self, pol_to_dates, site_to_dates, site_pol_to_dates
    ):
        # Site exists in the UI but has no precomputed entry — treat as no data
        result = compute_allowed_bounds(
            ["UnknownSite"],
            "NO2",
            pol_to_dates,
            site_to_dates,
            site_pol_to_dates,
            GLOBAL_MIN,
            GLOBAL_MAX,
        )
        assert result == (None, None)

    def test_unknown_pollutant_falls_back_to_global(
        self, pol_to_dates, site_to_dates, site_pol_to_dates
    ):
        # Pollutant not in dict → get() falls back to global bounds
        result = compute_allowed_bounds(
            [],
            "OZONE_UNKNOWN",
            pol_to_dates,
            site_to_dates,
            site_pol_to_dates,
            GLOBAL_MIN,
            GLOBAL_MAX,
        )
        assert result == (GLOBAL_MIN, GLOBAL_MAX)


# ═══════════════════════════════════════════════════════════════
# format_with_units
# ═══════════════════════════════════════════════════════════════


class TestFormatWithUnits:
    """
    KPI card values — if this formats badly the numbers on screen are wrong.
    """

    def test_normal_float_two_decimals(self):
        assert format_with_units(12.3456) == "12.35 µg/m³"

    def test_zero_value(self):
        assert format_with_units(0.0) == "0.00 µg/m³"

    def test_integer_input(self):
        # Should still format as float
        assert format_with_units(5) == "5.00 µg/m³"

    def test_none_returns_placeholder(self):
        assert format_with_units(None) == "--"

    def test_nan_returns_placeholder(self):
        assert format_with_units(float("nan")) == "--"

    def test_custom_decimals(self):
        assert format_with_units(12.3456, decimals=0) == "12 µg/m³"

    def test_custom_units(self):
        result = format_with_units(5.0, units="ppb")
        assert result == "5.00 ppb"

    def test_large_value(self):
        assert format_with_units(1234.5) == "1234.50 µg/m³"

    def test_negative_value(self):
        # Edge case: shouldn't crash (sensor calibration can produce negatives)
        assert format_with_units(-3.2) == "-3.20 µg/m³"


# ═══════════════════════════════════════════════════════════════
# threshold_comparison_subtitle
# ═══════════════════════════════════════════════════════════════


class TestThresholdComparisonSubtitle:
    """
    Drives the colour and wording shown below each KPI value.
    Critical for correct 'above/below/equal' messaging to the user.
    """

    def test_value_above_threshold_is_danger(self):
        result = threshold_comparison_subtitle(
            value=50.0,
            threshold_value=40.0,
            threshold_metric="annual",
            threshold_standard="UK",
        )
        assert result["status"] == "danger"
        assert "above" in result["text"]
        assert "10.00" in result["text"]

    def test_value_below_threshold_is_good(self):
        result = threshold_comparison_subtitle(
            value=30.0,
            threshold_value=40.0,
            threshold_metric="annual",
            threshold_standard="UK",
        )
        assert result["status"] == "good"
        assert "below" in result["text"]
        assert "10.00" in result["text"]

    def test_value_equal_to_threshold_is_neutral(self):
        result = threshold_comparison_subtitle(
            value=40.0,
            threshold_value=40.0,
            threshold_metric="annual",
            threshold_standard="UK",
        )
        assert result["status"] == "neutral"
        assert "Equal" in result["text"]

    def test_none_value_returns_unavailable(self):
        result = threshold_comparison_subtitle(value=None, threshold_value=40.0)
        assert result["status"] == "unavailable"

    def test_none_threshold_returns_unavailable(self):
        result = threshold_comparison_subtitle(value=40.0, threshold_value=None)
        assert result["status"] == "unavailable"

    def test_nan_value_returns_unavailable(self):
        result = threshold_comparison_subtitle(value=float("nan"), threshold_value=40.0)
        assert result["status"] == "unavailable"

    def test_label_includes_standard_and_metric(self):
        result = threshold_comparison_subtitle(
            value=50.0,
            threshold_value=40.0,
            threshold_metric="hourly",
            threshold_standard="WHO",
        )
        assert "WHO" in result["text"]
        assert "hourly" in result["text"]

    def test_label_metric_only(self):
        result = threshold_comparison_subtitle(
            value=50.0, threshold_value=40.0, threshold_metric="daily"
        )
        assert "daily threshold" in result["text"]

    def test_label_standard_only(self):
        result = threshold_comparison_subtitle(
            value=50.0, threshold_value=40.0, threshold_standard="WHO"
        )
        assert "WHO threshold" in result["text"]

    def test_label_no_standard_no_metric(self):
        result = threshold_comparison_subtitle(value=50.0, threshold_value=40.0)
        assert "threshold" in result["text"]

    def test_custom_units_appear_in_text(self):
        result = threshold_comparison_subtitle(
            value=50.0, threshold_value=40.0, units="ppb"
        )
        assert "ppb" in result["text"]

    def test_diff_precision_two_decimal_places(self):
        # 45.678 - 40.0 = 5.678 → should show "5.68"
        result = threshold_comparison_subtitle(value=45.678, threshold_value=40.0)
        assert "5.68" in result["text"]
