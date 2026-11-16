import pytest

import local_search_api as api
from normalizer import embeddings


def test_embeddings_batch_query_and_products(monkeypatch):
    class Encoder:
        def encode(self, texts, **kwargs):
            assert texts == ['lightweight laptop', 'Laptop A', 'Laptop B']
            assert kwargs['normalize_embeddings'] is True
            return [[1, 0], [0, 1], [1, 0]]

    monkeypatch.setattr(embeddings, '_model', Encoder)
    assert embeddings.semantic_scores('lightweight laptop', [{'title': 'Laptop A'}, {'title': 'Laptop B'}]) == [0, 1]


def test_live_candidate_ranking_preserves_requirements_and_cheapest_order(monkeypatch):
    monkeypatch.setenv('SHOPPIE_ENABLE_SBERT', '1')
    monkeypatch.setattr(api, 'load_database_config', object)
    def laptop(title, price):
        return {'title': title, 'category': 'laptops', 'price': price}

    cheap = 'Laptop A 16GB RAM'
    portable = 'Laptop B 16GB RAM'
    products = [laptop(cheap, 600), laptop(portable, 700),
                laptop('Laptop C 8GB RAM', 450), laptop('Laptop D 16GB RAM', 900),
                {'title': '24-inch monitor', 'category': 'monitors', 'price': 100}]
    query = 'laptop with at least 16GB RAM under $800'

    def score(text, candidates):
        assert text == query
        assert [p['title'] for p in candidates] == [cheap, portable]
        return [0.2, 0.9]

    monkeypatch.setattr(api, 'semantic_scores', score)
    assert [p['title'] for p in api.search_products(query, products)] == [portable, cheap]
    assert [p['title'] for p in api.search_products('cheap ' + query, products)] == [cheap]


@pytest.mark.parametrize('bad_scores', ([0.9], [0.9, float('nan')], None))
def test_sbert_failure_preserves_keyword_ranking(monkeypatch, bad_scores):
    monkeypatch.setenv('SHOPPIE_ENABLE_SBERT', '1')
    def score(*args):
        if bad_scores is None:
            raise RuntimeError('model unavailable')
        return bad_scores

    monkeypatch.setattr(api, 'semantic_scores', score)
    ranked = [(0.8, {'title': 'Laptop A'}), (0.6, {'title': 'Laptop B'})]
    assert api.rerank_keyword_matches('laptop', ranked) is ranked


def test_opt_out_never_calls_the_model(monkeypatch):
    monkeypatch.delenv('SHOPPIE_ENABLE_SBERT', raising=False)
    calls = []
    monkeypatch.setattr(api, 'semantic_scores', lambda *args: calls.append(args))
    ranked = [(0.8, {'title': 'Laptop A'}), (0.6, {'title': 'Laptop B'})]
    assert api.rerank_keyword_matches('laptop', ranked) is ranked
    assert calls == []
