"""Retired discovery reference for regression tests; never used by the app or CLI.

Best Buy API, Brave, and sitemap providers require separate access. They are kept
only to preserve earlier tested code; the main workflow supports Gemini only.
"""

import gzip
import io
import os
import re
import zlib
from urllib.parse import quote, unquote, urlsplit, urljoin
import xml.etree.ElementTree as ET

import requests
from scraper.scraper import clean_url, unique_urls
from backend.access import fetch_robots, read_public, robots_permit

PROVIDERS = ("bestbuy_sitemap", "bestbuy_api", "brave")
SITEMAP_HOST = "sitemaps.bestbuy.com"


def usable_urls(values, retailer=None):
    urls = []
    for value in values:
        try:
            url = clean_url(value)
            if retailer and urlsplit(url).hostname not in {retailer + ".com", "www." + retailer + ".com"}:
                continue
            urls.append(url)
        except (ValueError, AttributeError, TypeError):
            continue
    return unique_urls(urls)


def brave_urls(query, limit):
    key = os.environ.get("BRAVE_SEARCH_API_KEY")
    if not key:
        raise ValueError("Live discovery needs BRAVE_SEARCH_API_KEY for Brave, or choose bestbuy_sitemap (no API key).")
    search_query = query + " (site:amazon.com OR site:bestbuy.com OR site:target.com OR site:walmart.com)"
    if len(search_query) > 600 or len(search_query.split()) > 75:
        raise ValueError("Live discovery query exceeds the search API size limit")
    try:
        response = requests.get("https://api.search.brave.com/res/v1/web/search",
            headers={"X-Subscription-Token": key, "Accept": "application/json"},
            params={"q": search_query, "count": 20}, timeout=20, allow_redirects=False)
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("Unexpected search response")
        found = response.json().get("web", {}).get("results", [])
        if not isinstance(found, list):
            raise ValueError("Expected search results")
    except (requests.RequestException, ValueError, AttributeError):
        raise ValueError("Brave discovery failed, was denied, or was rate limited; no fallback request was made.") from None
    return usable_urls(item.get("url") for item in found if isinstance(item, dict))[:limit]


def sitemap_locations(data):
    if data.startswith(b"\x1f\x8b"):
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as archive:
                data = archive.read(16_000_001)
        except (OSError, EOFError, zlib.error):
            raise ValueError("Invalid compressed sitemap") from None
    if len(data) > 16_000_000 or b"\x00" in data or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("Sitemap exceeds safe XML limits")
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        raise ValueError("Source did not return a valid sitemap") from None
    kind = root.tag.rsplit("}", 1)[-1]
    if kind not in {"sitemapindex", "urlset"}:
        raise ValueError("Expected a sitemap index or URL set")
    locations = []
    for item in root:
        for child in item:
            if child.tag.rsplit("}", 1)[-1] == "loc" and child.text:
                locations.append(child.text.strip())
    return kind, locations


def bestbuy_sitemap(query, limit):
    robots = fetch_robots("https://www.bestbuy.com")
    # uses only product sitemaps actually advertised by the retailer
    roots = [line.split(":", 1)[1].strip() for line in robots.splitlines()
             if line.lower().startswith("sitemap:") and "sitemaps_pdp" in line]
    pending = list(roots[:1])
    host_rules = fetch_robots("https://" + SITEMAP_HOST) if pending else ""
    visited, products, entries, truncated = set(), [], 0, False
    while pending and len(visited) < 3:
        url = pending.pop(0)
        parts = urlsplit(url)
        if (parts.scheme != "https" or parts.hostname != SITEMAP_HOST or parts.port
                or parts.username or parts.password or parts.query or parts.fragment
                or not re.fullmatch(r"/sitemaps_pdp(?:\.\d+)?\.xml(?:\.gz)?", parts.path)):
            raise ValueError("Published sitemap points outside the supported product sitemap host/path")
        if url in visited:
            continue
        if not robots_permit(host_rules, url):
            raise ValueError("Published sitemap is disallowed by its host's robots rules")
        visited.add(url)
        kind, locations = sitemap_locations(read_public(url))
        if kind == "sitemapindex":
            pending.extend(locations[:2])
            truncated = truncated or len(locations) > 2
        else:
            entries += min(len(locations), 50_000)
            truncated = truncated or len(locations) > 50_000
            products.extend(usable_urls(locations[:50_000], "bestbuy"))
    words = set(re.findall(r"[a-z0-9]+", query.casefold())) - {"laptop", "notebook", "ram", "ssd", "gb", "tb", "with", "and"}
    ranked = []
    for url in products:
        slug = unquote(urlsplit(url).path).casefold()
        if not any(word in slug for word in ("laptop", "macbook", "notebook", "chromebook")):
            continue
        tokens = set(re.findall(r"[a-z0-9]+", slug))
        score = len(words & tokens)
        if score:
            ranked.append((score, url))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    urls = unique_urls([url for score, url in ranked])[:limit]
    return {"urls": urls, "documents_read": len(visited), "entries_scanned": entries,
            "coverage": "bounded published sitemap sample; URL keywords only, not a full catalog search",
            "truncated": bool(pending) or truncated}


def bestbuy_api_urls(query, limit):
    key = os.environ.get("BESTBUY_API_KEY")
    if not key:
        raise ValueError("bestbuy_api needs a Best Buy developer API key in BESTBUY_API_KEY; no paid search API is used.")
    words = re.findall(r"[a-zA-Z0-9]+", query)[:12]
    expression = "&".join("search=" + quote(word, safe="") for word in words)
    if not expression:
        raise ValueError("Discovery query must contain product keywords")
    try:
        response = requests.get("https://api.bestbuy.com/v1/products(" + expression + ")",
            params={"apiKey": key, "format": "json", "show": "sku,name,url", "pageSize": limit},
            timeout=20, allow_redirects=False)
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("Unexpected API response")
        products = response.json()["products"]
        if not isinstance(products, list):
            raise ValueError("Expected products array")
    except (requests.RequestException, ValueError, KeyError, TypeError):
        # never echoes request URLs: this API carries its secret in query parameters
        raise ValueError("Best Buy API discovery failed or was denied/rate limited; check developer access.") from None
    urls = []
    for product in products[:limit]:
        if not isinstance(product, dict):
            continue
        direct = usable_urls([product.get("url")], "bestbuy")
        if direct:
            urls.extend(direct)
            continue
        # resolves only the documented API product-page redirect, without forwarding a key
        value = product.get("url")
        if not isinstance(value, str):
            continue
        parts = urlsplit(value)
        if (parts.scheme != "https" or parts.netloc != "api.bestbuy.com" or parts.query or parts.fragment
                or not re.fullmatch(r"/click/[A-Za-z0-9_-]+/\d+/pdp", parts.path)):
            continue
        try:
            with requests.get(value, timeout=15, allow_redirects=False, stream=True) as link:
                if link.status_code not in {301, 302, 303, 307, 308}:
                    raise ValueError("Best Buy product-link resolution was blocked or unsupported")
                destination = urljoin(value, link.headers.get("Location", ""))
                urls.extend(usable_urls([destination], "bestbuy"))
        except requests.RequestException:
            raise ValueError("Best Buy product-link resolution failed; no retry was made") from None
    urls = unique_urls(urls)
    if products and not urls:
        raise ValueError("Best Buy returned tracking/unsupported links rather than supported product URLs; no URLs were constructed.")
    return urls[:limit]


def discover_report(query, limit=8, provider=None):
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        raise ValueError("Use a nonempty discovery query of at most 500 characters")
    provider = provider or os.environ.get("SHOPPIE_DISCOVERY_PROVIDER", "brave")
    limit = min(max(int(limit), 1), 8)
    if provider == "bestbuy_sitemap":
        report = bestbuy_sitemap(query, limit)
    elif provider == "bestbuy_api":
        report = {"urls": bestbuy_api_urls(query, limit)}
    elif provider == "brave":
        report = {"urls": brave_urls(query, limit)}
    else:
        raise ValueError("Choose bestbuy_sitemap, bestbuy_api, or brave")
    return {"provider": provider, "limit": limit, **report}


def discover(query, limit=8, provider=None):
    return discover_report(query, limit, provider)["urls"]
