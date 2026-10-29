"""Isolated Supabase/PostgreSQL tests; all hosted requests are mocked."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import json
from unittest.mock import Mock

import pytest

from backend.models import SearchRequest
from backend.storage import LocalStore, listing_id
from backend.supabase import SupabaseConfig, SupabaseStore, configuration
from backend.service import ShoppingService
from backend.settings import setting
from db.embeddings import index_store, metadata_for, build_text
from scraper.envelope import listing_from_product
from scraper.evaluate import FIXTURE_DIR
from scraper.scraper import extract_product
from scraper.validator import validate_record
from db.normalize import normalize

URL = "https://www.target.com/p/synthetic/-/A-90000001"
KEY = "sb_secret_test-only"


class Encoder:
    def encode(self, texts, **kwargs):
        return [[1.0] + [0.0] * 383 for _ in texts]


@pytest.fixture
def store(tmp_path):
    return SupabaseStore(SupabaseConfig("https://test-only.supabase.co", KEY), LocalStore(tmp_path / "cache.sqlite3"))


def legacy_row():
    return {"id": "shared-test-id", "title": "Apple MacBook Air M5 16GB RAM 512GB SSD",
            "price": "999.00", "currency": "USD", "product_url": URL,
            "source": "target.com", "category": "laptops", "scraped_at": "2026-10-28T12:00:00+00:00"}


def schema_for(row, table="products"):
    return {"definitions": {table: {"properties": {key: {} for key in row}}}}


def test_existing_config_loading_and_blank_example_does_not_hide_scraper_credentials(tmp_path, monkeypatch):
    (tmp_path / "scraper").mkdir()
    (tmp_path / ".env").write_text("SUPABASE_URL=\nSUPABASE_SECRET_KEY=\n")
    (tmp_path / "scraper/.env").write_text("SUPABASE_URL=https://test-only.supabase.co\nSUPABASE_SECRET_KEY=" + KEY)
    monkeypatch.setattr("backend.settings.ROOT", tmp_path)
    for name in ("SUPABASE_URL", "SUPABASE_SECRET_KEY", "SUPABASE_SCHEMA"):
        monkeypatch.delenv(name, raising=False)
    config = configuration()
    assert config.url == "https://test-only.supabase.co" and config.key == KEY
    assert KEY not in repr(config) and config.url not in repr(config)
    monkeypatch.setenv("SUPABASE_URL", "https://env-wins.supabase.co")
    assert configuration().url == "https://env-wins.supabase.co"


@pytest.mark.parametrize("name,value", [("SUPABASE_URL", "http://localhost"), ("SUPABASE_SECRET_KEY", "publishable-key"), ("SUPABASE_SCHEMA", "public;drop table")])
def test_unsafe_config_is_rejected_without_values(monkeypatch, name, value):
    monkeypatch.setenv("SUPABASE_URL", "https://test-only.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", KEY)
    monkeypatch.setenv("SUPABASE_SCHEMA", "public")
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError) as caught:
        configuration()
    assert value not in str(caught.value)


def test_legacy_reads_use_contract_and_never_invent_stock_or_brand(store, monkeypatch):
    row = legacy_row()
    request = Mock(side_effect=[schema_for(row), [row, row]])
    monkeypatch.setattr(store, "request", request)
    report = store.refresh()
    product = store.listings()[0]
    assert report["accepted"] == 1 and report["duplicates"] == 1
    assert product["attributes"] == {"ram_gb": 16, "storage_gb": 512, "cpu": "M5"}
    assert product["price"] == "999.00" and product["category"] == "laptop"
    assert product["availability"] is product["brand"] is product["description"] is None
    assert store.history(product["id"]) == []
    service = ShoppingService(store, mode="live", storage="supabase", model=Encoder())
    assert index_store(store, service.model)["created"] == 1
    assert index_store(store, service.model)["reused"] == 1
    response = service.deals(SearchRequest(q="Apple MacBook Air M5 16GB RAM 512GB SSD"))
    assert len(response["results"]) == 1 and not response["offers"]
    assert response["results"][0]["match_status"] == "manual_review"
    assert not response["live_two_retailer_milestone"]


def test_bad_shared_product_does_not_abort_batch(store, monkeypatch):
    row = legacy_row()
    bad = {**row, "source": "bestbuy.com"}
    monkeypatch.setattr(store, "request", Mock(side_effect=[schema_for(row), [bad, row]]))
    report = store.refresh()
    assert report["accepted"] == report["rejected"] == 1
    assert KEY not in json.dumps(report)


def test_shared_title_conflicts_with_attributes_are_rejected(store):
    with pytest.raises(ValueError, match="conflicts"):
        store.to_envelope({**legacy_row(), "attributes": {"ram_gb": 8}})


def test_shared_writes_blocked_before_requests(store, monkeypatch):
    request = Mock()
    monkeypatch.setattr(store, "request", request)
    with pytest.raises(ValueError, match="disabled"):
        store.ingest({})
    service = ShoppingService(store, mode="live", storage="supabase")
    with pytest.raises(ValueError, match="read-only"):
        service.collect("laptop")
    request.assert_not_called()


@pytest.mark.parametrize("code", [401, 403, 404, 406, 429, 500, 302])
def test_hosted_errors_never_expose_secret_or_forward_redirect(store, monkeypatch, code):
    response = Mock(status_code=code)
    response.json.return_value = {"message": KEY}
    get = Mock(return_value=response)
    monkeypatch.setattr("backend.supabase.requests.get", get)
    with pytest.raises(ValueError) as caught:
        store.inspect()
    assert KEY not in str(caught.value)
    assert get.call_args.kwargs["allow_redirects"] is False
    assert "Authorization" not in get.call_args.kwargs["headers"]


def test_missing_schema_is_not_migrated(store, monkeypatch):
    request = Mock(return_value={"definitions": {}})
    monkeypatch.setattr(store, "request", request)
    with pytest.raises(ValueError, match="not compatible"):
        store.refresh()
    assert request.call_count == 1


def test_pgvector_rpc_has_fixed_function_and_typed_filters(store, monkeypatch):
    store.config.schema = "shoppie"
    request = Mock(return_value=[])
    monkeypatch.setattr(store, "request", request)
    store.vector_candidates([1.0] * 384, SearchRequest(q="laptop", brand="x';DROP TABLE products;--", min_price=900, limit=5))
    assert request.call_args.args == ("rpc/vector_candidates",)
    payload = request.call_args.kwargs["payload"]
    assert len(payload["query_vector"]) == 384
    assert abs(sum(v*v for v in payload["query_vector"]) - 1) < 1e-6
    assert payload["minimum_price"] == "900" and payload["result_limit"] == 5
    with pytest.raises(ValueError, match="384"):
        store.vector_candidates([1.0], SearchRequest(q="laptop"))


def test_legacy_schema_cannot_use_assumed_vector_rpc(store):
    with pytest.raises(ValueError, match="no assumed"):
        store.vector_candidates([1.0] * 384, SearchRequest(q="laptop"))


def test_shared_vectors_reused_and_stale_hash_does_not_override_local_vector(store, monkeypatch):
    item = json.loads((FIXTURE_DIR / "manifest.json").read_text())["pages"][0]
    product = extract_product((FIXTURE_DIR / item["file"]).read_text(), item["url"])
    envelope = listing_from_product(validate_record(product))
    row = normalize(envelope)
    identity = listing_id(row)
    store.cache.ingest(envelope)
    store.rows = [{**row, "id": identity}]
    remote = {**metadata_for(build_text(row)), "embedding": json.dumps([1.0] + [0.0] * 383)}
    store.remote_vectors[identity] = remote
    assert len(store.get_embedding(identity)["vector"]) == 384
    assert index_store(store, Encoder())["reused"] == 1
    store.rows[0]["description"] = "Changed explicit description"
    assert index_store(store, Encoder())["created"] == 1
    assert store.get_embedding(identity)["input_hash"] != remote["input_hash"]
    assert index_store(store, Encoder())["reused"] == 1


def test_postgres_is_readonly_by_default_and_preserves_source_evidence(monkeypatch):
    from backend.postgres import PostgresStore
    store = PostgresStore("postgresql://test-only")
    connection = Mock()
    monkeypatch.setattr(store, "connect", connection)
    with pytest.raises(ValueError, match="disabled"):
        store.ingest({})
    with pytest.raises(ValueError, match="disabled"):
        store.put_embedding("id", {})
    connection.assert_not_called()
    queries = []
    class DB:
        def execute(self, sql):
            queries.append(sql)
            return self
        def fetchall(self): return []
    @contextmanager
    def read(): yield DB()
    monkeypatch.setattr(store, "connect", read)
    assert store.listings() == []
    assert "o.raw_payload" in queries[0]


def test_readonly_api_uses_shared_service_without_demo_uploads(store, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.api import app, get_service
    row = legacy_row()
    monkeypatch.setattr(store, "request", Mock(side_effect=[schema_for(row), [row]]))
    service = ShoppingService(store, mode="live", storage="supabase", model=Encoder())
    app.dependency_overrides[get_service] = lambda: service
    try:
        client = TestClient(app)
        response = client.get("/products")
        assert response.status_code == 200 and len(response.json()["products"]) == 1
        assert KEY not in response.text
        assert client.post("/demo/collect").status_code == 400
        assert client.get("/storage/status").status_code == 200
        assert client.get("/deals", params={"q": "laptop"}).status_code == 200
    finally:
        app.dependency_overrides.clear()
