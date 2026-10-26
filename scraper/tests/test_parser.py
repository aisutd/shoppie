"""Explicit offers, main-product identity, and safe HTTP behavior."""

import json
from hashlib import sha256
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from scraper.scraper import extract_product, fetch_page, identify_product
from scraper.validator import validate_record


FIXTURES = Path(__file__).parent / "fixtures"


def test_real_target_embedded_title_is_selected_without_fabricated_price():
    html = (FIXTURES / "target_91122087_embedded_2026-10-14.html").read_text(encoding="utf-8")
    record = extract_product(html, "https://www.target.com/p/macbook/-/A-91122087")
    assert record["title"] == "Apple MacBook Neo (A18 Pro, 2026) Laptop with Touch ID - 512GB, Citrus"
    assert record["price"] is None and record["currency"] is None
    other = extract_product(html, "https://www.target.com/p/other/-/A-91122081")
    assert other["title"] is None


def test_unscoped_recommendation_microdata_cannot_supply_main_price():
    html = '''<h1>Example laptop</h1>
    <section aria-label="Recommended accessory">
    <meta itemprop="price" content="19.99">
    <meta itemprop="priceCurrency" content="USD">
    </section>'''
    record = extract_product(html, "https://www.walmart.com/ip/12345678")
    assert record["price"] is None
    assert record["currency"] is None
    with pytest.raises(ValidationError):
        validate_record(record)


def test_recommendation_product_metadata_cannot_supply_main_price():
    html = '''<main><h1>Example laptop</h1></main>
    <aside><meta property="product:price:amount" content="19.99">
    <meta property="product:price:currency" content="USD"></aside>'''
    record = extract_product(html, URLS[2])
    assert record["price"] is None and record["currency"] is None


def test_target_named_price_is_scoped_to_main_content():
    html = '''<aside><span data-test="product-price">US$19.99</span></aside>
    <main><h1 data-test="product-title">Example laptop</h1>
    <span data-test="product-price">US$999.99</span></main>'''
    record = extract_product(html, URLS[2])
    assert record["price"] == "999.99" and record["currency"] == "USD"


def test_main_head_metadata_remains_supported():
    html = '''<html><head><meta property="product:price:amount" content="999.99">
    <meta property="product:price:currency" content="USD"></head>
    <body><main><h1>Example laptop</h1></main></body></html>'''
    assert str(validate_record(extract_product(html, URLS[2])).price) == "999.99"


def test_conflicting_main_prices_are_unknown():
    html = '''<main><h1>Example laptop</h1>
    <span data-test="product-price">US$999.99</span>
    <span data-test="product-price">US$19.99</span></main>'''
    assert extract_product(html, URLS[2])["price"] is None


def test_target_preselect_identifies_child_without_removing_query():
    from scraper.scraper import clean_url
    url = "https://www.target.com/p/apple-macbook-neo-a18-pro-2026-laptop/-/A-95288385?preselect=91122087"
    assert identify_product(url) == ("target", "91122087")
    assert clean_url(url) == url
    html = '<link rel="canonical" href="https://www.target.com/p/selected-laptop/-/A-91122087"><h1>Selected laptop</h1>'
    record = extract_product(html, url)
    assert record["product_id"] == "91122087"
    assert record["price"] is None and record["currency"] is None


@pytest.mark.parametrize("query", ["preselect=", "preselect=bad", "preselect=1&preselect=2"])
def test_ambiguous_target_preselect_rejects(query):
    with pytest.raises(ValueError, match="exactly one"):
        identify_product("https://www.target.com/p/laptop/-/A-95288385?" + query)
URLS = [
    "https://www.amazon.com/dp/B0DZD91W4F",
    "https://www.bestbuy.com/product/synthetic-test-laptop/TEST123",
    "https://www.target.com/p/synthetic-test-laptop/-/A-12345678",
    "https://www.walmart.com/ip/12345678",
]


def page(url, **changes):
    offer = {"@type": "Offer", "price": "123.45", "priceCurrency": "USD"}
    offer.update(changes)
    product = {"@type": "Product", "name": "Synthetic test laptop", "url": url, "offers": offer}
    return '<script type="application/ld+json">' + json.dumps(product) + '</script>'


@pytest.mark.parametrize("url", URLS)
def test_four_retailer_urls_and_explicit_offers(url):
    product = validate_record(extract_product(page(url), url))
    assert product.retailer == identify_product(url)[0]
    assert str(product.price) == "123.45"


def test_fixture_reads_exact_product_offer():
    candidate = extract_product((FIXTURES / "synthetic_product.html").read_text(), URLS[1])
    assert candidate["price"] == "123.45"
    assert candidate["availability"] == "https://schema.org/InStock"


def test_recommendation_does_not_replace_missing_price():
    candidate = extract_product((FIXTURES / "missing_price.html").read_text(), URLS[2])
    assert candidate["price"] is None
    assert candidate["currency"] is None


def test_bot_check_rejects():
    with pytest.raises(ValueError, match="bot check"):
        extract_product((FIXTURES / "bot_check.html").read_text(), URLS[0])


def test_wrong_product_and_aggregate_offer_reject():
    with pytest.raises(ValueError, match="main Product"):
        extract_product(page(URLS[1]), URLS[0])
    with pytest.raises(ValueError, match="exact Offer"):
        extract_product(page(URLS[0], **{"@type": "AggregateOffer", "lowPrice": "100"}), URLS[0])


def test_relative_canonical_and_offer_urls():
    product = {"@type": "Product", "name": "Synthetic laptop", "url": "/ip/12345678",
               "offers": {"@type": "Offer", "url": "/ip/12345678", "price": "123.45", "priceCurrency": "USD"}}
    html = '<link rel="canonical" href="/ip/12345678"><script type="application/ld+json">' + json.dumps(product) + '</script>'
    assert validate_record(extract_product(html, URLS[3])).product_id == "12345678"


def response(status, location=None):
    return Mock(status_code=status, headers={"Content-Type": "text/html", "Location": location}, text=page(URLS[3]))


def test_same_product_redirect_can_expand_a_short_url(monkeypatch):
    get = Mock(side_effect=[response(307, "/ip/synthetic-test-laptop/12345678"), response(200)])
    monkeypatch.setattr("scraper.scraper.requests.get", get)
    assert "Synthetic test laptop" in fetch_page(URLS[3])
    assert get.call_args.args[0].endswith("/ip/synthetic-test-laptop/12345678")
    assert get.call_args.kwargs["allow_redirects"] is False


@pytest.mark.parametrize("destination", [
    "https://www.walmart.com/ip/99999999",
    "https://evil.test/ip/12345678", "http://www.walmart.com/ip/12345678",
])
def test_redirect_cannot_change_product_or_retailer(monkeypatch, destination):
    get = Mock(return_value=response(307, destination))
    monkeypatch.setattr("scraper.scraper.requests.get", get)
    with pytest.raises(ValueError, match="Redirect left"):
        fetch_page(URLS[3])
    assert get.call_count == 1


def test_redirect_loop_is_bounded(monkeypatch):
    get = Mock(return_value=response(307, URLS[3]))
    monkeypatch.setattr("scraper.scraper.requests.get", get)
    with pytest.raises(ValueError, match="Too many"):
        fetch_page(URLS[3])
    assert get.call_count == 4


def test_selected_amazon_asin_cannot_change():
    with pytest.raises(ValueError, match="different ASIN"):
        extract_product('<input id="ASIN" value="OTHERASIN1">' + page(URLS[0]), URLS[0])


def test_bare_dollar_is_not_a_currency_code():
    html = '<h1>Synthetic laptop</h1><span data-test="product-price">$123.45</span>'
    candidate = extract_product(html, URLS[2])
    assert candidate["price"] == "123.45"
    assert candidate["currency"] is None


def test_dated_real_target_capture_extracts_verified_source_fields():
    path = FIXTURES / "target_1004661132_2026-10-14.html"
    metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    assert metadata["captured_on"] == "2026-10-14"
    # Universal-newline text keeps the checksum stable on Windows Git checkouts.
    assert sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest() == metadata["fixture_sha256"]
    candidate = extract_product(path.read_text(encoding="utf-8"), metadata["source_url"])
    for field, expected in metadata["expected_source_fields"].items():
        assert candidate[field] == expected
    assert candidate["title"].startswith("Lenovo Legion 5 15.1")
    assert candidate["product_id"] == "1004661132"
    # This real capture is incomplete; do not pretend it is an accepted live-price record.
    with pytest.raises(ValidationError) as error:
        validate_record(candidate)
    assert {issue["loc"] for issue in error.value.errors()} == {("price",), ("currency",)}


def test_saved_missing_product_fixture_has_clear_field_rejections():
    candidate = extract_product((FIXTURES / "missing_product_information.html").read_text(), URLS[1])
    with pytest.raises(ValidationError) as error:
        validate_record(candidate)
    assert {issue["loc"] for issue in error.value.errors()} == {("title",), ("price",), ("currency",)}


@pytest.mark.parametrize("filename,message", [
    ("multiple_offers.html", "Expected one exact Offer"),
    ("ambiguous_variants.html", "Cannot safely identify one main Product"),
])
def test_saved_ambiguous_sources_reject_clearly(filename, message):
    with pytest.raises(ValueError, match=message):
        extract_product((FIXTURES / filename).read_text(), URLS[1])


def test_saved_offer_without_commerce_fields_has_no_fabricated_defaults():
    candidate = extract_product((FIXTURES / "missing_offer_fields.html").read_text(), URLS[1])
    for field in ("price", "currency", "availability", "seller", "discount"):
        assert candidate[field] is None
    with pytest.raises(ValidationError) as error:
        validate_record(candidate)
    assert {issue["loc"] for issue in error.value.errors()} == {("price",), ("currency",)}
