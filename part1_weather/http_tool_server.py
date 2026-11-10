"""MCP server that gives the model a single tool: ``http_get``.

Requests are limited to the NOAA Weather API and the OpenStreetMap Nominatim
geocoder, so the assistant can reach the data it needs and nothing else.
"""

from __future__ import annotations

import json
import time
from urllib.parse import urlparse

import requests
from mcp.server.mcpserver import MCPServer

ALLOWED_HOSTS = {"api.weather.gov", "nominatim.openstreetmap.org"}
USER_AGENT = "hw0-6-weather-prompt/1.0 (course homework)"
MAX_BODY_CHARS = 60_000
NOMINATIM_MIN_INTERVAL = 1.1  # Nominatim usage policy: at most 1 request per second

mcp = MCPServer("noaa", log_level="WARNING")
_last_nominatim_call = 0.0


def check_url(url: str) -> str | None:
    """Return an error message if the URL may not be fetched, otherwise None."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return "Only https:// URLs are allowed."
    if parsed.hostname not in ALLOWED_HOSTS:
        return f"Host not allowed: {parsed.hostname}. Allowed hosts: {sorted(ALLOWED_HOSTS)}."
    return None


@mcp.tool()
def http_get(url: str) -> str:
    """Send an HTTP GET request and return the status code and response body as JSON.

    Only https://api.weather.gov/... and https://nominatim.openstreetmap.org/... are allowed.
    """
    global _last_nominatim_call
    error = check_url(url)
    if error:
        return json.dumps({"status": None, "error": error})

    if urlparse(url).hostname == "nominatim.openstreetmap.org":
        wait = NOMINATIM_MIN_INTERVAL - (time.monotonic() - _last_nominatim_call)
        if wait > 0:
            time.sleep(wait)
        _last_nominatim_call = time.monotonic()

    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json, application/json"},
            timeout=20,
        )
    except requests.RequestException as exc:
        return json.dumps({"status": None, "error": f"Request failed: {exc}"})

    body = resp.text
    if len(body) > MAX_BODY_CHARS:
        body = body[:MAX_BODY_CHARS] + "\n...[truncated]"
    return json.dumps({"status": resp.status_code, "url": resp.url, "body": body})


if __name__ == "__main__":
    mcp.run()
