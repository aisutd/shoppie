"""Manual observations are explicit, validated, and isolated from fetching."""

import pytest

from scraper import main


URL = "https://www.bestbuy.com/product/synthetic-test-laptop/TEST123"


def test_manual_entry_does_not_fetch_or_connect(monkeypatch, capsys):
    answers = iter(["Synthetic test laptop", "123.45", "USD", "yes"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    def forbidden(*args, **kwargs):
        raise AssertionError("No fetch or database configuration allowed")
    monkeypatch.setattr(main.scraper, "fetch_page", forbidden)
    monkeypatch.setattr(main.config, "load_database_config", forbidden)
    assert main.main(["--manual", "--url", URL]) == 0
    output = capsys.readouterr().out
    assert '"extraction_method": "manual"' in output
    assert "validated=1" in output and "saved=0" in output
    assert "fetched=0, extracted=0" in output


@pytest.mark.parametrize("price,currency,confirmed", [("", "USD", "yes"), ("0", "USD", "yes"), ("123.45", "", "yes"), ("123.45", "USD", "no")])
def test_missing_invalid_or_unconfirmed_manual_data_rejects(monkeypatch, price, currency, confirmed):
    answers = iter(["Synthetic test laptop", price, currency, confirmed])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    assert main.main(["--manual", "--url", URL]) == 1


def test_manual_save_uses_confirmed_upsert(monkeypatch, capsys):
    from scraper import database
    answers = iter(["Synthetic test laptop", "123.45", "USD", "yes"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    monkeypatch.setattr(main.config, "load_database_config", lambda: object())
    monkeypatch.setattr(database, "connect", lambda config: object())
    saved = []
    monkeypatch.setattr(database, "upsert_product", lambda db, product: saved.append(product))
    assert main.main(["--manual", "--url", URL, "--limit", "1", "--save"]) == 0
    assert len(saved) == 1
    assert "saved=1, failed_saves=0" in capsys.readouterr().out
