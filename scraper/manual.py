"""Collect a human-verified observation; never guess missing source fields."""

from datetime import datetime, timezone

from scraper.scraper import clean_url, identify_product


def collect_product(url):
    url = clean_url(url)
    retailer, product_id = identify_product(url)
    print("MANUAL ENTRY: use the exact selected product page open in your browser.")
    print("Copy source values only. Leave unknown optional fields blank.")
    print("Currency must be explicitly established; a bare $ is insufficient.")
    title = input("Laptop title: ").strip()
    price = input("Current full product price (not a monthly payment): ").strip()
    currency = input("Explicit currency code: ").strip()
    image_url = input("Verified HTTPS product image URL (optional): ").strip()
    description = input("Verified product description (optional): ").strip()
    availability = input("Explicit availability, such as InStock or OutOfStock (optional): ").strip()
    confirmed = input("Did you verify the selected variant and every value entered? Type yes: ").strip().lower()
    if confirmed != "yes":
        raise ValueError("Manual observation was not confirmed; no record collected.")
    return {
        "retailer": retailer, "product_id": product_id, "product_url": url,
        "title": title, "price": price or None, "currency": currency or None,
        "image_url": image_url or None, "description": description or None,
        "availability": availability or None, "seller": None, "discount": None,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "extraction_method": "manual",
    }
