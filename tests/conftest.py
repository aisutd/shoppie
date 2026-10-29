"""Keep mocked fetches independent without imposing real request delays."""

import pytest


@pytest.fixture(autouse=True)
def reset_scraper_run(monkeypatch):
    from scraper import scraper
    scraper.reset_fetch_state()
    monkeypatch.setattr(scraper, 'MIN_SECONDS_BETWEEN_REQUESTS', 0)
    yield
    scraper.reset_fetch_state()
