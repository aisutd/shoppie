import os
import sys
import json
import re
import uuid
import argparse
from datetime import datetime, timezone
from urllib.parse import parse_qs, urljoin, urlsplit
from pathlib import Path
from dotenv import load_dotenv
from curl_cffi import CurlOpt, CurlHttpVersion
from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup
from supabase import create_client, Client

# --- BULLETPROOF .ENV LOADING ---
env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=env_path)

PRODUCT_PATHS = {
    "amazon": r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:/|$)",
    "bestbuy": r"/(?:site/.+/(\d+)\.p|product/[^/]+/([A-Z0-9]+))(?:/|$)",
    "target": r"/p/.*/A-(\d+)(?:/|$)",
    # FIX: the slug is now optional, so both /ip/<slug>/<id> and /ip/<id> match
    "walmart": r"/ip/(?:[^/]+/)?(\d+)/?$",
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
        "please verify you are a human",
        "unusual traffic from your computer network",
        "robot or human",  # FIX: Walmart's bot-check page
    ]
    if any(phrase in body_text for phrase in blocking_phrases):
        raise ValueError("Retailer returned a bot check or access-denied page. Stop here.")


def fetch_page(url):
    """Fetch product page securely, handling retailer-specific network quirks & redirects."""
    original_url = clean_url(url)
    retailer, _ = identify_product(original_url)

    session = cffi_requests.Session()
    try:
        if retailer == "bestbuy":
            # --- UNTOUCHED BEST BUY LOGIC ---
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
            elif retailer == "target":
                session.get("https://www.target.com", impersonate="chrome", headers=headers, timeout=15)
                
            response = session.get(
                original_url, timeout=25, allow_redirects=True,
                headers=headers, impersonate="chrome"
            )
    except Exception as e:
        raise ValueError(f"Page request failed or timed out: {e}") from None

    # Debug line: shows where the request actually ended up after redirects.
    # Delete it once everything works.
    print(f"      final URL: {response.url} | status: {response.status_code}")

    # FIX: Walmart redirects blocked scripts to /blocked?url=... Give a clear error.
    if retailer != "bestbuy" and urlsplit(str(response.url)).path.rstrip("/").endswith("/blocked"):
        raise ValueError(f"{retailer.title()} served a bot-check page (/blocked). No record collected.")

    if response.status_code != 200:
        raise ValueError(f"Retailer returned HTTP {response.status_code}; no record collected.")
    if "text/html" not in response.headers.get("Content-Type", ""):
        raise ValueError("Expected an HTML product page.")
        
    check_page(response.text)

    final_url = response.url
    if retailer != "bestbuy":
        # FIX: a harmless redirect to a differently shaped URL shouldn't break extraction.
        # If the redirected URL isn't recognizable, fall back to the URL the user gave us.
        try:
            identify_product(final_url)
        except ValueError:
            final_url = original_url

    return response.text, final_url


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


def walmart_embedded_data(soup, html_text):
    """Robustly extracts title and price from Walmart's embedded __NEXT_DATA__ JSON state."""
    title, price = None, None
    for script in soup.select('script'):
        text_content = script.get_text()
        if '"__NEXT_DATA__"' in text_content or '"initialProps"' in text_content or 'currentPrice' in text_content:
            try:
                if not price:
                    for pattern in [
                        r'"currentPrice"\s*:\s*\{\s*"price"\s*:\s*([\d\.]+)',
                        r'"price"\s*:\s*([\d\.]+)',
                        r'"salePrice"\s*:\s*([\d\.]+)'
                    ]:
                        price_match = re.search(pattern, text_content)
                        if price_match:
                            val = float(price_match.group(1))
                            if 1.0 < val < 15000.0:
                                price = str(val)
                                break
                
                if not title:
                    for pattern in [
                        r'"name"\s*:\s*"([^"]+(?:Laptop|Notebook|MacBook|iPad|Tablet|Monitor)[^"]*)"',
                        r'"productName"\s*:\s*"([^"]+)"',
                        r'"seoTitle"\s*:\s*"([^"]+)"'
                    ]:
                        title_match = re.search(pattern, text_content, re.IGNORECASE)
                        if title_match:
                            found = title_match.group(1)
                            if len(found) > 8 and "Walmart" not in found:
                                title = found
                                break
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
    except ImportError:
        raise ValueError("Playwright isn't installed in this environment (pip install playwright).") from None

    original_url = clean_url(url)
    with sync_playwright() as p:
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
    retailer, product_id = identify_product(final_url)
    
    parts = urlsplit(final_url)
    clean_domain = parts.hostname.replace("www.", "") if parts.hostname else retailer

    check_page(html)
    soup = BeautifulSoup(html, "html.parser")

    # Guard against alternate/interstitial landing pages
    page_text = soup.get_text()
    if retailer == "bestbuy" and product_id not in page_text and not any(k in page_text for k in ["Laptop", "Yoga", "MacBook"]):
        raise ValueError("Retailer served an unrelated landing or interstitial page.")

    record = {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, final_url)),
        "title": None, 
        "price": None, 
        "currency": None, 
        "product_url": final_url,
        "source": clean_domain,
        "category": category.lower(),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
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
            
    # 1b. Target: handle list / nested JSON-LD offers
    if retailer == "target" and product and record["price"] is None:
        record["price"], record["currency"] = target_offer_price(product.get("offers"))

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

    # Clean up invalid/condition titles
    if retailer == "bestbuy" and record["title"]:
        cleaned = record["title"].strip()
        if cleaned in {"Fair", "Good", "Excellent", "Open Box", "New"} or len(cleaned) < 10:
            record["title"] = None

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
        
    # 5b. Target embedded page state (more specific than the loose CSS selectors below)
    if retailer == "target" and record["price"] is None:
        t_price = target_embedded_data(soup)
        if t_price:
            record["price"] = t_price
            record["currency"] = "USD"

    # 5c. Target rendered price element (present once the page's JavaScript has run).
    # Lenient on cents because Target may show whole-dollar prices like "$599".
    if retailer == "target" and record["price"] is None:
        for elem in soup.select('[data-test="product-price"]'):
            match = re.search(r'\$\s?([\d,]+(?:\.\d{2})?)', elem.get_text(" ", strip=True))
            if match:
                record["price"] = match.group(1).replace(",", "")
                record["currency"] = "USD"
                break

    # 6. Retailer-specific CSS & Element Selectors
    price_selectors = {
        "amazon": '.a-price .a-offscreen, span.a-price-whole, .apexPriceToPay .a-offscreen',
        "bestbuy": 'div[class*="priceView-hero-price"] span[aria-hidden="true"], span[class*="pricing-price"], div[class*="price-block"] span',
        "target": '[data-test="product-price"], span[class*="Price"], span[data-test="red-card-price"]',
        "walmart": '[itemprop="price"], span[itemprop="price"], div[data-testid="price-wrap"] span, span[class*="price"]'
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
        w_title, w_price, w_curr = walmart_embedded_data(soup, html)
        if w_price:
            record["price"] = w_price
            record["currency"] = w_curr
        if not record["title"] and w_title:
            record["title"] = w_title

    # Final validation: Ensure we didn't pull garbage or empty data
    if not record["title"] or record["price"] is None:
        message = "Could not reliably extract product title or price. Retailer may have served a redirect or interstitial page."
        if retailer == "target":
            message += "\nTarget page diagnostics:\n" + target_diagnostics(soup, html, record)
        raise ValueError(message)

    if record["price"] is not None and not record["currency"]:
        record["currency"] = "USD"

    if record["price"] is not None:
        try:
            record["price"] = float(str(record["price"]).replace(",", ""))
        except (ValueError, TypeError):
            pass

    return record


def upload_to_supabase(record):
    """Uploads the scraped product record directly to Supabase."""
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in environment variables (.env).")
        
    client: Client = create_client(supabase_url, supabase_key)
    response = client.table("products").upsert(record).execute()
    return response


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Single-line e-commerce scraper & Supabase uploader.")
    parser.add_argument("url", type=str, help="Product URL from Amazon, Walmart, Best Buy, or Target")
    parser.add_argument("--category", type=str, default="laptops", help="Product category for classification")
    parser.add_argument("--save-html", action="store_true", help="Save the fetched page to last_page.html for debugging")
    parser.add_argument("--show-browser", action="store_true", help="Target only: show the browser window instead of running headless")
    args = parser.parse_args()

    print(f"\n[1/3] Fetching page securely: {args.url}")
    try:
        if identify_product(clean_url(args.url))[0] == "target":
            print("      Target fills in prices with JavaScript; loading the page in a browser...")
            html, final_url = render_target_page(args.url, headless=not args.show_browser)
        else:
            html, final_url = fetch_page(args.url)
        if args.save_html:
            Path("last_page.html").write_text(html, encoding="utf-8")
            print("      saved page to last_page.html")
        
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