"""Collect a human-verified observation; never guess missing source fields."""

from datetime import datetime, timezone

from scraper.scraper import clean_url, identify_product


def collect_product(url):
    url = clean_url(url)
    retailer, product_id = identify_product(url)
    print("MANUAL ENTRY: use the exact selected product page open in your browser.")
    print("Copy source values only. Leave unknown fields blank; validation will reject them.")
    print("Currency must be explicitly established; a bare $ is insufficient.")
    title = input("Laptop title: ").strip()
    price = input("Current full product price (not a monthly payment): ").strip()
    currency = input("Explicit currency code: ").strip()
    confirmed = input("Did you verify the exact URL/variant, title, price and currency? Type yes: ").strip().lower()
    if confirmed != "yes":
        raise ValueError("Manual observation was not confirmed; no record collected.")
    return {
        "retailer": retailer, "product_id": product_id, "product_url": url,
        "title": title, "price": price or None, "currency": currency or None,
        "availability": None, "seller": None, "discount": None,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "extraction_method": "manual",
    }
