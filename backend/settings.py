"""Read local backend settings without exporting or displaying secrets."""

import os
from pathlib import Path
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def setting(name, default=""):
    if name in os.environ:
        return os.environ[name].strip()
    # root settings take priority; existing scraper credentials remain supported
    for path in (ROOT / ".env", ROOT / "scraper/.env"):
        values = dotenv_values(path, interpolate=False) if path.exists() else {}
        if values.get(name):
            return values[name].strip()
    return default


def configuration_status():
    return {"gemini_configured": bool(setting("GEMINI_API_KEY")),
            "gemini_enabled": setting("SHOPPIE_ALLOW_GEMINI") == "1",
            "gemini_model": setting("GEMINI_MODEL", "gemini-3.8-flash"),
            "supabase_url_configured": bool(setting("SUPABASE_URL")),
            "supabase_key_configured": bool(setting("SUPABASE_SECRET_KEY")),
            "postgres_dsn_configured": bool(setting("SHOPPIE_DATABASE_URL")),
            "shared_writes_enabled": False}
