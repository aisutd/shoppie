"""Offline checks for the scraper JSON contract and MySQL query behavior."""

import json
import sqlite3
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from db.ingest import ImportFailure, import_file, load_batch
from db.connection import read_config
from db.embeddings import build_text
from db.normalize import normalize, parse_money
from db.queries import find_listings, get_latest_observation, get_listing, get_price_history
from db.similarity import assess_identity, cosine_similarity
from normalizer.matching import group_listings
from normalizer.models import NormalizedListing, Source
from scraper.envelope import make_envelope
from scraper.scraper import extract_product
from scraper.validator import validate_record

URL = "https://www.bestbuy.com/product/synthetic-test-laptop/TEST123"
FIXTURE = Path(__file__).resolve().parents[1] / "scraper/tests/fixtures/synthetic_product.html"
sqlite3.register_adapter(Decimal, str)
sqlite3.register_converter("DECIMAL", lambda value: Decimal(value.decode()))
sqlite3.register_adapter(datetime, lambda value: value.isoformat(" "))
sqlite3.register_converter("TIMESTAMP", lambda value: datetime.fromisoformat(value.decode()))


class Cursor:
    def __init__(self, connection, dictionary=False):
        self.connection = connection
        self.dictionary = dictionary
        self.cursor = connection.database.cursor()
        self.lastrowid = None

    def execute(self, sql, params=()):
        sql = sql.replace("%s", "?").replace(" FOR UPDATE", "")
        self.cursor.execute(sql, params)
        self.lastrowid = self.cursor.lastrowid

    def convert(self, row):
        if row is None:
            return None
        if not self.dictionary:
            return tuple(row)
        return dict(row)

    def fetchone(self):
        return self.convert(self.cursor.fetchone())

    def fetchall(self):
        return [self.convert(row) for row in self.cursor.fetchall()]

    def close(self):
        self.cursor.close()


class LocalDatabase:
    """A tiny SQL stand-in; no MySQL server or live data is touched."""

    def __init__(self):
        self.database = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES)
        self.database.row_factory = sqlite3.Row
        self.database.executescript("""
            CREATE TABLE retailers (id INTEGER PRIMARY KEY, retailer_key TEXT, name TEXT);
            INSERT INTO retailers VALUES (1, 'best_buy', 'Best Buy');
            CREATE TABLE listings (
                id INTEGER PRIMARY KEY, retailer_id INTEGER, retailer_sku TEXT,
                source_url TEXT, source_url_hash TEXT, title TEXT, brand TEXT,
                model_number TEXT, gtin TEXT, category TEXT, attributes TEXT,
                details_observed_at TIMESTAMP, UNIQUE (retailer_id, source_url_hash));
            CREATE TABLE listing_observations (
                id INTEGER PRIMARY KEY, listing_id INTEGER, scraped_at TIMESTAMP,
                price DECIMAL, shipping_cost DECIMAL, currency TEXT,
                `condition` TEXT, seller TEXT, availability TEXT, raw_payload TEXT,
                UNIQUE (listing_id, scraped_at));
        """)

    def cursor(self, dictionary=False, buffered=False):
        return Cursor(self, dictionary)

    def start_transaction(self):
        self.database.execute("BEGIN")

    def commit(self):
        self.database.commit()

    def rollback(self):
        self.database.rollback()

    def close(self):
        self.database.close()


def sample_row():
    html = FIXTURE.read_text(encoding="utf-8")
    product = validate_record(extract_product(html, URL))
    return make_envelope([product])["listings"][0]


def test_explicit_json_ld_details_are_exported():
    product_data = {"@type": "Product", "url": URL, "name": "Example laptop",
        "brand": {"name": "Example"}, "model": "EX14", "category": "Laptops",
        "gtin13": "0012345678901", "color": "Blue",
        "additionalProperty": [{"name": "RAM", "value": "16 GB"},
                               {"name": "Storage", "value": "512 GB"}],
        "offers": {"@type": "Offer", "price": "123.45", "priceCurrency": "USD"}}
    html = '<script type="application/ld+json">' + json.dumps(product_data) + '</script>'
    exported = make_envelope([validate_record(extract_product(html, URL))])["listings"][0]
    assert exported["retailer_key"] == "best_buy"
    assert exported["raw"]["gtin"] == "0012345678901"
    assert exported["raw"]["attributes"] == {"ram_gb": 16, "storage_gb": 512, "color": "Blue"}
    assert normalize(exported)["model_number"] == "EX14"


def test_missing_json_ld_title_uses_main_heading():
    product_data = {"@type": "Product", "url": URL,
                    "offers": {"@type": "Offer", "price": "123.45",
                               "priceCurrency": "USD"}}
    html = '<h1>Example laptop</h1><script type="application/ld+json">' + json.dumps(product_data) + '</script>'
    assert extract_product(html, URL)["title"] == "Example laptop"


def batch(tmp_path, rows):
    path = tmp_path / "batch.json"
    path.write_text(json.dumps({"schema_version": 1, "listings": rows}), encoding="utf-8")
    return path


def test_scraper_json_normalization_and_retrieval(tmp_path):
    first = sample_row()
    first["raw"].update(brand="Example", model="EX14", category="laptops",
                        attributes={"ram_gb": "16", "storage_gb": "512", "color": "Blue"})
    later = deepcopy(first)
    later["scraped_at"] = "2030-01-02T00:00:00Z"
    later["raw"].update(price="199.99", title="Newer synthetic test laptop")
    older = deepcopy(first)
    older["scraped_at"] = "2020-01-01T00:00:00Z"
    older["raw"]["title"] = "Older synthetic test laptop"
    db = LocalDatabase()
    path = batch(tmp_path, [first, later, older, first])
    summary = import_file(path, connection=db)
    assert (summary["imported"], summary["skipped"], summary["rejected"]) == (3, 1, 0)
    listing = get_listing(db, 1)
    assert listing["title"] == "Newer synthetic test laptop"
    assert listing["attributes"] == {"ram_gb": 16, "storage_gb": 512, "color": "Blue"}
    assert listing["retailer_key"] == "best_buy"
    assert get_latest_observation(db, 1)["price"] == Decimal("199.99")
    assert get_latest_observation(db, 1)["raw_payload"] == later
    history = get_price_history(db, 1)
    assert len(history) == 3
    assert [row["scraped_at"].year for row in history] == [2020, first_year(first), 2030]
    assert len(find_listings(db, "Example", "EX14")) == 1
    db.close()


def first_year(row):
    return int(row["scraped_at"][:4])


def test_invalid_row_does_not_stop_batch(tmp_path):
    good = sample_row()
    bad = deepcopy(good)
    bad["raw"]["price"] = "starting at $10"
    db = LocalDatabase()
    summary = import_file(batch(tmp_path, [bad, good]), connection=db)
    assert summary["rejected"] == 1 and summary["imported"] == 1
    assert "price" in summary["errors"][0]["reason"]
    db.close()


def test_same_timestamp_with_changed_data_is_conflict(tmp_path):
    good = sample_row()
    conflict = deepcopy(good)
    conflict["raw"]["price"] = "99.99"
    db = LocalDatabase()
    summary = import_file(batch(tmp_path, [good, conflict]), connection=db)
    assert summary["imported"] == 1 and summary["rejected"] == 1
    assert "conflicts" in summary["errors"][0]["reason"]
    assert len(get_price_history(db, 1)) == 1
    db.close()


def test_newest_unknown_price_stays_unknown(tmp_path):
    good = sample_row()
    later = deepcopy(good)
    later["scraped_at"] = "2030-01-02T00:00:00Z"
    later["raw"].update(price=None, currency=None, title=None)
    db = LocalDatabase()
    summary = import_file(batch(tmp_path, [good, later]), connection=db)
    assert summary["imported"] == 2
    assert get_listing(db, 1)["title"] is None
    assert get_latest_observation(db, 1)["price"] is None
    assert get_price_history(db, 1)[0]["price"] == Decimal("123.45")
    db.close()


def test_bad_envelope_and_required_fields(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"schema_version": 2, "listings": []}')
    with pytest.raises(ValueError, match="schema_version"):
        load_batch(path)
    row = sample_row()
    del row["scraped_at"]
    with pytest.raises(ValueError, match="scraped_at"):
        normalize(row)
    row = sample_row()
    row["raw"]["currency"] = "EUR"
    with pytest.raises(ValueError, match="currency"):
        normalize(row)
    with pytest.raises(ValueError, match="amount"):
        parse_money(True, "USD")
    row = sample_row()
    row["source_url"] = "https://www.amazon.com/dp/B0DZD91W4F"
    with pytest.raises(ValueError, match="host does not match"):
        normalize(row)


def test_connection_settings_are_read_from_environment(monkeypatch):
    for name in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="DB_HOST"):
        read_config()
    for name, value in (("DB_HOST", "localhost"), ("DB_NAME", "shoppie_test"),
                        ("DB_USER", "student"), ("DB_PASSWORD", "local-only")):
        monkeypatch.setenv(name, value)
    config = read_config()
    assert config["port"] == 3306 and config["time_zone"] == "+00:00"
    monkeypatch.setenv("DB_PORT", "bad")
    with pytest.raises(ValueError, match="DB_PORT"):
        read_config()


def test_database_failure_rolls_back_listing(tmp_path):
    db = LocalDatabase()
    db.database.execute("DROP TABLE listing_observations")
    with pytest.raises(ImportFailure) as error:
        import_file(batch(tmp_path, [sample_row()]), connection=db)
    assert error.value.summary["imported"] == 0
    assert db.database.execute("SELECT COUNT(*) FROM listings").fetchone()[0] == 0
    db.close()


def test_variant_conflicts_and_semantic_scores_do_not_merge():
    left = {"brand": "Example", "model_number": "EX14", "attributes": {"ram_gb": 8}}
    right = {"brand": "Example", "model_number": "EX14", "attributes": {"ram_gb": 16}}
    assert assess_identity(left, right)["status"] == "rejected"
    right["attributes"]["ram_gb"] = 8
    assert assess_identity(left, right)["status"] == "uncertain"
    assert cosine_similarity([1, 0], [0, 1]) == 0
    assert build_text({**left, "title": "Example laptop", "seller": "Seller A",
                       "attributes": {"ram_gb": 8, "condition": "used"}}) == (
                           "Example | Example laptop | EX14 | ram_gb: 8")
    listings = [NormalizedListing(source=Source(retailer=name), name="Example laptop",
                brand="Example", model_number="EX14", category="laptop", specs=specs)
                for name, specs in (("target", {"ram_gb": 8}),
                                    ("bestbuy", {"ram_gb": 8}))]
    assert len(group_listings(listings)) == 2
