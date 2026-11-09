import json
from collections import Counter
from unittest.mock import Mock

import pytest
import requests

import local_search_api as api
from product_references import IMAGE_DIR, REFERENCE_FILE, load_reference_catalog
from scraper.scraper import identify_product


@pytest.fixture
def stored_catalog(monkeypatch):
    products = [
        {"id": "one", "title": "Apple MacBook Neo 256GB", "category": "laptops",
         "source": "bestbuy.com", "price": "699.99"},
        {"id": "two", "title": "Apple MacBook Neo 256GB", "category": "laptops",
         "source": "walmart.com", "price": "799.99"},
    ]
    monkeypatch.setattr(api, "load_database_config", lambda: object())
    monkeypatch.setattr(api, "load_catalog", lambda _: products)
    monkeypatch.setattr(api, "_ollama_retry_at", 0)
    monkeypatch.setattr(api, "interpret_query", Mock(side_effect=requests.ConnectionError()))
    return products


def test_twenty_references_only_contain_identity_and_links():
    products = load_reference_catalog()
    assert Counter(p["source"] for p in products) == {"target.com": 10, "amazon.com": 10}
    identities = set()
    for product in products:
        retailer, product_id = identify_product(product["product_url"])
        identities.add((retailer, product_id))
        assert product["source"] == f"{retailer}.com"
        assert product["price"] is None and product["is_reference"]
        assert not product.keys() & {"currency", "description", "availability", "is_demo"}
    assert len(identities) == 20


def test_bundled_photos_include_credit_and_license():
    products = load_reference_catalog()
    photos = [p for p in products if p.get("image_url")]
    assert {p["id"]: p["image_url"].split("/")[-1] for p in photos} == {
        "reference-target-91122075": "neo-silver.jpg",
        "reference-target-94649372": "sony-xm6-black.jpg",
        "reference-target-93606140": "airpods-4.jpg",
        "reference-amazon-B0GR6FHGXX": "neo-indigo-front.jpg",
        "reference-amazon-B0GR1493ZV": "air-m5.jpg",
        "reference-amazon-B0FWD726XF": "pro-m5.jpg",
        "reference-amazon-B0F3QJLD3B": "sony-xm6-silver.jpg",
    }
    for product in photos:
        assert product["image_url"].startswith("/reference-images/")
        assert (IMAGE_DIR / product["image_url"].split("/")[-1]).is_file()
        credit = product["image_credit"]
        assert credit["author"] and credit["license"]
        assert credit["source_url"].startswith("https://")
        assert credit["license_url"].startswith("https://")


def test_invalid_image_falls_back_without_discarding_reference(tmp_path):
    valid = json.loads(REFERENCE_FILE.read_text())[0]
    valid["image"]["file"] = "../neo-silver.jpg"
    path = tmp_path / "references.json"
    path.write_text(json.dumps([valid]))
    product, = load_reference_catalog(path)
    assert "image_url" not in product and "image_credit" not in product


def test_normal_search_combines_references_and_priced_rows_without_mutation(stored_catalog):
    results = api.search_products("MacBook Neo")
    assert {p["source"] for p in results} == {"bestbuy.com", "walmart.com", "target.com", "amazon.com"}
    assert [p["price"] for p in results if not p.get("is_reference")] == ["699.99", "799.99"]
    assert all("match_reason" not in p for p in stored_catalog)
    api.interpret_query.assert_not_called()


@pytest.mark.parametrize("query,prices", [
    ("MacBook Neo under $750", ["699.99"]),
    ("cheapest MacBook Neo", ["699.99"]),
    ("MacBook Neo $512", ["699.99", "799.99"]),
])
def test_price_searches_exclude_unknown_prices(stored_catalog, query, prices):
    assert [p["price"] for p in api.search_products(query)] == prices


def test_stored_variant_wins_over_reference_with_alternate_url(stored_catalog):
    stored_catalog.append({
        **stored_catalog[0], "source": "target.com",
        "product_url": "https://target.com/p/macbook-neo/-/A-91122075?ref=example",
    })
    results = api.search_products("MacBook Neo")
    assert sum(p["source"] == "target.com" for p in results) == 1
    assert not next(p for p in results if p["source"] == "target.com").get("is_reference")


def test_reference_model_and_category_matching(stored_catalog):
    assert [p["id"] for p in api.search_products("Samsung SSD")] == [
        "reference-target-93215986", "reference-amazon-B0BHJJ9Y77",
    ]
    assert api.search_products("AirPods 5") == []
    assert api.search_products("Sony WH-1000XM5") == []
    assert api.search_products("Logitech mouse") == []


def test_demo_stays_separate(stored_catalog):
    products = api.search_products("MacBook Neo", demo=True)
    assert products and all(p["is_demo"] and "is_reference" not in p for p in products)


def test_invalid_reference_rows_are_skipped(tmp_path):
    valid = json.loads(REFERENCE_FILE.read_text())[0]
    path = tmp_path / "references.json"
    path.write_text(json.dumps([
        {}, {**valid, "title": " "}, {**valid, "price": 1}, {**valid, "product_id": "123"},
        {**valid, "product_url": "https://target.com.example.com/p/-/A-91122075"},
        {**valid, "category": "invalid"}, valid, valid,
    ]))
    assert len(load_reference_catalog(path)) == 1
    assert load_reference_catalog(tmp_path / "missing.json") == []
