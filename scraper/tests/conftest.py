"""Enforce offline tests without Supabase credentials or private .env reads."""

import socket
from pathlib import Path

import pytest

from scraper import config


@pytest.fixture(autouse=True)
def offline_without_real_credentials(monkeypatch):
    for name in ("SUPABASE_URL", "SUPABASE_SECRET_KEY", "SUPABASE_PUBLISHABLE_KEY",
                 "SUPABASE_KEY", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
        monkeypatch.delenv(name, raising=False)

    def blocked_network(*args, **kwargs):
        raise AssertionError("Offline tests must not open network connections.")

    monkeypatch.setattr(socket.socket, "connect", blocked_network)
    monkeypatch.setattr(socket, "create_connection", blocked_network)

    real_dotenv = Path(__file__).resolve().parents[1] / ".env"
    parse_dotenv = config.dotenv_values

    def temporary_dotenv_only(path, *args, **kwargs):
        if Path(path).resolve() == real_dotenv:
            raise AssertionError("Tests must use temporary configuration, not scraper/.env.")
        return parse_dotenv(path, *args, **kwargs)

    monkeypatch.setattr(config, "dotenv_values", temporary_dotenv_only)
