"""Read-only connectivity checks; all credentials/responses are synthetic."""

from unittest.mock import Mock

import pytest
import requests

from scraper import config, main
from scraper.database import Database, DatabaseError, check_database


KEY = "sb_secret_SYNTHETIC_TEST_ONLY"


def response(status, body):
    result = Mock(status_code=status)
    result.json.return_value = body
    return result


@pytest.fixture
def database():
    return Database("https://synthetic.supabase.co", KEY)


@pytest.mark.parametrize("body", [[], [{"id": "ROW_MUST_NOT_PRINT"}]])
def test_check_is_single_read_only_query(monkeypatch, capsys, database, body):
    get = Mock(return_value=response(200, body))
    post = Mock(side_effect=AssertionError("No writes or login"))
    monkeypatch.setattr("scraper.database.requests.get", get)
    monkeypatch.setattr("scraper.database.requests.post", post)
    check_database(database)
    get.assert_called_once_with(
        "https://synthetic.supabase.co/rest/v1/products",
        params={"select": "id", "limit": "1"},
        headers={"apikey": KEY, "Accept": "application/json"},
        timeout=25, allow_redirects=False,
    )
    post.assert_not_called()
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("status,body,category", [
    (401, {"message": KEY}, "AUTHENTICATION FAILURE"),
    (400, {"code": "PGRST301", "message": KEY}, "AUTHENTICATION FAILURE"),
    (403, {"message": KEY}, "PERMISSION FAILURE"),
    (400, {"code": "42501", "message": KEY}, "PERMISSION FAILURE"),
    (404, {"code": "PGRST205", "message": KEY}, "MISSING TABLE"),
    (404, {"code": "42P01", "message": KEY}, "MISSING TABLE"),
    (400, {"code": "PGRST204", "message": KEY}, "SCHEMA FAILURE"),
    (404, {"message": KEY}, "CONNECTION/REQUEST FAILURE"),
    (503, {"message": KEY}, "CONNECTION/REQUEST FAILURE"),
    (429, {"message": KEY}, "CONNECTION/REQUEST FAILURE"),
    (302, {"message": KEY}, "CONNECTION/REQUEST FAILURE"),
    (500, {"code": [KEY]}, "CONNECTION/REQUEST FAILURE"),
])
def test_failures_are_classified_without_response_messages(monkeypatch, database, status, body, category):
    monkeypatch.setattr("scraper.database.requests.get", Mock(return_value=response(status, body)))
    with pytest.raises(DatabaseError) as error:
        check_database(database)
    assert category in str(error.value)
    assert KEY not in str(error.value)


@pytest.mark.parametrize("exception", [requests.Timeout(KEY), requests.ConnectionError(KEY), requests.exceptions.SSLError(KEY)])
def test_network_errors_never_echo_exception_or_key(monkeypatch, database, exception):
    monkeypatch.setattr("scraper.database.requests.get", Mock(side_effect=exception))
    with pytest.raises(DatabaseError) as error:
        check_database(database)
    assert "CONNECTION FAILURE" in str(error.value)
    assert KEY not in str(error.value)


def test_malformed_success_response_is_not_accessible(monkeypatch, database):
    result = response(200, {})
    monkeypatch.setattr("scraper.database.requests.get", Mock(return_value=result))
    with pytest.raises(DatabaseError, match="RESPONSE FAILURE"):
        check_database(database)
    result.json.side_effect = ValueError(KEY)
    with pytest.raises(DatabaseError) as error:
        check_database(database)
    assert KEY not in str(error.value)


def test_missing_config_reports_variable_names_without_request(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(config, "SCRIPT_DIR", tmp_path)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    request = Mock(side_effect=AssertionError("No request without config"))
    monkeypatch.setattr("scraper.database.requests.get", request)
    assert main.main(["--check-db"]) == 1
    output = capsys.readouterr().out
    assert "MISSING CONFIGURATION" in output
    assert "SUPABASE_URL" in output and "SUPABASE_SECRET_KEY" in output
    request.assert_not_called()


def test_env_overrides_script_dotenv_from_other_working_directory(tmp_path, monkeypatch):
    folder = tmp_path / "scraper"
    folder.mkdir()
    (folder / ".env").write_text("SUPABASE_URL=https://fileproject.supabase.co\nSUPABASE_SECRET_KEY=sb_secret_FILE_SYNTHETIC\n")
    monkeypatch.setattr(config, "SCRIPT_DIR", folder)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SUPABASE_URL", "https://envproject.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", KEY)
    settings = config.load_database_config()
    assert settings.url == "https://envproject.supabase.co"
    assert settings.secret_key == KEY
    assert KEY not in repr(settings)


def test_cli_check_never_loads_urls_or_scrapes(monkeypatch, capsys):
    monkeypatch.setattr(config, "load_database_config", lambda: config.DatabaseConfig("https://synthetic.supabase.co", KEY))
    forbidden = Mock(side_effect=AssertionError("Check must not scrape or save"))
    monkeypatch.setattr(config, "load_urls", forbidden)
    monkeypatch.setattr("scraper.main.scraper.fetch_page", forbidden)
    monkeypatch.setattr("scraper.database.requests.post", forbidden)
    monkeypatch.setattr("scraper.database.requests.get", Mock(return_value=response(200, [{"id": "ROW_MUST_NOT_PRINT"}])))
    assert main.main(["--check-db"]) == 0
    output = capsys.readouterr().out
    assert "DB CHECK OK" in output and "controlled write test" in output
    assert KEY not in output and "ROW_MUST_NOT_PRINT" not in output
    forbidden.assert_not_called()


@pytest.mark.parametrize("flags", [["--save"], ["--url", "anything"], ["--urls", "urls.txt"], ["--browser"], ["--stage", "extract"]])
def test_check_cannot_be_combined_with_pipeline_flags(flags):
    with pytest.raises(SystemExit):
        main.main(["--check-db", *flags])


@pytest.mark.parametrize("url,key", [
    ("http://synthetic.supabase.co", KEY),
    ("https://synthetic.supabase.co", "sb_publishable_SYNTHETIC"),
    ("https://synthetic.supabase.co", "sb_secret_SYNTHETIC\nINJECTED"),
])
def test_invalid_config_is_redacted(tmp_path, monkeypatch, url, key):
    monkeypatch.setattr(config, "SCRIPT_DIR", tmp_path)
    monkeypatch.setenv("SUPABASE_URL", url)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", key)
    with pytest.raises(config.ConfigurationError) as error:
        config.load_database_config()
    assert "INVALID CONFIGURATION" in str(error.value)
    assert key not in str(error.value)
