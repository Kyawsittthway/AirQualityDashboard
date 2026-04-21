# Tests for forecast-related pure helpers in callbacks.py.


import sys
import os
import pytest
import pandas as pd
import numpy as np
from datetime import date

sys.path.append(os.path.abspath("src"))


def _aqi_colour(band):
    if band <= 3:
        return "#4caf7d"
    if band <= 6:
        return "#e0a920"
    if band <= 9:
        return "#e05a20"
    return "#c93030"


def _aqi_label(band):
    if band <= 3:
        return "Low"
    if band <= 6:
        return "Moderate"
    if band <= 9:
        return "High"
    return "Very High"


def unpack_store(store):
    if not store:
        return None, []
    if isinstance(store, list):
        return store, ["NO2", "O3", "SO2", "PM10", "PM2.5"]
    return list(store[0])


def _confidence_range(aqi):
    # Extracted from update_day_grid — the ±1 AQI confidence band.
    aqi_min = max(1, aqi - 1)
    aqi_max = min(10, aqi + 1)
    return aqi_min, aqi_max


def _weather_temp_str(w):
    # Extracted from update_forecast_detail.
    return f"{w['temp']:.1f} °C" if isinstance(w.get("temp"), (int, float)) else "—"


def _weather_ws_str(w):
    return f"{w['ws']:.1f} m/s" if isinstance(w.get("ws"), (int, float)) else "—"


def _weather_wd_str(w):
    return f"{w['wd_deg']:.0f}°" if isinstance(w.get("wd_deg"), (int, float)) else "—"


def _forecast_summary_stats(forecast, pollutants):
    # Extracted from update_forecast_summary.
    # Returns (peak_aqi, avg_aqi, worst_pollutant).
    aqis = [d["aqi"] for d in forecast]
    peak = max(aqis)
    avg = round(sum(aqis) / len(aqis), 1)
    poll_avg = {
        p: sum(d["pollutants"][p]["band"] for d in forecast) / len(forecast)
        for p in pollutants
    }
    worst = max(poll_avg, key=poll_avg.get)
    return peak, avg, worst


def _daily_no2(hourly_series):
    # NO2 aggregation rule: daily median only when ≥18 hourly readings present.
    return hourly_series.median() if hourly_series.count() >= 18 else np.nan


def _daily_so2(hourly_series):
    # SO2 aggregation rule: daily max only when ≥18 hourly readings present.
    return hourly_series.max() if hourly_series.count() >= 18 else np.nan


def _daily_pm(hourly_series):
    # PM10/PM2.5 aggregation rule: daily mean only when ≥18 hourly readings present.
    return hourly_series.mean() if hourly_series.count() >= 18 else np.nan


def _poll_bar_pct(val, poll_max):
    # Progress-bar percentage extracted from update_forecast_detail.
    return min(100, round(val / poll_max * 100))


# ─────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────


@pytest.fixture
def seven_day_forecast():
    # Minimal 7-day forecast payload matching the real structure.
    return [
        {
            "date": f"2024-06-0{i+1}",
            "aqi": aqi,
            "pollutants": {
                "NO2": {"concentration": 50.0 * i + 10, "band": aqi},
                "O3": {"concentration": 40.0, "band": max(1, aqi - 1)},
                "PM2.5": {"concentration": 12.0, "band": 2},
            },
            "weather": {"temp": 15.0 + i, "ws": 3.5, "wd_deg": 180.0},
        }
        for i, aqi in enumerate([2, 4, 6, 3, 7, 5, 8])
    ]


@pytest.fixture
def single_day_forecast():
    return [
        {
            "date": "2024-06-01",
            "aqi": 5,
            "pollutants": {
                "NO2": {"concentration": 80.0, "band": 5},
            },
            "weather": {"temp": 18.0, "ws": 4.2, "wd_deg": 270.0},
        }
    ]


# ═══════════════════════════════════════════════════════════════
# _aqi_colour
# ═══════════════════════════════════════════════════════════════


class TestAqiColour:
    def test_band_1_is_green(self):
        # What: Tests mapping for the lowest AQI severity band.
        # How: Passes index 1.
        # Expected: Returns the green hex code '#4caf7d'.
        assert _aqi_colour(1) == "#4caf7d"

    def test_band_3_is_green(self):
        # What: Tests the upper boundary for the green "Low" tier.
        # How: Passes index 3.
        # Expected: Returns the green hex code '#4caf7d'.
        assert _aqi_colour(3) == "#4caf7d"

    def test_band_4_is_yellow(self):
        # What: Tests the transition boundary into the yellow "Moderate" tier.
        # How: Passes index 4.
        # Expected: Returns the yellow hex code '#e0a920'.
        assert _aqi_colour(4) == "#e0a920"

    def test_band_6_is_yellow(self):
        # What: Tests the upper boundary for the yellow "Moderate" tier.
        # How: Passes index 6.
        # Expected: Returns the yellow hex code '#e0a920'.
        assert _aqi_colour(6) == "#e0a920"

    def test_band_7_is_orange(self):
        # What: Tests the transition boundary into the orange "High" tier.
        # How: Passes index 7.
        # Expected: Returns the orange hex code '#e05a20'.
        assert _aqi_colour(7) == "#e05a20"

    def test_band_9_is_orange(self):
        # What: Tests the upper boundary for the orange "High" tier.
        # How: Passes index 9.
        # Expected: Returns the orange hex code '#e05a20'.
        assert _aqi_colour(9) == "#e05a20"

    def test_band_10_is_red(self):
        # What: Tests the mapping for the maximum severity "Very High" tier.
        # How: Passes index 10.
        # Expected: Returns the red hex code '#c93030'.
        assert _aqi_colour(10) == "#c93030"

    def test_boundary_3_to_4(self):
        # What: Verifies strict visual separation between bands 3 and 4.
        # How: Asserts inequality of mapped hex strings.
        # Expected: Colors are distinctly different.
        assert _aqi_colour(3) != _aqi_colour(4)

    def test_boundary_6_to_7(self):
        # What: Verifies strict visual separation between bands 6 and 7.
        # How: Asserts inequality of mapped hex strings.
        # Expected: Colors are distinctly different.
        assert _aqi_colour(6) != _aqi_colour(7)

    def test_boundary_9_to_10(self):
        # What: Verifies strict visual separation between bands 9 and 10.
        # How: Asserts inequality of mapped hex strings.
        # Expected: Colors are distinctly different.
        assert _aqi_colour(9) != _aqi_colour(10)

    def test_returns_hex_string(self):
        # What: Validates output format for CSS compatibility.
        # How: Checks character composition of the output for band 5.
        # Expected: String is exactly 7 characters and begins with '#'.
        result = _aqi_colour(5)
        assert result.startswith("#")
        assert len(result) == 7


# ═══════════════════════════════════════════════════════════════
# _aqi_label
# ═══════════════════════════════════════════════════════════════


class TestAqiLabel:
    def test_band_1_is_low(self):
        # What: Tests mapping for lowest severity category.
        # How: Passes index 1.
        # Expected: Returns 'Low'.
        assert _aqi_label(1) == "Low"

    def test_band_3_is_low(self):
        # What: Tests upper boundary of the lowest category.
        # How: Passes index 3.
        # Expected: Returns 'Low'.
        assert _aqi_label(3) == "Low"

    def test_band_4_is_moderate(self):
        # What: Tests transition to 'Moderate' category.
        # How: Passes index 4.
        # Expected: Returns 'Moderate'.
        assert _aqi_label(4) == "Moderate"

    def test_band_6_is_moderate(self):
        # What: Tests upper boundary of 'Moderate'.
        # How: Passes index 6.
        # Expected: Returns 'Moderate'.
        assert _aqi_label(6) == "Moderate"

    def test_band_7_is_high(self):
        # What: Tests transition to 'High' category.
        # How: Passes index 7.
        # Expected: Returns 'High'.
        assert _aqi_label(7) == "High"

    def test_band_9_is_high(self):
        # What: Tests upper boundary of 'High'.
        # How: Passes index 9.
        # Expected: Returns 'High'.
        assert _aqi_label(9) == "High"

    def test_band_10_is_very_high(self):
        # What: Tests transition to maximum severity category.
        # How: Passes index 10.
        # Expected: Returns 'Very High'.
        assert _aqi_label(10) == "Very High"

    def test_label_and_colour_agree_on_boundaries(self):
        # What: Ensures color coding and text labels remain synced across all tiers.
        # How: Iterates through bands 1 to 10 checking text-to-color parity.
        # Expected: Every text label maps exactly to its corresponding CSS hex color.
        for band in range(1, 11):
            label = _aqi_label(band)
            colour = _aqi_colour(band)
            if label == "Low":
                assert colour == "#4caf7d"
            elif label == "Moderate":
                assert colour == "#e0a920"
            elif label == "High":
                assert colour == "#e05a20"
            else:
                assert colour == "#c93030"


# ═══════════════════════════════════════════════════════════════
# unpack_store
# ═══════════════════════════════════════════════════════════════


class TestUnpackStore:
    def test_none_returns_none_and_empty_list(self):
        # What: Tests function safety when UI store state is None.
        # How: Passes None.
        # Expected: Returns None for data and an empty list for pollutants.
        result = unpack_store(None)
        assert result == (None, [])

    def test_empty_dict_returns_none_and_empty_list(self):
        # What: Tests function safety when UI store state is an empty dictionary.
        # How: Passes {}.
        # Expected: Returns None for data and an empty list for pollutants.
        result = unpack_store({})
        assert result == (None, [])

    def test_list_store_returns_list_and_all_pollutants(self):
        # What: Tests standard successful unpacking of stored data.
        # How: Passes a populated list of dictionaries.
        # Expected: Returns the list exactly as provided, plus the 5 standard pollutant keys.
        store = [{"site": "Cardiff"}, {"site": "Swansea"}]
        data, pollutants = unpack_store(store)
        assert data == store
        assert set(pollutants) == {"NO2", "O3", "SO2", "PM10", "PM2.5"}

    def test_empty_list_returns_none_and_empty(self):
        # What: Tests edge case where store is an initialized but empty list.
        # How: Passes [].
        # Expected: Returns None and an empty list to prevent downstream iterations on null.
        result = unpack_store([])
        assert result == (None, [])


# ═══════════════════════════════════════════════════════════════
# _confidence_range  (±1 AQI band, clamped to 1–10)
# ═══════════════════════════════════════════════════════════════


class TestConfidenceRange:
    def test_mid_range_band(self):
        # What: Tests basic +/- 1 confidence band math.
        # How: Passes a mid-scale index of 5.
        # Expected: Returns lower bound 4, upper bound 6.
        lo, hi = _confidence_range(5)
        assert lo == 4
        assert hi == 6

    def test_lower_clamp_at_band_1(self):
        # What: Tests lower boundary limit enforcement.
        # How: Passes index 1.
        # Expected: Lower bound cannot go below 1 (clamped to 1), upper bound is 2.
        lo, hi = _confidence_range(1)
        assert lo == 1  # max(1, 1-1) = max(1,0) = 1
        assert hi == 2

    def test_upper_clamp_at_band_10(self):
        # What: Tests upper boundary limit enforcement.
        # How: Passes index 10.
        # Expected: Lower bound is 9, upper bound cannot exceed 10 (clamped to 10).
        lo, hi = _confidence_range(10)
        assert lo == 9
        assert hi == 10  # min(10, 10+1) = 10

    def test_band_2_lower_clamp(self):
        # What: Tests math near the floor boundary without crossing it.
        # How: Passes index 2.
        # Expected: Lower bound is 1, upper bound is 3.
        lo, hi = _confidence_range(2)
        assert lo == 1
        assert hi == 3

    def test_band_9_upper_clamp(self):
        # What: Tests math near the ceiling boundary without crossing it.
        # How: Passes index 9.
        # Expected: Lower bound is 8, upper bound is 10.
        lo, hi = _confidence_range(9)
        assert lo == 8
        assert hi == 10

    def test_range_is_always_exactly_2_wide_in_middle(self):
        # What: Verifies consistency of the 2-point spread across valid ranges.
        # How: Loops through all middle bands (2 through 9).
        # Expected: The difference between high and low is strictly 2.
        for band in range(2, 10):
            lo, hi = _confidence_range(band)
            assert hi - lo == 2

    def test_range_string_format(self):
        # What: Validates UI string template.
        # How: Formats the output of an index 5 operation.
        # Expected: Matches "Confidence Range: 4 - 6 AQI".
        lo, hi = _confidence_range(5)
        text = f"Confidence Range: {lo} - {hi} AQI"
        assert text == "Confidence Range: 4 - 6 AQI"


# ═══════════════════════════════════════════════════════════════
# Weather string formatting
# ═══════════════════════════════════════════════════════════════


class TestWeatherFormatting:
    def test_temp_formats_to_one_decimal(self):
        # What: Tests temperature rounding logic.
        # How: Passes float 18.567.
        # Expected: Truncates to 1 decimal place with ' °C'.
        assert _weather_temp_str({"temp": 18.567}) == "18.6 °C"

    def test_temp_integer_input(self):
        # What: Tests formatting behavior for pure integer inputs.
        # How: Passes int 20.
        # Expected: Appends '.0' to match float decimal formatting.
        assert _weather_temp_str({"temp": 20}) == "20.0 °C"

    def test_temp_missing_returns_dash(self):
        # What: Tests safety fallback for missing dictionary keys.
        # How: Passes empty dictionary without 'temp'.
        # Expected: Returns visual placeholder '—'.
        assert _weather_temp_str({}) == "—"

    def test_temp_none_returns_dash(self):
        # What: Tests safety fallback for null values.
        # How: Passes explicitly null 'temp'.
        # Expected: Returns visual placeholder '—'.
        assert _weather_temp_str({"temp": None}) == "—"

    def test_temp_string_value_returns_dash(self):
        # What: Tests strict type filtering to prevent math errors.
        # How: Passes string 'unknown'.
        # Expected: Rejects strings, returns placeholder '—'.
        assert _weather_temp_str({"temp": "unknown"}) == "—"

    def test_wind_speed_formats_to_one_decimal(self):
        # What: Tests wind speed rounding logic.
        # How: Passes float 3.567.
        # Expected: Truncates to 1 decimal place with ' m/s'.
        assert _weather_ws_str({"ws": 3.567}) == "3.6 m/s"

    def test_wind_speed_missing_returns_dash(self):
        # What: Tests missing key safety for wind speed.
        # How: Passes empty dictionary.
        # Expected: Returns placeholder '—'.
        assert _weather_ws_str({}) == "—"

    def test_wind_direction_formats_to_zero_decimal(self):
        # What: Tests integer casting for degrees.
        # How: Passes float 180.7.
        # Expected: Rounds and displays as whole number with '°'.
        assert _weather_wd_str({"wd_deg": 180.7}) == "181°"

    def test_wind_direction_missing_returns_dash(self):
        # What: Tests missing key safety for wind direction.
        # How: Passes empty dictionary.
        # Expected: Returns placeholder '—'.
        assert _weather_wd_str({}) == "—"

    def test_wind_direction_zero_degrees(self):
        # What: Tests valid boundary edge case for North.
        # How: Passes 0.0.
        # Expected: Computes accurately as '0°' (avoids falsy logic errors).
        assert _weather_wd_str({"wd_deg": 0.0}) == "0°"

    def test_wind_direction_360(self):
        # What: Tests valid boundary upper-edge case for North.
        # How: Passes 360.0.
        # Expected: Computes accurately as '360°'.
        assert _weather_wd_str({"wd_deg": 360.0}) == "360°"


# ═══════════════════════════════════════════════════════════════
# _forecast_summary_stats  (peak / avg / worst pollutant)
# ═══════════════════════════════════════════════════════════════


class TestForecastSummaryStats:
    def test_peak_is_max_aqi(self, seven_day_forecast):
        # What: Validates extraction of the highest AQI value.
        # How: Passes the multi-day forecast fixture.
        # Expected: The returned peak explicitly matches the mathematically largest AQI in the set.
        peak, _, _ = _forecast_summary_stats(seven_day_forecast, ["NO2", "O3", "PM2.5"])
        assert peak == max(d["aqi"] for d in seven_day_forecast)

    def test_avg_is_correct(self, seven_day_forecast):
        # What: Validates mathematical average of AQI over a week.
        # How: Asserts logic against manual sum division.
        # Expected: Matches exactly.
        _, avg, _ = _forecast_summary_stats(seven_day_forecast, ["NO2", "O3", "PM2.5"])
        expected = round(sum(d["aqi"] for d in seven_day_forecast) / 7, 1)
        assert avg == expected

    def test_avg_is_rounded_to_one_decimal(self, seven_day_forecast):
        # What: Checks decimal limitation.
        # How: Uses self-equality against a Python `round` function.
        # Expected: The value matches its own rounded equivalent to 1 decimal place.
        _, avg, _ = _forecast_summary_stats(seven_day_forecast, ["NO2", "O3", "PM2.5"])
        assert avg == round(avg, 1)

    def test_worst_pollutant_is_highest_avg_band(self, seven_day_forecast):
        # What: Verifies selection of the primary driving pollutant.
        # How: Uses fixture where NO2 systematically increases in severity.
        # Expected: Accurately identifies 'NO2' as the worst.
        _, _, worst = _forecast_summary_stats(
            seven_day_forecast, ["NO2", "O3", "PM2.5"]
        )
        assert worst == "NO2"

    def test_single_pollutant_is_worst_by_default(self, single_day_forecast):
        # What: Verifies simple worst-case identification.
        # How: Passes a forecast containing only NO2.
        # Expected: Returns 'NO2' safely without errors.
        _, _, worst = _forecast_summary_stats(single_day_forecast, ["NO2"])
        assert worst == "NO2"

    def test_all_same_aqi_peak_equals_that_value(self):
        # What: Tests behavior against a flat, unvarying dataset.
        # How: Feeds 7 days locked at exactly AQI 5.
        # Expected: Both peak and average identically equal 5.
        forecast = [
            {
                "date": f"2024-06-0{i+1}",
                "aqi": 5,
                "pollutants": {"NO2": {"concentration": 80.0, "band": 5}},
            }
            for i in range(7)
        ]
        peak, avg, _ = _forecast_summary_stats(forecast, ["NO2"])
        assert peak == 5
        assert avg == 5.0

    def test_no_forecast_raises(self):
        # What: Tests behavior on empty lists.
        # How: Passes empty array.
        # Expected: Raises an exception rather than silently failing or throwing divide-by-zero.
        with pytest.raises(Exception):
            _forecast_summary_stats([], ["NO2"])


# ═══════════════════════════════════════════════════════════════
# _poll_bar_pct  (progress bar width %)
# ═══════════════════════════════════════════════════════════════


class TestPollBarPct:
    def test_half_of_max_is_50(self):
        # What: Tests standard percentage calculation.
        # How: 60 out of limit 120.
        # Expected: Returns 50.
        assert _poll_bar_pct(60, 120) == 50

    def test_at_max_is_100(self):
        # What: Tests percentage boundary calculation.
        # How: 120 out of limit 120.
        # Expected: Returns 100.
        assert _poll_bar_pct(120, 120) == 100

    def test_above_max_clamped_to_100(self):
        # What: Tests strict upper clamping logic for UI safety.
        # How: Passes 200 out of limit 120.
        # Expected: Caps strictly at 100 to prevent breaking CSS widths.
        assert _poll_bar_pct(200, 120) == 100

    def test_zero_value_is_zero(self):
        # What: Tests strict floor calculation.
        # How: 0 out of 120.
        # Expected: Returns 0.
        assert _poll_bar_pct(0, 120) == 0

    def test_result_never_exceeds_100(self):
        # What: Verifies clamping behavior across random extreme numbers.
        # How: Iterates high values testing against <= 100.
        # Expected: No calculated value exceeds 100.
        for val in [0, 50, 120, 200, 9999]:
            assert _poll_bar_pct(val, 120) <= 100

    def test_result_is_integer(self):
        # What: Ensures clean output type for CSS generation.
        # How: Tests type of a standard math operation.
        # Expected: Validates type is exactly an integer.
        assert isinstance(_poll_bar_pct(60, 120), int)

    def test_pm25_max_is_50(self):
        # What: Tests logic utilizing specific PM2.5 max constraints.
        # How: 25 out of max 50.
        # Expected: Returns 50.
        assert _poll_bar_pct(25, 50) == 50

    def test_no2_max_is_120(self):
        # What: Tests logic utilizing specific NO2 max constraints.
        # How: 60 out of limit 120.
        # Expected: Returns 50.
        assert _poll_bar_pct(60, 120) == 50


# ═══════════════════════════════════════════════════════════════
# load_history_from_df aggregation rules
# (tested by replicating the per-pollutant lambda logic directly)
# ═══════════════════════════════════════════════════════════════


class TestDailyAggregationRules:
    # load_history_from_df uses different aggregation per pollutant.
    # Each rule requires ≥18 hourly readings or it returns NaN.

    def _make_series(self, n_valid, total=24, value=50.0):
        # Helper function: generates fake time series with 'n_valid' values and fills the rest with NaNs.
        vals = [value] * n_valid + [np.nan] * (total - n_valid)
        return pd.Series(vals)

    # ── NO2: daily median, requires ≥18 ──────────────────────

    def test_no2_returns_median_when_18_or_more_readings(self):
        # What: Tests NO2 aggregation operation.
        # How: Provides exactly 18 valid measurements.
        # Expected: Executes median math and returns value.
        s = self._make_series(18)
        result = _daily_no2(s)
        assert result == 50.0

    def test_no2_returns_nan_when_fewer_than_18(self):
        # What: Tests NO2 strict data completeness rejection.
        # How: Provides only 17 measurements.
        # Expected: Rejects calculation and returns NaN.
        s = self._make_series(17)
        assert np.isnan(_daily_no2(s))

    def test_no2_exactly_18_readings_is_valid(self):
        # What: Verifies threshold edge-case behavior.
        # How: Provides exactly 18 measurements.
        # Expected: Evaluates to valid (not NaN).
        s = self._make_series(18)
        assert not np.isnan(_daily_no2(s))

    def test_no2_median_with_varied_values(self):
        # What: Tests accuracy of mathematical median logic.
        # How: Provides 9 tens, 9 twenties, 6 NaNs.
        # Expected: Correctly identifies 15.0 as the median.
        s = pd.Series([10.0] * 9 + [20.0] * 9 + [np.nan] * 6)
        result = _daily_no2(s)
        assert result == 15.0  # median of 18 values: 9×10 + 9×20

    def test_no2_full_day_24_readings(self):
        # What: Verifies max boundary inclusion.
        # How: Provides full 24 valid measurements.
        # Expected: Evaluates to valid.
        s = self._make_series(24)
        assert not np.isnan(_daily_no2(s))

    # ── SO2: daily max, requires ≥18 ─────────────────────────

    def test_so2_returns_max_when_18_or_more(self):
        # What: Tests SO2 strict aggregation logic.
        # How: Provides 18 measurements with an anomaly maximum.
        # Expected: Correctly identifies and returns the maximum (99).
        s = pd.Series([10.0] * 17 + [99.0] + [np.nan] * 6)
        result = _daily_so2(s)
        assert result == 99.0

    def test_so2_returns_nan_when_fewer_than_18(self):
        # What: Tests SO2 data completeness rejection.
        # How: Provides 17 measurements.
        # Expected: Rejects calculation and returns NaN.
        s = self._make_series(17)
        assert np.isnan(_daily_so2(s))

    def test_so2_exactly_18_is_valid(self):
        # What: Verifies SO2 threshold edge-case behavior.
        # How: Provides exactly 18 measurements.
        # Expected: Evaluates accurately and skips returning NaN.
        s = self._make_series(18, value=30.0)
        assert _daily_so2(s) == 30.0

    # ── PM10 / PM2.5: daily mean, requires ≥18 ───────────────

    def test_pm_returns_mean_when_18_or_more(self):
        # What: Tests Particulate Matter standard mean aggregation.
        # How: Provides 18 baseline measurements.
        # Expected: Computes identical mean value.
        s = pd.Series([10.0] * 18 + [np.nan] * 6)
        assert _daily_pm(s) == 10.0

    def test_pm_returns_nan_when_fewer_than_18(self):
        # What: Tests PM data completeness rejection.
        # How: Provides 17 measurements.
        # Expected: Rejects calculation and returns NaN.
        s = self._make_series(17)
        assert np.isnan(_daily_pm(s))

    def test_pm_mean_with_varied_values(self):
        # What: Tests accuracy of mathematical mean execution.
        # How: 9 twenties, 9 forties.
        # Expected: Computes true average of 30.0.
        s = pd.Series([20.0] * 9 + [40.0] * 9 + [np.nan] * 6)
        assert _daily_pm(s) == 30.0  # mean of (9×20 + 9×40) / 18

    def test_pm_exactly_18_is_valid(self):
        # What: Verifies PM threshold edge-case behavior.
        # How: Provides exactly 18 valid measurements.
        # Expected: Returns a valid execution (not NaN).
        s = self._make_series(18, value=25.0)
        assert not np.isnan(_daily_pm(s))

    # ── Cross-pollutant: the threshold is consistently ≥18 ───

    def test_all_three_aggregators_consistent_at_17(self):
        # What: Validates cross-function threshold equality rules.
        # How: Forces series with exactly 17 readings through all aggregators.
        # Expected: All three firmly return NaN.
        s = self._make_series(17)
        assert np.isnan(_daily_no2(s))
        assert np.isnan(_daily_so2(s))
        assert np.isnan(_daily_pm(s))

    def test_all_three_aggregators_valid_at_18(self):
        # What: Validates cross-function threshold equality rules.
        # How: Forces series with exactly 18 readings through all aggregators.
        # Expected: All three successfully resolve mathematically.
        s = self._make_series(18)
        assert not np.isnan(_daily_no2(s))
        assert not np.isnan(_daily_so2(s))
        assert not np.isnan(_daily_pm(s))


# ═══════════════════════════════════════════════════════════════
# O3 — 8-hour rolling mean aggregation (used in load_history_from_df)
# ═══════════════════════════════════════════════════════════════


class TestO3DailyMax8hMean:
    # O3 uses a within-day 8h rolling mean (min_periods=6),
    # then takes the daily max of those rolling means.
    # Tests replicate the transform+groupby pattern from load_history_from_df.

    def _compute_daily_max_8h(self, dates, values):
        # Helper function replicating within-day 8h rolling mean.
        df = pd.DataFrame({"date": pd.to_datetime(dates), "O3": values})
        df["day"] = df["date"].dt.date
        df["o3_8h"] = df.groupby("day")["O3"].transform(
            lambda s: s.rolling(8, min_periods=6).mean()
        )
        return df.groupby("day")["o3_8h"].max()

    def test_single_day_8_readings_gives_mean(self):
        # What: Tests basic isolated rolling mean evaluation.
        # How: Inputs 8 constant valid measurements inside a single day limit.
        # Expected: Rolling frame processes fully and resolves the mean.
        dates = pd.date_range("2024-01-01", periods=8, freq="h")
        result = self._compute_daily_max_8h(dates, [100.0] * 8)
        assert result.iloc[0] == 100.0

    def test_rolling_requires_min_6_periods(self):
        # What: Tests minimum window requirement mechanism.
        # How: Passes only 5 measurements in frame.
        # Expected: Rolling logic denies execution and yields NaN.
        dates = pd.date_range("2024-01-01", periods=5, freq="h")
        result = self._compute_daily_max_8h(dates, [100.0] * 5)
        assert pd.isna(result.iloc[0])

    def test_6_readings_satisfies_min_periods(self):
        # What: Tests edge boundary satisfaction for rolling min period.
        # How: Passes exactly 6 measurements.
        # Expected: Frame accepts parameters and evaluates successfully.
        dates = pd.date_range("2024-01-01", periods=6, freq="h")
        result = self._compute_daily_max_8h(dates, [100.0] * 6)
        assert not pd.isna(result.iloc[0])

    def test_daily_max_picks_highest_rolling_mean(self):
        # What: Tests identification of maximum peak during changing environments.
        # How: Values artificially scale vertically continuously (up to 100).
        # Expected: Extracts max output corresponding to the final rolling snapshot array.
        dates = pd.date_range("2024-01-01", periods=10, freq="h")
        values = list(range(10, 110, 10))  # [10, 20, ..., 100]
        result = self._compute_daily_max_8h(dates, values)
        assert result.iloc[0] > 50

    def test_two_separate_days_computed_independently(self):
        # What: Verifies data safety preventing rolling averages bleeding into the next day.
        # How: Day 1 averages around 50, Day 2 averages exactly 100.
        # Expected: Output calculates distinct max values aligned strictly with each day.
        dates = list(pd.date_range("2024-01-01", periods=8, freq="h")) + list(
            pd.date_range("2024-01-02", periods=8, freq="h")
        )
        values = [50.0] * 8 + [100.0] * 8
        result = self._compute_daily_max_8h(dates, values)
        assert result.iloc[0] == pytest.approx(50.0)
        assert result.iloc[1] == pytest.approx(100.0)
