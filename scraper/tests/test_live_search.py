"""Offline contract tests: no retailer traffic, credentials or Supabase writes."""

from pathlib import Path
from io import BytesIO
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import local_search_api as api
from scraper import bestbuy_search as discovery
from scraper import live_search as live
from scraper.bestbuy_search import DiscoveryError


URL = "https://www.bestbuy.com/product/synthetic-macbook-air/TESTM5"
DATABASE = SimpleNamespace(url="https://synthetic.supabase.co", secret_key="sb_secret_SYNTHETIC")


@pytest.fixture
def candidate():
    return {
        "id": "temporary-scraper-id", "title": "Synthetic MacBook Air M5 24GB RAM 512GB SSD",
        "description": "Synthetic laptop", "image_url": None,
        "price": "999.99", "currency": "USD", "product_url": URL,
        "source": "bestbuy.com", "category": "laptops",
        "scraped_at": "2026-11-03T12:00:00Z",
    }


def prepare_collection(monkeypatch, candidate, urls=None):
    monkeypatch.setattr(live, "discover_bestbuy_urls", Mock(return_value=urls or [URL]))
    fetch = Mock(return_value=("<html>synthetic</html>", URL))
    monkeypatch.setattr(live.tech_scraper, "fetch_page", fetch)
    monkeypatch.setattr(live.tech_scraper, "extract_product", Mock(return_value=candidate))
    save = Mock()
    monkeypatch.setattr(live.tech_scraper, "upload_to_supabase", save)
    return fetch, save


def test_discovery_extracts_product_links_only():
    html = (Path(__file__).parent / "fixtures/bestbuy_search_results.html").read_text()
    assert discovery.parse_search_results(html) == [
        URL, "https://www.bestbuy.com/site/synthetic-laptop/1234567.p"
    ]
    assert discovery.parse_search_results(html, limit=1) == [URL]


def test_discovery_supports_json_ld_item_lists():
    html = '''<script type="application/ld+json">{"@type":"ItemList",
    "itemListElement":[{"@type":"ListItem","item":{"url":"/product/test/TESTM5"}}]}</script>'''
    assert discovery.parse_search_results(html) == ["https://www.bestbuy.com/product/test/TESTM5"]


def test_query_is_encoded_not_used_as_a_url():
    assert discovery.search_url("M5 & 24 GB").endswith("st=M5+%26+24+GB")


@pytest.mark.parametrize("html", ["<h1>Verify you are human</h1>", "<html>unexpected layout</html>"])
def test_blocked_or_unknown_pages_are_not_empty_successes(html):
    with pytest.raises(ValueError):
        discovery.parse_search_results(html)


def test_explicit_no_results_is_distinct():
    assert discovery.parse_search_results("<h1>No results</h1>") == []


def test_discovery_rejects_redirects_without_following(monkeypatch):
    get = Mock(return_value=SimpleNamespace(status_code=302))
    monkeypatch.setattr(discovery, "_search_request", get)
    with pytest.raises(ValueError, match="HTTP 302"):
        discovery.discover_bestbuy_urls("macbook")
    assert get.call_args.args[0].startswith(discovery.SEARCH_ROOT)


def test_collection_validates_saves_and_returns_own_records(monkeypatch, candidate):
    fetch, save = prepare_collection(monkeypatch, candidate)
    products, report = live.collect_live_products("MacBook M5", DATABASE)
    assert report["status"] == "complete"
    assert report["saved"] == report["collected"] == 1
    assert products[0]["price"] == "999.99"
    assert "id" not in products[0]
    assert save.call_args.kwargs["database"] is DATABASE
    assert fetch.call_args.kwargs["warmup"] is False


@pytest.mark.parametrize("field,value", [("price", "NaN"), ("price", "-10"), ("price", True),
    ("price", "1.234"), ("currency", "CAD"), ("image_url", "javascript:alert(1)")])
def test_bad_records_are_never_saved(monkeypatch, candidate, field, value):
    candidate[field] = value
    _, save = prepare_collection(monkeypatch, candidate)
    products, report = live.collect_live_products("MacBook", DATABASE)
    assert products == [] and report["failed"] == 1
    save.assert_not_called()


def test_redirect_to_different_product_is_not_saved(monkeypatch, candidate):
    fetch, save = prepare_collection(monkeypatch, candidate)
    fetch.return_value = ("html", "https://www.bestbuy.com/product/other/OTHER")
    assert live.collect_live_products("MacBook", DATABASE)[0] == []
    save.assert_not_called()


def test_save_failure_keeps_fresh_results_and_reports_it(monkeypatch, candidate):
    _, save = prepare_collection(monkeypatch, candidate)
    save.side_effect = ValueError("secret details must not be echoed")
    products, report = live.collect_live_products("MacBook", DATABASE)
    assert len(products) == 1 and report["saved"] == 0
    assert report["status"] == "partial" and report["failed_saves"] == 1
    assert "secret details" not in str(report)


def test_failed_page_does_not_discard_later_success(monkeypatch, candidate):
    fetch, save = prepare_collection(monkeypatch, candidate, [URL, URL])
    fetch.side_effect = [ValueError("blocked"), ("html", URL)]
    products, report = live.collect_live_products("MacBook", DATABASE)
    assert len(products) == 1 and report["failed"] == 1 and report["saved"] == 1


def test_busy_collection_uses_catalog_fallback():
    assert live._collection_lock.acquire(blocking=False)
    try:
        products, report = live.collect_live_products("MacBook", DATABASE)
        assert products == [] and report["status"] == "busy"
    finally:
        live._collection_lock.release()


@pytest.mark.parametrize("title,category", [("Apple iPhone 15", "phones"),
    ("Sony WH1000XM5 Headphones", "headphones"), ("Apple MacBook Air", "laptops")])
def test_categories_are_based_on_collected_titles(title, category):
    assert live.infer_category(title) == category


def test_live_search_bypasses_old_catalog_and_invalidates_cache(monkeypatch, candidate):
    monkeypatch.setattr(api, "load_database_config", lambda: DATABASE)
    monkeypatch.setattr(api, "load_catalog", Mock(side_effect=AssertionError("must use this request's candidates")))
    collector = Mock(return_value=([candidate], {"saved": 1, "errors": [], "result_source": "live"}))
    monkeypatch.setattr(api, "collect_live_products", collector)
    api._catalog_cache["expires_at"] = float("inf")
    response = api.search_response("MacBook Air M5 24 GB RAM under $1200")
    assert response["products"][0]["product_url"] == URL
    assert api._catalog_cache["expires_at"] == 0
    assert "$1200" not in collector.call_args.args[0]
    assert "24" in collector.call_args.args[0]


def test_failed_collection_preserves_existing_catalog_search(monkeypatch, candidate):
    monkeypatch.setattr(api, "load_database_config", lambda: DATABASE)
    monkeypatch.setattr(api, "collect_live_products", lambda *a: ([], {"saved": 0, "errors": [], "result_source": "catalog"}))
    monkeypatch.setattr(api, "load_catalog", lambda *a: [candidate])
    assert api.search_response("MacBook")["collection"]["matched"] == 1


def test_model_expansion_cannot_leak_unrelated_catalog_records(monkeypatch, candidate):
    monkeypatch.setattr(api, "interpret_query", lambda *a: ["MacBook"])
    monkeypatch.setattr(api.requests, "get", Mock(side_effect=AssertionError("no global database read")))
    assert api.search_with_model_terms("study machine", DATABASE, candidate_products=[candidate])[0]["product_url"] == URL


def test_model_outage_does_not_lose_collected_data(monkeypatch, candidate):
    monkeypatch.setattr(api, "load_database_config", lambda: DATABASE)
    monkeypatch.setattr(api, "collect_live_products", lambda *a: ([candidate], {"saved": 1, "errors": [], "result_source": "live"}))
    monkeypatch.setattr(api, "interpret_query", Mock(side_effect=ValueError("model unavailable")))
    response = api.search_response("zzzzunknown")
    assert response["products"] == [] and response["collection"]["errors"]


def test_endpoint_returns_products_and_collection_status(monkeypatch, candidate):
    body = b'{"query":"MacBook M5"}'
    response = {"products": [candidate], "collection": {"status": "complete"}}
    search = Mock(return_value=response)
    monkeypatch.setattr(api, "search_response", search)
    handler = object.__new__(api.SearchHandler)
    handler.path = "/api/search"
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = BytesIO(body)
    handler.send_json = Mock()
    handler.do_POST()
    search.assert_called_once_with("MacBook M5")
    handler.send_json.assert_called_once_with(200, response)


def test_endpoint_rejects_empty_query_before_any_collection(monkeypatch):
    search = Mock()
    monkeypatch.setattr(api, "search_response", search)
    body = b'{"query":" "}'
    handler = object.__new__(api.SearchHandler)
    handler.path = "/api/search"
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = BytesIO(body)
    handler.send_json = Mock()
    handler.do_POST()
    search.assert_not_called()
    assert handler.send_json.call_args.args[0] == 400


def test_missing_dependency_reason_is_visible_and_specific(monkeypatch):
    monkeypatch.setattr(live, "discover_bestbuy_urls", Mock(side_effect=DiscoveryError(
        "missing_dependency", "Install curl_cffi in the backend environment."
    )))
    products, report = live.collect_live_products("MacBook", DATABASE)
    assert products == [] and report["failure_code"] == "missing_dependency"
    assert report["errors"] == ["Install curl_cffi in the backend environment."]


def test_missing_transport_never_silently_uses_another_downloader(monkeypatch):
    monkeypatch.setitem(sys.modules, "curl_cffi", None)
    get = Mock(side_effect=AssertionError("must not silently downgrade"))
    monkeypatch.setattr(discovery.requests, "get", get)
    with pytest.raises(DiscoveryError) as error:
        discovery._search_request(discovery.search_url("MacBook"), 12)
    assert error.value.code == "missing_dependency"
    get.assert_not_called()


def test_m5_search_never_returns_m4_even_if_description_mentions_m5(monkeypatch, candidate):
    monkeypatch.setattr(api, "load_database_config", lambda: DATABASE)
    wrong = {**candidate, "title": "Apple MacBook Air M4 24GB Memory", "description": "Compare with MacBook Air M5 24GB RAM"}
    monkeypatch.setattr(api, "interpret_query", Mock(side_effect=AssertionError("no need for model expansion")))
    assert api.search_products("MacBook Air M5 24 GB RAM", catalog=[wrong]) == []
    assert api.search_products("MacBook Air M5 24 GB RAM", catalog=[wrong, candidate])[0]["title"] == candidate["title"]


def test_unknown_chip_and_wrong_family_do_not_satisfy_explicit_request(candidate):
    wrong = {**candidate, "title": "MacBook Pro M5 24GB RAM"}
    unknown = {**candidate, "title": "MacBook Air 24GB RAM"}
    assert api.apply_identity_requirements("MacBook Air M5", [wrong, unknown, candidate]) == [candidate]


def test_ai_fallback_cannot_override_chip_requirement(monkeypatch, candidate):
    monkeypatch.setattr(api, "interpret_query", lambda *a: ["MacBook"])
    wrong = {**candidate, "title": "MacBook Air M4 24GB RAM"}
    assert api.search_with_model_terms("MacBook M5", DATABASE, candidate_products=[wrong], original_query="MacBook Air M5") == []


def test_memory_is_not_borrowed_from_other_variants(candidate):
    wrong = {**candidate, "title": "MacBook Air M5 16GB Memory", "description": "24GB RAM configurations also exist"}
    assert api.extract_memory_gb(wrong) == 16
    assert api.apply_memory_condition([wrong], {"minimum": 24}) == []


def test_discovery_query_collapses_memory_phrase(monkeypatch, candidate):
    monkeypatch.setattr(api, "load_database_config", lambda: DATABASE)
    collector = Mock(return_value=([candidate], {"saved": 1, "errors": [], "result_source": "live"}))
    monkeypatch.setattr(api, "collect_live_products", collector)
    api.search_response("MacBook Air M5 24 GB Ram")
    assert collector.call_args.args[0].lower() == "macbook air m5 24gb"


def test_missing_ollama_does_not_break_catalog_fallback(monkeypatch):
    monkeypatch.setattr(api, "load_database_config", lambda: DATABASE)
    monkeypatch.setattr(api, "load_catalog", lambda *a: [])
    monkeypatch.setattr(api, "collect_live_products", lambda *a: ([], {"saved": 0, "errors": [], "result_source": "catalog"}))
    monkeypatch.setattr(api, "interpret_query", Mock(side_effect=api.requests.ConnectionError("offline")))
    response = api.search_response("unknownconcept")
    assert response["products"] == []
    assert "Ollama" in response["collection"]["errors"][0]


def test_memory_mismatch_does_not_trigger_unnecessary_ai(monkeypatch, candidate):
    monkeypatch.setattr(api, "load_database_config", lambda: DATABASE)
    monkeypatch.setattr(api, "interpret_query", Mock(side_effect=AssertionError("no AI needed")))
    wrong = {**candidate, "title": "MacBook Air M5 16GB RAM"}
    assert api.search_products("MacBook Air M5 24GB RAM", catalog=[wrong]) == []


def test_discovery_combines_pages_and_deduplicates_product_aliases(monkeypatch):
    other = "https://www.bestbuy.com/product/other-macbook/OTHER15"
    def page(url, limit, timeout):
        if "15+inch" in url:
            return [URL, other]
        return [URL]
    monkeypatch.setattr(discovery, "_discover_page", page)
    assert discovery.discover_bestbuy_urls("MacBook Air M5 24GB") == [URL, other]


def test_discovery_does_not_expand_an_explicit_screen_size():
    pages = discovery.discovery_pages('MacBook Air M5 15-inch 24GB')
    assert not any("13+inch" in page for page in pages)
    assert len(pages) <= 5


def test_discovery_stops_at_requested_candidate_limit(monkeypatch):
    page = Mock(return_value=[URL])
    monkeypatch.setattr(discovery, "_discover_page", page)
    assert discovery.discover_bestbuy_urls("MacBook", limit=1) == [URL]
    page.assert_called_once()


def test_secondary_page_failure_preserves_primary_candidates(monkeypatch):
    def page(url, limit, timeout):
        if "cp=" in url:
            raise DiscoveryError("http_error", "HTTP 503")
        return [URL]
    monkeypatch.setattr(discovery, "_discover_page", page)
    assert discovery.discover_bestbuy_urls("MacBook") == [URL]


def test_primary_page_failure_does_not_fan_out(monkeypatch):
    page = Mock(side_effect=DiscoveryError("page_rejected", "verification page"))
    monkeypatch.setattr(discovery, "_discover_page", page)
    with pytest.raises(DiscoveryError):
        discovery.discover_bestbuy_urls("MacBook")
    page.assert_called_once()


def test_discovery_can_return_more_than_three_candidates(monkeypatch):
    urls = [f"https://www.bestbuy.com/product/synthetic/TEST{i}" for i in range(10)]
    monkeypatch.setattr(discovery, "_discover_page", lambda url, limit, timeout: urls[:limit])
    assert discovery.discover_bestbuy_urls("laptop") == urls[:8]


def test_multiple_live_records_flow_through_collection_and_spec_filters(monkeypatch, candidate):
    monkeypatch.setattr(api, "load_database_config", lambda: DATABASE)
    records = [
        {**candidate, "product_url": URL},
        {**candidate, "product_url": "https://www.bestbuy.com/product/other/OTHER15",
         "title": "MacBook Air 15-inch M5 24GB Memory 1TB SSD", "price": "1099.99"},
        {**candidate, "product_url": "https://www.bestbuy.com/product/wrong/WRONG16",
         "title": "MacBook Air M5 16GB Memory"},
        {**candidate, "product_url": "https://www.bestbuy.com/product/old/OLDM4",
         "title": "MacBook Air M4 24GB Memory"},
    ]
    by_url = {record["product_url"]: record for record in records}
    monkeypatch.setattr(live, "discover_bestbuy_urls", lambda *a, **kw: list(by_url))
    monkeypatch.setattr(live.tech_scraper, "fetch_page", lambda url, **kw: (url, url))
    monkeypatch.setattr(live.tech_scraper, "extract_product", lambda html, url: by_url[url])
    save = Mock()
    monkeypatch.setattr(live.tech_scraper, "upload_to_supabase", save)
    response = api.search_response("MacBook Air M5 24 GB RAM")
    assert {product["product_url"] for product in response["products"]} == {record["product_url"] for record in records[:2]}
    assert response["collection"]["matched"] == 2
    assert response["collection"]["saved"] == save.call_count == 4
