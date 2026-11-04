"""Regression tests for type confusion and specifications (no network/AI)."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import local_search_api as api
from scraper.search_intent import apply_requirements, parse_requirements, product_type


QUERY = "Show me 24 inch monitors with 160hz"


def listing(title, category="monitors", description=""):
    return {"title": title, "category": category, "description": description,
            "price": "199.99", "product_url": "https://www.bestbuy.com/product/test/TEST"}


@pytest.fixture(autouse=True)
def database(monkeypatch):
    monkeypatch.setattr(api, "load_database_config", lambda: SimpleNamespace(url="https://synthetic.supabase.co", secret_key="synthetic"))


def test_no_monitor_category_in_catalog_never_returns_laptops(monkeypatch):
    products = [listing("MacBook Air M5 24GB Memory 13-inch Laptop", "laptops"),
                listing('ASUS Zenbook 14-inch laptop', 'laptops', 'Works with monitors at 160Hz')]
    monkeypatch.setattr(api, "interpret_query", Mock(side_effect=AssertionError("do not relax explicit requirements")))
    assert api.search_products(QUERY, catalog=products) == []


def test_only_matching_monitor_is_returned():
    good = listing("Acer 24-inch Gaming Monitor 160Hz")
    candidates = [good, listing('Acer 27-inch Monitor 160Hz'),
                  listing('Acer 24-inch Monitor 60Hz'), listing('Acer 24-inch Monitor 165Hz'),
                  listing('Monitor stand for 24-inch displays 160Hz'),
                  listing('MacBook 24-inch 160Hz Laptop', 'monitors')]
    results = api.search_products(QUERY, catalog=candidates)
    assert [product['title'] for product in results] == [good['title']]


@pytest.mark.parametrize("query", ['24-inch monitors with 160 Hz', '24" monitors 160hz', '24 inches monitors 160HZ'])
def test_units_and_punctuation(query):
    good = listing('ASUS 24-inch Monitor 160Hz')
    assert apply_requirements(query, [good]) == [good]


def test_numbers_are_not_interchangeable_between_specifications():
    assert apply_requirements(QUERY, [listing('24GB monitor 160-inch 24Hz')]) == []


def test_missing_specs_and_generic_description_are_not_evidence():
    unknown = listing('Dell Gaming Monitor', description='Compare with 24-inch 160Hz monitors')
    assert apply_requirements(QUERY, [unknown]) == []


def test_labeled_description_specs_can_verify_selected_monitor():
    good = listing('Dell Gaming Monitor', description='Screen size: 24 inches. Refresh rate: 160Hz.')
    assert apply_requirements(QUERY, [good]) == [good]


def test_title_takes_precedence_over_description_variants():
    bad = listing('Dell 27-inch Monitor 60Hz', description='Screen size: 24 inches. Refresh rate: 160Hz.')
    assert apply_requirements(QUERY, [bad]) == []


def test_at_least_is_not_exact_refresh_rate():
    good = listing('Dell 24-inch Monitor 180Hz')
    assert apply_requirements('24-inch monitor at least 160hz', [good]) == [good]
    assert apply_requirements(QUERY, [good]) == []


@pytest.mark.parametrize('query,category', [('headphones', 'headphones'), ('wireless mouse', 'mice'),
    ('keyboard for my ipad', 'keyboards'), ('monitor for laptop', 'monitors'),
    ('gaming laptops', 'laptops'), ('monitor arm', 'monitor_accessories'), ('SSD', 'storage')])
def test_known_product_types(query, category):
    assert product_type(query) == category


def test_ai_fallback_cannot_ignore_type_or_specs(monkeypatch):
    monkeypatch.setattr(api, 'interpret_query', lambda *a: ['laptop', 'monitor'])
    products = [listing('MacBook 24GB Laptop', 'laptops'), listing('Dell 27-inch Monitor 160Hz')]
    assert api.search_with_model_terms(QUERY, None, candidate_products=products, original_query=QUERY) == []


def test_catalog_fallback_keeps_original_requirements(monkeypatch):
    monkeypatch.setattr(api, 'collect_live_products', lambda *a: ([], {'saved': 0, 'errors': [], 'result_source': 'catalog'}))
    monkeypatch.setattr(api, 'load_catalog', lambda *a: [listing('MacBook Air 24GB 15-inch Laptop', 'laptops')])
    response = api.search_response(QUERY)
    assert response['products'] == []
    assert response['collection']['matched'] == 0
    assert response['collection']['requirements']['product_type'] == 'monitors'


def test_live_candidates_keep_original_requirements(monkeypatch):
    good = listing('Acer 24-inch Monitor 160Hz')
    wrong = listing('MacBook Air 24GB 15-inch Laptop', 'laptops')
    monkeypatch.setattr(api, 'collect_live_products', lambda *a: ([wrong, good], {'saved': 2, 'errors': [], 'result_source': 'live'}))
    response = api.search_response(QUERY)
    assert [product['title'] for product in response['products']] == [good['title']]


def test_ai_database_results_are_also_filtered(monkeypatch):
    monkeypatch.setattr(api, 'interpret_query', lambda *a: ['monitor'])
    wrong = listing('MacBook Air 24GB Laptop', 'laptops')
    monkeypatch.setattr(api.requests, 'get', lambda *a, **kw: SimpleNamespace(raise_for_status=lambda: None, json=lambda: [wrong]))
    monkeypatch.setattr(api, 'load_catalog', lambda *a: [wrong])
    db = SimpleNamespace(url='https://synthetic.supabase.co', secret_key='synthetic')
    assert api.search_with_model_terms(QUERY, db, original_query=QUERY) == []
