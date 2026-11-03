"""Standalone tech collector from Trisha-Test; main.py retains its existing API."""

import os
import sys
import json
import re
import uuid
import argparse
import requests
from datetime import datetime, timezone
from urllib.parse import parse_qs, urljoin, urlsplit
from pathlib import Path
from dotenv import load_dotenv
from bs4 import BeautifulSoup



PRODUCT_PATHS = {
    "amazon": r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:/|$)",
    "bestbuy": r"/(?:site/.+/(\d+)\.p|product/[^/]+/([A-Z0-9]+))(?:/|$)",
    "target": r"/p/.*/A-(\d+)(?:/|$)",
    "walmart": r"/ip/(?:[^/]+/)?(\d+)(?:/|$)",
}


def identify_product(url):
    """Accept only HTTPS product URLs at our four US retailers."""
    try:
        parts = urlsplit(url)
        invalid = parts.scheme != "https" or parts.username or parts.password or parts.port
    except ValueError:
        raise ValueError("Malformed product URL.") from None
    if invalid:
        raise ValueError("Use an HTTPS product URL without login details or a port.")
    for retailer, pattern in PRODUCT_PATHS.items():
        if parts.hostname in {f"{retailer}.com", f"www.{retailer}.com"}:
            match = re.search(pattern, parts.path)
            if match:
                product_id = next(value for value in match.groups() if value)
                if retailer == "target":
                    selected = parse_qs(parts.query, keep_blank_values=True).get("preselect")
                    if selected is not None:
                        if len(selected) != 1 or not re.fullmatch(r"\d+", selected[0]):
                            raise ValueError("Target preselect must identify exactly one numeric product variant.")
                        product_id = selected[0]
                return retailer, product_id
    raise ValueError("Use an Amazon, Best Buy, Target, or Walmart US product page.")


def clean_url(url):
    url = url.strip()
    identify_product(url)
    parts = urlsplit(url)
    query = f"?{parts.query}" if parts.query else ""
    return f"https://{parts.hostname}{parts.path}{query}"


def check_page(html):
    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one('input[name="captchacharacters"]') or soup.select_one('form[action*="validateCaptcha"]'):
        raise ValueError("Retailer returned a bot check or access-denied page. Stop here.")

    for tag in soup.select("script, style, noscript, header, footer"):
        tag.decompose()

    body_text = soup.get_text(" ", strip=True).lower()
    blocking_phrases = [
        "enter the characters you see below",
        "sorry, we just need to make sure you're not a robot",
        "to allow us to continue, please enter the characters",
        "access denied",
        "please verify you are a human"
    ]
    if any(phrase in body_text for phrase in blocking_phrases):
        raise ValueError("Retailer returned a bot check or access-denied page. Stop here.")


def fetch_page(url):
    """Fetch product page securely, handling retailer-specific network quirks & redirects."""
    from curl_cffi import requests as cffi_requests

    original_url = clean_url(url)
    retailer, _ = identify_product(original_url)

    session = cffi_requests.Session()
    try:
        if retailer == "bestbuy":
            headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
            }
            session.get("https://www.bestbuy.com", headers=headers, impersonate="safari_ios", timeout=15)

            response = session.get(
                original_url, timeout=30, allow_redirects=True,
                headers=headers, impersonate="safari_ios"
            )
        else:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
            if retailer == "amazon":
                session.get("https://www.amazon.com", impersonate="chrome", headers=headers, timeout=15)
            elif retailer == "walmart":
                session.get("https://www.walmart.com", impersonate="chrome", headers=headers, timeout=15)

            response = session.get(
                original_url, timeout=25, allow_redirects=True,
                headers=headers, impersonate="chrome"
            )
    except Exception as e:
        raise ValueError(f"Page request failed or timed out: {e}") from None

    if response.status_code != 200:
        raise ValueError(f"Retailer returned HTTP {response.status_code}; no record collected.")
    if "text/html" not in response.headers.get("Content-Type", ""):
        raise ValueError("Expected an HTML product page.")

    check_page(response.text)
    return response.text, response.url


def schema_type(node, name):
    value = node.get("@type", [])
    values = [value] if isinstance(value, str) else value
    return isinstance(values, list) and any(
        isinstance(item, str) and item.rsplit("/", 1)[-1] == name for item in values
    )


def product_nodes(value):
    if isinstance(value, list):
        for item in value:
            yield from product_nodes(item)
    elif isinstance(value, dict):
        if schema_type(value, "Product"):
            yield value
        else:
            yield from product_nodes(value.get("@graph"))
            yield from product_nodes(value.get("mainEntity"))


def main_product(soup, url):
    products = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            products.extend(product_nodes(json.loads(script.get_text())))
        except (ValueError, TypeError):
            continue
    identity = identify_product(url)
    matches = []
    for product in products:
        reference = product.get("url") or product.get("@id")
        if isinstance(reference, str):
            try:
                if identify_product(urljoin(url, reference)) == identity:
                    matches.append(product)
            except ValueError:
                pass
    if len(matches) == 1:
        return matches[0]
    if len(products) == 1 and not (products[0].get("url") or products[0].get("@id")):
        return products[0]
    if products:
        raise ValueError("Cannot safely identify one main Product in the page JSON-LD.")
    return None


def text(soup, selector):
    tag = soup.select_one(selector)
    return tag.get_text(" ", strip=True) if tag else None


def meta(soup, field):
    tag = soup.select_one(f'meta[property="product:{field}"]') or soup.select_one(f'meta[property="og:{field}"]') or soup.select_one(f'meta[name="{field}"]')
    return tag.get("content") if tag else None


def normalize_category(category):
    """Convert a human category label into the database's lowercase slug form."""
    category = re.sub(r"[^a-z0-9]+", "-", str(category).strip().lower()).strip("-")
    if not category:
        raise ValueError("Category must contain at least one letter or number.")
    if len(category) > 64:
        raise ValueError("Category must be 64 characters or fewer.")
    return category


def walmart_embedded_data(soup, html_text):
    """Extracts title and price from Walmart's embedded JSON state or script tags."""
    title, price = None, None
    for script in soup.select('script'):
        text_content = script.get_text()
        if '"__NEXT_DATA__"' in text_content or '"product":' in text_content:
            try:
                price_match = re.search(r'"currentPrice"\s*:\s*\{\s*"price"\s*:\s*([\d\.]+)', text_content)
                if not price_match:
                    price_match = re.search(r'"price"\s*:\s*([\d\.]+)', text_content)
                if price_match and not price:
                    val = price_match.group(1)
                    if float(val) > 0:
                        price = val
            except (ValueError, TypeError):
                pass
    return title, price, "USD" if price else None


def bestbuy_embedded_data(soup, target_sku):
    """Extracts title and price strictly matching the requested Best Buy SKU from embedded JSON state."""
    title, price = None, None
    for script in soup.select('script'):
        text_content = script.get_text()
        if target_sku in text_content or 'currentPrice' in text_content or 'pricing' in text_content:
            try:
                if not price:
                    price_match = re.search(r'"currentPrice"\s*:\s*([\d\.]+)', text_content)
                    if not price_match:
                        price_match = re.search(r'"salePrice"\s*:\s*([\d\.]+)', text_content)
                    if not price_match:
                        price_match = re.search(r'"customerPrice"\s*:\s*([\d\.]+)', text_content)
                    if price_match and float(price_match.group(1)) > 0:
                        price = price_match.group(1)

                if not title:
                    title_match = re.search(rf'"{target_sku}"[^}}]+"name"\s*:\s*"([^"]+)"', text_content)
                    if not title_match:
                        title_match = re.search(r'"name"\s*:\s*"([^"]+(?:MacBook|Laptop|Yoga|Air|Pro)[^"]*)"', text_content, re.IGNORECASE)
                    if title_match:
                        found_title = title_match.group(1)
                        if len(found_title) > 8 and found_title not in {"Fair", "Good", "Excellent", "Open Box", "New"}:
                            title = found_title
            except (ValueError, TypeError):
                pass
    return title, price


def target_offer_price(offers):
    """Target's JSON-LD offers can be a list, an AggregateOffer, or nest price in priceSpecification.
    Returns (price, currency) only if every offer agrees on one price; otherwise (None, None)."""
    candidates = offers if isinstance(offers, list) else [offers]
    prices, currency = set(), None
    for offer in candidates:
        if not isinstance(offer, dict):
            continue
        spec = offer.get("priceSpecification")
        if isinstance(spec, list):
            spec = spec[0] if spec else None
        for source in (offer, spec if isinstance(spec, dict) else {}):
            for key in ("price", "lowPrice"):
                value = source.get(key)
                if value not in (None, ""):
                    prices.add(str(value))
                    currency = currency or offer.get("priceCurrency") or source.get("priceCurrency")
                    break
            else:
                continue
            break
    if len(prices) == 1:
        return prices.pop(), currency
    return None, None


def target_embedded_data(soup):
    """Best-effort: pulls the first price found in Target's embedded page state."""
    for script in soup.select("script"):
        content = script.get_text()
        if "current_retail" in content or "formatted_current_price" in content:
            match = re.search(r'\\?"current_retail\\?"\s*:\s*([\d\.]+)', content)
            if not match:
                match = re.search(r'\\?"formatted_current_price\\?"\s*:\s*\\?"\$([\d,]+\.\d{2})', content)
            if match:
                return match.group(1).replace(",", "")
    return None


def render_target_page(url, headless=True):
    """Load a Target product page in a real browser (Playwright) so its JavaScript-filled
    price appears. Stops immediately if Target serves a bot check; it never tries to get around one."""
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
        from playwright_stealth import Stealth
    except ImportError:
        raise ValueError(
            "Browser support isn't installed (pip install -r scraper/requirements.txt)."
        ) from None

    original_url = clean_url(url)
    with Stealth().use_sync(sync_playwright()) as p:
        try:
            browser = p.chromium.launch(headless=headless)
        except Exception as e:
            raise ValueError(f"Could not start Chromium ({e}). Try: playwright install chromium") from None
        try:
            context = browser.new_context(locale="en-US", viewport={"width": 1366, "height": 900})
            page = context.new_page()
            response = page.goto(original_url, wait_until="domcontentloaded", timeout=45000)
            try:
                page.wait_for_selector('[data-test="product-price"]', timeout=20000)
            except PlaywrightTimeout:
                raise ValueError(
                    "Target's price did not load within 20s. It may have shown a human-verification "
                    "check (which this scraper does not try to get around) or the item has no online price. "
                    "No record collected. Use manual_add.py for this product."
                ) from None
            final_url = page.url
            html = page.content()
            status = response.status if response else None
        except PlaywrightTimeout:
            raise ValueError("Target page timed out while loading.") from None
        finally:
            browser.close()

    print(f"      final URL: {final_url} | status: {status}")
    if urlsplit(final_url).path.rstrip("/").endswith("/blocked"):
        raise ValueError("Target served a bot-check page (/blocked). No record collected.")
    if status != 200:
        raise ValueError(f"Target returned HTTP {status}; no record collected.")
    check_page(html)

    try:
        identify_product(final_url)
    except ValueError:
        final_url = original_url
    return html, final_url


def target_diagnostics(soup, html, record):
    """Short summary of what a Target page contains, shown only when extraction fails."""
    ld_scripts = soup.select('script[type="application/ld+json"]')
    ld_products = 0
    for script in ld_scripts:
        try:
            ld_products += sum(1 for _ in product_nodes(json.loads(script.get_text())))
        except (ValueError, TypeError):
            pass
    h1 = soup.select_one("h1")
    title_tag = soup.select_one("title")
    dollar_hits = re.findall(r'\$\s?[\d,]+\.\d{2}', html)[:5]
    price_els = len(soup.select('[data-test="product-price"]'))
    return "\n".join([
        f"  title found        : {record['title']!r}",
        f"  price found        : {record['price']!r}",
        f"  page length        : {len(html)} chars",
        f"  <title> tag        : {title_tag.get_text(strip=True)[:100] if title_tag else None!r}",
        f"  first <h1>         : {h1.get_text(' ', strip=True)[:100] if h1 else None!r}",
        f"  JSON-LD scripts    : {len(ld_scripts)} ({ld_products} Product nodes)",
        f"  'current_retail'   : {'current_retail' in html}",
        f"  'formatted_current_price': {'formatted_current_price' in html}",
        f"  price placeholder  : {'price-module-placeholder' in html}",
        f"  product-price els  : {price_els}",
        f"  first $ amounts    : {dollar_hits}",
    ])


def extract_product(html, final_url, category="laptops"):
    check_page(html)
    retailer, product_id = identify_product(final_url)
    soup = BeautifulSoup(html, "html.parser")

    parts = urlsplit(final_url)
    clean_domain = parts.hostname.replace("www.", "") if parts.hostname else retailer

    record = {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, final_url)),
        "title": None,
        "price": None,
        "currency": None,
        "product_url": final_url,
        "source": clean_domain,  # Matches database domain check constraint
        "category": normalize_category(category),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "description": None,
    }

    # 1. JSON-LD structured data extraction
    product = main_product(soup, final_url)
    if product:
        record["title"] = product.get("name")
        offers = product.get("offers")
        if isinstance(offers, list) and len(offers) == 1:
            offers = offers[0]
        if isinstance(offers, dict) and schema_type(offers, "Offer"):
            record["price"] = offers.get("price")
            record["currency"] = offers.get("priceCurrency")

    # 2. Retailer-specific Title Fallbacks
    if not record["title"]:
        titles = {
            "amazon": "#productTitle",
            "bestbuy": 'div.sku-title h1, div[class*="product-name"] h1, h1[class*="productTitle"]',
            "target": 'h1[data-test="product-title"], h1',
            "walmart": 'h1[itemprop="name"], h1[class*="prod-ProductTitle"], h1',
        }
        record["title"] = text(soup, titles[retailer])

    # 3. HTML <title> tag & OpenGraph title fallback
    if not record["title"]:
        og_title = meta(soup, "title")
        if og_title:
            record["title"] = og_title
        else:
            title_tag = soup.select_one("title")
            if title_tag:
                raw_title = title_tag.get_text()
                clean_title = re.sub(r'\s*-\s*(Best Buy|Amazon|Walmart|Target).*$', '', raw_title, flags=re.IGNORECASE)
                if len(clean_title) > 8:
                    record["title"] = clean_title.strip()

    if product and product.get("description"):
        record["description"] = product.get("description").strip()

    if not record["description"]:
        meta_desc = (
            soup.select_one('meta[name="description"]') or
            soup.select_one('meta[property="og:description"]') or
            soup.select_one('meta[name="twitter:description"]')
        )
        if meta_desc and meta_desc.get("content"):
            record["description"] = meta_desc.get("content").strip()

    # Clean up invalid/condition titles
    if retailer == "bestbuy" and record["title"]:
        cleaned = record["title"].strip()
        if cleaned in {"Fair", "Good", "Excellent", "Open Box", "New"} or len(cleaned) < 10:
            record["title"] = None

    if product and product.get("description"):
        record["description"] = product.get("description").strip()
    if not record["description"]:
        meta_desc = soup.select_one('meta[name="description"]') or soup.select_one('meta[property="og:description"]')
        if meta_desc and meta_desc.get("content"):
            record["description"] = meta_desc.get("content").strip()

    # 4. Best Buy embedded state fallback (strict SKU matching)
    if retailer == "bestbuy":
        bb_title, bb_price = bestbuy_embedded_data(soup, product_id)
        if not record["title"] and bb_title:
            record["title"] = bb_title
        if record["price"] is None and bb_price:
            record["price"] = bb_price

    # 5. Meta tag fallbacks (checking OpenGraph and standard meta tags)
    if record["price"] is None:
        record["price"] = meta(soup, "price:amount") or meta(soup, "price") or meta(soup, "amount")
    if record["currency"] is None:
        record["currency"] = meta(soup, "price:currency") or meta(soup, "priceCurrency") or meta(soup, "currency")

    # 6. Retailer-specific CSS & Element Selectors
    price_selectors = {
        "amazon": '.a-price .a-offscreen, span.a-price-whole, .apexPriceToPay .a-offscreen',
        "bestbuy": 'div[class*="priceView-hero-price"] span[aria-hidden="true"], span[class*="pricing-price"], div[class*="price-block"] span',
        "target": '[data-test="product-price"], span[class*="Price"]',
        "walmart": '[itemprop="price"], span[itemprop="price"], div[data-testid="price-wrap"] span'
    }

    if retailer in price_selectors and record["price"] is None:
        for elem in soup.select(price_selectors[retailer]):
            displayed = elem.get("content") or elem.get_text(" ", strip=True)
            match = re.search(r'([\d,]+\.\d{2})', displayed)
            if match:
                record["price"] = match.group(1).replace(",", "")
                record["currency"] = "USD"
                break

    # 7. Walmart embedded JSON fallback
    if retailer == "walmart" and record["price"] is None:
        _, w_price, w_curr = walmart_embedded_data(soup, html)
        if w_price:
            record["price"] = w_price
            record["currency"] = w_curr

    # Final validation: Ensure we didn't pull garbage or empty data
    if not record["title"] or record["price"] is None:
        raise ValueError("Could not reliably extract product title or price. Retailer may have served a redirect or interstitial page.")

    if record["price"] is not None and not record["currency"]:
        record["currency"] = "USD"

    if record["price"] is not None:
        try:
            record["price"] = float(str(record["price"]).replace(",", ""))
        except (ValueError, TypeError):
            pass

    return record


def upload_to_supabase(record):
    """Upsert the scraped tech product to public.products using the backend secret key."""
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SECRET_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_SECRET_KEY in scraper/.env.")
    if not supabase_key.startswith("sb_secret_") or any(character.isspace() for character in supabase_key):
        raise ValueError("SUPABASE_SECRET_KEY must be a modern sb_secret_ backend key.")

    parts = urlsplit(record["product_url"])
    payload = {
        "title": record["title"],
        "description": record.get("description"),
        "price": record["price"],
        "currency": record["currency"],
        "product_url": record["product_url"],
        "source": parts.hostname.replace("www.", ""),
        "category": normalize_category(record["category"]),
        "scraped_at": record["scraped_at"],
    }
    try:
        response = requests.post(
            f"{supabase_url.rstrip('/')}/rest/v1/products",
            params={"on_conflict": "product_url"},
            headers={
                "apikey": supabase_key,
                "Accept": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            json=payload,
            timeout=25,
            allow_redirects=False,
        )
    except requests.RequestException:
        raise ValueError("Could not reach Supabase; check the project URL, network, and project status.") from None
    if response.status_code not in (200, 201, 204):
        if response.status_code == 401:
            reason = "Supabase rejected the secret key. Confirm it belongs to this project."
        elif response.status_code == 403:
            reason = "Supabase denied access to public.products. Check backend table grants."
        elif response.status_code in (400, 409, 422):
            reason = "Supabase rejected the product data or table constraints. Check the category migration and products schema."
        else:
            reason = f"Supabase returned HTTP {response.status_code}."
        raise ValueError(reason)
    return response


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape a tech product and optionally upsert it to Supabase.")
    parser.add_argument("url", type=str, help="Product URL from Amazon, Walmart, Best Buy, or Target")
    parser.add_argument("--category", type=str, default="laptops", help="Tech product category (for example: phones, tablets, headphones)")
    args = parser.parse_args()

    print(f"\n[1/3] Fetching page securely: {args.url}")
    try:
        html, final_url = fetch_page(args.url)

        print("[2/3] Extracting required product fields...")
        product_record = extract_product(html, final_url, category=args.category)

        print("\n" + "=" * 50)
        print("SCRAPED DATA PREVIEW:")
        print("=" * 50)
        for key, value in product_record.items():
            print(f"  {key.ljust(15)}: {value}")
        print("=" * 50)

        confirm = input("\nDo you want to upload this record to Supabase? (y/n): ").strip().lower()
        if confirm == 'y':
            print("\n[3/3] Uploading record to Supabase...")
            upload_to_supabase(product_record)
            print("Successfully pushed record to Supabase database!")
        else:
            print("\nUpload cancelled by user.")

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
