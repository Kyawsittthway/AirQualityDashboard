# Tests for the pure helper functions embedded in callbacks.py. Updated so it no longer needs seperation of functions in logics.py(deleted).

# Because these functions (filter_df, get_days, etc.) are defined inside
# register_callbacks(), we copy their logic here verbatim so they can be
# tested without a live Dash app or database connection.

# Run with:  pytest tests/test_app_callbacks.py -v


import sys
import os
import pytest
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta

sys.path.append(os.path.abspath("src"))

# ─────────────────────────────────────────────────────────────
# Pure helpers
# ─────────────────────────────────────────────────────────────

RATIFIED_CUTOFF = pd.Timestamp("2025-09-30 00:00:00")


def has_full_date_range(start_date, end_date):
    return bool(start_date) and bool(end_date)


def filter_df(wales_df_long, sites, pollutant, start_date, end_date):
    dff = wales_df_long.copy()
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
    return dff.sort_values("date")


def get_days(start_date, end_date):
    if not start_date or not end_date:
        return None
    return max((pd.to_datetime(end_date) - pd.to_datetime(start_date)).days + 1, 1)


def get_mode(days):
    if days <= 1:
        return "day"
    if days < 30:
        return "short"
    if days < 180:
        return "medium"
    return "long"


def apply_dq_cap(start_dt, end_dt, dq):
    if dq == "Ratified":
        end_dt = min(end_dt, RATIFIED_CUTOFF)
    return start_dt, end_dt


def compute_allowed_bounds(
    sites,
    pollutant,
    pol_to_dates,
    site_to_dates,
    site_pol_to_dates,
    global_min,
    global_max,
):
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


def format_with_units(value, decimals=2, units="µg/m³"):
    if value is None or pd.isna(value):
        return "--"
    return f"{value:.{decimals}f} {units}"


def filters_missing(sites, pollutant, start_date, end_date):
    return not sites or not pollutant or not start_date or not end_date


def ensure_list(value):
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return value


def update_year(
    sites,
    pollutant,
    current_years,
    all_years,
    site_to_years,
    pollutant_to_years,
    site_pollutant_to_years,
):
    # Pure year-dropdown logic extracted from the callback.
    if sites is None:
        sites = []
    if current_years is None:
        current_years = []
    if not sites and not pollutant:
        valid = all_years
    elif sites and not pollutant:
        sites_pol = [site_to_years.get(s, set()) for s in sites]
        valid = sorted(set.intersection(*sites_pol)) if sites_pol else []
    elif not sites and pollutant:
        valid = sorted(pollutant_to_years.get(pollutant, set()))
    else:
        sites_pol = [site_pollutant_to_years.get((s, pollutant), set()) for s in sites]
        valid = sorted(set.intersection(*sites_pol)) if sites_pol else []
    if current_years:
        valid = sorted(set(valid) | set(current_years))
    return [{"label": y, "value": y} for y in valid if y < 2026]


# ─────────────────────────────────────────────────────────────
# Also test toggle logic (module-level callbacks, no Dash needed)
# ─────────────────────────────────────────────────────────────


def toggle_threshold_logic(button_id, uk_clicks, who_clicks):
    if not uk_clicks and not who_clicks:
        return "toggle-option active", "toggle-option", "UK"
    if button_id == "toggle-uk":
        return "toggle-option active", "toggle-option", "UK"
    return "toggle-option", "toggle-option active", "WHO"


def toggle_theme_logic(button_id, dark_clicks, light_clicks):
    if not dark_clicks and not light_clicks:
        return "toggle-option active", "toggle-option", "dark", "dark"
    if button_id == "toggle-dark":
        return "toggle-option active", "toggle-option", "dark", "dark"
    return "toggle-option", "toggle-option active", "light", "light"


def toggle_dq_logic(button_id, all_clicks, ratified_clicks):
    if not all_clicks and not ratified_clicks:
        return "toggle-option active", "toggle-option", "All"
    if button_id == "toggle-all":
        return "toggle-option active", "toggle-option", "All"
    return "toggle-option", "toggle-option active", "Ratified"


# ─────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────

GLOBAL_MIN = date(2022, 1, 1)
GLOBAL_MAX = date(2024, 12, 31)


@pytest.fixture
def sample_df():
    # Minimal long-format DataFrame mirroring wales_df_long.
    return pd.DataFrame(
        {
            "site": ["Cardiff", "Cardiff", "Swansea", "Swansea"],
            "pollutants": ["NO2", "PM2.5", "NO2", "PM2.5"],
            "date": pd.to_datetime(
                ["2024-01-01", "2024-01-02", "2024-01-01", "2024-01-02"]
            ),
            "value": [10.0, 20.0, 30.0, 40.0],
        }
    )


@pytest.fixture
def site_to_dates():
    return {
        "Cardiff": (date(2023, 1, 1), date(2024, 12, 31)),
        "Swansea": (date(2022, 6, 1), date(2024, 6, 30)),
    }


@pytest.fixture
def pol_to_dates():
    return {
        "NO2": (date(2022, 1, 1), date(2024, 12, 31)),
        "PM2.5": (date(2023, 1, 1), date(2024, 6, 30)),
    }


@pytest.fixture
def site_pol_to_dates():
    return {
        ("Cardiff", "NO2"): (date(2023, 1, 1), date(2024, 12, 31)),
        ("Cardiff", "PM2.5"): (date(2023, 6, 1), date(2024, 6, 30)),
        ("Swansea", "NO2"): (date(2022, 6, 1), date(2024, 6, 30)),
        ("Swansea", "PM2.5"): (date(2023, 3, 1), date(2024, 3, 31)),
    }


# ═══════════════════════════════════════════════════════════════
# toggle_threshold_logic
# ═══════════════════════════════════════════════════════════════


class TestToggleThreshold:
    def test_uk_button_sets_uk(self):
        # What: Tests standard toggle interaction for UK standard.
        # How: Passes 'toggle-uk' with 1 click.
        # Expected: UI classes updated, state set to 'UK'.
        result = toggle_threshold_logic("toggle-uk", 1, 0)
        assert result == ("toggle-option active", "toggle-option", "UK")

    def test_who_button_sets_who(self):
        # What: Tests standard toggle interaction for WHO standard.
        # How: Passes 'toggle-who' with 1 click.
        # Expected: UI classes updated, state set to 'WHO'.
        result = toggle_threshold_logic("toggle-who", 0, 1)
        assert result == ("toggle-option", "toggle-option active", "WHO")

    def test_no_clicks_defaults_to_uk(self):
        # What: Tests initial render state logic.
        # How: Passes None for click counts.
        # Expected: Defaults to 'UK'.
        result = toggle_threshold_logic(None, None, None)
        assert result == ("toggle-option active", "toggle-option", "UK")

    def test_uk_class_is_active_for_uk(self):
        # What: Tests CSS active class mapping.
        # How: Simulates UK selection.
        # Expected: 'active' class on UK button, not on WHO.
        uk_cls, who_cls, standard = toggle_threshold_logic("toggle-uk", 1, 0)
        assert "active" in uk_cls
        assert "active" not in who_cls


# ═══════════════════════════════════════════════════════════════
# toggle_theme_logic
# ═══════════════════════════════════════════════════════════════


class TestToggleTheme:
    def test_dark_button_sets_dark(self):
        # What: Tests theme selection (Dark mode).
        # How: Passes 'toggle-dark' button id.
        # Expected: Returns dark UI classes and state strings.
        result = toggle_theme_logic("toggle-dark", 1, 0)
        assert result == ("toggle-option active", "toggle-option", "dark", "dark")

    def test_light_button_sets_light(self):
        # What: Tests theme selection (Light mode).
        # How: Passes 'toggle-light' button id.
        # Expected: Returns light UI classes and state strings.
        result = toggle_theme_logic("toggle-light", 0, 1)
        assert result == ("toggle-option", "toggle-option active", "light", "light")

    def test_no_clicks_defaults_to_dark(self):
        # What: Tests initial default theme.
        # How: No clicks passed.
        # Expected: Defaults to 'dark'.
        result = toggle_theme_logic(None, None, None)
        assert result == ("toggle-option active", "toggle-option", "dark", "dark")

    def test_data_theme_matches_selection(self):
        # What: Verifies synced store/data-theme attributes.
        # How: Simulates Light mode selection.
        # Expected: Both theme attributes equal 'light'.
        _, _, theme_store, data_theme = toggle_theme_logic("toggle-light", 0, 1)
        assert theme_store == data_theme == "light"


# ═══════════════════════════════════════════════════════════════
# toggle_dq_logic
# ═══════════════════════════════════════════════════════════════


class TestToggleDq:
    def test_all_button_sets_all(self):
        # What: Tests data quality filter (All Data).
        # How: Passes 'toggle-all'.
        # Expected: State string returned is 'All'.
        result = toggle_dq_logic("toggle-all", 1, 0)
        assert result == ("toggle-option active", "toggle-option", "All")

    def test_ratified_button_sets_ratified(self):
        # What: Tests data quality filter (Ratified Data).
        # How: Passes 'toggle-ratified'.
        # Expected: State string returned is 'Ratified'.
        result = toggle_dq_logic("toggle-ratified", 0, 1)
        assert result == ("toggle-option", "toggle-option active", "Ratified")

    def test_no_clicks_defaults_to_all(self):
        # What: Tests initial default data quality state.
        # How: Passes None.
        # Expected: Defaults to 'All'.
        result = toggle_dq_logic(None, None, None)
        assert result[2] == "All"


# ═══════════════════════════════════════════════════════════════
# has_full_date_range
# ═══════════════════════════════════════════════════════════════


class TestHasFullDateRange:
    def test_both_present_true(self):
        # What: Checks valid date pair handling.
        # How: Passes standard start and end string dates.
        # Expected: Returns True.
        assert has_full_date_range("2024-01-01", "2024-03-01") is True

    def test_start_missing_false(self):
        # What: Checks missing start date behavior.
        # How: Start is None, End is valid.
        # Expected: Returns False.
        assert has_full_date_range(None, "2024-03-01") is False

    def test_end_missing_false(self):
        # What: Checks missing end date behavior.
        # How: Start is valid, End is None.
        # Expected: Returns False.
        assert has_full_date_range("2024-01-01", None) is False

    def test_both_missing_false(self):
        # What: Checks entirely missing date parameters.
        # How: Both are None.
        # Expected: Returns False.
        assert has_full_date_range(None, None) is False

    def test_empty_strings_false(self):
        # What: Checks handling of empty string types.
        # How: Passes empty strings instead of None.
        # Expected: Returns False.
        assert has_full_date_range("", "") is False

    def test_one_empty_string_false(self):
        # What: Checks partial empty string handling.
        # How: Passes valid start, empty end string.
        # Expected: Returns False.
        assert has_full_date_range("2024-01-01", "") is False


# ═══════════════════════════════════════════════════════════════
# get_days
# ═══════════════════════════════════════════════════════════════


class TestGetDays:
    def test_same_day_returns_one(self):
        # What: Checks inclusive counting logic for same day.
        # How: Start and end dates are identical.
        # Expected: Returns 1 (not 0).
        assert get_days("2024-01-01", "2024-01-01") == 1

    def test_one_week_is_seven(self):
        # What: Checks basic day difference calculation.
        # How: Span of a standard 7-day week.
        # Expected: Returns 7.
        assert get_days("2024-01-01", "2024-01-07") == 7

    def test_full_january_is_31(self):
        # What: Checks month span length.
        # How: Jan 1 to Jan 31.
        # Expected: Returns 31.
        assert get_days("2024-01-01", "2024-01-31") == 31

    def test_leap_year_february(self):
        # What: Checks date math respects leap years.
        # How: Feb 1 to Feb 29 on 2024.
        # Expected: Returns 29.
        assert get_days("2024-02-01", "2024-02-29") == 29

    def test_cross_year_boundary(self):
        # What: Checks date math across new years.
        # How: Dec 31 to Jan 1.
        # Expected: Returns 2.
        assert get_days("2023-12-31", "2024-01-01") == 2

    def test_none_start_returns_none(self):
        # What: Checks safety fallback.
        # How: Missing start date.
        # Expected: Returns None.
        assert get_days(None, "2024-01-31") is None

    def test_none_end_returns_none(self):
        # What: Checks safety fallback.
        # How: Missing end date.
        # Expected: Returns None.
        assert get_days("2024-01-01", None) is None

    def test_both_none_returns_none(self):
        # What: Checks safety fallback.
        # How: Both dates missing.
        # Expected: Returns None.
        assert get_days(None, None) is None

    def test_minimum_is_one(self):
        # What: Asserts fallback floor logic.
        # How: Tests 0 gap calculation.
        # Expected: Will be >= 1.
        assert get_days("2024-06-15", "2024-06-15") >= 1


# ═══════════════════════════════════════════════════════════════
# get_mode
# ═══════════════════════════════════════════════════════════════


class TestGetMode:
    # Exact boundaries
    def test_exactly_one_day(self):
        # What: Tests day-level mode mapping.
        # How: Value 1.
        # Expected: 'day'.
        assert get_mode(1) == "day"

    def test_two_days_is_short(self):
        # What: Tests short-term transition boundary.
        # How: Value 2.
        # Expected: 'short'.
        assert get_mode(2) == "short"

    def test_29_is_short(self):
        # What: Tests upper bound of short-term.
        # How: Value 29.
        # Expected: 'short'.
        assert get_mode(29) == "short"

    def test_30_is_medium(self):
        # What: Tests transition to medium-term.
        # How: Value 30.
        # Expected: 'medium'.
        assert get_mode(30) == "medium"

    def test_179_is_medium(self):
        # What: Tests upper bound of medium-term.
        # How: Value 179.
        # Expected: 'medium'.
        assert get_mode(179) == "medium"

    def test_180_is_long(self):
        # What: Tests transition to long-term.
        # How: Value 180.
        # Expected: 'long'.
        assert get_mode(180) == "long"

    def test_365_is_long(self):
        # What: Tests standard long-term duration.
        # How: Value 365.
        # Expected: 'long'.
        assert get_mode(365) == "long"

    # Mid-range sanity
    def test_15_is_short(self):
        # What: Mid-range short test.
        # How: Value 15.
        # Expected: 'short'.
        assert get_mode(15) == "short"

    def test_90_is_medium(self):
        # What: Mid-range medium test.
        # How: Value 90.
        # Expected: 'medium'.
        assert get_mode(90) == "medium"

    def test_730_is_long(self):
        # What: Extreme long test.
        # How: Value 730 (2 years).
        # Expected: 'long'.
        assert get_mode(730) == "long"


# ═══════════════════════════════════════════════════════════════
# apply_dq_cap
# ═══════════════════════════════════════════════════════════════


class TestApplyDqCap:
    CUTOFF = pd.Timestamp("2025-09-30 00:00:00")

    def test_ratified_mode_caps_end_date_after_cutoff(self):
        # What: Tests date-limiting for ratified data rules.
        # How: Requests end date past the hard cutoff.
        # Expected: Caps returned end date strictly at the CUTOFF.
        start = pd.Timestamp("2024-01-01")
        end = pd.Timestamp("2025-12-31")  # after cutoff
        _, capped = apply_dq_cap(start, end, "Ratified")
        assert capped == self.CUTOFF

    def test_ratified_mode_leaves_end_before_cutoff_unchanged(self):
        # What: Tests safe-range logic under ratified filter.
        # How: Requests end date prior to cutoff.
        # Expected: Returns originally requested end date.
        start = pd.Timestamp("2024-01-01")
        end = pd.Timestamp("2024-06-01")  # before cutoff
        _, result = apply_dq_cap(start, end, "Ratified")
        assert result == end

    def test_all_mode_does_not_cap(self):
        # What: Tests unrestricted 'All' data filter behavior.
        # How: Requests end date past the cutoff, with 'All' mode.
        # Expected: Ignores cutoff limit and returns requested end date.
        start = pd.Timestamp("2024-01-01")
        end = pd.Timestamp("2026-01-01")
        _, result = apply_dq_cap(start, end, "All")
        assert result == end

    def test_start_date_never_changed(self):
        # What: Ensures start date is un-mutated.
        # How: Passes a valid start and over-limit end.
        # Expected: Start date returned matches input.
        start = pd.Timestamp("2024-01-01")
        end = pd.Timestamp("2026-01-01")
        s, _ = apply_dq_cap(start, end, "Ratified")
        assert s == start

    def test_end_exactly_on_cutoff_unchanged(self):
        # What: Tests limit edge boundary.
        # How: Requests end date exactly equal to the cutoff.
        # Expected: Returns the exact cutoff (inclusive).
        start = pd.Timestamp("2024-01-01")
        end = self.CUTOFF
        _, result = apply_dq_cap(start, end, "Ratified")
        assert result == self.CUTOFF


# ═══════════════════════════════════════════════════════════════
# filter_df
# ═══════════════════════════════════════════════════════════════


class TestFilterDf:
    def test_filter_by_single_site(self, sample_df):
        # What: Tests basic single-value slice logic.
        # How: Filters fixture by 'Cardiff'.
        # Expected: Returns 2 rows, only containing 'Cardiff'.
        result = filter_df(sample_df, ["Cardiff"], None, None, None)
        assert set(result["site"]) == {"Cardiff"}
        assert len(result) == 2

    def test_filter_by_multiple_sites(self, sample_df):
        # What: Tests array/list IN condition matching.
        # How: Filters fixture by 'Cardiff' AND 'Swansea'.
        # Expected: Retains rows matching either site.
        result = filter_df(sample_df, ["Cardiff", "Swansea"], None, None, None)
        assert set(result["site"]) == {"Cardiff", "Swansea"}

    def test_filter_by_pollutant(self, sample_df):
        # What: Tests direct column equivalence filter.
        # How: Filters purely on 'NO2'.
        # Expected: Returns only 'NO2' rows.
        result = filter_df(sample_df, None, "NO2", None, None)
        assert set(result["pollutants"]) == {"NO2"}

    def test_start_date_excludes_earlier_rows(self, sample_df):
        # What: Tests start date minimum boundaries.
        # How: Passes Jan 2 start, omits Jan 1 data.
        # Expected: All remaining dates are >= Jan 2.
        result = filter_df(sample_df, None, None, "2024-01-02", None)
        assert all(result["date"] >= pd.Timestamp("2024-01-02"))

    def test_end_date_is_inclusive(self, sample_df):
        # What: Tests day-end inclusive wrapping logic.
        # How: Passes Jan 2 end date.
        # Expected: Retains all 4 rows including those logged ON Jan 2.
        result = filter_df(sample_df, None, None, "2024-01-01", "2024-01-02")
        assert len(result) == 4

    def test_end_date_excludes_next_day(self, sample_df):
        # What: Verifies strict cutoffs.
        # How: Passes Jan 1 end date.
        # Expected: Dates are capped before midnight of Jan 2.
        result = filter_df(sample_df, None, None, None, "2024-01-01")
        assert all(result["date"] <= pd.Timestamp("2024-01-01 23:59:59"))

    def test_combined_site_and_pollutant(self, sample_df):
        # What: Tests overlapping compound filters.
        # How: Filters 'Cardiff' and 'NO2' simultaneously.
        # Expected: Exact intersection (1 row).
        result = filter_df(sample_df, ["Cardiff"], "NO2", None, None)
        assert len(result) == 1
        assert result.iloc[0]["site"] == "Cardiff"
        assert result.iloc[0]["pollutants"] == "NO2"

    def test_unknown_site_returns_empty(self, sample_df):
        # What: Tests safe failure on null matches.
        # How: Filters for non-existent 'Newport'.
        # Expected: Returns an empty dataframe.
        result = filter_df(sample_df, ["Newport"], None, None, None)
        assert result.empty

    def test_no_filters_returns_all_rows(self, sample_df):
        # What: Verifies pristine pass-through.
        # How: None passed for all filters.
        # Expected: Output row count matches input.
        assert len(filter_df(sample_df, None, None, None, None)) == len(sample_df)

    def test_empty_site_list_returns_all_rows(self, sample_df):
        # What: Tests empty list bypass fallback.
        # How: Passes [] for sites.
        # Expected: Ignores site filter, returns all.
        result = filter_df(sample_df, [], None, None, None)
        assert len(result) == len(sample_df)

    def test_result_sorted_by_date(self, sample_df):
        # What: Validates mandatory sorting applied before return.
        # How: Shuffles input, applies blank filter.
        # Expected: Output list's dates are strictly ordered.
        shuffled = sample_df.sample(frac=1, random_state=42)
        result = filter_df(shuffled, None, None, None, None)
        dates = result["date"].tolist()
        assert dates == sorted(dates)

    def test_returns_copy_not_view(self, sample_df):
        # What: Ensures mutability safety to protect source memory.
        # How: Mutates output df and checks original.
        # Expected: Original sample_df 'value' column is unaltered.
        result = filter_df(sample_df, None, None, None, None)
        result["value"] = 999
        assert list(sample_df["value"]) != [999, 999, 999, 999]


# ═══════════════════════════════════════════════════════════════
# compute_allowed_bounds
# ═══════════════════════════════════════════════════════════════


class TestComputeAllowedBounds:
    # Key rule: multiple sites → LATEST start (max of mins) × EARLIEST end (min of maxes).
    # Non-overlapping → (None, None).

    def test_no_sites_no_pollutant_returns_global(
        self, pol_to_dates, site_to_dates, site_pol_to_dates
    ):
        # What: Verifies generic unconstrained bounds lookup.
        # How: Passes empty arrays/None.
        # Expected: Defaults back to GLOBAL min/max.
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
        # What: Tests pollutant-level macro bounds lookup.
        # How: Queries NO2 across all sites.
        # Expected: Matches NO2 definition in pol_to_dates fixture.
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
        # What: Tests site-level macro bounds lookup.
        # How: Queries Cardiff across all pollutants.
        # Expected: Matches Cardiff definition in site_to_dates fixture.
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
        # What: Tests specific narrow bounds query.
        # How: Queries Cardiff + NO2.
        # Expected: Matches exact tuple in site_pol_to_dates.
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
        # What: Tests math for overlapping availability limits.
        # How: Cardiff (2023->2024) and Swansea (2022->2024 mid).
        # Expected: Correctly identifies overlap: 2023-01-01 -> 2024-06-30.
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
        # What: Tests intersection logic for completely distinct date arrays.
        # How: Passes sets from 2020/2021 and 2023/2024.
        # Expected: Min bound > Max bound, fails safely returning (None, None).
        custom = {
            ("SiteA", "NO2"): (date(2020, 1, 1), date(2021, 1, 1)),
            ("SiteB", "NO2"): (date(2023, 1, 1), date(2024, 1, 1)),
        }
        result = compute_allowed_bounds(
            ["SiteA", "SiteB"],
            "NO2",
            pol_to_dates,
            site_to_dates,
            custom,
            GLOBAL_MIN,
            GLOBAL_MAX,
        )
        assert result == (None, None)

    def test_unknown_site_returns_none_none(
        self, pol_to_dates, site_to_dates, site_pol_to_dates
    ):
        # What: Tests safety when checking non-existent bounds.
        # How: Passes 'UnknownSite'.
        # Expected: Empty intersection returns (None, None).
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
        # What: Tests safety mechanism for unindexed pollutants.
        # How: Passes 'OZONE_UNKNOWN'.
        # Expected: Reverts to static GLOBAL min/max.
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
    def test_normal_float_two_decimals(self):
        # What: Tests standard UI label formatting.
        # How: Formats 12.3456.
        # Expected: Drops extra decimals, appends default µg/m³.
        assert format_with_units(12.3456) == "12.35 µg/m³"

    def test_zero(self):
        # What: Tests handling of numeric zero formatting.
        # How: Passes 0.0.
        # Expected: Maintains the requested decimal places correctly ('0.00').
        assert format_with_units(0.0) == "0.00 µg/m³"

    def test_integer_input(self):
        # What: Tests casting and formatting of pure integers.
        # How: Passes 5.
        # Expected: Translates correctly to '5.00'.
        assert format_with_units(5) == "5.00 µg/m³"

    def test_none_returns_placeholder(self):
        # What: Tests safe empty value translation.
        # How: Passes None.
        # Expected: Uses '--' placeholder string.
        assert format_with_units(None) == "--"

    def test_nan_returns_placeholder(self):
        # What: Tests math exception value translation.
        # How: Passes float NaN.
        # Expected: Uses '--' placeholder string.
        assert format_with_units(float("nan")) == "--"

    def test_custom_decimals(self):
        # What: Tests optional override for significant figures.
        # How: Forces decimals=0 on float.
        # Expected: Translates to integer visually ('12 µg/m³').
        assert format_with_units(12.3456, decimals=0) == "12 µg/m³"

    def test_custom_units(self):
        # What: Tests optional override for appended unit label.
        # How: Forces unit text to 'ppb'.
        # Expected: Overwrites default string.
        assert format_with_units(5.0, units="ppb") == "5.00 ppb"

    def test_large_value(self):
        # What: Tests magnitude formatting (no comma injection).
        # How: Passes > 1k values.
        # Expected: Follows rules verbatim '1234.50'.
        assert format_with_units(1234.5) == "1234.50 µg/m³"

    def test_negative_value(self):
        # What: Tests sign preservation in formatting.
        # How: Passes -3.2.
        # Expected: Retains negative notation.
        assert format_with_units(-3.2) == "-3.20 µg/m³"


# ═══════════════════════════════════════════════════════════════
# filters_missing
# ═══════════════════════════════════════════════════════════════


class TestFiltersMissing:
    def test_all_present_returns_false(self):
        # What: Validates standard full-param presence checker.
        # How: Provides sites, pollutant, and both dates.
        # Expected: Returns False (nothing missing).
        assert filters_missing(["Cardiff"], "NO2", "2024-01-01", "2024-12-31") is False

    def test_no_sites_returns_true(self):
        # What: Tests site check.
        # How: Missing site var.
        # Expected: True.
        assert filters_missing(None, "NO2", "2024-01-01", "2024-12-31") is True

    def test_no_pollutant_returns_true(self):
        # What: Tests pollutant check.
        # How: Missing pollutant var.
        # Expected: True.
        assert filters_missing(["Cardiff"], None, "2024-01-01", "2024-12-31") is True

    def test_no_start_date_returns_true(self):
        # What: Tests date check.
        # How: Missing start date var.
        # Expected: True.
        assert filters_missing(["Cardiff"], "NO2", None, "2024-12-31") is True

    def test_no_end_date_returns_true(self):
        # What: Tests date check.
        # How: Missing end date var.
        # Expected: True.
        assert filters_missing(["Cardiff"], "NO2", "2024-01-01", None) is True

    def test_all_missing_returns_true(self):
        # What: Validates multi-absence check.
        # How: Everything None.
        # Expected: True.
        assert filters_missing(None, None, None, None) is True

    def test_empty_site_list_returns_true(self):
        # What: Validates strict boolean equivalence behavior.
        # How: Evaluates explicitly empty array.
        # Expected: True.
        assert filters_missing([], "NO2", "2024-01-01", "2024-12-31") is True


# ═══════════════════════════════════════════════════════════════
# ensure_list
# ═══════════════════════════════════════════════════════════════


class TestEnsureList:
    def test_none_returns_empty_list(self):
        # What: Asserts conversion safety.
        # How: Passes None.
        # Expected: Returns [].
        assert ensure_list(None) == []

    def test_empty_string_returns_empty_list(self):
        # What: Asserts conversion safety.
        # How: Passes empty string.
        # Expected: Returns [].
        assert ensure_list("") == []

    def test_string_becomes_single_item_list(self):
        # What: Asserts auto-wrapping of strings.
        # How: Passes 'Cardiff'.
        # Expected: Returns ['Cardiff'].
        assert ensure_list("Cardiff") == ["Cardiff"]

    def test_list_returned_unchanged(self):
        # What: Asserts bypass logic if already a list.
        # How: Passes existing list.
        # Expected: Exact same list back.
        assert ensure_list(["Cardiff", "Swansea"]) == ["Cardiff", "Swansea"]

    def test_empty_list_returns_empty_list(self):
        # What: Asserts pass-through on empty arrays.
        # How: Passes [].
        # Expected: returns [].
        assert ensure_list([]) == []


# ═══════════════════════════════════════════════════════════════
# update_year (year dropdown logic)
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def year_lookups():
    return {
        "all_years": [2020, 2021, 2022, 2023, 2024, 2025],
        "site_to_years": {
            "Cardiff": {2022, 2023, 2024},
            "Swansea": {2021, 2022, 2023},
        },
        "pollutant_to_years": {
            "NO2": {2021, 2022, 2023, 2024},
            "PM2.5": {2022, 2023},
        },
        "site_pollutant_to_years": {
            ("Cardiff", "NO2"): {2022, 2023, 2024},
            ("Cardiff", "PM2.5"): {2022, 2023},
            ("Swansea", "NO2"): {2021, 2022, 2023},
            ("Swansea", "PM2.5"): {2022, 2023},
        },
    }


class TestUpdateYear:
    def test_no_selection_shows_all_years(self, year_lookups):
        # What: Validates default rendering state for year options.
        # How: No filters passed.
        # Expected: Drops 6 year options back matching all_years.
        result = update_year(None, None, None, **year_lookups)
        assert len(result) == 6

    def test_single_site_filters_to_site_years(self, year_lookups):
        # What: Validates filtering years based entirely on site rules.
        # How: Queries Cardiff, parses 'value' out of dict responses.
        # Expected: Only 22, 23, 24 are available.
        result = update_year(["Cardiff"], None, None, **year_lookups)
        values = [r["value"] for r in result]
        assert set(values) == {2022, 2023, 2024}

    def test_pollutant_only_filters_to_pollutant_years(self, year_lookups):
        # What: Validates filtering years based entirely on pollutant rules.
        # How: Queries PM2.5, parses response.
        # Expected: Only 22, 23 are available.
        result = update_year(None, "PM2.5", None, **year_lookups)
        values = [r["value"] for r in result]
        assert set(values) == {2022, 2023}

    def test_site_and_pollutant_returns_intersection(self, year_lookups):
        # What: Validates intersection logic when combining selectors.
        # How: Cardiff + NO2 requested.
        # Expected: 22, 23, 24 intersection match exactly.
        result = update_year(["Cardiff"], "NO2", None, **year_lookups)
        values = [r["value"] for r in result]
        assert set(values) == {2022, 2023, 2024}

    def test_two_sites_returns_common_years(self, year_lookups):
        # What: Validates logic handling for multiple site selection overlap.
        # How: Cardiff + Swansea.
        # Expected: Intersection of both available sites (22, 23).
        result = update_year(["Cardiff", "Swansea"], None, None, **year_lookups)
        values = [r["value"] for r in result]
        assert set(values) == {2022, 2023}

    def test_current_years_preserved_even_if_not_in_valid(self, year_lookups):
        # What: Confirms UI memory safety so active selections don't vanish.
        # How: Restricts valid set to Cardiff (22-24) but passes current_years 21.
        # Expected: 2021 should artificially be preserved in the list.
        result = update_year(["Cardiff"], None, [2021], **year_lookups)
        values = [r["value"] for r in result]
        assert 2021 in values

    def test_year_2026_excluded(self, year_lookups):
        # What: Checks the hardcoded `< 2026` cutoff rule from function.
        # How: Intercepts lookups to forcibly include 2026.
        # Expected: 2026 should be aggressively filtered from returned dicts.
        lookups_with_2026 = {**year_lookups, "all_years": [2024, 2025, 2026]}
        result = update_year(None, None, None, **lookups_with_2026)
        values = [r["value"] for r in result]
        assert 2026 not in values

    def test_result_is_list_of_dicts_with_label_and_value(self, year_lookups):
        # What: Validates exact required structure for Dash dropdown format.
        # How: Generates options arrays.
        # Expected: Standardized 'label' and 'value' mapping dictionary.
        result = update_year(None, None, None, **year_lookups)
        assert all("label" in r and "value" in r for r in result)

    def test_unknown_site_returns_empty(self, year_lookups):
        # What: Checks safe failing with unrecognized variables.
        # How: Inputs site 'Bangor'.
        # Expected: List is empty.
        result = update_year(["Bangor"], None, None, **year_lookups)
        assert result == []
