"""Map validated scraper records to the database's version 1 JSON envelope."""

from scraper.validator import Laptop

RETAILER_KEYS = {"amazon": "amazon", "walmart": "walmart",
                 "target": "target", "bestbuy": "best_buy"}
AVAILABILITY = {"InStock": "in_stock", "OutOfStock": "out_of_stock",
                "SoldOut": "out_of_stock", "Discontinued": "out_of_stock"}


def listing_from_product(product):
    if not isinstance(product, Laptop):
        raise TypeError("A validated Laptop is required")
    return {
        "retailer_key": RETAILER_KEYS[product.retailer],
        "retailer_sku": product.product_id,
        "source_url": product.product_url,
        "scraped_at": product.observed_at.isoformat(),
        "raw": {
            "title": product.title,
            "description": product.description,
            "shipping_cost": str(product.shipping_cost) if product.shipping_cost is not None else None,
            "price": str(product.price) if product.price is not None else None,
            "currency": product.currency,
            "brand": product.brand,
            "model": product.model,
            "gtin": product.gtin,
            "category": product.category,
            "attributes": dict(product.attributes),
            "availability": AVAILABILITY.get(product.availability),
            "seller": product.seller,
            "extraction_method": product.extraction_method,
        },
    }


def make_envelope(products):
    return {"schema_version": 1,
            "listings": [listing_from_product(product) for product in products]}
