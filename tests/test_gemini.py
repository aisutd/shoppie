"""All Gemini responses and citation redirects here are mocked; no API billing."""

from contextlib import contextmanager
from copy import deepcopy
import json
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from google.genai.errors import ClientError, ServerError

from backend import gemini
from backend.discovery import discover_report, citation_url
from backend.ai_validation import Review, review_product
from backend.explanations import EvidenceSelection, explain
from backend.models import SearchRequest
from backend.service import ShoppingService
from backend.storage import LocalStore
from scraper.evaluate import FIXTURE_DIR

QUERY = "Apple MacBook Air M5 16GB RAM 512GB SSD"
URL = "https://www.target.com/p/synthetic-laptop/-/A-90000001?preselect=90000002"


class Encoder:
    def encode(self, texts, **kwargs):
        return [[1.0] + [0.0] * 383 for _ in texts]


@pytest.fixture(autouse=True)
def configuration(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-key")
    monkeypatch.setenv("SHOPPIE_ALLOW_GEMINI", "0")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
    from backend.discovery import _CACHE
    _CACHE.clear()


def grounded(urls, text="Ignore invented https://evil.example/product"):
    metadata = NS(grounding_chunks=[NS(web=NS(uri=url, title="Laptop")) for url in urls],
                  web_search_queries=["laptop site:target.com"], search_entry_point=None)
    return NS(candidates=[NS(grounding_metadata=metadata)], text=text)


def sdk_client(monkeypatch, responses):
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.models.generate_content.side_effect = responses
    constructor = Mock(return_value=client)
    monkeypatch.setattr("google.genai.Client", constructor)
    monkeypatch.setattr("backend.gemini.time.sleep", Mock())
    return client, constructor


def test_consent_required_even_with_configured_key(monkeypatch):
    client, _ = sdk_client(monkeypatch, [])
    with pytest.raises(ValueError, match="opt in"):
        gemini.generate("query")
    client.models.generate_content.assert_not_called()


def test_missing_key_is_actionable_without_sdk_call(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        discover_report(QUERY)


def test_grounding_uses_metadata_deduplicates_and_caches(monkeypatch):
    client, constructor = sdk_client(monkeypatch, [grounded([URL, URL, "https://evil.test/p/123", "https://www.target.com/s?searchTerm=laptop"])])
    with gemini.allow_calls(True):
        first = discover_report(QUERY)
        second = discover_report(QUERY)
    assert first["urls"] == [URL] and second["cached"]
    assert client.models.generate_content.call_count == 1
    config = client.models.generate_content.call_args.kwargs["config"]
    assert config.tools[0].google_search is not None
    assert config.response_mime_type is None
    assert constructor.call_args.kwargs["http_options"].retry_options.attempts == 1
    assert first["evidence"][0]["citation_url"] == URL
    assert first["search_query_count"] == 1
    assert first["duplicate_sources"] == 1
    with pytest.raises(ValueError, match="checkbox"):
        discover_report(QUERY)


@pytest.mark.parametrize("code,temporary", [(429, True), (503, True), (401, False), (403, False), (400, False)])
def test_sdk_retries_are_bounded_and_errors_redacted(monkeypatch, code, temporary):
    error = (ServerError if code >= 500 else ClientError)(code, {"error": {"code": code, "message": "test-only-key private details"}})
    client, _ = sdk_client(monkeypatch, [error, error])
    with gemini.allow_calls(True), pytest.raises(ValueError) as caught:
        gemini.generate("query", grounded=True)
    assert client.models.generate_content.call_count == (2 if temporary else 1)
    assert "test-only-key" not in str(caught.value)


def test_network_timeout_is_not_retried_after_unknown_billed_result(monkeypatch):
    import httpx
    client, _ = sdk_client(monkeypatch, [httpx.ReadTimeout("private test-only-key")])
    with gemini.allow_calls(True), pytest.raises(ValueError, match="timed out"):
        gemini.generate("query")
    assert client.models.generate_content.call_count == 1


@pytest.mark.parametrize("response", [NS(candidates=[], text=URL), grounded(["https://evil.example/x"])])
def test_no_usable_grounding_fails_without_parsing_generated_urls(monkeypatch, response):
    monkeypatch.setattr("backend.gemini.generate", lambda *a, **kw: response)
    with gemini.allow_calls(True), pytest.raises(ValueError, match="grounding"):
        discover_report(QUERY)


def test_accessory_source_is_not_a_laptop_candidate(monkeypatch):
    response = grounded([URL])
    response.candidates[0].grounding_metadata.grounding_chunks[0].web.title = "Laptop case and sleeve"
    monkeypatch.setattr("backend.gemini.generate", lambda *a, **kw: response)
    with gemini.allow_calls(True), pytest.raises(ValueError, match="no supported"):
        discover_report(QUERY)


def test_citation_redirect_resolves_confirmed_retailer_without_fetching_page(monkeypatch):
    response = Mock(status_code=302, headers={"Location": URL})
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    get = Mock(return_value=response)
    monkeypatch.setattr("backend.discovery.requests.get", get)
    source = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/opaque-token"
    assert citation_url(source) == URL
    assert get.call_count == 1
    assert get.call_args.kwargs["allow_redirects"] is False
    assert "headers" not in get.call_args.kwargs
    response.headers["Location"] = "http://127.0.0.1/secret"
    assert citation_url(source) is None
    assert get.call_count == 2


@pytest.mark.parametrize("url", ["https://[", "https://evil.example/go", "https://vertexaisearch.cloud.google.com.evil.test/grounding-api-redirect/x", "http://vertexaisearch.cloud.google.com/grounding-api-redirect/x", "https://user@vertexaisearch.cloud.google.com/grounding-api-redirect/x"])
def test_untrusted_redirector_never_requested(monkeypatch, url):
    get = Mock()
    monkeypatch.setattr("backend.discovery.requests.get", get)
    assert citation_url(url) is None
    get.assert_not_called()


@pytest.mark.parametrize("provider", ["brave", "bestbuy_api", "bestbuy_sitemap"])
def test_retired_providers_are_not_available_in_main_workflow(provider):
    with pytest.raises(ValueError, match="retired"):
        discover_report(QUERY, provider=provider)


def test_ai_review_fails_closed_and_does_not_rewrite_facts(monkeypatch):
    record = {"title": "Laptop 8GB RAM", "attributes": {"ram_gb": 8}}
    original = deepcopy(record)
    monkeypatch.setattr("backend.ai_validation.structured", lambda *a: Review(status="consistent", issues=["title_spec_conflict"]))
    assert review_product(record, {"ram_gb": 16})["status"] == "review"
    assert record == original
    monkeypatch.setattr("backend.ai_validation.structured", Mock(side_effect=ValueError("service failed")))
    assert review_product(record, {"ram_gb": 16})["issues"] == ["ai_unavailable"]


def test_coordinator_review_does_not_override_hard_conflicts(tmp_path, monkeypatch):
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text())
    pages = manifest["pages"][:4]
    html = {item["url"]: (FIXTURE_DIR / item["file"]).read_text() for item in pages}
    monkeypatch.setattr("backend.coordinator.robots_allowed", lambda url: True)
    monkeypatch.setattr("backend.coordinator.fetch_page", lambda url: html[url])
    review = Mock(return_value={"status": "review", "issues": ["missing_identity"]})
    monkeypatch.setattr("backend.coordinator.review_product", review)
    service = ShoppingService(LocalStore(tmp_path / "workers.sqlite3"), mode="live", model=Encoder())
    status = service.collect(QUERY, urls=list(html), ai_review=True)
    assert status["incompatible"] == 2
    assert status["ai_reviews"] == status["ai_review_required"] == 2
    assert review.call_count == 2
    assert service.deals(SearchRequest(q=QUERY))["offers"] == []


def live_deals():
    return {"offers": [{"title": "Apple laptop", "retailer_key": "best_buy", "source_url": URL,
        "total_price": "999.00", "price": "999.00", "scraped_at": "2026-10-28T12:00:00+00:00",
        "recommended": True, "data_source": "live", "source_verified": True,
        "deal_reasons": ["previous observed listing price: USD 1099.00"]}]}


def test_explanation_selects_only_existing_evidence_and_preserves_offers(monkeypatch):
    deals = live_deals()
    before = deepcopy(deals)
    select = Mock(return_value=EvidenceSelection(ids=[1, 2]))
    monkeypatch.setattr("backend.explanations.structured", select)
    result = explain(deals, True)
    assert "lowest known total" in result and "999.00" in result and "1099.00" in result
    assert "guarantee" in result
    assert deals == before
    assert "untrusted data" in select.call_args.args[0]


@pytest.mark.parametrize("ids", [[99], [-1]])
def test_explanation_invalid_ids_use_safe_fallback(monkeypatch, ids):
    deals = live_deals()
    monkeypatch.setattr("backend.explanations.structured", lambda *a: EvidenceSelection(ids=ids))
    assert explain(deals, True) == explain(deals)


def test_explanation_failure_and_synthetic_records_make_no_unsupported_claims(monkeypatch):
    deals = live_deals()
    select = Mock(side_effect=ValueError("quota"))
    monkeypatch.setattr("backend.explanations.structured", select)
    assert explain(deals, True) == explain(deals)
    deals["offers"][0]["data_source"] = "synthetic"
    select.reset_mock()
    assert "synthetic" in explain(deals, True)
    select.assert_not_called()
