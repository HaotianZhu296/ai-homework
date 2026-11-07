"""Movie search Lambda: GET /search?q=<keywords>.

Runs a `match` query on the `title` field of the `movies` index and returns
`{"results": [...], "total": N}`. Requests to OpenSearch are signed with
SigV4 (requests-aws4auth) using the function's execution-role credentials.
"""

import json
import logging
import os

import boto3
import requests
from requests_aws4auth import AWS4Auth

logger = logging.getLogger()
logger.setLevel(logging.INFO)

INDEX_NAME = os.environ.get("INDEX_NAME", "movies")
DEFAULT_SIZE = 20
MAX_SIZE = 50
MAX_QUERY_LENGTH = 200
REQUEST_TIMEOUT_SECS = 8

CORS_HEADERS = {
    "Access-Control-Allow-Origin": os.environ.get("ALLOWED_ORIGIN", "*"),
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
}

_http = requests.Session()
_auth = None


def _get_auth():
    """SigV4 signer for the `es` service, built once per container.

    `refreshable_credentials` lets the signer pick up rotated role credentials
    without rebuilding the object.
    """
    global _auth
    if _auth is None:
        session = boto3.Session()
        region = os.environ.get("AWS_REGION") or session.region_name
        _auth = AWS4Auth(
            region=region,
            service="es",
            refreshable_credentials=session.get_credentials(),
        )
    return _auth


def _endpoint():
    endpoint = os.environ["OPENSEARCH_ENDPOINT"].rstrip("/")
    if not endpoint.startswith(("https://", "http://")):
        endpoint = "https://" + endpoint
    return endpoint


def response(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", **CORS_HEADERS},
        "body": json.dumps(body),
    }


def parse_size(raw):
    """Optional `size` parameter, clamped to 1..MAX_SIZE."""
    try:
        size = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_SIZE
    return max(1, min(size, MAX_SIZE))


def build_query(q, size=DEFAULT_SIZE):
    """Full-text match on `title` only."""
    return {
        "size": size,
        "track_total_hits": True,
        "query": {"match": {"title": {"query": q}}},
    }


def format_hit(hit):
    source = dict(hit.get("_source") or {})
    source.pop("type", None)  # leftover field from the old bulk format
    source["id"] = source.get("id") or hit.get("_id")
    source["score"] = hit.get("_score")
    return source


def parse_search_response(data):
    hits = data.get("hits") or {}
    total = hits.get("total", 0)
    if isinstance(total, dict):
        total = total.get("value", 0)
    return {
        "results": [format_hit(h) for h in hits.get("hits", [])],
        "total": int(total),
    }


def handler(event, context):
    params = (event or {}).get("queryStringParameters") or {}
    q = (params.get("q") or "").strip()

    if not q:
        return response(400, {"error": "Query parameter 'q' is required and cannot be empty."})
    if len(q) > MAX_QUERY_LENGTH:
        return response(400, {"error": f"Query parameter 'q' must be at most {MAX_QUERY_LENGTH} characters."})

    body = build_query(q, parse_size(params.get("size")))
    url = f"{_endpoint()}/{INDEX_NAME}/_search"

    try:
        resp = _http.post(url, auth=_get_auth(), json=body, timeout=REQUEST_TIMEOUT_SECS)
    except requests.RequestException:
        logger.exception("OpenSearch request failed")
        return response(502, {"error": "Search service is unavailable. Please try again."})

    if resp.status_code != 200:
        logger.error("OpenSearch returned %s: %s", resp.status_code, resp.text[:500])
        return response(502, {"error": "Search service returned an error. Please try again."})

    return response(200, parse_search_response(resp.json()))
