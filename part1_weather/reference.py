"""Deterministic version of the procedure in prompt.md, plus an output validator.

``run_weather.py`` uses these to check the assistant: every reply must pass
``validate_output``, and its values must match ``reference_forecast`` for the
same input.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from urllib.parse import quote

import requests

USER_AGENT = "hw0-6-weather-prompt/1.0 (course homework)"
OUTPUT_KEYS = [
    "location",
    "forecast_period",
    "temperature",
    "temperature_unit",
    "short_forecast",
    "wind_speed",
    "wind_direction",
]
COORD_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


def _get(url: str) -> requests.Response:
    return requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json, application/json"},
        timeout=20,
    )


def parse_input(user_input: str) -> tuple[str, str | None]:
    """Split 'location | period' into its two parts."""
    location, _, period = user_input.partition("|")
    return location.strip(), (period.strip() or None)


def error_output(user_input: str) -> dict:
    return {"location": user_input, **{k: None for k in OUTPUT_KEYS[1:]}}


def resolve_coordinates(location: str) -> tuple[float, float] | None:
    match = COORD_RE.match(location)
    if match:
        lat, lon = float(match.group(1)), float(match.group(2))
    else:
        time.sleep(1.1)  # Nominatim usage policy: at most 1 request per second
        url = (
            "https://nominatim.openstreetmap.org/search?q="
            f"{quote(location)}&format=jsonv2&limit=1&countrycodes=us"
        )
        results = _get(url).json()
        if not results:
            return None
        lat, lon = float(results[0]["lat"]), float(results[0]["lon"])
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return round(lat, 4), round(lon, 4)


WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def choose_period(periods: list[dict], requested: str) -> dict | None:
    """Match by name; for weekdays, fall back to the weekday of startTime (holidays are renamed)."""
    wanted = requested.strip().lower()
    for p in periods:
        if p["name"].lower() == wanted:
            return p
    day, _, night = wanted.partition(" ")
    if day in WEEKDAYS and night in ("", "night"):
        for p in periods:
            start = datetime.fromisoformat(p["startTime"])
            if start.weekday() == WEEKDAYS.index(day) and p["isDaytime"] == (night == ""):
                return p
    return None


def reference_forecast(user_input: str) -> dict:
    location, period_name = parse_input(user_input)
    coords = resolve_coordinates(location)
    if coords is None:
        return error_output(user_input)

    points = _get(f"https://api.weather.gov/points/{coords[0]},{coords[1]}")
    if points.status_code != 200:
        return error_output(user_input)
    props = points.json()["properties"]
    rel = props["relativeLocation"]["properties"]

    forecast = _get(props["forecast"])
    if forecast.status_code >= 500:
        forecast = _get(props["forecast"])
    if forecast.status_code != 200:
        return error_output(user_input)

    periods = forecast.json()["properties"]["periods"]
    if period_name:
        period = choose_period(periods, period_name)
        if period is None:
            return error_output(user_input)
    else:
        period = periods[0]

    return {
        "location": f"{rel['city']}, {rel['state']}",
        "forecast_period": period["name"],
        "temperature": period["temperature"],
        "temperature_unit": period["temperatureUnit"],
        "short_forecast": period["shortForecast"],
        "wind_speed": period["windSpeed"],
        "wind_direction": period["windDirection"],
    }


def validate_output(text: str) -> tuple[dict | None, list[str]]:
    """Check a raw reply against the output rules. Returns (parsed, problems)."""
    problems: list[str] = []
    if text != text.strip():
        problems.append("reply has leading or trailing whitespace")
    if text.strip().startswith("```"):
        problems.append("reply is wrapped in a code fence")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, problems + [f"not valid JSON: {exc}"]
    if not isinstance(data, dict):
        return None, problems + ["top-level value is not an object"]

    if list(data) != OUTPUT_KEYS:
        problems.append(f"keys are {list(data)}, expected {OUTPUT_KEYS}")
    if not isinstance(data.get("location"), str):
        problems.append("location must be a string")

    is_error = all(data.get(k) is None for k in OUTPUT_KEYS[1:])
    if not is_error:
        temp = data.get("temperature")
        if not isinstance(temp, int) or isinstance(temp, bool):
            problems.append("temperature must be an integer")
        for key in ("forecast_period", "temperature_unit", "short_forecast", "wind_speed", "wind_direction"):
            if not isinstance(data.get(key), str):
                problems.append(f"{key} must be a string")
    return data, problems
