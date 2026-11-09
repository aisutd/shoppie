"""Read the local catalog of product identities and retailer links."""

import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from scraper.scraper import clean_url, identify_product


REFERENCE_FILE = Path(__file__).with_suffix(".json")
CATEGORIES = {"laptops", "monitors", "tablets", "headphones", "storage"}
FIELDS = {"product_id", "title", "category", "product_url", "manufacturer_url"}
IMAGE_FIELDS = {"file", "author", "license", "source_url", "license_url", "note"}
IMAGE_DIR = REFERENCE_FILE.parent / "public" / "reference-images"


def reference_image(image):
    # only serve bundled photos with their source and license attached
    if not isinstance(image, dict) or image.keys() != IMAGE_FIELDS:
        return {}
    if not all(isinstance(value, str) and value.strip() for value in image.values()):
        return {}
    filename = image["file"]
    if not re.fullmatch(r"[a-z0-9-]+\.jpg", filename) or not (IMAGE_DIR / filename).is_file():
        return {}
    try:
        urls = [urlsplit(image[key]) for key in ("source_url", "license_url")]
        if not all(url.scheme == "https" and url.hostname for url in urls):
            return {}
    except ValueError:
        return {}
    return {
        "image_url": f"/reference-images/{filename}",
        "image_credit": {key: value for key, value in image.items() if key != "file"},
    }


@lru_cache(maxsize=1)
def load_reference_catalog(path=REFERENCE_FILE):
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(rows, list):
        return []

    # accept identity facts and licensed artwork only; never accept offer fields
    products = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or row.keys() - {"image"} != FIELDS:
            continue
        if not all(isinstance(row[field], str) and row[field].strip() for field in FIELDS):
            continue
        try:
            url = clean_url(row["product_url"])
            retailer, product_id = identify_product(url)
            manufacturer = urlsplit(row["manufacturer_url"])
        except ValueError:
            continue
        identity = (retailer, product_id)
        if (retailer not in {"target", "amazon"} or product_id != row["product_id"]
                or row["category"] not in CATEGORIES or identity in seen
                or manufacturer.scheme != "https" or not manufacturer.hostname):
            continue
        seen.add(identity)
        products.append({
            "id": f"reference-{retailer}-{product_id}",
            "title": row["title"].strip(),
            "category": row["category"],
            "product_url": url,
            "source": f"{retailer}.com",
            "price": None,
            "is_reference": True,
            **reference_image(row.get("image")),
        })
    return products
