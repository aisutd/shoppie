"""Exact-URL retrieval and updated observation payloads; HTTP is mocked."""

from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from scraper.database import Database, DatabaseError, get_product, upsert_product
from scraper.scraper import extract_product
from scraper.validator import validate_record


URL = "https://www.bestbuy.com/product/synthetic-test-laptop/TEST123"
DB = Database("https://synthetic.supabase.co", "sb_secret_SYNTHETIC")


def test_retrieval_filters_exact_url_and_returns_row_or_none(monkeypatch):
    row = {"id": "synthetic-id", "product_url": URL + "?variant=one&variant=two"}
    response = Mock(status_code=200)
    response.json.return_value = [row]
    get = Mock(return_value=response)
    monkeypatch.setattr("scraper.database.requests.get", get)
    assert get_product(DB, row["product_url"]) == row
    assert get.call_args.kwargs["params"]["product_url"] == "eq." + row["product_url"]
    assert get.call_args.kwargs["allow_redirects"] is False
    response.json.return_value = []
    assert get_product(DB, URL) is None


@pytest.mark.parametrize("rows", [{}, [None], [{"product_url": "wrong"}],
                                 [{"product_url": URL}, {"product_url": URL}]])
def test_malformed_or_nonunique_retrieval_rejects(monkeypatch, rows):
    response = Mock(status_code=200)
    response.json.return_value = rows
    monkeypatch.setattr("scraper.database.requests.get", Mock(return_value=response))
    with pytest.raises(DatabaseError, match="RESPONSE FAILURE"):
        get_product(DB, URL)


def test_retrieval_errors_are_redacted(monkeypatch):
    get = Mock(side_effect=requests.Timeout("SECRET_MUST_NOT_PRINT"))
    monkeypatch.setattr("scraper.database.requests.get", get)
    with pytest.raises(DatabaseError) as error:
        get_product(DB, URL)
    assert "SECRET_MUST_NOT_PRINT" not in str(error.value)
    response = Mock(status_code=403)
    response.json.return_value = {}
    get.side_effect = None
    get.return_value = response
    with pytest.raises(DatabaseError, match="PERMISSION FAILURE"):
        get_product(DB, URL)
    response.status_code = 200
    response.json.side_effect = ValueError("SECRET_MUST_NOT_PRINT")
    with pytest.raises(DatabaseError, match="RESPONSE FAILURE"):
        get_product(DB, URL)


def test_repeat_upsert_sends_new_observation_without_replacing_id(monkeypatch):
    html = (Path(__file__).parent / "fixtures/synthetic_product.html").read_text()
    first = validate_record(extract_product(html, URL))
    candidate = first.model_dump()
    candidate.update(price="150.00", observed_at=first.observed_at + timedelta(seconds=1))
    second = validate_record(candidate)
    post = Mock(return_value=Mock(status_code=204))
    monkeypatch.setattr("scraper.database.requests.post", post)
    upsert_product(DB, first)
    upsert_product(DB, second)
    before, after = [call.kwargs["json"] for call in post.call_args_list]
    assert before["product_url"] == after["product_url"] == URL
    assert after["price"] == "150.00"
    assert after["scraped_at"] > before["scraped_at"]
    assert "id" not in before and "id" not in after
