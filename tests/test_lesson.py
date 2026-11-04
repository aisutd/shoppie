"""Synthetic parser/unit cases only. These are NOT real retailer observations."""

import json
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from lesson import __main__ as cli
from lesson.database import save_product
from lesson.extract import extract_product
from lesson.pages import identify_product
from lesson.validate import Laptop


URLS = [
    "https://www.amazon.com/dp/B0DZDC3WW5",
    "https://www.bestbuy.com/product/example-laptop/TEST123",
    "https://www.target.com/p/example-laptop/-/A-12345678",
    "https://www.walmart.com/ip/12345678",
]


def page(source_url, **offer_changes):
    offer = {"@type": "Offer", "price": "123.45", "priceCurrency": "USD"}
    offer.update(offer_changes)
    product = {"@type": "Product", "name": "Synthetic test laptop", "url": source_url, "offers": offer}
    return '<script type="application/ld+json">' + json.dumps(product) + '</script>'


@pytest.mark.parametrize("url", URLS)
def test_all_four_retailers_use_explicit_offer(url):
    product = Laptop.model_validate(extract_product(page(url), url))
    assert str(product.price) == "123.45"
    assert product.currency == "USD"
    assert product.availability is None
    assert product.discount is None


@pytest.mark.parametrize("changes", [
    {"price": None}, {"price": ""}, {"price": "NaN"}, {"price": "Infinity"},
    {"price": "-1"}, {"price": "0"}, {"price": True}, {"price": "123.456"},
    {"priceCurrency": None}, {"priceCurrency": "$"}, {"priceCurrency": "CAD"},
    {"availability": "probably available"},
])
def test_missing_or_invalid_commerce_fields_reject(changes):
    with pytest.raises(ValidationError):
        Laptop.model_validate(extract_product(page(URLS[0], **changes), URLS[0]))


@pytest.mark.parametrize("availability", ["InStock", "https://schema.org/OutOfStock"])
def test_availability_comes_from_explicit_field(availability):
    result = Laptop.model_validate(extract_product(page(URLS[0], availability=availability), URLS[0]))
    assert result.availability == availability.rsplit("/", 1)[-1]


def test_aggregate_price_is_not_an_exact_offer():
    with pytest.raises(ValueError, match="exact Offer"):
        extract_product(page(URLS[0], **{"@type": "AggregateOffer", "lowPrice": "100"}), URLS[0])


def test_related_product_or_offer_cannot_supply_price():
    with pytest.raises(ValueError, match="main Product"):
        extract_product(page(URLS[1]), URLS[0])
    with pytest.raises(ValueError, match="different product"):
        extract_product(page(URLS[0], url=URLS[1]), URLS[0])


def test_multiple_offers_are_rejected():
    product = {"@type": "Product", "name": "Synthetic laptop", "offers": [
        {"@type": "Offer", "price": "100", "priceCurrency": "USD"},
        {"@type": "Offer", "price": "200", "priceCurrency": "USD"},
    ]}
    with pytest.raises(ValueError, match="exact Offer"):
        extract_product('<script type="application/ld+json">' + json.dumps(product) + '</script>', URLS[0])


def test_recommendation_not_searched_for_prices():
    html = '<h1>Synthetic laptop</h1><aside>Related laptop $199.00</aside>'
    candidate = extract_product(html, URLS[2])
    assert candidate["price"] is None
    assert candidate["currency"] is None


def test_amazon_dollar_symbol_alone_does_not_mean_usd():
    html = '''<span id="productTitle">Synthetic laptop</span>
      <div id="corePrice_feature_div"><span class="a-price"><span class="a-offscreen">$123.45</span></span></div>'''
    candidate = extract_product(html, URLS[0])
    assert candidate["price"] == "123.45"
    assert candidate["currency"] is None


@pytest.mark.parametrize("url", [
    "http://www.amazon.com/dp/B0DZDC3WW5", "https://amazon.com.evil.test/dp/B0DZDC3WW5",
    "https://www.target.com/c/laptops", "https://name:password@www.walmart.com/ip/123",
])
def test_unsupported_urls_reject(url):
    with pytest.raises(ValueError):
        identify_product(url)


def test_bot_challenge_rejects_even_if_status_was_200():
    with pytest.raises(ValueError, match="bot check"):
        extract_product('<title>Robot Check</title>' + page(URLS[0]), URLS[0])


def test_accessories_reject():
    candidate = extract_product(page(URLS[0]), URLS[0])
    candidate["title"] = "Laptop replacement charger"
    with pytest.raises(ValidationError):
        Laptop.model_validate(candidate)


def test_default_cli_never_calls_database(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["lesson", "--url", URLS[0]])
    monkeypatch.setattr(cli, "fetch_page", lambda url: page(url))
    save = Mock(side_effect=AssertionError("Must not write"))
    monkeypatch.setattr("lesson.database.save_product", save)
    assert cli.main() == 0
    save.assert_not_called()
    assert "Extraction only" in capsys.readouterr().out


def test_invalid_candidate_never_calls_database_even_with_save(monkeypatch):
    monkeypatch.setattr("sys.argv", ["lesson", "--url", URLS[0], "--save"])
    monkeypatch.setattr(cli, "fetch_page", lambda url: page(url, price=None))
    save = Mock(side_effect=AssertionError("Must not write"))
    monkeypatch.setattr("lesson.database.save_product", save)
    assert cli.main() == 1
    save.assert_not_called()


def test_save_is_explicit_and_sends_only_validated_data(monkeypatch):
    monkeypatch.setattr("sys.argv", ["lesson", "--url", URLS[0], "--save"])
    monkeypatch.setattr(cli, "fetch_page", lambda url: page(url))
    save = Mock()
    monkeypatch.setattr("lesson.database.save_product", save)
    assert cli.main() == 0
    assert isinstance(save.call_args.args[0], Laptop)


def test_local_html_cannot_be_saved(monkeypatch):
    monkeypatch.setattr("sys.argv", ["lesson", "--url", URLS[0], "--html", "anything.html", "--save"])
    with pytest.raises(SystemExit):
        cli.main()


def test_database_auth_and_payload_do_not_print_credentials(monkeypatch, capsys):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_SYNTHETIC")
    monkeypatch.setattr("builtins.input", lambda prompt: "synthetic@example.test")
    monkeypatch.setattr("getpass.getpass", lambda prompt: "SYNTHETIC_PASSWORD")
    login = Mock(status_code=200)
    login.json.return_value = {"access_token": "SYNTHETIC_TOKEN"}
    post = Mock(side_effect=[login, Mock(status_code=201)])
    monkeypatch.setattr("lesson.database.requests.post", post)
    save_product(Laptop.model_validate(extract_product(page(URLS[0]), URLS[0])))
    payload = post.call_args_list[1].kwargs["json"]
    assert payload["price"] == "123.45"
    assert "submitted_by" not in payload
    assert "SYNTHETIC" not in capsys.readouterr().out


def test_admin_key_is_refused(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_secret_SYNTHETIC")
    with pytest.raises(ValueError, match="never use"):
        save_product(Laptop.model_validate(extract_product(page(URLS[0]), URLS[0])))


@pytest.mark.parametrize("url,selector", [
    (URLS[1], 'data-testid="customer-price"'),
    (URLS[2], 'data-test="product-price"'),
    (URLS[3], 'itemprop="price"'),
])
def test_retailer_main_price_selector_needs_explicit_currency(url, selector):
    html = f'<h1>Synthetic laptop</h1><span {selector}>$123.45</span>'
    candidate = extract_product(html, url)
    assert candidate["price"] == "123.45"
    assert candidate["currency"] is None
    html += '<meta itemprop="priceCurrency" content="USD">'
    assert Laptop.model_validate(extract_product(html, url)).currency == "USD"


def test_selected_amazon_variant_must_match_requested_asin():
    html = '<input id="ASIN" value="OTHERASIN1">' + page(URLS[0])
    with pytest.raises(ValueError, match="different ASIN"):
        extract_product(html, URLS[0])


def test_script_mention_of_bot_route_is_not_a_challenge():
    html = '<script>const route = "validatecaptcha";</script>' + page(URLS[0])
    assert Laptop.model_validate(extract_product(html, URLS[0])).price > 0


def test_credentials_are_not_echoed_if_terminal_cannot_hide_input(monkeypatch):
    import getpass
    import warnings
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_SYNTHETIC")
    monkeypatch.setattr("builtins.input", lambda prompt: "synthetic@example.test")
    def unsafe_terminal(prompt):
        warnings.warn("Cannot hide input", getpass.GetPassWarning)
        raise AssertionError("Must stop before fallback input")
    monkeypatch.setattr("getpass.getpass", unsafe_terminal)
    with pytest.raises(ValueError, match="Hidden password"):
        save_product(Laptop.model_validate(extract_product(page(URLS[0]), URLS[0])))
