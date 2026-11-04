"""Configuration, save boundaries and upserts, using fake services only."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from scraper import config, main, scraper
from scraper.database import Database, connect, upsert_product
from scraper.validator import validate_record


URL = "https://www.bestbuy.com/product/synthetic-test-laptop/TEST123"
FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_product.html"


def test_imports_do_not_connect_or_load_dotenv():
    # A separate interpreter keeps patched imports from contaminating other tests.
    code = """
import requests, dotenv
def forbidden(*args, **kwargs):
    raise AssertionError('No import-time configuration or networking')
requests.post = requests.get = dotenv.dotenv_values = forbidden
import scraper.config, scraper.scraper, scraper.validator, scraper.database, scraper.main
"""
    result = subprocess.run([sys.executable, "-c", code], cwd=config.SCRIPT_DIR.parent,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_urls_are_relative_to_script_directory_not_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    urls = config.load_urls()
    assert len(urls) == 4
    assert {scraper.identify_product(url)[0] for url in urls} == {"amazon", "bestbuy", "target", "walmart"}


def test_url_file_comments_blank_lines_and_duplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SCRIPT_DIR", tmp_path)
    (tmp_path / "urls.txt").write_text(f"# comment\n\n{URL}\n{URL}\n", encoding="utf-8")
    assert config.load_urls() == [URL]


def test_dotenv_path_and_environment_precedence(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SCRIPT_DIR", tmp_path)
    (tmp_path / ".env").write_text(
        "SUPABASE_URL=https://fromfile.supabase.co\nSUPABASE_SECRET_KEY=sb_secret_SYNTHETIC_FILE\n"
    )
    monkeypatch.setenv("SUPABASE_URL", "https://fromterminal.supabase.co")
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    settings = config.load_database_config()
    assert settings.url == "https://fromterminal.supabase.co"
    assert settings.secret_key == "sb_secret_SYNTHETIC_FILE"
    assert "SYNTHETIC" not in repr(settings)


def test_extraction_only_never_loads_database_config(monkeypatch, capsys):
    monkeypatch.setattr(main.scraper, "fetch_page", lambda url: FIXTURE.read_text())
    failure = Mock(side_effect=AssertionError("No database settings"))
    monkeypatch.setattr(main.config, "load_database_config", failure)
    assert main.main(["--url", URL]) == 0
    failure.assert_not_called()
    assert "validated=1" in capsys.readouterr().out


def test_rejected_record_never_connects_even_with_save(monkeypatch):
    monkeypatch.setattr(main.scraper, "fetch_page", lambda url: '<h1>Synthetic laptop</h1>')
    connection = Mock(side_effect=AssertionError("Invalid rows must not reach a connection"))
    monkeypatch.setattr("scraper.database.connect", connection)
    assert main.main(["--url", URL, "--save"]) == 1
    connection.assert_not_called()


def test_batch_saves_connect_only_once_and_uses_validated_records(monkeypatch, capsys):
    monkeypatch.setattr(main.scraper, "fetch_page", lambda url: FIXTURE.read_text())
    monkeypatch.setattr(main.config, "load_database_config", lambda: config.DatabaseConfig("https://example.supabase.co", "sb_secret_SYNTHETIC"))
    connection = Mock(return_value=object())
    upsert = Mock()
    monkeypatch.setattr("scraper.database.connect", connection)
    monkeypatch.setattr("scraper.database.upsert_product", upsert)
    assert main.main(["--url", URL, "--url", URL, "--save"]) == 0
    connection.assert_called_once()
    assert upsert.call_count == 1
    assert upsert.call_args.args[1].product_id == "TEST123"
    assert "saved=1" in capsys.readouterr().out


def test_batch_continues_after_bad_url(monkeypatch, capsys):
    monkeypatch.setattr(main.scraper, "fetch_page", lambda url: FIXTURE.read_text())
    assert main.main(["--url", "https://not-a-retailer.test/", "--url", URL]) == 1
    output = capsys.readouterr().out
    assert "validated=1" in output and "rejected=1" in output


@pytest.mark.parametrize("flags", [["--html", str(FIXTURE), "--save"], ["--stage", "fetch", "--save"]])
def test_save_cannot_skip_live_validation(flags):
    with pytest.raises(SystemExit):
        main.main(["--url", URL, *flags])


def test_upsert_has_stable_conflict_key_and_preserves_missing_fields(monkeypatch, capsys):
    post = Mock(return_value=Mock(status_code=201))
    monkeypatch.setattr("scraper.database.requests.post", post)
    database = Database("https://example.supabase.co", "sb_secret_SYNTHETIC")
    product = validate_record(scraper.extract_product(FIXTURE.read_text(), URL))
    upsert_product(database, product)
    upsert_product(database, product)
    assert post.call_count == 2
    for call in post.call_args_list:
        assert call.args[0].endswith("/rest/v1/products")
        assert call.kwargs["params"] == {"on_conflict": "product_url"}
        assert call.kwargs["headers"]["Prefer"] == "resolution=merge-duplicates,return=minimal"
        assert call.kwargs["json"]["source"] == "bestbuy.com"
        assert call.kwargs["json"]["category"] == "laptops"
        assert "seller" not in call.kwargs["json"]
        assert "discount" not in call.kwargs["json"]
        assert "id" not in call.kwargs["json"]
        assert "created_at" not in call.kwargs["json"]
    assert "sb_secret_SYNTHETIC" not in repr(database)
    assert "SYNTHETIC" not in capsys.readouterr().out


def test_database_errors_do_not_leak_request_tokens(monkeypatch):
    import requests
    monkeypatch.setattr("scraper.database.requests.post", Mock(side_effect=requests.ConnectionError("SYNTHETIC_TOKEN")))
    product = validate_record(scraper.extract_product(FIXTURE.read_text(), URL))
    database = Database("https://example.supabase.co", "sb_secret_SYNTHETIC")
    with pytest.raises(ValueError) as error:
        upsert_product(database, product)
    assert "SYNTHETIC_TOKEN" not in str(error.value)


def test_connect_prepares_backend_without_prompt_or_network(monkeypatch, capsys):
    forbidden = Mock(side_effect=AssertionError("No sign-in or connection during preparation"))
    monkeypatch.setattr("builtins.input", forbidden)
    monkeypatch.setattr("scraper.database.requests.post", forbidden)
    monkeypatch.setattr("scraper.database.requests.get", forbidden)
    result = connect(config.DatabaseConfig("https://example.supabase.co", "sb_secret_SYNTHETIC"))
    assert result.secret_key == "sb_secret_SYNTHETIC"
    assert "sb_secret_SYNTHETIC" not in repr(result)
    assert capsys.readouterr().out == ""
    forbidden.assert_not_called()
