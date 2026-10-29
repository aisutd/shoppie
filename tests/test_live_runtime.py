"""Opt-in local UI/browser checks; no retailer or search API is contacted."""

import os
from pathlib import Path
import pytest

pytestmark = pytest.mark.skipif(os.environ.get("SHOPPIE_RUNTIME_TESTS") != "1", reason="set SHOPPIE_RUNTIME_TESTS=1 for local browser/dashboard checks")


def test_installed_chromium_supports_visible_and_headless_modes():
    from scraper.browser_check import check_browser
    for headed in (False, True):
        result = check_browser(headed)
        assert result["browser"] == "Chromium"
        assert result["headed"] is headed
        assert result["source"] == "controlled local HTML"
        assert not result["live_offer_verified"]


def test_dashboard_live_discovery_failure_is_visible_without_fake_offers(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    from backend.storage import LocalStore
    store = LocalStore(tmp_path / "live-ui.sqlite3")
    monkeypatch.setattr("backend.service.LocalStore", lambda *args, **kwargs: store)
    def blocked(*args, **kwargs):
        raise ValueError("Robots request returned HTTP 403; access not confirmed")
    monkeypatch.setattr("backend.discovery.discover_report", blocked)
    root = Path(__file__).resolve().parents[1]
    app = AppTest.from_file(str(root / "dashboard.py"), default_timeout=30).run()
    app.radio[0].set_value("Live · permitted sources").run()
    next(button for button in app.button if button.label == "Discover candidate links only").click().run()
    assert not app.exception
    assert any("403" in error.value for error in app.error)
    assert any("No live offer has been verified" in message.value for message in app.info)
    assert store.listings() == []


def test_dashboard_shared_products_stay_unverified_and_use_local_embeddings(tmp_path, monkeypatch):
    from unittest.mock import Mock
    from streamlit.testing.v1 import AppTest
    from backend.storage import LocalStore
    from backend.supabase import SupabaseConfig, SupabaseStore
    store = SupabaseStore(SupabaseConfig("https://test-only.supabase.co", "sb_secret_test-only"), LocalStore(tmp_path / "shared-ui.sqlite3"))
    row = {"id": "test-only", "title": "Apple MacBook Air M5 16GB RAM 512GB SSD", "price": "999.00", "currency": "USD",
           "product_url": "https://www.target.com/p/synthetic/-/A-90000001", "source": "target.com", "category": "laptops", "scraped_at": "2026-10-28T12:00:00+00:00"}
    metadata = {"definitions": {"products": {"properties": {key: {} for key in row}}}}
    monkeypatch.setattr(store, "request", Mock(side_effect=[metadata, [row]]))
    monkeypatch.setattr("backend.supabase.SupabaseStore", lambda *a, **kw: store)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "dashboard.py"), default_timeout=60).run()
    app.radio[0].set_value("Live · permitted sources").run()
    next(select for select in app.selectbox if select.label == "Offer storage").set_value("Supabase · read only").run()
    assert store.rows is None
    next(select for select in app.selectbox if select.label == "Availability").set_value("Any").run()
    next(text for text in app.text_input if text.label == "Which laptop are you looking for?").set_value("laptop").run()
    next(button for button in app.button if button.label == "Read shared products").click().run()
    assert not app.exception
    assert any(metric.label == "Exact comparable offers" and metric.value == "0" for metric in app.metric)
    assert len(store.get_embedding(store.listings()[0]["id"])["vector"]) == 384
    assert not any("sb_secret_test-only" in str(message.value) for message in app.json)
