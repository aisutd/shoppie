"""A visible/headless Chromium check with local HTML and no retailer access."""

import json
import os
from pathlib import Path


def check_browser(headed=False):
    from playwright.sync_api import sync_playwright
    root = Path(__file__).resolve().parents[1]
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(root / ".local/browsers"))
    with sync_playwright() as playwright:
        with playwright.chromium.launch(headless=not headed) as browser:
            page = browser.new_page()
            page.set_content("<h1>Shoppie local Chromium check</h1><p>No retailer request is made.</p>")
            assert page.locator("h1").inner_text() == "Shoppie local Chromium check"
            if headed:
                page.wait_for_timeout(1500)
            return {"browser": "Chromium", "version": browser.version, "headed": headed,
                    "source": "controlled local HTML", "live_offer_verified": False}
