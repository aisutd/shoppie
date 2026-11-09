"""Manual observations are explicit, validated, and isolated from fetching."""

from unittest.mock import Mock

import pytest

from scraper import main


URL = "https://www.bestbuy.com/product/synthetic-test-laptop/TEST123"


def test_manual_entry_does_not_fetch_or_connect(monkeypatch, capsys):
    answers = iter(["Synthetic test laptop", "123.45", "USD", "", "", "", "yes"])
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
    answers = iter(["Synthetic test laptop", price, currency, "", "", "", confirmed])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    assert main.main(["--manual", "--url", URL]) == 1


def test_manual_save_uses_confirmed_upsert(monkeypatch, capsys):
    from scraper import database
    answers = iter(["Synthetic test laptop", "123.45", "USD", "", "", "", "yes"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    monkeypatch.setattr(main.config, "load_database_config", lambda: object())
    monkeypatch.setattr(database, "connect", lambda config: object())
    saved = []
    monkeypatch.setattr(database, "upsert_product", lambda db, product: saved.append(product))
    assert main.main(["--manual", "--url", URL, "--limit", "1", "--save"]) == 0
    assert len(saved) == 1
    assert "saved=1, failed_saves=0" in capsys.readouterr().out


@pytest.mark.parametrize("retailer,url,product_id", [
    ("target", "https://www.target.com/p/synthetic-laptop/-/A-90000001?preselect=90000002", "90000002"),
    ("amazon", "https://www.amazon.com/dp/B0TEST0001", "B0TEST0001"),
])
def test_manual_variant_details_reach_existing_uploader(retailer, url, product_id, monkeypatch, capsys):
    from scraper import config, database

    image_url = "https://images.example.test/laptop.jpg"
    description = "Synthetic 16GB laptop description."
    answers = iter(["Synthetic MacBook laptop", "999.00", "USD", image_url, description, "InStock", "yes"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    settings = config.DatabaseConfig("https://synthetic.supabase.co", "sb_secret_SYNTHETIC")
    monkeypatch.setattr(main.config, "load_database_config", lambda: settings)
    post = Mock(return_value=Mock(status_code=201))
    monkeypatch.setattr(database.requests, "post", post)

    assert main.main(["--manual", "--url", url, "--save"]) == 0
    post.assert_called_once()
    request = post.call_args.kwargs
    row = request["json"]
    assert request["params"] == {"on_conflict": "product_url"}
    assert row["product_url"] == url and row["source"] == retailer + ".com"
    assert row["category"] == "laptops" and row["title"] == "Synthetic MacBook laptop"
    assert row["price"] == "999.00" and row["currency"] == "USD"
    assert row["image_url"] == image_url and row["description"] == description
    assert "availability" not in row
    assert f'"product_id": "{product_id}"' in capsys.readouterr().out


@pytest.mark.parametrize("image_url,availability", [
    ("https://images.example.test/laptop photo.jpg", "InStock"),
    ("", "OutOfStock"),
])
def test_invalid_manual_details_stop_before_database_settings(image_url, availability, monkeypatch):
    answers = iter(["Synthetic MacBook laptop", "999.00", "USD", image_url, "", availability, "yes"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    settings = Mock(side_effect=AssertionError("Rejected input cannot reach the uploader"))
    monkeypatch.setattr(main.config, "load_database_config", settings)
    assert main.main(["--manual", "--url", "https://www.amazon.com/dp/B0TEST0001", "--save"]) == 1
    settings.assert_not_called()
