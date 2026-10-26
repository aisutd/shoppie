"""Command contracts and write limits, using synthetic pages and fake HTTP only."""

import json
import os
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from scraper import config, main, scraper
from scraper.database import DatabaseError
from scraper.validator import validate_record


FIRST = "https://www.bestbuy.com/product/synthetic-laptop/TEST123"
SECOND = "https://www.bestbuy.com/product/synthetic-laptop/TEST456"
THIRD = "https://www.bestbuy.com/product/synthetic-laptop/TEST789"


def synthetic_page(url):
    product = {"@type": "Product", "name": "Synthetic test laptop", "url": url,
               "offers": {"@type": "Offer", "price": "123.45", "priceCurrency": "USD"}}
    return '<script type="application/ld+json">' + json.dumps(product) + '</script>'


@pytest.fixture
def pipeline(monkeypatch):
    monkeypatch.setattr(config, "load_urls", Mock(return_value=[FIRST, SECOND, THIRD]))
    fetch = Mock(side_effect=synthetic_page)
    monkeypatch.setattr(main.scraper, "fetch_page", fetch)
    settings = Mock(return_value=config.DatabaseConfig("https://synthetic.supabase.co", "sb_secret_SYNTHETIC_ONLY"))
    monkeypatch.setattr(config, "load_database_config", settings)
    post = Mock(return_value=Mock(status_code=201))
    monkeypatch.setattr("scraper.database.requests.post", post)
    return fetch, settings, post


def test_bare_command_scrapes_validates_prints_without_database(pipeline, capsys):
    fetch, settings, post = pipeline
    assert main.main([]) == 0
    assert fetch.call_count == 3
    settings.assert_not_called()
    post.assert_not_called()
    output = capsys.readouterr().out
    assert '"title": "Synthetic test laptop"' in output
    assert "validated=3, rejected=0, saved=0, failed_saves=0" in output


def test_real_fixture_extracts_without_credentials_or_network(monkeypatch, capsys):
    fixtures = Path(__file__).parent / "fixtures"
    path = fixtures / "target_1004661132_2026-10-14.html"
    metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    assert "SUPABASE_URL" not in os.environ
    assert "SUPABASE_SECRET_KEY" not in os.environ
    forbidden = Mock(side_effect=AssertionError("Extraction must not access database settings or HTTP"))
    monkeypatch.setattr(config, "load_database_config", forbidden)
    monkeypatch.setattr("requests.get", forbidden)
    monkeypatch.setattr("requests.post", forbidden)
    assert main.main(["--url", metadata["source_url"], "--html", str(path.resolve()), "--stage", "extract"]) == 0
    output = capsys.readouterr().out
    assert "Lenovo Legion 5" in output
    assert '"price": null' in output and '"currency": null' in output
    assert "Extraction only" in output
    forbidden.assert_not_called()


def test_failed_fetch_continues_to_later_urls_without_database(pipeline, capsys):
    fetch, settings, post = pipeline
    fetch.side_effect = [ValueError("Synthetic fetch failure"), synthetic_page(SECOND), synthetic_page(THIRD)]
    assert main.main(["--http-only"]) == 1
    assert [call.args[0] for call in fetch.call_args_list] == [FIRST, SECOND, THIRD]
    settings.assert_not_called()
    post.assert_not_called()
    assert "validated=2, rejected=1, saved=0, failed_saves=0" in capsys.readouterr().out


def test_save_uploads_validated_records_and_reports_confirmed_success(pipeline, capsys):
    fetch, settings, post = pipeline
    assert main.main(["--save"]) == 0
    settings.assert_called_once()
    assert post.call_count == 3
    output = capsys.readouterr().out
    assert output.count("SAVED:") == 3
    assert "validated=3, rejected=0, saved=3, failed_saves=0" in output
    for call in post.call_args_list:
        assert call.kwargs["params"] == {"on_conflict": "product_url"}


def test_limit_one_stops_after_first_confirmed_save(pipeline, capsys):
    fetch, settings, post = pipeline
    assert main.main(["--limit", "1", "--save"]) == 0
    fetch.assert_called_once_with(FIRST)
    post.assert_called_once()
    assert "validated=1, rejected=0, saved=1, failed_saves=0" in capsys.readouterr().out


def test_limit_one_does_not_skip_rejected_pages(pipeline, capsys):
    fetch, settings, post = pipeline
    fetch.side_effect = [ValueError("Synthetic fetch failure"), '<h1>Synthetic laptop</h1>', synthetic_page(THIRD)]
    assert main.main(["--http-only", "--limit", "1", "--save"]) == 1  # Isolate HTTP stage failures.
    assert fetch.call_count == 3
    post.assert_called_once()
    assert "validated=1, rejected=2, saved=1, failed_saves=0" in capsys.readouterr().out


def test_limit_one_stops_after_failed_write_without_trying_another_product(pipeline, capsys):
    fetch, settings, post = pipeline
    post.side_effect = requests.Timeout("SYNTHETIC_SECRET_MUST_NOT_PRINT")
    assert main.main(["--limit", "1", "--save"]) == 1
    fetch.assert_called_once_with(FIRST)
    post.assert_called_once()
    output = capsys.readouterr().out
    assert "validated=1, rejected=0, saved=0, failed_saves=1" in output
    assert "SAVED:" not in output
    assert "SYNTHETIC_SECRET_MUST_NOT_PRINT" not in output


def test_write_failure_continues_to_later_urls_without_limit(pipeline, monkeypatch, capsys):
    fetch, settings, post = pipeline
    upsert = Mock(side_effect=[DatabaseError("Synthetic write failure"), None, None])
    monkeypatch.setattr("scraper.database.upsert_product", upsert)
    assert main.main(["--save"]) == 1
    assert fetch.call_count == 3
    assert upsert.call_count == 3
    output = capsys.readouterr().out
    assert "validated=3, rejected=0, saved=2, failed_saves=1" in output
    assert output.count("SAVED:") == 2


@pytest.mark.parametrize("status", [202, 302, 401, 403, 500])
def test_non_confirmed_http_responses_never_print_saved(pipeline, capsys, status):
    fetch, settings, post = pipeline
    post.return_value.status_code = status
    post.return_value.json.return_value = {}
    assert main.main(["--limit", "1", "--save"]) == 1
    output = capsys.readouterr().out
    assert "SAVED:" not in output
    assert "saved=0, failed_saves=1" in output


def test_configuration_failure_is_counted_separately_from_validation(pipeline, capsys):
    fetch, settings, post = pipeline
    settings.side_effect = config.ConfigurationError("MISSING CONFIGURATION: synthetic test")
    assert main.main(["--save"]) == 1
    assert fetch.call_count == 3
    post.assert_not_called()
    settings.assert_called_once()
    assert "validated=3, rejected=0, saved=0, failed_saves=3" in capsys.readouterr().out


def test_deduplicate_file_and_cli_urls_but_keep_query_variants(pipeline, capsys):
    fetch, settings, post = pipeline
    assert main.main(["--url", FIRST, "--url", FIRST + "#details", "--url", FIRST + "?skuId=1",
                      "--url", FIRST + "?skuId=2", "--url", FIRST + "?skuId=1", "--save"]) == 0
    assert [call.args[0] for call in fetch.call_args_list] == [FIRST, FIRST + "?skuId=1", FIRST + "?skuId=2"]
    assert [call.kwargs["json"]["product_url"] for call in post.call_args_list] == [FIRST, FIRST + "?skuId=1", FIRST + "?skuId=2"]
    assert "Skipped 2 duplicate" in capsys.readouterr().out


def test_default_url_file_is_deduplicated_by_pipeline(pipeline, monkeypatch):
    fetch, settings, post = pipeline
    monkeypatch.setattr(config, "load_urls", Mock(return_value=[FIRST, FIRST, FIRST + "#specs", SECOND]))
    assert main.main(["--save"]) == 0
    assert fetch.call_count == 2
    assert post.call_count == 2


@pytest.mark.parametrize("limit", ["0", "-1", "not-an-integer"])
def test_invalid_limit_rejects_before_loading_configuration(pipeline, limit):
    fetch, settings, post = pipeline
    with pytest.raises(SystemExit):
        main.main(["--limit", limit, "--save"])
    fetch.assert_not_called()
    settings.assert_not_called()
    post.assert_not_called()


def test_limit_cannot_be_used_with_database_check(pipeline):
    with pytest.raises(SystemExit):
        main.main(["--limit", "1", "--check-db"])


@pytest.mark.parametrize("stage", ["fetch", "extract", "validate"])
def test_limit_also_bounds_extraction_checkpoints(pipeline, stage):
    fetch, settings, post = pipeline
    assert main.main(["--limit", "1", "--stage", stage]) == 0
    fetch.assert_called_once()
    settings.assert_not_called()
    post.assert_not_called()


@pytest.mark.parametrize("url", [
    "https://www.amazon.com/dp/B0DZD91W4F?th=1&psc=1",
    FIRST + "?skuId=6571026&condition=new",
    "https://www.target.com/p/synthetic/-/A-12345678?preselect=23456789",
    "https://www.walmart.com/ip/12345678?selectedSellerId=123&variant=blue%2Bsilver&variant=&x=1&x=2",
])
def test_cleaning_and_validation_preserve_full_query(url):
    assert scraper.clean_url(url) == url
    product = validate_record(scraper.extract_product(synthetic_page(url), url))
    assert product.product_url == url


def test_only_generic_normalization_no_www_or_path_alias_merging():
    assert scraper.clean_url("  https://WWW.BESTBUY.COM/product/synthetic-laptop/TEST123?a=%2f&b=+#specs  ") == FIRST + "?a=%2f&b=+"
    assert scraper.unique_urls([FIRST, FIRST.replace("www.", ""), FIRST + "/"]) == [FIRST, FIRST.replace("www.", ""), FIRST + "/"]


def test_redirect_cannot_silently_drop_query_variant(monkeypatch):
    get = Mock(return_value=Mock(status_code=302, headers={"Location": FIRST}))
    monkeypatch.setattr("scraper.scraper.requests.get", get)
    with pytest.raises(ValueError, match="Redirect left"):
        scraper.fetch_page(FIRST + "?skuId=1")
    get.assert_called_once()
