import json

import pytest
import requests

import handler


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


SEARCH_RESULT = {
    "hits": {
        "total": {"value": 2, "relation": "eq"},
        "hits": [
            {
                "_id": "tt1453405",
                "_score": 5.1,
                "_source": {
                    "id": "tt1453405",
                    "title": "New Year's Eve",
                    "year": 2011,
                    "rating": 5.4,
                    "genres": ["Comedy", "Romance"],
                    "type": "add",
                },
            },
            {"_id": "tt0402399", "_score": 4.2, "_source": {"title": "The New World"}},
        ],
    }
}


@pytest.fixture
def calls(monkeypatch):
    """Record outgoing OpenSearch requests and return SEARCH_RESULT."""
    recorded = []

    def fake_post(url, auth=None, json=None, timeout=None):
        recorded.append({"url": url, "body": json, "auth": auth})
        return FakeResponse(200, SEARCH_RESULT)

    monkeypatch.setattr(handler._http, "post", fake_post)
    monkeypatch.setattr(handler, "_get_auth", lambda: "sigv4-auth")
    return recorded


def event(**params):
    return {"httpMethod": "GET", "path": "/search", "queryStringParameters": params or None}


def body(resp):
    return json.loads(resp["body"])


@pytest.mark.parametrize("evt", [event(), event(q=""), event(q="   "), {}, None])
def test_missing_or_empty_q_returns_400(evt, calls):
    resp = handler.handler(evt, None)
    assert resp["statusCode"] == 400
    assert "q" in body(resp)["error"]
    assert calls == []  # never reaches OpenSearch


def test_overlong_q_returns_400(calls):
    resp = handler.handler(event(q="x" * 201), None)
    assert resp["statusCode"] == 400


def test_match_query_on_title_only(calls):
    resp = handler.handler(event(q="  new  "), None)
    assert resp["statusCode"] == 200
    (call,) = calls
    assert call["url"] == "https://search-test.us-east-2.es.amazonaws.com/movies/_search"
    assert call["body"]["query"] == {"match": {"title": {"query": "new"}}}
    assert call["auth"] == "sigv4-auth"


def test_response_shape(calls):
    data = body(handler.handler(event(q="new"), None))
    assert set(data) == {"results", "total"}
    assert data["total"] == 2
    first = data["results"][0]
    assert first["title"] == "New Year's Eve"
    assert first["id"] == "tt1453405"
    assert "type" not in first
    assert data["results"][1]["id"] == "tt0402399"  # falls back to _id


def test_cors_headers_on_every_response(calls):
    for resp in (handler.handler(event(q="new"), None), handler.handler(event(), None)):
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
        assert resp["headers"]["Content-Type"] == "application/json"


@pytest.mark.parametrize("raw,expected", [(None, 20), ("5", 5), ("0", 1), ("999", 50), ("abc", 20)])
def test_size_is_clamped(raw, expected):
    assert handler.parse_size(raw) == expected


def test_opensearch_error_returns_502(monkeypatch):
    monkeypatch.setattr(handler, "_get_auth", lambda: None)
    monkeypatch.setattr(handler._http, "post", lambda *a, **k: FakeResponse(403, {"message": "denied"}))
    resp = handler.handler(event(q="new"), None)
    assert resp["statusCode"] == 502
    assert "error" in body(resp)


def test_network_failure_returns_502(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("unreachable")

    monkeypatch.setattr(handler, "_get_auth", lambda: None)
    monkeypatch.setattr(handler._http, "post", boom)
    assert handler.handler(event(q="new"), None)["statusCode"] == 502


def test_total_as_plain_number():
    assert handler.parse_search_response({"hits": {"total": 7, "hits": []}}) == {"results": [], "total": 7}
