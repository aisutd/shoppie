"""Resolve script-relative files; load backend settings only for DB commands."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values


SCRIPT_DIR = Path(__file__).resolve().parent


def script_path(path):
    """Relative config/input paths belong to scraper/, not the terminal's cwd."""
    path = Path(path)
    return path if path.is_absolute() else SCRIPT_DIR / path


def load_urls(path="urls.txt"):
    try:
        lines = script_path(path).read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        raise ValueError("Could not read the URL file. Relative paths start inside scraper/.") from None
    urls = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
    if not urls:
        raise ValueError("The URL file is empty. Add a real retailer product URL.")
    return list(dict.fromkeys(urls))


@dataclass(frozen=True)
class DatabaseConfig:
    url: str
    secret_key: str = field(repr=False)


class ConfigurationError(ValueError):
    """Safe configuration message containing variable names, never values."""


def load_database_config():
    """Used by --check-db or --save. Importing this module reads no credentials."""
    try:
        local = dotenv_values(SCRIPT_DIR / ".env", encoding="utf-8-sig", interpolate=False)
    except (OSError, UnicodeError):
        raise ConfigurationError("CONFIGURATION FAILURE: could not read scraper/.env.") from None
    url = os.environ.get("SUPABASE_URL", local.get("SUPABASE_URL") or "").strip().rstrip("/")
    key = os.environ.get("SUPABASE_SECRET_KEY", local.get("SUPABASE_SECRET_KEY") or "").strip()
    missing = []
    if not url:
        missing.append("SUPABASE_URL")
    if not key:
        missing.append("SUPABASE_SECRET_KEY")
    if missing:
        raise ConfigurationError("MISSING CONFIGURATION: set " + ", ".join(missing) + " in scraper/.env or environment variables.")
    if not re.fullmatch(r"https://[a-z0-9-]+\.supabase\.co", url):
        raise ConfigurationError("INVALID CONFIGURATION: SUPABASE_URL must be an HTTPS Supabase project URL.")
    if not key.startswith("sb_secret_") or any(character.isspace() for character in key):
        raise ConfigurationError("INVALID CONFIGURATION: SUPABASE_SECRET_KEY must be a modern sb_secret_ backend key.")
    return DatabaseConfig(url=url, secret_key=key)
