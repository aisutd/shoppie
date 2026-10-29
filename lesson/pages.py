"""Checkpoint 1: fetch one public product page, without database access."""

import re
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup


PRODUCT_PATHS = {
    "amazon": r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:/|$)",
    "bestbuy": r"/(?:site/.+/(\d+)\.p|product/[^/]+/([A-Z0-9]+))(?:/|$)",
    "target": r"/p/.*/A-(\d+)(?:/|$)",
    "walmart": r"/ip/(?:[^/]+/)?(\d+)(?:/|$)",
}


def identify_product(url):
    """Accept only HTTPS product URLs at our four US retailers."""
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.username or parts.password or parts.port:
        raise ValueError("Use an HTTPS product URL without login details or a port.")
    for retailer, pattern in PRODUCT_PATHS.items():
        if parts.hostname in {f"{retailer}.com", f"www.{retailer}.com"}:
            match = re.search(pattern, parts.path)
            if match:
                product_id = next(value for value in match.groups() if value)
                return retailer, product_id
    raise ValueError("Use an Amazon, Best Buy, Target, or Walmart US product page.")


def clean_url(url):
    identify_product(url)
    # Discard tracking parameters and fragments; do not log arbitrary input URLs.
    parts = urlsplit(url)
    return f"https://{parts.hostname}{parts.path}"


def check_page(html):
    soup = BeautifulSoup(html, "html.parser")
    # Inspect visible text, not scripts that may merely mention a bot-check route.
    for tag in soup.select("script, style"):
        tag.decompose()
    lower = soup.get_text(" ", strip=True).lower()
    markers = ["robot check", "validatecaptcha", "verify you are human",
               "verify you're human", "press & hold", "access denied"]
    if any(marker in lower for marker in markers) or soup.select_one('input[name="captchacharacters"]'):
        raise ValueError("Retailer returned a bot check or access-denied page. Stop here.")


def fetch_page(url):
    url = clean_url(url)
    try:
        response = requests.get(
            url, timeout=25, allow_redirects=False,
            headers={"User-Agent": "ShoppieClassroom/1.0 (educational product-page reader)"},
        )
    except requests.RequestException:
        raise ValueError("Page request failed or timed out; no record collected.") from None
    # Redirects are intentionally rejected: review the destination in a browser.
    if response.status_code != 200:
        raise ValueError(f"Retailer returned HTTP {response.status_code}; no record collected.")
    if "text/html" not in response.headers.get("Content-Type", ""):
        raise ValueError("Expected an HTML product page.")
    check_page(response.text)
    return response.text


def fetch_rendered_page(url):
    """Optional Chrome rendering for JavaScript-rendered product pages."""
    try:
        from playwright.sync_api import sync_playwright, Error
    except ImportError:
        raise ValueError("Install requirements-browser.txt to use --browser.") from None
    url = clean_url(url)
    try:
        with sync_playwright() as playwright:
            with playwright.chromium.launch(channel="chrome", headless=True) as browser:
                page = browser.new_page()
                response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                if response is None or response.status != 200:
                    raise ValueError("Browser did not receive a successful product page.")
                # Give client-side product data time to appear; never solve bot checks.
                page.wait_for_timeout(5000)
                html = page.content()
                check_page(html)
                try:
                    same_product = identify_product(page.url) == identify_product(url)
                except ValueError:
                    same_product = False
                if not same_product:
                    raise ValueError("Browser redirected away from the requested product. Review the URL in your browser.")
    except Error:
        raise ValueError("Browser load failed, timed out, or closed. Check Chrome and network access.") from None
    check_page(html)
    return html
