"""Transport/stage diagnostics must never publish exception payloads."""
import json
from unittest.mock import Mock

import pytest
import requests
from playwright.sync_api import Error, TimeoutError as BrowserTimeout

from scraper import main, scraper
from scraper.diagnostics import ScraperFailure, browser_failure, request_failure
from scraper.tests.test_browser import browser_page  # Reuse the offline Playwright fixture.

URL = "https://www.bestbuy.com/product/synthetic-laptop/TEST123"


@pytest.mark.parametrize("error,category", [
    (requests.ConnectionError("ConnectionResetError(10054) SECRET"), "connection_reset"),
    (requests.ReadTimeout("SECRET"), "request_timeout"),
    (requests.ConnectionError("DNS SECRET"), "dns_or_connection_error"),
])
def test_request_categories_are_sanitized(monkeypatch, error, category):
    monkeypatch.setattr(scraper.requests, "get", Mock(side_effect=error))
    with pytest.raises(ScraperFailure) as caught:
        scraper.fetch_page(URL)
    assert caught.value.category == category
    assert "SECRET" not in caught.value.detail
    assert "SECRET" not in str(caught.value)


@pytest.mark.parametrize("error,operation,category", [
    (Error("SECRET net::ERR_HTTP2_PROTOCOL_ERROR https://secret"), "navigation", "browser_navigation_error"),
    (BrowserTimeout("SECRET"), "navigation", "browser_navigation_timeout"),
    (Error("SECRET"), "launch", "browser_launch_error"),
    (Error("Page has been closed SECRET"), "readiness", "page_closed"),
])
def test_browser_categories_are_sanitized(error, operation, category):
    actual, detail = browser_failure(error, operation)
    assert actual == category
    assert "SECRET" not in detail and "https://secret" not in detail
    if "HTTP2" in str(error):
        assert "ERR_HTTP2_PROTOCOL_ERROR" in detail


@pytest.mark.parametrize("status,location,category", [
    (503, None, "http_status_error"),
    (302, "https://www.bestbuy.com/product/other/OTHER123", "redirect_identity_mismatch"),
])
def test_http_status_and_redirect_diagnostics(monkeypatch, status, location, category):
    monkeypatch.setattr(scraper.requests, "get", Mock(return_value=Mock(
        status_code=status, headers={"Location": location}, text="")))
    with pytest.raises(ScraperFailure) as caught:
        scraper.fetch_page(URL)
    assert caught.value.category == category


@pytest.mark.parametrize("html,category,stage", [
    ("<h1>Verify you are human</h1>", "challenge_or_access_denied", "fetch"),
    ("<h1>Synthetic laptop</h1>", "validation_failed", "validation"),
    ('<script type="application/ld+json">{"@type":"Product","name":"Synthetic laptop","offers":[]}</script>',
     "extraction_failed", "extraction"),
])
def test_cli_stage_diagnostics(monkeypatch, capsys, html, category, stage):
    monkeypatch.setattr(scraper, "fetch_page", lambda url: html)
    assert main.main(["--http-only", "--url", URL]) == 1
    output = capsys.readouterr().out
    detail = json.loads(next(line.removeprefix("DIAGNOSTIC: ") for line in output.splitlines()
                             if line.startswith("DIAGNOSTIC: ")))
    assert detail["failure_category"] == category
    assert detail["failure_stage"] == stage


@pytest.mark.parametrize("error,category", [
    (Error("Page.goto: net::ERR_HTTP2_PROTOCOL_ERROR SECRET"), "browser_navigation_error"),
    (BrowserTimeout("SECRET"), "browser_navigation_timeout"),
])
def test_real_fetch_wrapper_preserves_navigation_category(browser_page, error, category):
    browser_page.goto.side_effect = error
    with pytest.raises(ScraperFailure) as caught:
        scraper.fetch_rendered_page(browser_page.url)
    assert caught.value.category == category
    assert "SECRET" not in caught.value.detail
    browser_page.content.assert_not_called()


def test_browser_readiness_category(browser_page):
    browser_page.content.return_value = "<h1>Synthetic laptop</h1>"
    with pytest.raises(ScraperFailure) as caught:
        scraper.fetch_rendered_page(browser_page.url)
    assert caught.value.category == "readiness_timeout"
    assert browser_page.content.call_count == 10
    assert browser_page.wait_for_timeout.call_count == 9


def test_browser_internal_extraction_stage(browser_page):
    browser_page.content.return_value = '<script type="application/ld+json">{"@type":"Product","offers":[]}</script>'
    with pytest.raises(ScraperFailure) as caught:
        scraper.fetch_rendered_page(browser_page.url)
    assert caught.value.category == "extraction_failed"
    assert caught.value.stage == "extraction"
    browser_page.wait_for_timeout.assert_not_called()
