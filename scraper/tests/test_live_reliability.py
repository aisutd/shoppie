"""Conservative live retrieval behavior, using offline captured/synthetic HTML."""
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from playwright import sync_api
from playwright.sync_api import Error

from scraper import main, scraper
from scraper.diagnostics import ScraperFailure
from scraper.tests.test_browser import browser_page
from scraper.validator import validate_record

URL = "https://www.amazon.com/dp/B0GR6KJ72L"
FIXTURES = Path(__file__).with_name("fixtures")


def amazon_page(price='<span class="a-offscreen">$689.00</span>'):
    return ('<main><input id="ASIN" value="B0GR6KJ72L"><span id="productTitle">Apple MacBook laptop</span>'
            '<div id="corePrice_feature_div"><span class="a-price">' + price + '</span></div></main>')


@pytest.mark.parametrize("asin,price", [("B0GR6935ZS", "1364.00"), ("B0GR6KJ72L", "689.00")])
def test_captured_amazon_price_and_identity(asin, price):
    html = (FIXTURES / f"amazon_{asin}_2026-10-26_excerpt.html").read_text(encoding="utf-8")
    product = validate_record(scraper.extract_product(html, f"https://www.amazon.com/dp/{asin}"))
    assert product.product_id == asin and str(product.price) == price
    assert product.currency == "USD" and product.availability == "InStock"
    if asin == "B0GR6KJ72L":
        assert (product.brand, product.model, product.cpu) == ("Apple", "MHFH4LL/A", "Apple A18 Pro")
        assert (product.ram, product.storage, product.screen_size, product.color) == ("8 GB", "256 GB", "13 inches", "Blush")
        assert product.condition is None


def test_amazon_bare_dollar_is_explicit_us_price_but_plain_number_is_not():
    assert validate_record(scraper.extract_product(amazon_page(), URL)).currency == "USD"
    record = scraper.extract_product(amazon_page('<span class="a-offscreen">689.00</span>'), URL)
    assert record["price"] == "689.00" and record["currency"] is None
    with pytest.raises(ValueError):
        validate_record(record)


def test_blank_accessibility_text_uses_explicit_price_parts():
    html = amazon_page('<span class="a-offscreen"> </span><span class="a-price-symbol">$</span>'
                       '<span class="a-price-whole">1,234<span class="a-price-decimal">.</span></span>'
                       '<span class="a-price-fraction">50</span>')
    product = validate_record(scraper.extract_product(html, URL))
    assert str(product.price) == "1234.50" and product.currency == "USD"


def test_list_price_and_accessory_price_cannot_replace_main_offer():
    html = amazon_page().replace('</div>', '<span class="a-price a-text-price"><span class="a-offscreen">$999.00</span></span></div>')
    html = html.replace('</main>', '<aside><span class="a-price"><span class="a-offscreen">$19.99</span></span></aside></main>')
    assert str(validate_record(scraper.extract_product(html, URL)).price) == "689.00"


@pytest.mark.parametrize("extra", [
    '<span class="a-price"><span class="a-offscreen">$19.99</span></span>',
    '<span class="a-price"><span class="a-offscreen">$57.42 per month</span></span>',
])
def test_conflicting_or_installment_main_prices_are_rejected(extra):
    with pytest.raises(ValueError):
        scraper.extract_product(amazon_page().replace('</div>', extra + '</div>'), URL)


@pytest.mark.parametrize("start,end,allowed", [
    (URL + '?sr=8-3&ref_=abc', 'https://www.amazon.com/name/dp/B0GR6KJ72L', True),
    ('https://www.walmart.com/ip/19715756171?utm_source=example', 'https://www.walmart.com/ip/laptop/19715756171', True),
    (URL, 'https://www.amazon.com/dp/B0GR6935ZS', False),
    (URL + '?condition=used', URL, False),
    (URL + '?seller=one', URL + '?seller=two', False),
    (URL + '?currency=CAD', URL, False),
    ('https://www.target.com/p/laptop/-/A-95288385?preselect=91122087',
     'https://www.target.com/p/laptop/-/A-95288385?preselect=91122088', False),
    ('https://www.target.com/p/laptop/-/A-95288385?preselect=91122087',
     'https://www.target.com/p/laptop/-/A-91122087', True),
    ('https://www.target.com/p/laptop/-/A-95288385?preselect=91122087',
     'https://www.target.com/p/laptop/-/A-95288385', False),
])
def test_redirects_preserve_selection(start, end, allowed):
    assert scraper.same_requested_product(start, end) == allowed


def test_http_tracking_redirect_is_followed(monkeypatch):
    get = Mock(side_effect=[Mock(status_code=302, headers={"Location": URL}),
                            Mock(status_code=200, headers={"Content-Type": "text/html"}, text=amazon_page())])
    monkeypatch.setattr(scraper.requests, "get", get)
    assert scraper.fetch_page(URL + '?sr=8-3') == amazon_page()
    assert get.call_count == 2


def test_walmart_challenge_redirect_is_terminal(monkeypatch):
    get = Mock(return_value=Mock(status_code=302, headers={"Location": "https://www.walmart.com/blocked?url=redacted"}))
    monkeypatch.setattr(scraper.requests, "get", get)
    browser = Mock(side_effect=AssertionError("Do not bypass a challenge"))
    monkeypatch.setattr(scraper, "fetch_rendered_page", browser)
    result = main.collect_live("https://www.walmart.com/ip/19715756171", "validate", Mock())
    assert result["error"].category == "challenge_or_access_denied"
    assert get.call_count == 1
    browser.assert_not_called()


@pytest.mark.parametrize("failure", [
    ScraperFailure("Request timed out", "request_timeout"),
    ScraperFailure("Connection reset", "connection_reset"),
    '<h1>Incomplete dynamic page</h1>',
    '<script type="application/ld+json">{"@type":"Product","offers":[]}</script>',
])
def test_default_collect_recovers_once(monkeypatch, failure):
    http = Mock(side_effect=failure) if isinstance(failure, Exception) else Mock(return_value=failure)
    browser = Mock(return_value=amazon_page())
    monkeypatch.setattr(scraper, "fetch_page", http)
    monkeypatch.setattr(scraper, "fetch_rendered_page", browser)
    events = []
    session = Mock()
    result = main.collect_live(URL, "validate", session, emit=events.append)
    assert result["error"] is None and result["product"].product_id == "B0GR6KJ72L"
    assert [e["mode"] for e in events] == ["http", "browser"]
    assert events[0]["fallback"] and not events[1]["fallback"]
    http.assert_called_once_with(URL)
    browser.assert_called_once_with(URL, session)


@pytest.mark.parametrize("failure", [
    ScraperFailure("Wrong product redirect", "redirect_identity_mismatch"),
    amazon_page().replace('value="B0GR6KJ72L"', 'value="B0GR6935ZS"'),
    amazon_page().replace('Apple MacBook laptop', 'Laptop charger'),
    amazon_page().replace('$689.00', 'CAD 689.00'),
])
def test_terminal_bad_data_never_becomes_an_accept(monkeypatch, failure):
    monkeypatch.setattr(scraper, "fetch_page", Mock(side_effect=failure) if isinstance(failure, Exception) else Mock(return_value=failure))
    browser = Mock(return_value=amazon_page())
    monkeypatch.setattr(scraper, "fetch_rendered_page", browser)
    result = main.collect_live(URL, "validate", Mock())
    assert result["product"] is None and result["error"] is not None
    browser.assert_not_called()


def test_main_automatic_fallback_is_the_default(monkeypatch, capsys):
    monkeypatch.setattr(scraper, "fetch_page", lambda url: '<h1>Incomplete page</h1>')
    browser = Mock(return_value=amazon_page())
    monkeypatch.setattr(scraper, "fetch_rendered_page", browser)
    assert main.main(["--url", URL]) == 0
    assert browser.call_count == 1
    assert 'validated=1, rejected=0' in capsys.readouterr().out


def test_browser_protocol_retry_is_bounded_and_closes_pages(browser_page):
    browser_page.goto.side_effect = [Error("net::ERR_HTTP2_PROTOCOL_ERROR"), Mock(status=200)]
    browser_page.content.return_value = '<main><h1>Example laptop</h1><span data-test="product-price">US$999.99</span></main>'
    scraper.fetch_rendered_page(browser_page.url)
    assert browser_page.goto.call_count == 2
    assert browser_page.close.call_count == 2


def test_browser_repeated_protocol_failure_stops_after_one_retry(browser_page):
    browser_page.goto.side_effect = Error("net::ERR_HTTP2_PROTOCOL_ERROR")
    with pytest.raises(ScraperFailure, match="Browser load failed"):
        scraper.fetch_rendered_page(browser_page.url)
    assert browser_page.goto.call_count == 2


def test_batch_reuses_browser_and_closes_each_page(browser_page, monkeypatch):
    manager = sync_api.sync_playwright()
    factory = Mock(return_value=manager)
    monkeypatch.setattr(sync_api, "sync_playwright", factory)
    browser_page.content.return_value = '<main><h1>Example laptop</h1><span data-test="product-price">US$999.99</span></main>'
    with scraper.BrowserSession() as session:
        scraper.fetch_rendered_page(browser_page.url, session)
        scraper.fetch_rendered_page(browser_page.url, session)
    assert factory.call_count == 1
    assert browser_page.close.call_count == 2


def test_invalid_url_never_fetches_or_launches_browser(monkeypatch):
    http, browser = Mock(), Mock()
    monkeypatch.setattr(scraper, "fetch_page", http)
    monkeypatch.setattr(scraper, "fetch_rendered_page", browser)
    with pytest.raises(ValueError):
        main.collect_live("https://example.com/not-a-product", "validate", Mock())
    http.assert_not_called()
    browser.assert_not_called()


def test_wrong_jsonld_product_never_browser_falls_back(monkeypatch):
    html = '<script type="application/ld+json">' + json.dumps(dict(
        **{"@type": "Product"}, name="Other laptop", url="https://www.amazon.com/dp/B0GR6935ZS")) + '</script>'
    monkeypatch.setattr(scraper, "fetch_page", lambda url: html)
    browser = Mock()
    monkeypatch.setattr(scraper, "fetch_rendered_page", browser)
    result = main.collect_live(URL, "validate", Mock())
    assert result["error"].category == "invalid_product_identity"
    browser.assert_not_called()


def test_matching_jsonld_and_displayed_price_can_complete_missing_currency():
    product = {"@type": "Product", "name": "Apple MacBook laptop", "url": URL,
               "offers": {"@type": "Offer", "price": 689.0}}
    html = amazon_page() + '<script type="application/ld+json">' + json.dumps(product) + '</script>'
    assert validate_record(scraper.extract_product(html, URL)).currency == "USD"
    product["offers"]["price"] = "799.00"
    with pytest.raises(ValueError, match="prices disagree"):
        scraper.extract_product(amazon_page() + '<script type="application/ld+json">' + json.dumps(product) + '</script>', URL)


def test_optional_jsonld_specifications_are_explicit_and_conflicts_unknown():
    product = {"@type": "Product", "name": "Apple MacBook laptop", "url": URL,
               "brand": {"@type": "Brand", "name": "Apple"}, "model": "Example model", "color": "Blue",
               "additionalProperty": [{"name": "RAM", "value": 16, "unitText": "GB"},
                                      {"name": "CPU Model", "value": "Apple M5"},
                                      {"name": "Storage", "value": "512 GB"},
                                      {"name": "Storage", "value": "1 TB"}],
               "offers": {"@type": "Offer", "price": "689.00", "priceCurrency": "USD",
                          "itemCondition": "https://schema.org/NewCondition"}}
    record = scraper.extract_product('<script type="application/ld+json">' + json.dumps(product) + '</script>', URL)
    result = validate_record(record)
    assert (result.brand, result.model, result.cpu, result.ram) == ("Apple", "Example model", "Apple M5", "16 GB")
    assert result.storage is None and result.screen_size is None
    assert result.condition == "NewCondition"


def test_amazon_optional_specs_do_not_use_wrong_asin_or_recommendations():
    html = amazon_page().replace('</main>', '''
      <div id="productOverview_feature_div" data-csa-c-asin="B0GR6935ZS">
        <table><tr><td>Brand</td><td>Wrong brand</td></tr></table></div>
      <aside><table id="productDetails_techSpec_section_1"><tr><th>CPU Model</th><td>Accessory CPU</td></tr></table></aside>
      </main>''')
    result = validate_record(scraper.extract_product(html, URL))
    assert result.brand is None and result.cpu is None


@pytest.mark.parametrize("active,expected,condition", [("new", "1149.00", "NewCondition"), ("used", "1080.06", "UsedCondition")])
def test_only_explicitly_selected_new_or_used_offer_supplies_price(active, expected, condition):
    html = '<main><input id="ASIN" value="B0GR6KJ72L"><span id="productTitle">Apple MacBook laptop</span><div id="buyBoxAccordion">'
    for name, amount, label in [("new", "1149.00", "Buy New"), ("used", "1080.06", "Used - Very Good")]:
        selected = name == active
        html += (f'<div data-a-accordion-row-name="{name}AccordionRow" class="{"a-accordion-active" if selected else ""}">'
                 f'<div class="a-accordion-row" aria-expanded="{str(selected).lower()}"><h5>{label}</h5></div>'
                 f'<div id="corePrice_feature_div" data-csa-c-asin="B0GR6KJ72L"><span class="a-price apex-pricetopay-value">'
                 f'<span class="a-offscreen">${amount}</span></span></div></div>')
    html += '</div>'
    for name, amount in [("new", "1149.00"), ("used", "1080.06")]:
        html += (f'<div id="apex_desktop_{name}AccordionRow" style="{"" if active == name else "display:none;"}">'
                 f'<div id="corePriceDisplay_desktop_feature_div"><span class="a-price priceToPay">'
                 f'<span class="a-offscreen">${amount}</span></span></div></div>')
    result = validate_record(scraper.extract_product(html + '</main>', URL))
    assert str(result.price) == expected and result.condition == condition


def test_hidden_offer_availability_cannot_contaminate_main_offer():
    html = amazon_page().replace('</main>', '<div hidden><div id="availability"><span class="primary-availability-message">In Stock</span></div></div></main>')
    assert scraper.extract_product(html, URL)["availability"] is None


def test_jsonld_cannot_supply_another_offer_condition():
    product = {"@type": "Product", "name": "Apple MacBook laptop", "url": URL,
               "offers": {"@type": "Offer", "price": "689.00", "priceCurrency": "USD",
                          "itemCondition": "https://schema.org/NewCondition"}}
    html = amazon_page() + '''<div id="buyBoxAccordion"><div data-a-accordion-row-name="usedAccordionRow" class="a-accordion-active">
      <div class="a-accordion-row" aria-expanded="true"><h5>Used - Very Good</h5></div></div></div>'''
    with pytest.raises(ScraperFailure, match="condition does not match"):
        scraper.extract_product(html + '<script type="application/ld+json">' + json.dumps(product) + '</script>', URL)


def test_hidden_form_input_with_title_id_does_not_erase_visible_title():
    html = amazon_page().replace('</main>', '<input type="hidden" id="productTitle" value="form data"></main>')
    assert validate_record(scraper.extract_product(html, URL)).title == "Apple MacBook laptop"


@pytest.mark.parametrize("url", ["https://www.amazon.com/checkpoint/continue?token=SECRET",
                                 "https://www.walmart.com/blocked?token=SECRET"])
def test_checkpoint_routes_are_terminal_without_publishing_tokens(url):
    with pytest.raises(ScraperFailure) as caught:
        scraper.check_checkpoint_url(url)
    assert caught.value.category == "challenge_or_access_denied"
    assert "SECRET" not in str(caught.value) and "SECRET" not in caught.value.detail


def test_explicit_browser_mode_does_not_fetch_http(monkeypatch):
    http, browser = Mock(), Mock(return_value=amazon_page())
    monkeypatch.setattr(scraper, "fetch_page", http)
    monkeypatch.setattr(scraper, "fetch_rendered_page", browser)
    assert main.collect_live(URL, "validate", Mock(), browser=True)["product"] is not None
    http.assert_not_called()
    assert browser.call_count == 1


def test_http_only_does_not_launch_browser_for_incomplete_data(monkeypatch):
    monkeypatch.setattr(scraper, "fetch_page", lambda url: '<h1>Incomplete</h1>')
    browser = Mock()
    monkeypatch.setattr(scraper, "fetch_rendered_page", browser)
    assert main.collect_live(URL, "validate", Mock(), http_only=True)["error"] is not None
    browser.assert_not_called()


def test_keep_html_preserves_a_fetched_page_even_when_validation_rejects(monkeypatch, tmp_path):
    html = '<h1>Incomplete dynamic product page</h1>'
    monkeypatch.setattr(main.config, "SCRIPT_DIR", tmp_path)
    monkeypatch.setattr(scraper, "fetch_page", lambda url: html)
    assert main.main(["--url", URL, "--http-only", "--keep-html"]) == 1
    assert (tmp_path / "data/pages/amazon-B0GR6KJ72L.html").read_text(encoding="utf-8") == html
