"""Product-bound price recovery; no network or credentials."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scraper import bestbuy_search as search
from scraper import live_search as live


URL = 'https://www.bestbuy.com/product/synthetic-24-inch-monitor/TEST24'
OTHER = 'https://www.bestbuy.com/product/other-monitor/OTHER'

@pytest.fixture(autouse=True)
def disable_walmart_by_default(monkeypatch):
    monkeypatch.setattr(
        live,
        "discover_walmart_products",
        lambda *args, **kwargs: [],
    )


def card(url=URL, price='$129.99', title='Synthetic 24-inch 160Hz Monitor'):
    return f'''<div class="product-list-item-sv">
    <a class="product-list-item-link" href="{url}">{title}</a>
    <template id="B:a"></template><div>Loading...</div></div>
    <div hidden id="S:a"><div data-testid="price-block-customer-price">
    <span class="sr-only">{price}</span><span aria-hidden="true">129 99</span>
    </div></div><script>$RC("B:a","S:a")</script>'''


def test_streamed_price_stays_with_its_card():
    records = search.parse_search_cards(card() + '<div data-testid="price-block-customer-price"><span class="sr-only">$999.99</span></div>')
    assert list(records) == [URL]
    assert records[URL]['price'] == '129.99'


def test_explicit_regular_price_is_kept_only_when_higher():
    html = card().replace(
        '</div></div><script>',
        '</div><div data-testid="price-block-regular-price">'
        '<span class="sr-only">$159.99</span></div></div><script>',
    )
    assert search.parse_search_cards(html)[URL]['regular_price'] == '159.99'

    not_discounted = html.replace('$159.99', '$99.99')
    assert search.parse_search_cards(not_discounted)[URL]['regular_price'] is None


def test_unlinked_fragment_is_not_product_price():
    assert search.parse_search_cards(card().replace('$RC("B:a","S:a")', '')) == {}


@pytest.mark.parametrize('price', ['$10/month', '$129 - $199', 'Save $20', '$NaN', '$129.999'])
def test_ambiguous_or_financing_prices_are_rejected(price):
    assert search.parse_search_cards(card(price=price)) == {}


def test_missing_price_never_uses_other_card():
    html = card().replace('data-testid="price-block-customer-price"', 'data-testid="price-block-regular-price"')
    html += '<div data-testid="price-block-customer-price"><span class="sr-only">$9.99</span></div>'
    assert search.parse_search_cards(html) == {}


def test_different_product_is_rejected_even_if_it_matches_specs(monkeypatch):
    monkeypatch.setattr(search, '_search_request', lambda *a: SimpleNamespace(status_code=200, headers={'Content-Type': 'text/html'}, text=card(OTHER)))
    with pytest.raises(ValueError, match='exact listing'):
        search.recover_search_card(URL)


def test_recovery_uses_model_keywords_and_validates_identity(monkeypatch):
    get = Mock(return_value=SimpleNamespace(status_code=200, headers={'Content-Type': 'text/html'}, text=card()))
    monkeypatch.setattr(search, '_search_request', get)
    assert search.recover_search_card(URL)['price'] == '129.99'
    assert get.call_args.args[0].endswith('st=synthetic+24+inch+monitor')


def test_variant_query_must_agree(monkeypatch):
    monkeypatch.setattr(search, '_search_request', lambda *a: SimpleNamespace(status_code=200, headers={'Content-Type': 'text/html'}, text=card()))
    with pytest.raises(ValueError):
        search.recover_search_card(URL + '?variant=other')


def test_transport_failure_recovers_and_saves_validated_card(monkeypatch):
    monkeypatch.setattr(live, 'discover_bestbuy_urls', lambda *a, **kw: [URL])
    monkeypatch.setattr(live.tech_scraper, 'fetch_page', Mock(side_effect=ValueError('Page request failed or timed out: HTTP/2 stream error')))
    monkeypatch.setattr(live, 'recover_search_card', lambda *a, **kw: search.parse_search_cards(card())[URL])
    save = Mock()
    monkeypatch.setattr(live.tech_scraper, 'upload_to_supabase', save)
    products, report = live.collect_live_products('monitor', object())
    assert len(products) == report['recovered'] == report['saved'] == 1
    assert products[0]['category'] == 'monitors'
    assert save.call_args.args[0]['price'] == '129.99'


@pytest.mark.parametrize('error', ['Retailer returned a bot check or access-denied page. Stop here.', 'Retailer returned HTTP 403; no record collected.'])
def test_http_rejection_and_challenges_are_not_retried(monkeypatch, error):
    monkeypatch.setattr(live, 'discover_bestbuy_urls', lambda *a, **kw: [URL])
    monkeypatch.setattr(live.tech_scraper, 'fetch_page', Mock(side_effect=ValueError(error)))
    fallback = Mock(side_effect=AssertionError('must stop'))
    monkeypatch.setattr(live, 'recover_search_card', fallback)
    assert live.collect_live_products('monitor', object())[0] == []
    fallback.assert_not_called()
