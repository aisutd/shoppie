"""Verify the direct-URL collectors and stored catalog with synthetic services."""

import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import local_search_api as api
from scraper import config, main, product_access, scraper, tech_scraper
from scraper.database import Database, upsert_product
from scraper.validator import validate_record

FIXTURES = Path(__file__).parent / "fixtures"
TARGET = "https://www.target.com/p/synthetic-laptop/-/A-90000001?preselect=90000002"
AMAZON = "https://www.amazon.com/dp/B0TEST0001"


@pytest.fixture(params=[
    (TARGET, "target_selected_offer.html", "1049.00"),
    (AMAZON, "amazon_primary_offer.html", "999.00"),
])
def offer(request):
    url, fixture, price = request.param
    return url, (FIXTURES / fixture).read_text(), price


def test_same_direct_url_fetch_and_catalog_payload(offer, monkeypatch):
    url, html, price = offer
    get = Mock(return_value=SimpleNamespace(status_code=200, headers={"Content-Type": "text/html"}, text=html))
    monkeypatch.setattr(product_access, "fetch_robots", lambda origin: "User-agent: *\nAllow: /")
    monkeypatch.setattr(scraper.requests, "get", get)
    monkeypatch.setattr(tech_scraper, "load_dotenv", Mock())
    monkeypatch.setenv("SUPABASE_URL", "https://synthetic.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_SYNTHETIC")
    post = Mock(return_value=SimpleNamespace(status_code=201))
    monkeypatch.setattr(tech_scraper.requests, "post", post)

    record = tech_scraper.extract_product(*tech_scraper.fetch_page(url), category="Laptops")
    tech_scraper.upload_to_supabase(record)
    tech_row = post.call_args.kwargs["json"]
    upsert_product(Database("https://synthetic.supabase.co", "sb_secret_SYNTHETIC"),
                   validate_record(scraper.extract_product(html, url)))
    staged_row = post.call_args.kwargs["json"]
    assert set(tech_row) == {"title", "description", "image_url", "price", "currency", "product_url", "source", "category", "scraped_at"}
    assert {k: v for k, v in tech_row.items() if k != "scraped_at"} == {k: v for k, v in staged_row.items() if k != "scraped_at"}
    assert tech_row["price"] == price and tech_row["currency"] == "USD"
    assert tech_row["product_url"] == url and tech_row["category"] == "laptops"
    assert tech_row["source"] == scraper.identify_product(url)[0] + ".com"
    assert tech_row["image_url"].startswith("https://") and "512GB" in tech_row["description"]
    get.assert_called_once()
    assert get.call_args.args[0] == url and get.call_args.kwargs["allow_redirects"] is False
    assert "impersonate" not in get.call_args.kwargs
    assert all(call.kwargs["params"] == {"on_conflict": "product_url"} for call in post.call_args_list)


def test_wrong_selected_variant_and_missing_currency_reject(offer):
    url, html, _ = offer
    wrong = html.replace('value="B0TEST0001"', 'value="B0TEST0002"') if url == AMAZON else html.replace('/A-90000002"', '/A-90000003"', 1)
    with pytest.raises(ValueError, match="different"):
        tech_scraper.extract_product(wrong, url)
    with pytest.raises(ValueError, match="currency"):
        tech_scraper.extract_product(html.replace('"USD"', '""'), url)


def test_conflicting_prices_reject(offer):
    url, html, _ = offer
    if url == TARGET:
        html = html.replace("$1,049.00", "$899.00")
    else:
        html = html.replace('<span class="a-price a-text-price">', '<span class="a-price">')
    with pytest.raises(ValueError, match="Conflicting price"):
        tech_scraper.extract_product(html, url)


@pytest.mark.parametrize("url", [TARGET, AMAZON])
def test_robots_and_http_denials_stop_without_retry(url, monkeypatch):
    get = Mock()
    monkeypatch.setattr(scraper.requests, "get", get)
    monkeypatch.setattr(product_access, "fetch_robots", lambda origin: "User-agent: *\nDisallow: /*")
    with pytest.raises(ValueError, match="robots"):
        tech_scraper.fetch_page(url)
    get.assert_not_called()
    monkeypatch.setattr(product_access, "fetch_robots", lambda origin: "User-agent: *\nAllow: /")
    get.return_value = SimpleNamespace(status_code=403)
    with pytest.raises(ValueError, match="HTTP 403"):
        tech_scraper.fetch_page(url)
    get.assert_called_once()


def test_amazon_unavailable_does_not_reach_staged_upload(monkeypatch):
    html = (FIXTURES / "amazon_primary_offer.html").read_text().replace("InStock", "OutOfStock")
    monkeypatch.setattr(scraper, "fetch_page", lambda url: html)
    settings = Mock(side_effect=AssertionError("Rejected product cannot reach database settings"))
    monkeypatch.setattr(config, "load_database_config", settings)
    assert main.main(["--url", AMAZON, "--save"]) == 1
    settings.assert_not_called()


@pytest.mark.parametrize("url", [TARGET, AMAZON])
def test_captcha_rejects_before_product_fields(url):
    html = (FIXTURES / "bot_check.html").read_text()
    with pytest.raises(ValueError, match="bot check"):
        tech_scraper.extract_product(html, url)


def test_tech_category_keeps_non_laptop_products_supported():
    html = (FIXTURES / "amazon_primary_offer.html").read_text().replace("MacBook Air laptop", "Tablet")
    assert tech_scraper.extract_product(html, AMAZON, category="Tablets")["category"] == "tablets"


def test_existing_search_route_reads_and_returns_all_four_sources(monkeypatch):
    products = [tech_scraper.extract_product((FIXTURES / filename).read_text(), url)
                for url, filename in [(TARGET, "target_selected_offer.html"), (AMAZON, "amazon_primary_offer.html")]]
    for retailer, url in [("bestbuy", "https://www.bestbuy.com/product/synthetic-laptop/TEST123"),
                          ("walmart", "https://www.walmart.com/ip/synthetic-laptop/12345678")]:
        products.append({**products[0], "id": retailer, "source": retailer + ".com", "product_url": url})
    database = config.DatabaseConfig("https://synthetic.supabase.co", "sb_secret_SYNTHETIC")
    monkeypatch.setattr(api, "load_database_config", lambda: database)
    monkeypatch.setattr(api, "_catalog_cache", {"expires_at": 0, "products": []})
    get = Mock(return_value=Mock(json=lambda: products))
    monkeypatch.setattr(api.requests, "get", get)
    post = Mock(side_effect=AssertionError("Stored search should only read matching rows"))
    monkeypatch.setattr(api.requests, "post", post)
    handler = api.SearchHandler.__new__(api.SearchHandler)
    query = json.dumps({"query": "MacBook under $1200"}).encode()
    handler.path = "/api/search"
    handler.headers = {"Content-Length": str(len(query))}
    handler.rfile = BytesIO(query)
    handler.send_json = Mock()
    handler.do_POST()
    status, payload = handler.send_json.call_args.args
    assert status == 200
    assert {p["source"] for p in payload["products"]} == {"target.com", "amazon.com", "bestbuy.com", "walmart.com"}
    assert all(p["image_url"] and p["product_url"] for p in payload["products"])
    assert get.call_args.args[0].endswith("/rest/v1/products")
    post.assert_not_called()


def test_target_family_canonical_uses_only_child_bound_offer():
    html = (FIXTURES / "target_selected_offer.html").read_text()
    html = html.replace('/A-90000002"', '/A-90000001"', 1).replace('$1,049.00', '$1.99')
    result = tech_scraper.extract_product(html, TARGET)
    assert result["price"] == "1049.00"
    assert result["product_url"] == TARGET
    assert result["image_url"] is None


def test_target_structured_current_price_can_be_nested_in_offer():
    product = {"@type": "Product", "url": TARGET, "name": "Synthetic laptop",
               "offers": {"@type": "Offer", "priceSpecification": {"@type": "UnitPriceSpecification", "price": "1049.00", "priceCurrency": "USD"}}}
    html = '<script type="application/ld+json">' + json.dumps(product) + '</script>'
    assert tech_scraper.extract_product(html, TARGET)["price"] == "1049.00"
    product["offers"]["priceSpecification"]["billingDuration"] = 12
    html = '<script type="application/ld+json">' + json.dumps(product) + '</script>'
    with pytest.raises(ValueError, match="pricing schedule"):
        tech_scraper.extract_product(html, TARGET)


def test_structured_offer_cannot_override_conflicting_visible_price(offer):
    url, html, _ = offer
    product = {"@type": "Product", "url": url,
               "name": "Synthetic MacBook Air laptop 16GB RAM 512GB SSD",
               "offers": {"@type": "Offer", "price": "499.00", "priceCurrency": "USD"}}
    html += '<script type="application/ld+json">' + json.dumps(product) + '</script>'
    with pytest.raises(ValueError, match="Conflicting price"):
        tech_scraper.extract_product(html, url)
