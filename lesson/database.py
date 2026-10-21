"""Checkpoint 4: sign in and insert a validated observation into Supabase."""

import getpass
import os
import re
import warnings

import requests

from lesson.validate import Laptop


def save_product(product: Laptop):
    # The CLI calls this function only after validation AND an explicit --save.
    # Importing this module does not read credentials or open a connection.
    base_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
    if not re.fullmatch(r"https://[a-z0-9-]+\.supabase\.co", base_url):
        raise ValueError("Set SUPABASE_URL to your shared project's HTTPS URL.")
    if not key.startswith("sb_publishable_"):
        raise ValueError("Set SUPABASE_PUBLISHABLE_KEY; never use a secret/admin key here.")
    email = input("Supabase student email: ").strip()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("Supabase password (hidden): ")
    except getpass.GetPassWarning:
        raise ValueError("Hidden password input is unavailable. Run in VS Code's terminal.") from None
    try:
        login = requests.post(
            f"{base_url}/auth/v1/token?grant_type=password",
            headers={"apikey": key}, json={"email": email, "password": password},
            timeout=25, allow_redirects=False,
        )
        if login.status_code != 200:
            raise ValueError("Sign-in failed. Check your confirmed account and project settings.")
        token = login.json()["access_token"]
        row = product.model_dump(mode="json")
        # Supabase uses auth.uid() to populate submitted_by; clients don't set it.
        saved = requests.post(
            f"{base_url}/rest/v1/lesson_laptop_observations",
            headers={"apikey": key, "Authorization": f"Bearer {token}",
                     "Prefer": "return=minimal"},
            json=row, timeout=25, allow_redirects=False,
        )
    except (requests.RequestException, KeyError, requests.exceptions.JSONDecodeError):
        # Never print exception bodies: they may contain request headers/tokens.
        raise ValueError("Database request failed; save status may be unknown. Check the table before retrying.") from None
    if saved.status_code not in (200, 201, 204):
        raise ValueError(
            f"Save failed (HTTP {saved.status_code}). Check schema, classroom membership and RLS."
        )
