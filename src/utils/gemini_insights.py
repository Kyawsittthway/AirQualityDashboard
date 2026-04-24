# Google gemini api key needed, visit google gemini studio to obtain
import os
import json
from google import genai
from datetime import datetime, timedelta

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CACHE_DIR = os.path.join(BASE_DIR, "data", "insights_cache")
CACHE_FILE = os.path.join(CACHE_DIR, "forecast_insights.json")
os.makedirs(CACHE_DIR, exist_ok=True)


POLL_LABELS = {"NO2": "NO₂", "O3": "O₃", "SO2": "SO₂", "PM10": "PM10", "PM2.5": "PM2.5"}


def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    else:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)


def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)


def generate_forecast_insight(
    site: str, forecast: list[dict], measured: list[str]
) -> str:
    cache = load_cache()
    current_day = str(datetime.now().date())
    cache_key = f"{site}_{current_day}"
    if cache_key in cache:
        return cache[cache_key]
    else:
        if forecast and isinstance(forecast[0], list):
            forecast = forecast[0]
        days_summary = []
        for day in forecast:
            if not isinstance(day, dict):
                continue
            p = day["pollutants"]
            poll_parts = ", ".join(
                f"{POLL_LABELS.get(m, m)}={p[m]['concentration']:.1f}µg/m³"
                for m in measured
                if m in p
            )
            days_summary.append(
                f"{day['date']}: AQI {day['aqi']} ({day['aqi_label']}) — {poll_parts}"
            )

        prompt = f"""You are an air quality expert for a Welsh public dashboard. 
        Summarise this 7-day forecast for {site} in 2-3 concise sentences of plain prose.

        Key context:
        - The forecast has a natural margin of error of ±1 AQI level; use probabilistic language like "likely" or "expected range."
        - Site measures: {', '.join(POLL_LABELS.get(m, m) for m in measured)}.
        - Focus on the peak day and the primary pollutant ({', '.join(measured)}).

        Data:
        {chr(10).join(days_summary)}

        Instructions: No markdown, no bullets, no headers. Mention if the uncertainty range could push levels into a higher health band and provide a brief recommendation."""

        try:
            response = client.models.generate_content(
                model="gemini-3-flash-preview", contents=prompt
            )
            cache[cache_key] = response.text.strip()
            save_cache(cache)
            return response.text.strip()
        except Exception as exc:
            return f"Insight unavailable: {exc}"
