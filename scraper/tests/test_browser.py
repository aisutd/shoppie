"""Browser readiness with synthetic HTML; no retailer requests."""

from unittest.mock import Mock

import pytest
from playwright import sync_api

from scraper.scraper import fetch_rendered_page


URL = "https://www.target.com/p/example-laptop/-/A-12345678"
READY = '''<main><h1>Example laptop</h1>
<span data-test="product-price">US$999.99</span></main>'''


@pytest.fixture
def browser_page(monkeypatch):
    page = Mock(url=URL)
    page.goto.return_value = Mock(status=200)
    browser = Mock()
    browser.new_page.return_value = page
    launcher = Mock()
    launcher.chromium.launch.return_value.__enter__ = Mock(return_value=browser)
    launcher.chromium.launch.return_value.__exit__ = Mock(return_value=False)
    manager = Mock()
    manager.__enter__ = Mock(return_value=launcher)
    manager.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(sync_api, "sync_playwright", lambda: manager)
    return page


def test_waits_for_product_fields_then_returns_matching_snapshot(browser_page):
    browser_page.content.side_effect = ["<h1>Example laptop</h1>", READY]
    assert fetch_rendered_page(URL) == READY
    browser_page.wait_for_timeout.assert_called_once_with(2000)


def test_ready_product_returns_without_fixed_delay(browser_page):
    browser_page.content.return_value = READY
    assert fetch_rendered_page(URL) == READY
    browser_page.wait_for_timeout.assert_not_called()


def test_incomplete_product_has_bounded_failure(browser_page):
    browser_page.content.return_value = "<h1>Example laptop</h1>"
    with pytest.raises(ValueError, match="readiness timed out; missing price, currency"):
        fetch_rendered_page(URL)
    assert browser_page.content.call_count == 10
    assert browser_page.wait_for_timeout.call_count == 9


@pytest.mark.parametrize("html,message", [
    ("<h1>Verify you are human</h1>", "bot check"),
    ("<h1>There was a temporary issue</h1>", "temporary product-data issue"),
])
def test_challenge_or_source_error_stops_immediately(browser_page, html, message):
    browser_page.content.return_value = html
    with pytest.raises(ValueError, match=message):
        fetch_rendered_page(URL)
    browser_page.wait_for_timeout.assert_not_called()


def test_redirect_rejects_even_with_complete_fields(browser_page):
    browser_page.url = URL + "?preselect=99999999"
    browser_page.content.return_value = READY
    with pytest.raises(ValueError, match="redirected away"):
        fetch_rendered_page(URL)
    browser_page.wait_for_timeout.assert_not_called()
