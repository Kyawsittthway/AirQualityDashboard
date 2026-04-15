from __future__ import annotations
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from xgboost import XGBRegressor

# 1.  SITES

SITE_META: dict[str, dict] = {
    "Aston Hill":                   {"lat": 52.50385,  "lon": -3.034178,  "type": "Rural Background"},
    "Cardiff Centre":               {"lat": 51.48178,  "lon": -3.17625,   "type": "Urban Background"},
    "Cardiff Newport Road":         {"lat": 51.49096,  "lon": -3.152305,  "type": "Urban Traffic"},
    "Chepstow A48":                 {"lat": 51.638094, "lon": -2.678731,  "type": "Urban Traffic"},
    "Cwmbran Crownbridge":          {"lat": 51.653819, "lon": -3.00637,   "type": "Urban Background"},
    "Hafod-yr-ynys Hill Roadside":  {"lat": 51.680493, "lon": -3.133516,  "type": "Urban Traffic"},
    "Narberth":                     {"lat": 51.782616, "lon": -4.69237,   "type": "Rural Background"},
    "Newport":                      {"lat": 51.601203, "lon": -2.977281,  "type": "Urban Background"},
    "Port Talbot Margam":           {"lat": 51.58395,  "lon": -3.770822,  "type": "Urban Industrial"},
    "Swansea Roadside":             {"lat": 51.632696, "lon": -3.947374,  "type": "Urban Traffic"},
    "Wrexham":                      {"lat": 53.042282, "lon": -3.002829,  "type": "Urban Traffic"},
}

# 2.  FEATURE LISTS  (must match training order)

_BASE_WEATHER = ["ws", "temp", "wd_x", "wd_y"]
_BASE_GEO = ["latitude", "longitude"]
_BASE_TIME = ["is_weekend", "month_sin", "month_cos", "year"]
_BASE_DOW = [f"day_of_week_{i}" for i in range(
    1, 7)]          # 0 = Monday is dropped
_BASE_LOC_TYPES = ["location_type_Urban Background",
                   "location_type_Urban Industrial"]

# NO2 model was trained separately with a slightly different feature set
FEATURES: dict[str, list[str]] = {
    "NO2": (
        _BASE_WEATHER + _BASE_GEO + _BASE_TIME +
        ["lag_1", "lag_7", "rolling_3"] +
        _BASE_LOC_TYPES + ["location_type_Urban Traffic"] +
        _BASE_DOW
    ),
    "O3": (
        _BASE_WEATHER + _BASE_GEO + _BASE_TIME +
        ["lag_1", "lag_3", "lag_7", "rolling_3", "rolling_7"] +
        _BASE_LOC_TYPES + _BASE_DOW
    ),
    "SO2": (
        _BASE_WEATHER + _BASE_GEO + _BASE_TIME +
        ["lag_1", "lag_3", "lag_7", "rolling_3", "rolling_7"] +
        _BASE_LOC_TYPES + _BASE_DOW
    ),
    "PM10": (
        _BASE_WEATHER + _BASE_GEO + _BASE_TIME +
        ["lag_1", "lag_3", "lag_7", "rolling_3", "rolling_7"] +
        _BASE_LOC_TYPES + _BASE_DOW
    ),
    "PM2.5": (
        _BASE_WEATHER + _BASE_GEO + _BASE_TIME +
        ["lag_1", "lag_3", "lag_7", "rolling_3", "rolling_7"] +
        _BASE_LOC_TYPES + _BASE_DOW + ["rolling_max_3"]
    ),
}

# PM10 and PM2.5 targets were log-transformed during training
LOG_TRANSFORM_POLLUTANTS = {"PM10", "PM2.5"}

# Model file names
MODEL_FILES: dict[str, str] = {
    "NO2":   "no2_model_14march.json",
    "O3":    "o3_model_14march.json",
    "SO2":   "so2_model_14march.json",
    "PM10":  "pm10_model_14march.json",
    "PM2.5": "pm25_model_14march.json",
}

# 3.  AQI BANDING  (UK DAQI scale 1-10)

BAND_LABELS = {
    1: "Low",  2: "Low",  3: "Low",
    4: "Moderate",  5: "Moderate",  6: "Moderate",
    7: "High", 8: "High", 9: "High",
    10: "Very High",
}


def _band(value: float, thresholds: list[float]) -> int:
    for i, t in enumerate(thresholds, start=1):
        if value <= t:
            return i
    return 10


BAND_THRESHOLDS: dict[str, list[float]] = {
    "NO2":   [67, 134, 200, 267, 334, 400, 467, 534, 600],
    "O3":    [33,  66, 100, 120, 140, 160, 187, 213, 240],
    "SO2":   [88, 177, 266, 354, 443, 532, 710, 887, 1064],
    "PM10":  [16,  33,  50,  58,  66,  75,  83,  91, 100],
    "PM2.5": [11,  23,  35,  41,  47,  53,  58,  64,  70],
}


def pollutant_band(pollutant: str, value: float) -> int:
    return _band(value, BAND_THRESHOLDS[pollutant])


def overall_aqi(bands: dict[str, int]) -> int:
    """Overall AQI = maximum band across available pollutants."""
    return max(bands.values()) if bands else 1

# 4.  HELPER: build one-row feature vector


def _build_row(
    target_date: date,
    site: str,
    weather: dict[str, float],   # {"ws", "temp", "wd_deg"}
    # ordered past values, most recent LAST; length >= 7
    value_buffer: list[float],
    pollutant: str,
) -> pd.DataFrame:
    meta = SITE_META[site]
    loc_type = meta["type"]

    # Temporal features
    dt = pd.Timestamp(target_date)
    dow = dt.dayofweek                        # 0=Mon … 6=Sun
    month = dt.month
    year = dt.year
    month_sin = math.sin(2 * math.pi * month / 12)
    month_cos = math.cos(2 * math.pi * month / 12)
    is_weekend = 1 if dow >= 5 else 0

    # Wind direction → circular components
    wd_rad = math.radians(weather.get("wd_deg", 0))
    wd_x = math.cos(wd_rad)
    wd_y = math.sin(wd_rad)

    # Lag / rolling features from value_buffer
    # buffer[-1] = lag_1, buffer[-3] = lag_3, buffer[-7] = lag_7
    def buf(offset: int) -> float:
        idx = -offset
        if abs(idx) > len(value_buffer):
            return float(np.nanmean(value_buffer)) if value_buffer else 0.0
        v = value_buffer[idx]
        return float(np.nanmean(value_buffer)) if (v is None or math.isnan(v)) else v

    lag_1 = buf(1)
    lag_3 = buf(3)
    lag_7 = buf(7)

    # Rolling means (exclude the "today" slot – just the prior days)
    recent_3 = [buf(i) for i in range(1, 4)]
    recent_7 = [buf(i) for i in range(1, 8)]
    rolling_3 = float(np.nanmean(recent_3))
    rolling_7 = float(np.nanmean(recent_7))
    rolling_max_3 = float(np.nanmax(recent_3))

    # Location-type dummies
    lt_urban_bg = 1 if loc_type == "Urban Background" else 0
    lt_urban_ind = 1 if loc_type == "Urban Industrial" else 0
    lt_urban_tr = 1 if loc_type == "Urban Traffic" else 0

    # Day-of-week dummies (0 = Monday is the reference, dropped)
    dow_dummies = {f"day_of_week_{i}": (
        1 if dow == i else 0) for i in range(1, 7)}

    row: dict[str, Any] = {
        "ws":           weather.get("ws", 0),
        "temp":         weather.get("temp", 10),
        "wd_x":         wd_x,
        "wd_y":         wd_y,
        "latitude":     meta["lat"],
        "longitude":    meta["lon"],
        "is_weekend":   is_weekend,
        "month_sin":    month_sin,
        "month_cos":    month_cos,
        "year":         year,
        "lag_1":        lag_1,
        "lag_3":        lag_3,
        "lag_7":        lag_7,
        "rolling_3":    rolling_3,
        "rolling_7":    rolling_7,
        "rolling_max_3": rolling_max_3,
        "location_type_Urban Background":  lt_urban_bg,
        "location_type_Urban Industrial":  lt_urban_ind,
        "location_type_Urban Traffic":     lt_urban_tr,
        **dow_dummies,
    }

    df = pd.DataFrame([row])[FEATURES[pollutant]]

    df["is_weekend"] = pd.Categorical(df["is_weekend"], categories=[0, 1])
    return df


# ─────────────────────────────────────────────
# 5.  MAIN PREDICTOR CLASS
# ─────────────────────────────────────────────

class AQIPredictor:
    def __init__(self, model_dir: str | Path = "."):
        self.model_dir = Path(model_dir)
        self.models: dict[str, XGBRegressor] = {}
        self._load_models()

    def _load_models(self) -> None:
        for pollutant, filename in MODEL_FILES.items():
            path = self.model_dir / filename
            if not path.exists():
                raise FileNotFoundError(
                    f"Model file not found: {path}\n"
                )
            m = XGBRegressor()
            m.load_model(str(path))
            self.models[pollutant] = m

    # ------------------------------------------------------------------

    def _predict_pollutant_7days(
        self,
        pollutant: str,
        site: str,
        history_values: list[float],
        weather_forecast: list[dict],  # 7 dicts: {"ws", "temp", "wd_deg"}
        start_date: date,
    ) -> list[float]:

        model = self.models[pollutant]
        # keep a rolling window of length ≥ 7
        buffer = list(history_values[-7:])
        predictions: list[float] = []

        for day_offset in range(7):
            target_date = start_date + timedelta(days=day_offset)
            weather = weather_forecast[day_offset]

            X_row = _build_row(target_date, site, weather, buffer, pollutant)
            raw = float(model.predict(X_row)[0])

            # Back-transform for log-space models
            if pollutant in LOG_TRANSFORM_POLLUTANTS:
                pred = float(np.expm1(max(raw, 0)))
            else:
                pred = max(raw, 0.0)

            predictions.append(pred)
            buffer.append(pred)       # use prediction as future "known" value

        return predictions

    # ------------------------------------------------------------------

    def predict(
        self,
        site: str,
        history: pd.DataFrame,
        weather_fc: list[dict],
        start_date: date | None = None,
        pollutants: list[str] | None = None
    ) -> list[dict]:
        if site not in SITE_META:
            raise ValueError(
                f"Unknown site '{site}'. Valid sites: {list(SITE_META)}")
        if len(weather_fc) != 7:
            raise ValueError(
                "weather_fc must contain exactly 7 dicts (one per forecast day).")

        if start_date is None:
            start_date = date.today()

        # Ensure history is sorted and parse dates
        hist = history.copy()
        hist["date"] = pd.to_datetime(hist["date"])
        hist = hist.sort_values("date").tail(14)   # only need the last 14

        if pollutants is None:
            valid_cols = ["NO2", "O3", "SO2", "PM10", "PM2.5"]
            pollutants = [c for c in history.columns if c in valid_cols]

        # Predict each pollutant independently
        raw_preds: dict[str, list[float]] = {}
        for p in pollutants:
            col = p  # column name in history df
            hist_vals = hist[col].fillna(hist[col].median()).tolist()
            raw_preds[p] = self._predict_pollutant_7days(
                p, site, hist_vals, weather_fc, start_date
            )

        # Assemble final output
        output = []
        for i in range(7):
            day_date = start_date + timedelta(days=i)
            bands = {p: pollutant_band(p, raw_preds[p][i]) for p in pollutants}
            aqi = overall_aqi(bands)

            output.append({
                "date":      day_date.isoformat(),
                "aqi":       aqi,
                "aqi_label": BAND_LABELS[aqi],
                "pollutants": {
                    p: {
                        "concentration": round(raw_preds[p][i], 2),
                        "band": bands[p],
                    }
                    for p in pollutants
                },
            })

        return output
