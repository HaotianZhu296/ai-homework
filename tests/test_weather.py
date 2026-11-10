import json

from http_tool_server import check_url
from reference import OUTPUT_KEYS, choose_period, error_output, parse_input, validate_output

GOOD = {
    "location": "Seattle, WA",
    "forecast_period": "Tonight",
    "temperature": 49,
    "temperature_unit": "F",
    "short_forecast": "Light Rain Likely",
    "wind_speed": "6 to 14 mph",
    "wind_direction": "S",
}

PERIODS = [
    {"name": "Tonight", "startTime": "2026-11-09T21:00:00-06:00", "isDaytime": False},
    {"name": "Tuesday", "startTime": "2026-11-10T06:00:00-06:00", "isDaytime": True},
    {"name": "Tuesday Night", "startTime": "2026-11-10T18:00:00-06:00", "isDaytime": False},
    {"name": "Veterans Day", "startTime": "2026-11-11T06:00:00-06:00", "isDaytime": True},
    {"name": "Wednesday Night", "startTime": "2026-11-11T18:00:00-06:00", "isDaytime": False},
]


def test_valid_reply_passes():
    parsed, problems = validate_output(json.dumps(GOOD))
    assert parsed == GOOD and problems == []


def test_error_reply_passes():
    _, problems = validate_output(json.dumps(error_output("Paris, France")))
    assert problems == []


def test_extra_key_fails():
    _, problems = validate_output(json.dumps({**GOOD, "detailedForecast": "Rain likely."}))
    assert any("keys are" in p for p in problems)


def test_wrong_key_order_fails():
    reordered = {k: GOOD[k] for k in reversed(OUTPUT_KEYS)}
    _, problems = validate_output(json.dumps(reordered))
    assert problems


def test_string_temperature_fails():
    _, problems = validate_output(json.dumps({**GOOD, "temperature": "49"}))
    assert "temperature must be an integer" in problems


def test_code_fence_and_prose_fail():
    _, fenced = validate_output("```json\n" + json.dumps(GOOD) + "\n```")
    assert fenced
    _, prose = validate_output("Here is the forecast:\n" + json.dumps(GOOD))
    assert any("not valid JSON" in p for p in prose)


def test_parse_input_splits_period():
    assert parse_input("Chicago, IL | Wednesday") == ("Chicago, IL", "Wednesday")
    assert parse_input("47.6062, -122.3321") == ("47.6062, -122.3321", None)


def test_choose_period_by_name_ignores_case():
    assert choose_period(PERIODS, "tuesday night")["name"] == "Tuesday Night"


def test_choose_period_falls_back_to_weekday_for_holidays():
    assert choose_period(PERIODS, "Wednesday")["name"] == "Veterans Day"
    assert choose_period(PERIODS, "Wednesday Night")["name"] == "Wednesday Night"


def test_choose_period_unknown_returns_none():
    assert choose_period(PERIODS, "Someday") is None


def test_tool_only_allows_noaa_and_geocoder():
    assert check_url("https://api.weather.gov/points/47.6062,-122.3321") is None
    assert check_url("https://nominatim.openstreetmap.org/search?q=Boston") is None
    assert check_url("https://example.com/") is not None
    assert check_url("http://api.weather.gov/points/1,2") is not None
