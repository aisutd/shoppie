import os
from datetime import datetime

from supabase import create_client


UPLOAD_FIELDS = (
    "title",
    "price",
    "currency",
    "product_url",
    "source",
    "category",
    "scraped_at",
)


def upload_products(validated_products):
    """Upload products already validated against public.products."""
    rows_by_url = {}

    for product in validated_products:
        # Explicitly omit id so existing generated IDs survive upserts.
        row = {field: product[field] for field in UPLOAD_FIELDS}

        timestamp = row["scraped_at"]

        if isinstance(timestamp, datetime):
            observed_at = timestamp
        elif isinstance(timestamp, str):
            observed_at = datetime.fromisoformat(
                timestamp.replace("Z", "+00:00")
            )
        else:
            raise ValueError("scraped_at must be a datetime or ISO timestamp")

        if observed_at.utcoffset() is None:
            raise ValueError("scraped_at must include a UTC offset")

        row["scraped_at"] = observed_at.isoformat()

        # Retain the newest observation if this batch repeats a URL.
        url = row["product_url"]
        previous = rows_by_url.get(url)

        if previous is None or observed_at >= previous[0]:
            rows_by_url[url] = (observed_at, row)

    rows = [entry[1] for entry in rows_by_url.values()]

    if not rows:
        return 0

    client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SECRET_KEY"],
    )

    for start in range(0, len(rows), 100):
        client.table("products").upsert(
            rows[start:start + 100],
            on_conflict="product_url",
        ).execute()

    return len(rows)