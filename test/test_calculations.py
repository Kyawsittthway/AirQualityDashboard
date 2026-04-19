# Tests for utils/calculations.py

# Run with:  pytest tests/test_calculations.py -v


import sys
import os
import pytest
import numpy as np
import pandas as pd

sys.path.append(os.path.abspath("src"))

from utils.calculations import (
    calculate_exceedance,
    exceedance_summary,
    calculate_completeness,
    calculate_completeness_by_site,
    calculate_summary_stats,
    get_status_class,
    format_date_range,
    hex_to_rgba,
    aqi_index,
    aqi_category,
    degrees_to_direction,
    LIMITS,
)


# ═══════════════════════════════════════════════════════════════
# calculate_exceedance — guards
# ═══════════════════════════════════════════════════════════════


class TestCalculateExceedanceGuards:
    def test_empty_df_returns_none_type(self):
        # What: Tests the safety guard for empty datasets.
        # How: Passes a DataFrame with required columns but 0 rows.
        # Expected: Returns a dict with type 'none' and value 0.
        result = calculate_exceedance(pd.DataFrame(columns=["date", "NO2"]), "NO2")
        assert result["type"] == "none"
        assert result["value"] == 0

    def test_missing_pollutant_column_returns_none_type(self):
        # What: Tests behavior when requested pollutant data is missing.
        # How: Passes 'NO2' data but requests 'PM2.5' calculations.
        # Expected: Returns a dict with type 'none'.
        df = pd.DataFrame(
            {"date": pd.date_range("2024-01-01", periods=3), "NO2": [10, 20, 30]}
        )
        result = calculate_exceedance(df, "PM2.5", "UK")
        assert result["type"] == "none"

    def test_unknown_pollutant_returns_zero(self):
        # What: Tests handling of an unrecognized pollutant name.
        # How: Passes dummy pollutant 'XYZ' with no defined limits.
        # Expected: Returns value 0 gracefully instead of a KeyError.
        df = pd.DataFrame(
            {"date": pd.date_range("2024-01-01", periods=3), "XYZ": [1, 2, 3]}
        )
        assert calculate_exceedance(df, "XYZ", "UK")["value"] == 0

    def test_return_dict_always_has_four_keys(self):
        # What: Ensures output structure remains consistent for UI components.
        # How: Calls function with an empty DataFrame to trigger default return.
        # Expected: Dictionary contains exactly 'value', 'limit', 'label', and 'type'.
        df = pd.DataFrame(columns=["date", "NO2"])
        result = calculate_exceedance(df, "NO2")
        assert set(result.keys()) == {"value", "limit", "label", "type"}


# ═══════════════════════════════════════════════════════════════
# calculate_exceedance — PM2.5
# ═══════════════════════════════════════════════════════════════


class TestCalculateExceedancePM25:
    """
    WHO: count days where daily mean > 15 µg/m³
    UK:  count days where daily mean > 20 µg/m³
    """

    @pytest.fixture
    def pm25_df(self):
        return pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=5, freq="D"),
                # WHO (>15): days 2,3,5  → 3 exceedances
                # UK  (>20): day 5 only  → 1 exceedance
                "PM2.5": [5.0, 16.0, 18.0, 3.0, 21.0],
            }
        )

    def test_who_daily_count(self, pm25_df):
        # What: Tests PM2.5 calculation against WHO strict limits.
        # How: Uses fixture with 3 days > 15 µg/m³.
        # Expected: Identifies 3 exceedances, type 'count'.
        result = calculate_exceedance(pm25_df, "PM2.5", "WHO")
        assert result["value"] == 3
        assert result["type"] == "count"

    def test_uk_daily_count(self, pm25_df):
        # What: Tests PM2.5 calculation against UK limits.
        # How: Uses fixture with 1 day > 20 µg/m³.
        # Expected: Identifies 1 exceedance, type 'count'.
        result = calculate_exceedance(pm25_df, "PM2.5", "UK")
        assert result["value"] == 1
        assert result["type"] == "count"

    def test_who_limit_value(self, pm25_df):
        # What: Verifies correct reference limit is attached to WHO results.
        # How: Compares returned limit to defined WHO daily limit.
        # Expected: Exact match with WHO limits dict.
        assert (
            calculate_exceedance(pm25_df, "PM2.5", "WHO")["limit"]
            == LIMITS["WHO"]["PM2.5"]["daily"]
        )

    def test_uk_limit_value(self, pm25_df):
        # What: Verifies correct reference limit is attached to UK results.
        # How: Compares returned limit to defined UK annual limit.
        # Expected: Exact match with UK limits dict.
        assert (
            calculate_exceedance(pm25_df, "PM2.5", "UK")["limit"]
            == LIMITS["UK"]["PM2.5"]["annual"]
        )

    def test_no_exceedances_returns_zero(self):
        # What: Tests behavior when air quality is completely clean.
        # How: Passes dataframe where all values < 15 µg/m³.
        # Expected: Returns exceedance count of 0.
        df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=3, freq="D"),
                "PM2.5": [1.0, 2.0, 3.0],
            }
        )
        assert calculate_exceedance(df, "PM2.5", "WHO")["value"] == 0

    def test_label_contains_threshold_value(self, pm25_df):
        # What: Checks that the UI-facing label string describes the threshold.
        # How: Inspects the 'label' string of a WHO result.
        # Expected: String explicitly contains '15'.
        result = calculate_exceedance(pm25_df, "PM2.5", "WHO")
        assert "15" in result["label"]


# ═══════════════════════════════════════════════════════════════
# calculate_exceedance — NO2
# ═══════════════════════════════════════════════════════════════


class TestCalculateExceedanceNO2:
    """
    UK:  count hourly readings > 200 µg/m³ (limit = annual_allowed 18)
    WHO: count days where daily max > 25 µg/m³
    """

    @pytest.fixture
    def no2_df(self):
        # 3 readings exceed 200: 210, 220, 300
        return pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=6, freq="h"),
                "NO2": [100.0, 210.0, 220.0, 150.0, 300.0, 195.0],
            }
        )

    def test_uk_hourly_count(self, no2_df):
        # What: Tests NO2 exceedance counting for UK hourly standard.
        # How: Passes 6 hourly readings, 3 are > 200 µg/m³.
        # Expected: Returns exactly 3 exceedances.
        result = calculate_exceedance(no2_df, "NO2", "UK")
        assert result["value"] == 3
        assert result["type"] == "count"

    def test_uk_limit_is_annual_allowed(self, no2_df):
        # What: Ensures UK NO2 limit maps to annual allowed hourly exceedances.
        # How: Extracts 'limit' key from result.
        # Expected: Matches annual_allowed limit (18).
        result = calculate_exceedance(no2_df, "NO2", "UK")
        assert result["limit"] == LIMITS["UK"]["NO2"]["annual_allowed"]

    def test_who_daily_count(self):
        # What: Tests WHO daily counting for NO2.
        # How: Passes 2 daily max readings > 25 µg/m³.
        # Expected: Returns exceedance count of 2.
        df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=2, freq="D"),
                "NO2": [220.0, 30.0],
            }
        )
        assert calculate_exceedance(df, "NO2", "WHO")["value"] == 2

    def test_uk_label_mentions_200(self, no2_df):
        # What: Checks that the UI label correctly references 200 µg/m³.
        # How: Generates a UK NO2 result and inspects label.
        # Expected: Label contains the string '200'.
        assert "200" in calculate_exceedance(no2_df, "NO2", "UK")["label"]

    def test_all_below_threshold_returns_zero(self):
        # What: Validates behavior when NO2 levels are high but legal.
        # How: Passes values up to 199.0 µg/m³ (limit 200).
        # Expected: Identifies 0 exceedances.
        df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=4, freq="h"),
                "NO2": [10.0, 50.0, 100.0, 199.0],
            }
        )
        assert calculate_exceedance(df, "NO2", "UK")["value"] == 0


# ═══════════════════════════════════════════════════════════════
# calculate_exceedance — PM10
# ═══════════════════════════════════════════════════════════════


class TestCalculateExceedancePM10:
    def test_uk_daily_count(self):
        # What: Tests UK daily PM10 limit tracking.
        # How: Passes 4 days, 2 exceed UK daily limit of 50 µg/m³.
        # Expected: Returns 2 exceedances.
        df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=4, freq="D"),
                "PM10": [30.0, 55.0, 60.0, 40.0],  # 2 days > UK daily 50
            }
        )
        assert calculate_exceedance(df, "PM10", "UK")["value"] == 2

    def test_who_daily_count(self):
        # What: Tests WHO daily PM10 limit tracking.
        # How: Passes 3 days, 1 exceeds WHO limit of 45 µg/m³.
        # Expected: Returns 1 exceedance.
        df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=3, freq="D"),
                "PM10": [40.0, 50.0, 30.0],  # 1 day > WHO daily 45
            }
        )
        assert calculate_exceedance(df, "PM10", "WHO")["value"] == 1

    def test_limit_is_annual_allowed(self):
        # What: Verifies PM10 references annual permitted count.
        # How: Runs standard calculation and extracts UK limit.
        # Expected: Returns UK annual_allowed limit (35 days).
        df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=2, freq="D"),
                "PM10": [30.0, 60.0],
            }
        )
        assert (
            calculate_exceedance(df, "PM10", "UK")["limit"]
            == LIMITS["UK"]["PM10"]["annual_allowed"]
        )


# ═══════════════════════════════════════════════════════════════
# calculate_exceedance — SO2
# ═══════════════════════════════════════════════════════════════


class TestCalculateExceedanceSO2:
    def test_uk_daily_count(self):
        # What: Tests UK daily SO2 threshold detection.
        # How: Passes 3 days, 2 exceed UK 125 µg/m³ limit.
        # Expected: Returns 2 exceedances.
        df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=3, freq="D"),
                "SO2": [100.0, 130.0, 140.0],  # 2 days > UK daily 125
            }
        )
        assert calculate_exceedance(df, "SO2", "UK")["value"] == 2

    def test_who_daily_count(self):
        # What: Tests WHO daily SO2 threshold detection.
        # How: Passes 3 days, 2 exceed stricter WHO 40 µg/m³ limit.
        # Expected: Returns 2 exceedances.
        df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=3, freq="D"),
                "SO2": [30.0, 45.0, 50.0],  # 2 days > WHO daily 40
            }
        )
        assert calculate_exceedance(df, "SO2", "WHO")["value"] == 2

    def test_no_exceedances_returns_zero(self):
        # What: Confirms false positives are avoided when SO2 is low.
        # How: Passes readings safely below UK limit.
        # Expected: Returns 0 exceedances.
        df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=3, freq="D"),
                "SO2": [10.0, 20.0, 30.0],
            }
        )
        assert calculate_exceedance(df, "SO2", "UK")["value"] == 0


# ═══════════════════════════════════════════════════════════════
# calculate_exceedance — O3
# ═══════════════════════════════════════════════════════════════


class TestCalculateExceedanceO3:
    def test_8h_rolling_exceedance_detected(self):
        # What: Tests 8-hour rolling mean calculation unique to O3.
        # How: 8 consecutive hours at 130 (triggering > 120), then low.
        # Expected: Detects >=1 exceedance, type 'count'.
        df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=16, freq="h"),
                "O3": [130.0] * 8 + [50.0] * 8,
            }
        )
        result = calculate_exceedance(df, "O3", "UK")
        assert result["value"] >= 1
        assert result["type"] == "count"

    def test_below_threshold_no_exceedances(self):
        # What: Ensures rolling mean logic ignores high-but-legal levels.
        # How: Passes 8 hours of 80 µg/m³ (< 120 threshold).
        # Expected: Returns 0 exceedances.
        df = pd.DataFrame(
            {"date": pd.date_range("2024-01-01", periods=8, freq="h"), "O3": [80.0] * 8}
        )
        assert calculate_exceedance(df, "O3", "UK")["value"] == 0

    def test_limit_is_annual_allowed(self):
        # What: Verifies reference limit attached to O3 results.
        # How: Calculates O3 exceedances, checks 'limit' key.
        # Expected: Returns UK O3 annual_allowed limit (10 days).
        df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=8, freq="h"),
                "O3": [130.0] * 8,
            }
        )
        assert (
            calculate_exceedance(df, "O3", "UK")["limit"]
            == LIMITS["UK"]["O3"]["annual_allowed"]
        )


# ═══════════════════════════════════════════════════════════════
# exceedance_summary
# ═══════════════════════════════════════════════════════════════


class TestExceedanceSummary:

    @pytest.fixture
    def no2_df(self):
        """8 hourly NO2 readings — 3 exceed 200 µg/m³."""
        return pd.DataFrame(
            {
                "site": ["A"] * 8,
                "year": [2024] * 8,
                "pollutants": ["NO2"] * 8,
                "value": [50.0, 210.0, 220.0, 150.0, 300.0, 90.0, 80.0, 205.0],
                "date": pd.date_range("2024-01-01", periods=8, freq="h"),
            }
        )

    def test_returns_dataframe(self, no2_df):
        # What: Checks return type of summary generator.
        # How: Passes NO2 fixture.
        # Expected: Output is a pandas DataFrame.
        assert isinstance(exceedance_summary(no2_df), pd.DataFrame)

    def test_not_empty_for_valid_input(self, no2_df):
        # What: Verifies valid records are not dropped.
        # How: Passes valid NO2 fixture.
        # Expected: Resulting DataFrame is not empty.
        assert not exceedance_summary(no2_df).empty

    def test_required_columns_present(self, no2_df):
        # What: Ensures necessary columns exist for UI data table.
        # How: Iterates predefined list against output columns.
        # Expected: All 10 expected columns are present.
        result = exceedance_summary(no2_df)
        for col in [
            "Site",
            "Year",
            "pollutant",
            "uk_value",
            "uk_limit",
            "uk_exceeds",
            "who_value",
            "who_limit",
            "who_exceeds",
            "Year_str",
        ]:
            assert col in result.columns, f"Missing column: {col}"

    def test_site_name_correct(self, no2_df):
        # What: Validates group-by logic preserves site names.
        # How: Checks 'Site' column of summary.
        # Expected: Site name 'A' is retained.
        assert exceedance_summary(no2_df).iloc[0]["Site"] == "A"

    def test_year_is_int_dtype(self, no2_df):
        # What: Ensures 'Year' column allows numerical operations.
        # How: Checks datatype.
        # Expected: Datatype is int.
        result = exceedance_summary(no2_df)
        assert result["Year"].dtype in [int, np.int64, np.int32]

    def test_year_str_matches_year(self, no2_df):
        # What: Checks string representation of year for text filtering.
        # How: Inspects 'Year_str'.
        # Expected: Returns '2024' as string.
        result = exceedance_summary(no2_df)
        assert result.iloc[0]["Year_str"] == "2024"

    def test_exceeds_values_valid(self, no2_df):
        # What: Verifies strict text categorization for status labels.
        # How: Inspects 'uk_exceeds' and 'who_exceeds'.
        # Expected: Values are exactly 'Above' or 'Within'.
        result = exceedance_summary(no2_df)
        assert result.iloc[0]["uk_exceeds"] in ("Above", "Within")
        assert result.iloc[0]["who_exceeds"] in ("Above", "Within")

    def test_no2_high_values_marked_above(self):
        # What: Tests threshold trigger for non-compliant year.
        # How: Passes 30 exceedances (> UK limit 18).
        # Expected: 'uk_exceeds' labeled 'Above'.
        df = pd.DataFrame(
            {
                "site": ["A"] * 30,
                "year": [2024] * 30,
                "pollutants": ["NO2"] * 30,
                "value": [210.0] * 30,
                "date": pd.date_range("2024-01-01", periods=30, freq="h"),
            }
        )
        assert exceedance_summary(df).iloc[0]["uk_exceeds"] == "Above"

    def test_no2_low_values_marked_within(self):
        # What: Tests compliance labeling for clean data.
        # How: Passes 10 low-value readings.
        # Expected: Labels are 'Within'.
        df = pd.DataFrame(
            {
                "site": ["B"] * 10,
                "year": [2024] * 10,
                "pollutants": ["NO2"] * 10,
                "value": [5.0] * 10,
                "date": pd.date_range("2024-01-01", periods=10, freq="h"),
            }
        )
        result = exceedance_summary(df)
        assert result.iloc[0]["uk_exceeds"] == "Within"
        assert result.iloc[0]["who_exceeds"] == "Within"

    def test_two_sites_two_rows(self):
        # What: Verifies group-by logic handles multiple locations.
        # How: Feeds Site A and B data.
        # Expected: Summary table has 2 rows.
        df = pd.DataFrame(
            {
                "site": ["A"] * 5 + ["B"] * 5,
                "year": [2024] * 10,
                "pollutants": ["NO2"] * 10,
                "value": [5.0] * 10,
                "date": list(pd.date_range("2024-01-01", periods=5, freq="h")) * 2,
            }
        )
        assert len(exceedance_summary(df)) == 2

    def test_two_pollutants_two_rows(self):
        # What: Verifies group-by logic handles multiple pollutants.
        # How: Feeds NO2 and PM2.5 for Site A.
        # Expected: Summary table has 2 rows.
        df = pd.DataFrame(
            {
                "site": ["A"] * 8,
                "year": [2024] * 8,
                "pollutants": ["NO2"] * 4 + ["PM2.5"] * 4,
                "value": [5.0] * 8,
                "date": list(pd.date_range("2024-01-01", periods=4, freq="h")) * 2,
            }
        )
        result = exceedance_summary(df)
        assert set(result["pollutant"]) == {"NO2", "PM2.5"}

    def test_nan_rows_excluded_gracefully(self):
        # What: Tests handling of missing/NaN values.
        # How: Passes array with None elements.
        # Expected: Doesn't crash, returns populated DataFrame.
        df = pd.DataFrame(
            {
                "site": ["A"] * 5,
                "year": [2024] * 5,
                "pollutants": ["NO2"] * 5,
                "value": [None, 5.0, None, 10.0, 15.0],
                "date": pd.date_range("2024-01-01", periods=5, freq="h"),
            }
        )
        assert not exceedance_summary(df).empty

    def test_pm25_annual_mean_below_who_limit_within(self):
        # What: Tests WHO PM2.5 annual mean condition.
        # How: 365 days averaging 3.0 (< WHO annual 5).
        # Expected: 'who_exceeds' reads 'Within'.
        df = pd.DataFrame(
            {
                "site": ["A"] * 365,
                "year": [2024] * 365,
                "pollutants": ["PM2.5"] * 365,
                "value": [3.0] * 365,
                "date": pd.date_range("2024-01-01", periods=365, freq="D"),
            }
        )
        assert exceedance_summary(df).iloc[0]["who_exceeds"] == "Within"

    def test_so2_any_daily_exceedance_is_above(self):
        # What: Verifies zero-tolerance SO2 WHO policy.
        # How: 1 day exceeds 40 µg/m³.
        # Expected: 'who_exceeds' is 'Above' (limit is 0 allowed).
        df = pd.DataFrame(
            {
                "site": ["A"] * 3,
                "year": [2024] * 3,
                "pollutants": ["SO2"] * 3,
                "value": [20.0, 50.0, 15.0],
                "date": pd.date_range("2024-01-01", periods=3, freq="D"),
            }
        )
        assert exceedance_summary(df).iloc[0]["who_exceeds"] == "Above"

    def test_so2_no_exceedance_is_within(self):
        # What: Verifies clean SO2 data logic.
        # How: 3 clean readings.
        # Expected: 'who_exceeds' is 'Within'.
        df = pd.DataFrame(
            {
                "site": ["A"] * 3,
                "year": [2024] * 3,
                "pollutants": ["SO2"] * 3,
                "value": [10.0, 20.0, 15.0],
                "date": pd.date_range("2024-01-01", periods=3, freq="D"),
            }
        )
        assert exceedance_summary(df).iloc[0]["who_exceeds"] == "Within"


# ═══════════════════════════════════════════════════════════════
# calculate_completeness
# ═══════════════════════════════════════════════════════════════


class TestCalculateCompleteness:
    def test_all_valid_is_100(self):
        # What: Tests percentage calc for perfect data.
        # How: 4 dates, 4 non-null values.
        # Expected: Returns 100.0.
        df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=4),
                "NO2": [1.0, 2.0, 3.0, 4.0],
            }
        )
        assert calculate_completeness(df, "NO2") == 100.0

    def test_three_of_four_valid_is_75(self):
        # What: Tests percentage for partially missing data.
        # How: 4 dates, 1 None value.
        # Expected: Returns 75.0.
        df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=4),
                "NO2": [1.0, None, 3.0, 4.0],
            }
        )
        assert calculate_completeness(df, "NO2") == 75.0

    def test_all_null_returns_zero(self):
        # What: Tests handling of entirely null datasets.
        # How: All readings are None.
        # Expected: Returns 0.0 (no division by zero error).
        df = pd.DataFrame(
            {"date": pd.date_range("2024-01-01", periods=3), "NO2": [None, None, None]}
        )
        assert calculate_completeness(df, "NO2") == 0.0

    def test_empty_df_returns_zero(self):
        # What: Tests empty DataFrame handling.
        # How: 0 rows.
        # Expected: Returns 0.0.
        assert (
            calculate_completeness(pd.DataFrame(columns=["date", "NO2"]), "NO2") == 0.0
        )

    def test_missing_pollutant_column_returns_zero(self):
        # What: Tests missing pollutant column behavior.
        # How: Passes PM2.5, asks for NO2.
        # Expected: Returns 0.0.
        df = pd.DataFrame(
            {"date": pd.date_range("2024-01-01", periods=3), "PM2.5": [1.0, 2.0, 3.0]}
        )
        assert calculate_completeness(df, "NO2") == 0.0

    def test_result_rounded_to_one_decimal(self):
        # What: Ensures clean decimal rounding.
        # How: Calculates 2/3 completeness.
        # Expected: Result matches round(val, 1).
        df = pd.DataFrame(
            {"date": pd.date_range("2024-01-01", periods=3), "NO2": [1.0, None, 3.0]}
        )
        result = calculate_completeness(df, "NO2")
        assert result == round(result, 1)


# ═══════════════════════════════════════════════════════════════
# calculate_completeness_by_site
# ═══════════════════════════════════════════════════════════════


class TestCalculateCompletenessBySite:
    def test_two_sites_different_completeness(self):
        # What: Verifies grouping across multiple locations.
        # How: Site A 50%, Site B 100%.
        # Expected: Returns dict mapping correct percentages.
        df = pd.DataFrame({"site": ["A", "A", "B", "B"], "NO2": [1.0, None, 2.0, 3.0]})
        result = calculate_completeness_by_site(df, ["A", "B"], "NO2")
        a = next(r for r in result if r["site"] == "A")
        b = next(r for r in result if r["site"] == "B")
        assert a["completeness"] == 50.0
        assert b["completeness"] == 100.0

    def test_status_high_at_or_above_85(self):
        # What: Tests 'high' CSS status class.
        # How: 100% complete data.
        # Expected: maps 'status' to 'high'.
        df = pd.DataFrame({"site": ["A"] * 20, "NO2": [1.0] * 20})
        assert calculate_completeness_by_site(df, ["A"], "NO2")[0]["status"] == "high"

    def test_status_mid_at_75_to_84(self):
        # What: Tests 'mid' CSS status class.
        # How: 75% complete data.
        # Expected: maps 'status' to 'mid'.
        df = pd.DataFrame({"site": ["A"] * 4, "NO2": [1.0, 2.0, 3.0, None]})
        assert calculate_completeness_by_site(df, ["A"], "NO2")[0]["status"] == "mid"

    def test_status_low_below_75(self):
        # What: Tests 'low' CSS status class.
        # How: 25% complete data.
        # Expected: maps 'status' to 'low'.
        df = pd.DataFrame({"site": ["A"] * 4, "NO2": [1.0, None, None, None]})
        assert calculate_completeness_by_site(df, ["A"], "NO2")[0]["status"] == "low"

    def test_unknown_site_excluded(self):
        # What: Ensures unknown requested sites are skipped gracefully.
        # How: Requests 'Z' when only 'A' exists.
        # Expected: Returns empty list.
        df = pd.DataFrame({"site": ["A", "A"], "NO2": [1.0, 2.0]})
        assert calculate_completeness_by_site(df, ["Z"], "NO2") == []

    def test_empty_df_returns_empty_list(self):
        # What: Tests empty dataframe fallback.
        # How: Passes empty DataFrame.
        # Expected: Returns empty list.
        assert calculate_completeness_by_site(pd.DataFrame(), ["A"], "NO2") == []


# ═══════════════════════════════════════════════════════════════
# calculate_summary_stats
# ═══════════════════════════════════════════════════════════════


class TestCalculateSummaryStats:
    @pytest.fixture
    def df(self):
        return pd.DataFrame({"site": ["A", "A", "B"], "value": [10.0, 20.0, 30.0]})

    def test_mean_correct(self, df):
        # What: Tests grouped mathematical means.
        # How: Site A has 10/20, Site B has 30.
        # Expected: A=15.0, B=30.0.
        result = calculate_summary_stats(df)
        assert result.loc[result["Site"] == "A", "Mean"].values[0] == 15.0
        assert result.loc[result["Site"] == "B", "Mean"].values[0] == 30.0

    def test_min_max_correct(self, df):
        # What: Tests min/max functions.
        # How: Inspects Site A from fixture.
        # Expected: Min=10.0, Max=20.0.
        result = calculate_summary_stats(df)
        a = result[result["Site"] == "A"].iloc[0]
        assert a["Min"] == 10.0
        assert a["Max"] == 20.0

    def test_required_columns_present(self, df):
        # What: Checks output structure for UI.
        # How: Inspects columns.
        # Expected: Contains Site, Mean, Median, Min, Max, Std, Observations.
        result = calculate_summary_stats(df)
        for col in ["Site", "Mean", "Median", "Min", "Max", "Std", "Observations"]:
            assert col in result.columns

    def test_observations_is_int_type(self, df):
        # What: Validates count datatype.
        # How: Inspects 'Observations' dtype.
        # Expected: Cast to int.
        result = calculate_summary_stats(df)
        assert result["Observations"].dtype in [int, np.int64, np.int32]

    def test_numeric_columns_rounded_two_dp(self, df):
        # What: Verifies 2 decimal place UI rounding.
        # How: Checks Mean, Median, Min, Max floats.
        # Expected: Values match round(val, 2).
        result = calculate_summary_stats(df)
        for col in ["Mean", "Median", "Min", "Max"]:
            for val in result[col]:
                assert val == round(val, 2)

    def test_empty_df_returns_empty(self):
        # What: Verifies empty input behavior.
        # How: Passes empty DataFrame.
        # Expected: Returns empty DataFrame.
        assert calculate_summary_stats(pd.DataFrame()).empty

    def test_missing_value_column_returns_empty(self):
        # What: Tests schema mismatch safety.
        # How: Has 'concentration' instead of 'value'.
        # Expected: Returns empty DataFrame gracefully.
        df = pd.DataFrame({"site": ["A"], "concentration": [10.0]})
        assert calculate_summary_stats(df).empty


# ═══════════════════════════════════════════════════════════════
# get_status_class
# ═══════════════════════════════════════════════════════════════


class TestGetStatusClass:
    def test_zero_exceedance_is_good(self):
        # What: Tests status threshold logic.
        # How: 0 exceedances, limit 10.
        # Expected: 'good'.
        assert get_status_class(0, 10) == "good"

    def test_50_percent_of_limit_is_warning(self):
        # What: Tests warning boundary logic.
        # How: 5 exceedances, limit 10.
        # Expected: 'warning'.
        assert get_status_class(5, 10) == "warning"

    def test_above_50_percent_is_danger(self):
        # What: Tests danger boundary logic.
        # How: 6 exceedances, limit 10.
        # Expected: 'danger'.
        assert get_status_class(6, 10) == "danger"

    def test_at_limit_is_danger(self):
        # What: Tests at-limit boundary logic.
        # How: 10 exceedances, limit 10.
        # Expected: 'danger'.
        assert get_status_class(10, 10) == "danger"

    def test_none_returns_good(self):
        # What: Tests empty input safety.
        # How: Passes None.
        # Expected: Defaults safely to 'good'.
        assert get_status_class(None, 10) == "good"

    def test_dash_string_returns_good(self):
        # What: Tests placeholder string safety.
        # How: Passes '--'.
        # Expected: Defaults safely to 'good'.
        assert get_status_class("--", 10) == "good"

    def test_completeness_85_plus_is_good(self):
        # What: Tests reverse logic for completeness.
        # How: 90%, limit 10.
        # Expected: 'good'.
        assert get_status_class(90, 10, is_exceedance=False) == "good"

    def test_completeness_exactly_85_is_good(self):
        # What: Tests reverse logic boundary condition.
        # How: exactly 85%.
        # Expected: 'good'.
        assert get_status_class(85, 10, is_exceedance=False) == "good"

    def test_completeness_75_to_84_is_warning(self):
        # What: Tests reverse logic warning tier.
        # How: 80%.
        # Expected: 'warning'.
        assert get_status_class(80, 10, is_exceedance=False) == "warning"

    def test_completeness_exactly_75_is_warning(self):
        # What: Tests reverse logic exact boundary.
        # How: exactly 75%.
        # Expected: 'warning'.
        assert get_status_class(75, 10, is_exceedance=False) == "warning"

    def test_completeness_below_75_is_danger(self):
        # What: Tests reverse logic danger tier.
        # How: 60%.
        # Expected: 'danger'.
        assert get_status_class(60, 10, is_exceedance=False) == "danger"


# ═══════════════════════════════════════════════════════════════
# format_date_range  — now includes day number (%d %b %Y format)
# ═══════════════════════════════════════════════════════════════


class TestFormatDateRange:
    def test_same_year_contains_month_and_year(self):
        # What: Tests UI string generation for same-year dates.
        # How: Jan 1 2024 to Mar 1 2024.
        # Expected: Retains months, displays '2024' only once.
        result = format_date_range("2024-01-01", "2024-03-01")
        assert "Jan" in result
        assert "Mar" in result
        assert result.count("2024") == 1

    def test_same_year_includes_day_numbers(self):
        # What: Tests inclusion of day numbers in UI string.
        # How: Mid-month dates (15, 30).
        # Expected: Both days are present.
        result = format_date_range("2024-06-15", "2024-06-30")
        assert "15" in result
        assert "30" in result

    def test_cross_year_shows_both_years(self):
        # What: Tests UI string for cross-year dates.
        # How: Nov 2023 to Mar 2024.
        # Expected: Both years appear in output.
        result = format_date_range("2023-11-01", "2024-03-01")
        assert "2023" in result
        assert "2024" in result

    def test_none_start_returns_placeholder(self):
        # What: Tests missing start date.
        # How: Passes None, valid end date.
        # Expected: Returns '--'.
        assert format_date_range(None, "2024-03-01") == "--"

    def test_none_end_returns_placeholder(self):
        # What: Tests missing end date.
        # How: Passes valid start date, None.
        # Expected: Returns '--'.
        assert format_date_range("2024-01-01", None) == "--"

    def test_both_none_returns_placeholder(self):
        # What: Tests missing both dates.
        # How: Passes None, None.
        # Expected: Returns '--'.
        assert format_date_range(None, None) == "--"

    def test_empty_strings_return_placeholder(self):
        # What: Tests empty string fallback.
        # How: Passes "", "".
        # Expected: Returns '--'.
        assert format_date_range("", "") == "--"


# ═══════════════════════════════════════════════════════════════
# hex_to_rgba
# ═══════════════════════════════════════════════════════════════


class TestHexToRgba:
    def test_red_half_alpha(self):
        # What: Tests standard conversion.
        # How: '#ff0000' with 0.5 alpha.
        # Expected: Returns 'rgba(255,0,0,0.5)'.
        assert hex_to_rgba("#ff0000", 0.5) == "rgba(255,0,0,0.5)"

    def test_black_default_alpha(self):
        # What: Tests default alpha handling.
        # How: '#000000' with no alpha.
        # Expected: Applies default '0.12'.
        assert hex_to_rgba("#000000") == "rgba(0,0,0,0.12)"

    def test_white_full_alpha(self):
        # What: Tests 100% opacity handling.
        # How: '#ffffff' with 1.0 alpha.
        # Expected: 'rgba(255,255,255,1.0)'.
        assert hex_to_rgba("#ffffff", 1.0) == "rgba(255,255,255,1.0)"

    def test_arbitrary_colour(self):
        # What: Tests arbitrary hex math.
        # How: '#1a2b3c'.
        # Expected: 'rgba(26,43,60,0.5)'.
        assert hex_to_rgba("#1a2b3c", 0.5) == "rgba(26,43,60,0.5)"

    def test_default_alpha_is_012(self):
        # What: Confirms default 0.12 magic number behavior.
        # How: No alpha argument passed.
        # Expected: String contains '0.12'.
        assert "0.12" in hex_to_rgba("#ff0000")


# ═══════════════════════════════════════════════════════════════
# aqi_index  (NEW)
# ═══════════════════════════════════════════════════════════════


class TestAqiIndex:
    def test_nan_input_returns_nan(self):
        # What: Tests handling of invalid numeric inputs.
        # How: Passes np.nan.
        # Expected: Bypasses math and returns np.nan.
        assert np.isnan(aqi_index(np.nan, "NO2"))

    def test_value_at_band_1_limit_returns_1(self):
        # What: Tests lower boundary of AQI mapping.
        # How: NO2 band 1 limit is 67.
        # Expected: Returns index 1.
        assert aqi_index(67, "NO2") == 1

    def test_value_just_below_band_1_returns_1(self):
        # What: Tests standard low-value categorization.
        # How: Passes 10 for NO2.
        # Expected: Returns index 1.
        assert aqi_index(10, "NO2") == 1

    def test_value_just_above_band_1_returns_2(self):
        # What: Tests transitioning to severity band 2.
        # How: NO2 band 1 limit is 67; passes 68.
        # Expected: Bumps index to 2.
        assert aqi_index(68, "NO2") == 2

    def test_very_high_value_returns_10(self):
        # What: Tests severity ceiling enforcement.
        # How: Passes 10000 NO2.
        # Expected: Caps index at 10.
        assert aqi_index(10000, "NO2") == 10

    def test_pm25_band_1(self):
        # What: Tests PM2.5 AQI mapping.
        # How: Passes 5 (limit 11).
        # Expected: Returns 1.
        assert aqi_index(5, "PM2.5") == 1

    def test_pm10_mid_band(self):
        # What: Tests PM10 mid-range mapping.
        # How: Passes 40 (Band 3 limit 50).
        # Expected: Returns 3.
        assert aqi_index(40, "PM10") == 3

    def test_o3_band_2(self):
        # What: Tests O3 specific mapping.
        # How: Passes 50 (Band 2 limit 66).
        # Expected: Returns 2.
        assert aqi_index(50, "O3") == 2

    def test_so2_band_1(self):
        # What: Tests SO2 specific mapping.
        # How: Passes 50 (Band 1 limit 88).
        # Expected: Returns 1.
        assert aqi_index(50, "SO2") == 1

    def test_zero_value_returns_1(self):
        # What: Edge case for 0 pollution.
        # How: Passes 0.
        # Expected: Returns minimum index, 1.
        assert aqi_index(0, "NO2") == 1


# ═══════════════════════════════════════════════════════════════
# aqi_category  (NEW)
# ═══════════════════════════════════════════════════════════════


class TestAqiCategory:
    def test_nan_returns_nan(self):
        # What: Safety check for empty inputs.
        # How: Passes np.nan.
        # Expected: Returns pd.isna equivalent.
        assert pd.isna(aqi_category(np.nan))

    def test_band_1_is_low(self):
        # What: Tests mapping for lowest severity category.
        # How: Passes index 1.
        # Expected: Returns 'Low'.
        assert aqi_category(1) == "Low"

    def test_band_3_is_low(self):
        # What: Tests upper boundary of 'Low'.
        # How: Passes index 3.
        # Expected: Returns 'Low'.
        assert aqi_category(3) == "Low"

    def test_band_4_is_moderate(self):
        # What: Tests transition to 'Moderate'.
        # How: Passes index 4.
        # Expected: Returns 'Moderate'.
        assert aqi_category(4) == "Moderate"

    def test_band_6_is_moderate(self):
        # What: Tests upper boundary of 'Moderate'.
        # How: Passes index 6.
        # Expected: Returns 'Moderate'.
        assert aqi_category(6) == "Moderate"

    def test_band_7_is_high(self):
        # What: Tests transition to 'High'.
        # How: Passes index 7.
        # Expected: Returns 'High'.
        assert aqi_category(7) == "High"

    def test_band_9_is_high(self):
        # What: Tests upper boundary of 'High'.
        # How: Passes index 9.
        # Expected: Returns 'High'.
        assert aqi_category(9) == "High"

    def test_band_10_is_very_high(self):
        # What: Tests highest severity mapping.
        # How: Passes index 10.
        # Expected: Returns 'Very High'.
        assert aqi_category(10) == "Very High"

    def test_boundary_3_to_4(self):
        # What: Checks strict boundary between Low/Moderate.
        # How: Tests 3 and 4.
        # Expected: 3 is Low, 4 is Moderate.
        assert aqi_category(3) == "Low"
        assert aqi_category(4) == "Moderate"

    def test_boundary_6_to_7(self):
        # What: Checks strict boundary between Moderate/High.
        # How: Tests 6 and 7.
        # Expected: 6 is Moderate, 7 is High.
        assert aqi_category(6) == "Moderate"
        assert aqi_category(7) == "High"

    def test_boundary_9_to_10(self):
        # What: Checks strict boundary between High/Very High.
        # How: Tests 9 and 10.
        # Expected: 9 is High, 10 is Very High.
        assert aqi_category(9) == "High"
        assert aqi_category(10) == "Very High"


# ═══════════════════════════════════════════════════════════════
# degrees_to_direction  (NEW)
# ═══════════════════════════════════════════════════════════════


class TestDegreesToDirection:
    def test_nan_returns_nan(self):
        # What: Tests NaN behavior for wind direction mapping.
        # How: Passes np.nan.
        # Expected: Returns pd.isna equivalent.
        assert pd.isna(degrees_to_direction(np.nan))

    def test_north_at_zero(self):
        # What: Tests absolute North mapping.
        # How: Passes 0.
        # Expected: Returns 'N'.
        assert degrees_to_direction(0) == "N"

    def test_north_at_360(self):
        # What: Tests wraparound North boundary.
        # How: Passes 360.
        # Expected: Returns 'N'.
        assert degrees_to_direction(360) == "N"

    def test_north_upper_boundary(self):
        # What: Tests upper degree boundary for North.
        # How: Passes 337.5.
        # Expected: Returns 'N'.
        assert degrees_to_direction(337.5) == "N"

    def test_north_lower_boundary(self):
        # What: Tests lower boundary threshold for North.
        # How: Passes 22.4 (< 22.5).
        # Expected: Returns 'N'.
        assert degrees_to_direction(22.4) == "N"

    def test_ne_starts_at_22_5(self):
        # What: Tests transition to North-East.
        # How: Passes 22.5.
        # Expected: Returns 'NE'.
        assert degrees_to_direction(22.5) == "NE"

    def test_ne_ends_at_67_4(self):
        # What: Tests upper boundary for North-East.
        # How: Passes 67.4.
        # Expected: Returns 'NE'.
        assert degrees_to_direction(67.4) == "NE"

    def test_east_at_90(self):
        # What: Tests absolute East mapping.
        # How: Passes 90.
        # Expected: Returns 'E'.
        assert degrees_to_direction(90) == "E"

    def test_se_at_135(self):
        # What: Tests absolute South-East mapping.
        # How: Passes 135.
        # Expected: Returns 'SE'.
        assert degrees_to_direction(135) == "SE"

    def test_south_at_180(self):
        # What: Tests absolute South mapping.
        # How: Passes 180.
        # Expected: Returns 'S'.
        assert degrees_to_direction(180) == "S"

    def test_sw_at_225(self):
        # What: Tests absolute South-West mapping.
        # How: Passes 225.
        # Expected: Returns 'SW'.
        assert degrees_to_direction(225) == "SW"

    def test_west_at_270(self):
        # What: Tests absolute West mapping.
        # How: Passes 270.
        # Expected: Returns 'W'.
        assert degrees_to_direction(270) == "W"

    def test_nw_at_315(self):
        # What: Tests absolute North-West mapping.
        # How: Passes 315.
        # Expected: Returns 'NW'.
        assert degrees_to_direction(315) == "NW"

    def test_nw_upper_boundary(self):
        # What: Tests upper boundary for North-West.
        # How: Passes 337.4.
        # Expected: Returns 'NW'.
        assert degrees_to_direction(337.4) == "NW"

    def test_nw_lower_boundary(self):
        # What: Tests lower boundary for North-West.
        # How: Passes 292.5.
        # Expected: Returns 'NW'.
        assert degrees_to_direction(292.5) == "NW"
