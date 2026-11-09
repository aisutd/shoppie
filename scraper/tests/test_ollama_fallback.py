import json
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

import local_search_api as api


LAPTOP = {"title": "MacBook Air M4 16GB RAM", "category": "laptops", "price": "799.99"}


@pytest.fixture
def catalog(monkeypatch):
    monkeypatch.setattr(api, "_ollama_retry_at", 0)
    monkeypatch.setattr(api, "load_database_config", lambda: SimpleNamespace(
        url="https://example.test", secret_key="test-key"
    ))
    monkeypatch.setattr(api, "load_catalog", lambda _: [LAPTOP])
    monkeypatch.setattr(api, "load_reference_catalog", lambda: [])


def search(query):
    body = json.dumps({"query": query}).encode()
    handler = api.SearchHandler.__new__(api.SearchHandler)
    handler.path = "/api/search"
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = BytesIO(body)
    handler.send_json = Mock()
    handler.do_POST()
    return handler.send_json.call_args.args


def test_catalog_match_does_not_call_ollama(catalog, monkeypatch):
    post = Mock(side_effect=requests.ConnectionError())
    monkeypatch.setattr(api.requests, "post", post)
    status, body = search("MacBook")
    assert status == 200 and body["products"][0]["title"] == LAPTOP["title"]
    post.assert_not_called()


@pytest.mark.parametrize("error", [
    requests.ConnectionError("Connection refused"),
    requests.Timeout(),
    requests.HTTPError("Model not found"),
    RuntimeError("Unexpected Ollama error"),
])
def test_ollama_failure_returns_empty_and_cools_down(catalog, monkeypatch, error):
    post = Mock(side_effect=error)
    monkeypatch.setattr(api.requests, "post", post)
    now = [100]
    monkeypatch.setattr(api.time, "monotonic", lambda: now[0])
    assert search("AirPods") == (200, {"products": []})
    assert search("Logitech mouse") == (200, {"products": []})
    assert post.call_count == 1
    assert post.call_args.kwargs["timeout"] == (1, 5)
    now[0] += api.OLLAMA_RETRY_DELAY
    assert search("AirPods") == (200, {"products": []})
    assert post.call_count == 2


@pytest.mark.parametrize("payload", [
    None, [], {"message": []}, {"message": {"content": None}},
    {"message": {"content": "invalid json"}},
    {"message": {"content": "[]"}},
    {"message": {"content": '{"terms":"earbuds"}'}},
])
def test_invalid_ollama_response_returns_empty(catalog, monkeypatch, payload):
    monkeypatch.setattr(api.requests, "post", Mock(return_value=Mock(json=lambda: payload)))
    assert search("AirPods") == (200, {"products": []})


def test_invalid_http_json_returns_empty(catalog, monkeypatch):
    response = Mock()
    response.json.side_effect = requests.exceptions.JSONDecodeError("Invalid JSON", "bad", 0)
    monkeypatch.setattr(api.requests, "post", Mock(return_value=response))
    assert search("AirPods") == (200, {"products": []})


def test_available_ollama_searches_supabase_for_suggested_terms(catalog, monkeypatch):
    earbuds = {"title": "Wireless earbuds", "category": "headphones", "price": "99.99"}
    response = Mock(json=lambda: {"message": {"content": '{"terms":["wireless earbuds"]}'}})
    monkeypatch.setattr(api.requests, "post", Mock(return_value=response))
    get = Mock(return_value=Mock(json=lambda: [earbuds]))
    monkeypatch.setattr(api.requests, "get", get)
    status, body = search("AirPods")
    assert status == 200 and body["products"][0]["title"] == earbuds["title"]
    assert "title.ilike.*wireless earbuds*" in get.call_args.kwargs["params"]["or"]


@pytest.mark.parametrize("during_fallback", [False, True])
def test_supabase_connection_failure_is_still_an_error(catalog, monkeypatch, during_fallback):
    error = Mock(side_effect=requests.ConnectionError("private details"))
    if during_fallback:
        monkeypatch.setattr(api, "interpret_query", lambda _: ["earbuds"])
        monkeypatch.setattr(api.requests, "get", error)
    else:
        monkeypatch.setattr(api, "load_catalog", error)
    status, body = search("AirPods")
    assert status == 503 and "Supabase catalog" in body["error"]
    assert "private details" not in body["error"]


def test_catalog_category_price_and_ram_filters_still_apply(catalog, monkeypatch):
    products = [LAPTOP, {**LAPTOP, "price": "999.99"},
                {**LAPTOP, "title": "MacBook Air M4 8GB RAM"},
                {**LAPTOP, "category": "monitors"}]
    monkeypatch.setattr(api, "load_catalog", lambda _: products)
    post = Mock()
    monkeypatch.setattr(api.requests, "post", post)
    status, body = search("MacBook laptop 16GB RAM under $900")
    assert status == 200 and len(body["products"]) == 1
    assert all(body["products"][0][field] == value for field, value in LAPTOP.items())
    post.assert_not_called()
