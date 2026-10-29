"""Combined pipeline checks use synthetic records, mocked fetches, and no services."""

import json
from unittest.mock import Mock
import pytest
from bs4 import BeautifulSoup

from scraper import scraper
from scraper.ai_scraper_agent import run_ecommerce_agent
from scraper.embeddings import generate_product_embedding
from scraper.validator import validate_record
from scraper.evaluate import FIXTURE_DIR

URL = 'https://www.target.com/p/synthetic/-/A-90000001'


def embedded(items):
    data = {'props': {'dehydratedState': {'queries': [{'state': {'data': {'data': {'layout': {'zones': [{'module_groups': [{'modules': [{'module_data': {'data_by_tcin': items}}]}]}]}}}}}]}}}
    return '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(data) + '</script>'


def test_selected_target_fields_need_explicit_currency_and_stock():
    html = embedded([{'tcin': 90000001, 'title': 'Example laptop 16GB RAM 512GB SSD', 'price': {'current_retail': '999.00'}, 'fulfillment': {'shipping': {}}}])
    record = scraper.extract_product(html, URL)
    assert record['price'] == '999.00'
    assert record['currency'] is record['availability'] is None
    with pytest.raises(ValueError):
        validate_record(record)


def test_selected_target_price_does_not_leak_from_another_variant():
    html = embedded([{'tcin': '90000002', 'title': 'Other laptop', 'price': {'current_retail': 1, 'currency': 'USD'}},
                     {'tcin': '90000001', 'title': 'Example laptop', 'price': {'current_retail': '999.00', 'currency': 'USD'}, 'availability': 'InStock'}])
    product = validate_record(scraper.extract_product(html, URL))
    assert str(product.price) == '999.00' and product.currency == 'USD'
    assert product.availability == 'InStock'


def test_conflicting_target_prices_fail_closed():
    html = embedded([{'tcin': '90000001', 'price': {'current_retail': value}} for value in [1, 999]])
    with pytest.raises(ValueError, match='conflicting'):
        scraper.extract_product(html, URL)


def test_throttling_remembers_denial_without_retry(monkeypatch):
    get = Mock(return_value=Mock(status_code=429))
    monkeypatch.setattr(scraper.requests, 'get', get)
    with pytest.raises(scraper.BlockError):
        scraper.fetch_page(URL)
    with pytest.raises(scraper.BlockError):
        scraper.fetch_page(URL)
    assert get.call_count == 1


@pytest.mark.parametrize('availability', ['in_stock', 'in stock', 'https://schema.org/InStock'])
def test_availability_aliases_retain_full_backend_contract(availability):
    record = scraper.extract_product((FIXTURE_DIR / '01_bestbuy.html').read_text(), 'https://www.bestbuy.com/product/synthetic-macbook-air/SYNTH001')
    record['availability'] = availability
    product = validate_record(record)
    assert product.availability == 'InStock' and product.attributes['ram_gb'] == 16


def test_compatibility_embedding_uses_shared_normalized_model():
    model = Mock()
    model.encode.return_value = [[2.0] + [0.0] * 383]
    result = generate_product_embedding({'title': 'Example laptop', 'model': 'TEST-MODEL', 'attributes': {'ram_gb': 16}}, model)
    assert len(result) == 384 and result[0] == 1
    assert 'TEST-MODEL' in model.encode.call_args.args[0][0]


def test_ollama_failure_is_optional_and_makes_no_fetches():
    client = Mock()
    client.chat.side_effect = ConnectionError('not running')
    service = Mock()
    result = run_ecommerce_agent('Example laptop', [URL], service, client)
    assert result['stage'] == 'unavailable'
    service.collect.assert_not_called()


def test_ollama_cannot_invent_candidate_urls():
    client = Mock()
    client.chat.return_value = {'message': {'content': json.dumps({'urls': ['http://localhost/private']})}}
    service = Mock()
    assert run_ecommerce_agent('Laptop', [URL], service, client)['stage'] == 'unavailable'
    service.collect.assert_not_called()


def test_ollama_delegates_to_existing_workers():
    client = Mock()
    client.chat.return_value = {'message': {'content': json.dumps({'urls': [URL]})}}
    service = Mock(mode='live', storage='local')
    service.collect.return_value = {'stage': 'ready'}
    service.deals.return_value = {'offers': []}
    result = run_ecommerce_agent('Example laptop', [URL], service, client)
    service.collect.assert_called_once_with('Example laptop', urls=[URL], browser=True)
    assert result['results'] == {'offers': []}
