"""Offline business tests; MockEncoder is a test double, never an app fallback."""

from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json
import math
from contextlib import contextmanager

import pytest

from backend.models import SearchRequest
from backend.service import ShoppingService, DEMO_TIME
from backend.storage import LocalStore
from backend.deals import rank_deals
from backend.search import search
from db.embeddings import build_text, generate_batch, generate_embedding, index_store, validate_vector
from scraper.evaluate import evaluate_fixtures, FIXTURE_DIR

QUERY = "Apple MacBook Air M5 16GB RAM 512GB SSD"


class MockEncoder:
    def __init__(self):
        self.calls = []

    def encode(self, texts, **kwargs):
        self.calls.append(list(texts))
        result = []
        for text in texts:
            vector = [0.0] * 384
            for word in text.lower().split():
                vector[int(sha256(word.encode()).hexdigest()[:8], 16) % 384] += 1.0
            result.append(vector)
        return result


@pytest.fixture
def service(tmp_path):
    service = ShoppingService(LocalStore(tmp_path / "catalog.sqlite3"), model=MockEncoder())
    service.collect(QUERY)
    return service


def test_embeddings_dimensions_normalization_and_reuse(service):
    model = service.model
    vectors = generate_batch(model, ["Apple laptop", "Lenovo laptop"])
    assert len(vectors) == 2
    assert all(len(vector) == 384 for vector in vectors)
    assert all(math.isclose(sum(x*x for x in vector), 1) for vector in vectors)
    assert index_store(service.store, model) == {"created": 0, "reused": 7, "skipped": 0}
    row = service.store.listings()[0]
    updated = deepcopy(row["raw_payload"])
    updated["scraped_at"] = "2026-10-28T13:00:00+00:00"
    updated["raw"]["price"] = "123.00"
    service.store.ingest(updated)
    calls = len(model.calls)
    assert index_store(service.store, model)["reused"] == 7
    assert len(model.calls) == calls
    updated["scraped_at"] = "2026-10-28T14:00:00+00:00"
    updated["raw"]["description"] = "A changed explicit description"
    service.store.ingest(updated)
    assert index_store(service.store, model)["created"] == 1


@pytest.mark.parametrize("vector", [[1.0]*383, [0.0]*384, [float('nan')]*384, [True]*384])
def test_invalid_vectors_reject(vector):
    with pytest.raises(ValueError):
        validate_vector(vector)


def test_embedding_text_has_description_but_no_offer_information():
    text = build_text({"title": "Laptop", "brand": "Example", "category": "laptop",
        "description": "Explicit description", "price": "99.99", "retailer_key": "secret-retailer",
        "attributes": {"ram_gb": 16, "condition": "used"}})
    assert "Explicit description" in text and "category" not in text
    assert "laptop" in text and "99.99" not in text and "used" not in text and "secret-retailer" not in text


def test_hardware_variants_excluded_and_incomplete_needs_review(service):
    result = service.search(SearchRequest(q=QUERY))
    exact = [row for row in result["results"] if row["match_status"] == "exact"]
    assert {row["retailer_key"] for row in exact} == {"best_buy", "target"}
    assert len(exact) == 2
    assert len(result["results"]) == 3
    assert result["results"][-1]["match_status"] == "manual_review"
    assert all(row["attributes"]["storage_gb"] == 512 for row in result["results"])
    assert all(row["attributes"]["cpu"] == "Apple M5" for row in result["results"])


@pytest.mark.parametrize("changes", [{"max_price": 1000}, {"min_price": 1000},
    {"category": "monitor"}, {"availability": "out_of_stock"}, {"brand": "Lenovo"}])
def test_search_filters(service, changes):
    result = service.search(SearchRequest(q=QUERY, **changes))["results"]
    if "max_price" in changes:
        assert all(float(row["price"]) <= 1000 for row in result)
    elif "min_price" in changes:
        assert all(float(row["price"]) >= 1000 for row in result)
    else:
        assert result == []


def test_exact_model_query_and_empty_results(service):
    results = service.search(SearchRequest(q="MBA-M4-13"))["results"]
    assert len(results) == 1 and results[0]["model_number"] == "MBA-M4-13"
    assert service.search(SearchRequest(q=QUERY, model_number="DOES-NOT-EXIST"))["results"] == []
    with pytest.raises(ValueError, match="disagree"):
        service.search(SearchRequest(q=QUERY, ram_gb=8))


def test_duplicates_and_stale_vectors(service):
    before = len(service.store.listings())
    service.collect(QUERY)
    assert len(service.store.listings()) == before
    row = service.store.listings()[0]
    updated = deepcopy(row["raw_payload"])
    updated["scraped_at"] = "2026-10-28T13:00:00+00:00"
    updated["raw"]["description"] = "Changed identity text"
    service.store.ingest(updated)
    assert service.search(SearchRequest(q=QUERY))["indexed"] == 6


def test_deals_price_order_missing_shipping_stale_and_unavailable(service):
    response = service.deals(SearchRequest(q=QUERY))
    assert [row["total_price"] for row in response["offers"]] == ["999.00", "1049.00"]
    assert response["offers"][0]["recommended"]
    assert response["retailers"] == 2 and not response["live_two_retailer_milestone"]
    offers = deepcopy(response["offers"])
    offers[0]["shipping_cost"] = None
    ranked = rank_deals(offers, service.store, DEMO_TIME)
    assert ranked["offers"][0]["retailer_key"] == "target"
    assert ranked["offers"][-1]["total_price"] is None
    offers[0]["scraped_at"] = (DEMO_TIME - timedelta(days=5)).isoformat()
    offers[1]["availability"] = "out_of_stock"
    assert rank_deals(offers, service.store, DEMO_TIME)["offers"] == []


def test_labeled_quality_counts_are_not_live_reliability():
    report = evaluate_fixtures()
    assert report["counts"] == {"attempted":10,"fetched":10,"extracted":8,"validated":7,"rejected":3}
    assert report["incorrect_fields"] == {}
    assert report["missing_fields"]["attributes.ram_gb"] == 1
    assert report["metrics"]["incorrect_data_rate_among_accepted"] == 0
    assert report["metrics"]["exact_price_accuracy_present_labeled"] == 1
    assert report["accepted_incomplete_records"] == 1


def test_online_only_does_not_invent_stock_status():
    from scraper.scraper import extract_product
    from scraper.validator import validate_record
    from scraper.envelope import listing_from_product
    page = json.loads((FIXTURE_DIR/"manifest.json").read_text())["pages"][0]
    record = extract_product((FIXTURE_DIR/page["file"]).read_text(), page["url"])
    record["availability"] = "OnlineOnly"
    assert listing_from_product(validate_record(record))["raw"]["availability"] is None


def test_quality_report_detects_a_mocked_incorrect_accepted_price():
    from scraper.scraper import extract_product
    def faulty_extractor(html, url):
        record = extract_product(html, url)
        if url.endswith("SYNTH001"):
            record["price"] = "1.00"
        return record
    report = evaluate_fixtures(extractor=faulty_extractor)
    assert report["incorrect_fields"] == {"price": 1}
    assert report["metrics"]["incorrect_data_rate_among_accepted"] == 1/7


def test_gemini_failure_falls_back_without_changing_offers(service, monkeypatch):
    import requests
    from backend.explanations import explain
    deals = service.deals(SearchRequest(q=QUERY))
    expected = explain(deals)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("backend.explanations.structured", lambda *a, **k: (_ for _ in ()).throw(requests.Timeout()))
    assert explain(deals, True) == expected


def test_discovery_validates_urls_and_keeps_variant_queries(monkeypatch):
    from backend.legacy_discovery import discover
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-only")
    url = "https://www.target.com/p/synthetic/-/A-90000001?preselect=90000002"
    class Response:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"web":{"results":[{"url":url},{"url":url},{"url":"https://evil.test/ip/123"}]}}
    monkeypatch.setattr("backend.legacy_discovery.requests.get", lambda *a, **k: Response())
    assert discover(QUERY) == [url]


def test_live_without_discovery_configuration_is_clear(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    live = ShoppingService(LocalStore(tmp_path/"live.sqlite3"), mode="live", model=MockEncoder())
    status = live.collect(QUERY)
    assert status["stage"] == "failed" and status["attempted"] == 0
    assert "GEMINI_API_KEY" in status["errors"][0]
    assert live.store.listings() == []


def test_live_block_does_not_retry_same_retailer(tmp_path, monkeypatch):
    from backend.coordinator import collect
    urls = ["https://www.amazon.com/dp/B0DEMO0001", "https://www.amazon.com/dp/B0DEMO0002"]
    monkeypatch.setattr("backend.coordinator.discover", lambda q: urls)
    monkeypatch.setattr("backend.coordinator.robots_allowed", lambda url: True)
    calls = []
    def blocked(url):
        calls.append(url)
        return "<h1>Verify you are human</h1>"
    monkeypatch.setattr("backend.coordinator.fetch_page", blocked)
    status = collect(LocalStore(tmp_path/"blocked.sqlite3"), QUERY, mode="live")
    assert calls == [urls[0]]
    assert status["stage"] == "failed" and status["accepted"] == 0


def test_browser_rate_limit_is_reported_as_blocked():
    from types import SimpleNamespace
    from scraper.scraper import read_browser_page
    from scraper.evaluate import error_type
    page = SimpleNamespace(goto=lambda *args, **kwargs: SimpleNamespace(status=429))
    with pytest.raises(ValueError, match="HTTP 429") as caught:
        read_browser_page(page, "https://www.amazon.com/dp/B0DEMO0001")
    assert error_type(caught.value, "fetch") == "blocked"


def test_incomplete_cpu_generation_requires_review():
    from normalizer.matching import check_requirements
    row = {"attributes": {"cpu": "Intel Core i7", "ram_gb":16, "storage_gb":512}, "model_number":"EX14"}
    result = check_requirements(row, {"cpu":"Intel Core i7-1360P", "ram_gb":16,"storage_gb":512,"model_number":"EX14"})
    assert result["status"] == "manual_review"


def test_deals_do_not_compare_conflicting_models_or_colors(service):
    rows = service.deals(SearchRequest(q=QUERY))["offers"]
    rows[1]["attributes"]["color"] = "Red"
    assert rank_deals(rows, service.store, DEMO_TIME)["offers"] == []
    assert service.search(SearchRequest(q=QUERY, color="Red"))["results"] == []


def test_api_routes_and_validation(service):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from backend.api import app, get_service
    app.dependency_overrides[get_service] = lambda: service
    try:
        client = TestClient(app)
        assert client.get("/health").json()["dimensions"] == 384
        assert len(client.get("/products").json()["products"]) == 7
        assert len(client.get("/search", params={"q":QUERY}).json()["results"]) == 3
        response = client.get("/deals", params={"q":QUERY})
        assert response.status_code == 200 and len(response.json()["offers"]) == 2
        assert client.get("/search", params={"q":"", "limit":1000}).status_code == 422
        assert client.get("/search", params={"q":QUERY,"min_price":100,"max_price":10}).status_code == 422
        assert client.get("/scraper/status").json()["stage"] == "ready"
        assert client.post("/demo/collect").status_code == 200
        assert client.post("/scrape", json={"url":"http://localhost"}).status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_postgres_vector_query_is_parameterized(monkeypatch):
    from backend.postgres import PostgresStore
    store = PostgresStore("postgresql://unused-test-only")
    calls = []
    class DB:
        def execute(self, sql, params):
            calls.append((sql, params))
            return self
        def fetchall(self): return []
    @contextmanager
    def connection(): yield DB()
    monkeypatch.setattr(store, "connect", connection)
    store.vector_candidates([1.0]*384, SearchRequest(q=QUERY, brand="x';DROP TABLE products;--"))
    assert "%s" in calls[0][0]
    assert "DROP TABLE" not in calls[0][0] and "DROP TABLE" in calls[0][1][-2]
