"""Mocked live-path checks: all offers below are isolated synthetic test responses."""

from copy import deepcopy
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from backend.access import robots_permit
from backend.coordinator import collect, robots_allowed
from backend.legacy_discovery import discover_report, sitemap_locations, bestbuy_api_urls
from backend.models import SearchRequest
from backend.service import ShoppingService
from backend.storage import LocalStore
from db.embeddings import index_store
from scraper.envelope import listing_from_product
from scraper.evaluate import FIXTURE_DIR
from scraper.scraper import extract_product, extract_specs
from scraper.validator import validate_record

QUERY = "Apple MacBook Air M5 16GB RAM 512GB SSD"


class Encoder:
    def encode(self, texts, **kwargs):
        return [[1.0] + [0.0] * 383 for text in texts]


@pytest.fixture
def pages():
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text())
    return [(item["url"], (FIXTURE_DIR / item["file"]).read_text()) for item in manifest["pages"]]


@pytest.fixture
def live(tmp_path, monkeypatch, pages):
    monkeypatch.setattr("backend.coordinator.robots_allowed", lambda url: True)
    html = dict(pages)
    monkeypatch.setattr("backend.coordinator.fetch_page", lambda url: html[url])
    return ShoppingService(LocalStore(tmp_path / "isolated-live.sqlite3"), mode="live", model=Encoder())


def test_collection_counts_validation_and_configuration_separately(live, pages):
    urls = [pages[index][0] for index in (0, 1, 2, 7, 0)]
    status = live.collect(QUERY, urls=urls)
    assert status["discovered"] == status["attempted"] == status["fetched"] == status["extracted"] == 4
    assert status["duplicate_urls"] == 1
    assert status["accepted"] == 3 and status["invalid_records"] == 1
    assert status["compatible"] == 2 and status["incompatible"] == 1
    assert status["saved"] == 2 and status["incorrect_data_rate"] is None
    result = live.deals(SearchRequest(q=QUERY))
    assert [row["total_price"] for row in result["offers"]] == ["999.00", "1049.00"]
    assert all(row["source_verified"] for row in result["offers"])
    assert all(row["collection_run_id"] == status["run_id"] for row in result["offers"])
    # this proves mocked plumbing only, not a real two-retailer milestone
    assert result["live_two_retailer_milestone"]


def test_failed_new_collection_cannot_claim_old_offers_as_current_run(live, pages, monkeypatch):
    live.collect(QUERY, urls=[pages[0][0], pages[1][0]])
    monkeypatch.setattr("backend.coordinator.robots_allowed", lambda url: False)
    status = live.collect(QUERY, urls=[pages[0][0]])
    assert status["attempted"] == 0 and status["skipped"] == 1
    assert status["acceptance_rate"] is None
    result = live.deals(SearchRequest(q=QUERY))
    assert len(result["offers"]) == 2
    assert not result["live_two_retailer_milestone"]
    assert result["latest_collection_stage"] == "failed"


def test_synthetic_and_unverified_records_are_never_verified_live(live, pages):
    for index in (0, 1):
        row = listing_from_product(validate_record(extract_product(pages[index][1], pages[index][0])))
        row["raw"]["data_source"] = "synthetic" if index == 0 else "live"
        live.store.ingest(row)
    index_store(live.store, live.model)
    result = live.deals(SearchRequest(q=QUERY))
    assert len(result["results"]) == 1
    assert result["results"][0]["verification_status"] == "unverified"
    assert result["offers"] == [] and not result["live_two_retailer_milestone"]


def test_unavailable_without_price_replaces_older_in_stock_observation(live, pages, monkeypatch):
    live.collect(QUERY, urls=[pages[0][0]])
    product = json.loads(pages[0][1].split('<script type="application/ld+json">')[1].split('</script>')[0])
    product["offers"].update(price=None, priceCurrency=None, availability="https://schema.org/OutOfStock")
    html = '<script type="application/ld+json">' + json.dumps(product) + '</script>'
    monkeypatch.setattr("backend.coordinator.fetch_page", lambda url: html)
    status = live.collect(QUERY, urls=[pages[0][0]])
    assert status["accepted"] == status["unavailable"] == status["nonpriced_unavailable"] == 1
    assert status["invalid_records"] == 0
    row = live.store.listings()[0]
    assert row["price"] is None and row["availability"] == "out_of_stock"
    assert len(live.store.history(row["id"])) == 2
    assert live.deals(SearchRequest(q=QUERY))["offers"] == []


def test_skipped_invalid_urls_and_blocked_retailers_are_not_fetch_attempts(live, pages, monkeypatch):
    monkeypatch.setattr("backend.coordinator.robots_allowed", lambda url: False)
    status = live.collect(QUERY, urls=[pages[0][0], pages[0][0], "http://localhost/private"])
    assert status["attempted"] == status["failed_scrapes"] == status["invalid_records"] == 0
    assert status["skipped"] == status["invalid_urls"] == status["duplicate_urls"] == 1
    assert status["average_seconds_per_page"] is None


def test_page_permission_is_required_before_robots_network_request(monkeypatch, pages):
    monkeypatch.delenv("SHOPPIE_PAGE_RETAILERS", raising=False)
    network = Mock()
    monkeypatch.setattr("backend.coordinator.fetch_robots", network)
    assert not robots_allowed(pages[0][0])
    network.assert_not_called()
    monkeypatch.setenv("SHOPPIE_PAGE_RETAILERS", "bestbuy")
    network.return_value = "User-agent: *\nDisallow: /product/*"
    assert not robots_allowed(pages[0][0])


def test_robots_wildcards_longest_rule_and_specific_agent():
    text = "User-agent: *\nDisallow: /*?secret=*$\nAllow: /product/allowed\nUser-agent: ShoppieClassroom\nDisallow: /private/*\nAllow: /private/public$"
    assert not robots_permit(text, "https://www.bestbuy.com/private/secret")
    assert robots_permit(text, "https://www.bestbuy.com/private/public")
    assert robots_permit(text, "https://www.bestbuy.com/product/example?secret=1")
    assert not robots_permit("User-agent: *\nDisallow: /*?secret=*$", "https://www.bestbuy.com/product/example?secret=1")


def test_sitemap_discovery_is_bounded_and_keeps_only_real_returned_urls(monkeypatch, pages):
    root = "https://sitemaps.bestbuy.com/sitemaps_pdp.xml"
    child = "https://sitemaps.bestbuy.com/sitemaps_pdp.0000.xml.gz"
    urls = [pages[0][0], pages[0][0], "https://evil.example/product/laptop", "https://www.bestbuy.com/product/television/TV123"]
    index = ('<sitemapindex><sitemap><loc>' + child + '</loc></sitemap></sitemapindex>').encode()
    data = ('<urlset>' + ''.join('<url><loc>'+url+'</loc></url>' for url in urls) + '</urlset>').encode()
    monkeypatch.setattr("backend.legacy_discovery.fetch_robots", lambda origin: "User-agent: *\nAllow: /\nSitemap: " + root)
    get = Mock(side_effect=lambda url: index if url == root else gzip.compress(data))
    monkeypatch.setattr("backend.legacy_discovery.read_public", get)
    result = discover_report("Apple MacBook Air", provider="bestbuy_sitemap")
    assert result["urls"] == [pages[0][0]]
    assert result["documents_read"] == 2 and get.call_count == 2


def test_denied_sitemap_host_is_not_bypassed(monkeypatch):
    def robots(origin):
        if origin == "https://www.bestbuy.com":
            return "Sitemap: https://sitemaps.bestbuy.com/sitemaps_pdp.xml"
        raise ValueError("Robots request returned HTTP 403")
    monkeypatch.setattr("backend.legacy_discovery.fetch_robots", robots)
    get = Mock()
    monkeypatch.setattr("backend.legacy_discovery.read_public", get)
    with pytest.raises(ValueError, match="403"):
        discover_report("MacBook", provider="bestbuy_sitemap")
    get.assert_not_called()


@pytest.mark.parametrize("data", [b'<html>Access denied</html>', b'<!DOCTYPE a><urlset/>', b'<urlset>'])
def test_sitemap_invalid_or_unsafe_xml_rejects(data):
    with pytest.raises(ValueError):
        sitemap_locations(data)


def test_bestbuy_api_has_safe_search_and_secret_redaction(monkeypatch, pages):
    monkeypatch.setenv("BESTBUY_API_KEY", "DO-NOT-PRINT-THIS")
    response = Mock(status_code=200)
    response.json.return_value = {"products": [{"url":pages[0][0]}]}
    get = Mock(return_value=response)
    monkeypatch.setattr("backend.legacy_discovery.requests.get", get)
    assert bestbuy_api_urls('MacBook)&salePrice<1', 2) == [pages[0][0]]
    assert "salePrice<1" not in get.call_args.args[0]
    assert get.call_args.kwargs["allow_redirects"] is False
    response.status_code = 429
    with pytest.raises(ValueError) as caught:
        bestbuy_api_urls("MacBook", 2)
    assert "DO-NOT-PRINT-THIS" not in str(caught.value)


def test_bestbuy_api_resolves_documented_pdp_links_without_forwarding_key(monkeypatch, pages):
    monkeypatch.setenv("BESTBUY_API_KEY", "secret")
    result = Mock(status_code=200)
    result.json.return_value = {"products":[{"url":"https://api.bestbuy.com/click/token123/1234567/pdp"}]}
    link = Mock(status_code=302, headers={"Location":pages[0][0]})
    link.__enter__ = Mock(return_value=link)
    link.__exit__ = Mock(return_value=False)
    get = Mock(side_effect=[result, link])
    monkeypatch.setattr("backend.legacy_discovery.requests.get", get)
    assert bestbuy_api_urls("MacBook", 1) == [pages[0][0]]
    assert "params" not in get.call_args.kwargs
    assert get.call_args.kwargs["allow_redirects"] is False


def test_conflicting_cpu_options_and_ddr_memory_are_handled():
    assert extract_specs("Example laptop 16GB DDR5 RAM 512GB SSD")["ram_gb"] == 16
    with pytest.raises(ValueError, match="CPU"):
        extract_specs("MacBook laptop Apple M4 or Apple M5 16GB RAM 512GB SSD")
    with pytest.raises(ValueError, match="multiple configurations"):
        extract_specs("Laptop 8GB/16GB RAM 512GB SSD")


def test_conflicting_model_and_availability_reject(pages):
    html = pages[0][1]
    with pytest.raises(ValueError, match="model"):
        extract_product('<meta property="product:model" content="WRONG-MODEL">'+html, pages[0][0])
    with pytest.raises(ValueError, match="availability"):
        extract_product('<meta property="product:availability" content="https://schema.org/OutOfStock">'+html, pages[0][0])


def test_unavailable_bad_price_still_rejects_and_stock_price_is_required(pages):
    record = extract_product(pages[0][1], pages[0][0])
    record["price"] = None
    with pytest.raises(ValueError):
        validate_record(record, allow_unavailable=True)
    record.update(availability="https://schema.org/OutOfStock", price="not a price")
    with pytest.raises(ValueError):
        validate_record(record, allow_unavailable=True)


def test_existing_real_capture_remains_missing_price_not_a_live_offer():
    folder = Path(__file__).resolve().parents[1] / "scraper/tests/fixtures"
    metadata = json.loads((folder / "target_1004661132_2026-10-14.json").read_text())
    record = extract_product((folder / "target_1004661132_2026-10-14.html").read_text(), metadata["source_url"])
    assert record["title"].startswith("Lenovo Legion 5")
    assert record["price"] is None and record["currency"] is None
    with pytest.raises(ValueError):
        validate_record(record, allow_unavailable=True)


def test_unavailable_conflicting_listing_does_not_remove_valid_deals(live, pages):
    from backend.deals import rank_deals
    live.collect(QUERY, urls=[pages[0][0], pages[1][0]])
    offers = live.deals(SearchRequest(q=QUERY))["offers"]
    unavailable = deepcopy(offers[0])
    unavailable.update(id="unavailable-test", model_number="OTHER-MODEL", availability="out_of_stock")
    result = rank_deals(offers + [unavailable], live.store, require_verified=True)
    assert len(result["offers"]) == 2
    assert result["excluded"] == [{"id":"unavailable-test", "reason":"not explicitly in stock"}]


def test_storage_failure_is_not_counted_as_invalid_source_data(live, pages, monkeypatch):
    def unavailable_store(row):
        raise RuntimeError("isolated test database unavailable")
    monkeypatch.setattr(live.store, "ingest", unavailable_store)
    status = live.collect(QUERY, urls=[pages[0][0]])
    assert status["stage"] == "failed" and status["accepted"] == 1
    assert status["storage_failures"] == 1
    assert status["invalid_records"] == status["failed_scrapes"] == 0


@pytest.mark.parametrize("payload", [[], {"raw":{"data_source":[], "verification":[]}}])
def test_malformed_source_metadata_requires_review(payload):
    from backend.provenance import source_evidence
    result = source_evidence({"raw_payload":payload})
    assert result["verification_status"] == "unverified" and not result["source_verified"]
