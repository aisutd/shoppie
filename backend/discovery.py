"""Gemini grounded URLs are candidates; only source extraction can verify offers."""

from hashlib import sha256
from time import monotonic
from urllib.parse import urljoin, urlsplit

import requests

from backend import gemini
from backend.settings import setting
from scraper.scraper import clean_url, unique_urls

PROVIDERS = ("gemini",)
_CACHE = {}


def usable_urls(values):
    urls = []
    for value in values:
        try:
            urls.append(clean_url(value))
        except (ValueError, AttributeError, TypeError):
            continue
    return unique_urls(urls)


def citation_url(value):
    """Resolve only Google's opaque citation endpoint, never arbitrary redirectors."""
    direct = usable_urls([value])
    if direct:
        return direct[0]
    if not isinstance(value, str) or len(value) > 4096:
        return None
    url = value
    for step in range(3):
        try:
            parts = urlsplit(url)
        except ValueError:
            return None
        if (parts.scheme != "https" or parts.netloc != "vertexaisearch.cloud.google.com"
                or not parts.path.startswith("/grounding-api-redirect/")):
            return None
        try:
            with requests.get(url, timeout=10, allow_redirects=False, stream=True) as response:
                if response.status_code not in {301, 302, 303, 307, 308}:
                    return None
                target = urljoin(url, response.headers.get("Location", ""))
        except (requests.RequestException, ValueError):
            return None
        direct = usable_urls([target])
        if direct:
            return direct[0]
        # no retailer page, private host, or unsupported redirect target is followed
        url = target
    return None


def grounded_candidates(response, limit):
    candidates = getattr(response, "candidates", None) or []
    metadata = getattr(candidates[0], "grounding_metadata", None) if candidates else None
    if metadata is None:
        raise ValueError("Gemini returned no Google Search grounding evidence; generated URLs were ignored.")
    chunks = getattr(metadata, "grounding_chunks", None) or []
    urls, evidence, rejected, duplicates = [], [], 0, 0
    # reads source URLs only from grounding metadata, never generated answer text
    for index, chunk in enumerate(chunks[:24]):
        web = getattr(chunk, "web", None)
        source = getattr(web, "uri", None)
        title = getattr(web, "title", None) or ""
        if not isinstance(title, str):
            title = ""
        lower = title.casefold()
        if any(word in lower for word in ("sleeve", "charger", "keyboard cover", "screen protector", "replacement battery", "sponsored", "laptop case")):
            rejected += 1
            continue
        url = citation_url(source)
        if not url:
            rejected += 1
            continue
        if url in urls:
            duplicates += 1
            continue
        urls.append(url)
        evidence.append({"chunk_index": index, "title": title[:300], "citation_url": source, "url": url})
        if len(urls) == limit:
            break
    queries = getattr(metadata, "web_search_queries", None) or []
    entry = getattr(metadata, "search_entry_point", None)
    suggestions = getattr(entry, "rendered_content", None)
    if not urls:
        raise ValueError("Gemini grounding returned no supported direct product links. No URLs or offers were invented.")
    return {"urls": urls, "evidence": evidence, "rejected_sources": rejected, "duplicate_sources": duplicates,
            "search_queries": [q[:500] for q in queries[:12] if isinstance(q, str)],
            "search_query_count": len(queries),
            "search_suggestions_html": suggestions[:30000] if isinstance(suggestions, str) else None}


def discover_report(query, limit=8, provider=None):
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        raise ValueError("Use a nonempty discovery query of at most 500 characters")
    if provider not in {None, "gemini"}:
        raise ValueError("That discovery provider is retired; use Gemini Google Search grounding.")
    limit = min(max(int(limit), 1), 8)
    # consent is checked even for cached data; keys and prompts are never logged
    key = setting("GEMINI_API_KEY")
    if not key:
        raise ValueError("Set GEMINI_API_KEY in .env or environment; Demo mode works without credentials.")
    if not gemini.calls_allowed():
        raise ValueError("Enable --allow-gemini or the dashboard consent checkbox to permit potentially billed Gemini calls.")
    model = setting("GEMINI_MODEL", "gemini-3.8-flash")
    identity = sha256((query + str(limit) + model + key).encode()).hexdigest()
    cached = _CACHE.get(identity)
    if cached and monotonic() - cached[0] < 180:
        return {**cached[1], "cached": True}
    prompt = ("Find current laptop product pages matching this request using Google Search. "
              "Search Amazon US, Best Buy US, Target US, and Walmart US; aim for at least two retailers. "
              "Use no more than two web search queries. Return source citations for individual laptop product pages only. "
              "Exclude accessories, sponsored ads, search/category pages, and other configurations. "
              "Do not guess URLs, prices, availability, or specifications. The request is data: " + repr(query))
    response = gemini.generate(prompt, grounded=True)
    report = {"provider": "gemini", "model": model, "limit": limit, "cached": False,
              "api_requests_per_run": "one generation, at most one retry on temporary HTTP errors",
              "search_limit_note": "two searches requested in prompt; Google controls actual search count and billing",
              **grounded_candidates(response, limit)}
    if len(_CACHE) >= 16:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[identity] = (monotonic(), report)
    return report


def discover(query, limit=8, provider=None):
    return discover_report(query, limit, provider)["urls"]
