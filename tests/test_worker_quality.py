"""Labeled quality checks distinguish source mistakes from missing/blocked data."""

import json
from unittest.mock import Mock

from scraper.evaluate import evaluate_fixtures, evaluate_captures, FIXTURE_DIR
from scraper.scraper import extract_product
from backend.coordinator import collect
from backend.storage import LocalStore


def test_labeled_bad_data_rate_has_explicit_denominator():
    def faulty(html, url):
        record = extract_product(html, url)
        if url.endswith("SYNTH001"):
            record["price"] = "1.00"
            record["model"] = "WRONG-MODEL"
            record["attributes"]["ram_gb"] = 8
            record["availability"] = "https://schema.org/OutOfStock"
        return record
    report = evaluate_fixtures(faulty)
    quality = report["quality_counts"]
    assert quality["incorrect_accepted_records"] == 1
    assert quality["manually_checked_accepted_records"] == 7
    assert quality["incorrect_prices"] == quality["incorrect_model_numbers"] == 1
    assert quality["hardware_mismatches"] == quality["availability_errors"] == 1
    assert quality["blocked_pages"] == quality["missing_prices"] == 1
    assert report["metrics"]["bad_data_rate"] == 1 / 7
    assert "Synthetic" in report["source"]


def test_archive_has_no_accepted_prices_and_no_measured_live_bad_data_rate():
    report = evaluate_captures()
    assert "Archived Target" in report["source"]
    assert report["counts"]["attempted"] == report["counts"]["rejected"] == 2
    assert report["quality_counts"]["missing_prices"] == 2
    assert report["metrics"]["bad_data_rate"] is None
    assert report["metrics"]["field_accuracy_present_labeled"] == 1


def test_invented_price_for_explicitly_missing_source_is_incorrect_data():
    def invents_price(html, url):
        record = extract_product(html, url)
        if url.endswith("B0DEMO0002"):
            record.update(price="100.00", currency="USD")
        return record
    report = evaluate_fixtures(invents_price)
    assert report["incorrect_fields"] == {"price": 1, "currency": 1}
    assert report["quality_counts"]["incorrect_accepted_records"] == 1
    assert report["metrics"]["bad_data_rate"] == 1 / 8


def test_unlabeled_accepted_records_are_not_a_correctness_denominator(tmp_path):
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text())
    manifest["pages"] = manifest["pages"][:2]
    for item in manifest["pages"]:
        item["file"] = str(FIXTURE_DIR / item["file"])
        item["expected"] = {}
    path = tmp_path / "unlabeled.json"
    path.write_text(json.dumps(manifest))
    report = evaluate_fixtures(manifest_path=path)
    assert report["counts"]["validated"] == 2
    assert report["denominators"]["manually_checked_accepted_records"] == 0
    assert report["metrics"]["bad_data_rate"] is None


def test_duplicate_fixture_urls_counted_without_making_accuracy_claim(tmp_path):
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text())
    item = manifest["pages"][0]
    item["file"] = str(FIXTURE_DIR / item["file"])
    manifest["pages"] = [item, item]
    path = tmp_path / "duplicates.json"
    path.write_text(json.dumps(manifest))
    report = evaluate_fixtures(manifest_path=path)
    assert report["quality_counts"]["duplicate_listings"] == 1


def test_one_unexpected_worker_error_does_not_drop_next_candidate(tmp_path, monkeypatch):
    pages = json.loads((FIXTURE_DIR / "manifest.json").read_text())["pages"][:2]
    monkeypatch.setattr("backend.coordinator.robots_allowed", lambda url: True)
    fetch = Mock(side_effect=[RuntimeError("isolated worker failed"), (FIXTURE_DIR / pages[1]["file"]).read_text()])
    monkeypatch.setattr("backend.coordinator.fetch_page", fetch)
    status = collect(LocalStore(tmp_path / "workers.sqlite3"), "Apple MacBook Air M5 16GB RAM 512GB SSD", mode="live", urls=[p["url"] for p in pages])
    assert status["stage"] == "collected"
    assert status["processed"] == status["attempted"] == 2
    assert status["saved"] == 1
    assert status["events"][0]["error_type"] == "infrastructure"
    assert status["invalid_records"] == 0
    assert status["worker_failures"] == 1
