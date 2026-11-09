import json
from collections import Counter
from io import BytesIO
from unittest.mock import Mock

import pytest

import local_search_api as api
from demo_catalog import DEMO_LABEL, load_demo_catalog
from scraper.scraper import identify_product


def test_demo_is_explicit_and_refused_in_production(monkeypatch):
    for name in ("SHOPPIE_DEMO_CATALOG", "SHOPPIE_ENV", "NODE_ENV"):
        monkeypatch.delenv(name, raising=False)
    assert not api.local_demo_enabled()
    monkeypatch.setenv("SHOPPIE_DEMO_CATALOG", "1")
    assert api.local_demo_enabled()
    monkeypatch.setenv("SHOPPIE_ENV", "production")
    assert not api.local_demo_enabled()


def search_request(query, demo=False, dev_header=False):
    body = json.dumps({"query": query}).encode()
    handler = api.SearchHandler.__new__(api.SearchHandler)
    handler.path = "/api/search"
    handler.headers = {"Content-Length": str(len(body))}
    if dev_header:
        handler.headers["X-Shoppie-Local-Demo"] = "1"
    handler.rfile = BytesIO(body)
    handler.demo = demo
    handler.send_json = Mock()
    handler.do_POST()
    return handler.send_json.call_args.args


def test_demo_has_twenty_labeled_reference_products():
    products = load_demo_catalog()
    assert Counter(p["source"] for p in products) == {"target.com": 10, "amazon.com": 10}
    identities = {identify_product(p["product_url"]) for p in products}
    assert len(identities) == 20
    for product in products:
        assert product["is_demo"] and product["demo_label"] == DEMO_LABEL
        assert product["price"] is None
        assert not product.keys() & {"currency", "image_url", "seller", "availability", "description"}


@pytest.mark.parametrize("query,expected", [("Macbook", True), ("Macbook under $1200", False),
                                           ("cheapest laptop", False), ("zzzzzzzzzz", False)])
def test_demo_search_never_contacts_database_or_ollama(monkeypatch, query, expected):
    forbidden = Mock(side_effect=AssertionError("Demo must stay offline"))
    monkeypatch.setattr(api, "load_database_config", forbidden)
    monkeypatch.setattr(api.requests, "get", forbidden)
    monkeypatch.setattr(api.requests, "post", forbidden)
    status, response = search_request(query, demo=True, dev_header=True)
    assert status == 200 and response["demo"] is True
    assert bool(response["products"]) is expected
    assert all(p["is_demo"] and p["price"] is None for p in response["products"])
    forbidden.assert_not_called()


def test_demo_refuses_requests_without_dev_header():
    status, _ = search_request("Macbook", demo=True)
    assert status == 403


def test_default_search_still_returns_unmodified_stored_records(monkeypatch):
    product = {"id": "stored", "title": "MacBook Air M4", "category": "laptops", "price": "799.99"}
    monkeypatch.setattr(api, "load_database_config", lambda: object())
    monkeypatch.setattr(api, "load_catalog", lambda _: [product])
    status, response = search_request("MacBook", dev_header=True)
    assert status == 200 and "demo" not in response
    result, = [row for row in response["products"] if row["id"] == "stored"]
    assert result["price"] == "799.99" and "is_demo" not in result
    assert "match_reason" not in product
