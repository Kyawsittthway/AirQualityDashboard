"Fetch 7-day weather forecast for any Wales site using Open-Meteo."

from __future__ import annotations

import math
from datetime import date, timedelta

import requests


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def get_weather_forecast(
    lat: float,
    lon: float,
    days: int = 7,
) -> list[dict]:
    params = {
        "latitude":       lat,
        "longitude":      lon,
        "daily":          ["wind_speed_10m_max", "wind_direction_10m_dominant", "temperature_2m_mean"],
        "wind_speed_unit": "ms",
        "forecast_days":  days,
        "timezone":       "Europe/London",
    }

    resp = requests.get(OPEN_METEO_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()["daily"]

    forecasts = []
    for i in range(days):
        forecasts.append({
            "ws":     data["wind_speed_10m_max"][i] or 0.0,
            "temp":   data["temperature_2m_mean"][i] or 10.0,
            "wd_deg": data["wind_direction_10m_dominant"][i] or 0.0,
        })

    return forecasts


def get_weather_for_all_sites(site_meta: dict) -> dict[str, list[dict]]:
    # Deduplicate by rounded coords to avoid identical requests
    cache: dict[tuple, list[dict]] = {}
    result: dict[str, list[dict]] = {}

    for site, meta in site_meta.items():
        key = (round(meta["lat"], 3), round(meta["lon"], 3))
        if key not in cache:
            cache[key] = get_weather_forecast(meta["lat"], meta["lon"])
        result[site] = cache[key]

    return result


# Fallback: historical seasonal averages if open-meteo api is unavailable

MONTHLY_AVERAGES_WALES = {
    # month: (avg_temp_C, avg_ws_ms, avg_wd_deg)
    1:  (4.5,  4.5, 230),
    2:  (4.8,  4.4, 240),
    3:  (6.5,  4.2, 225),
    4:  (8.5,  3.8, 210),
    5:  (11.5, 3.5, 200),
    6:  (14.0, 3.2, 195),
    7:  (16.0, 3.0, 210),
    8:  (15.8, 3.1, 220),
    9:  (13.0, 3.5, 230),
    10: (10.0, 4.0, 240),
    11: (7.0,  4.3, 235),
    12: (5.0,  4.6, 235),
}


def get_weather_fallback(start_date: date, days: int = 7) -> list[dict]:
    out = []
    for i in range(days):
        d = start_date + __import__("datetime").timedelta(days=i)
        temp, ws, wd = MONTHLY_AVERAGES_WALES[d.month]
        out.append({"ws": ws, "temp": temp, "wd_deg": wd})
    return out
