"""Read local MySQL listings and observations without changing the database."""

import json
from datetime import timezone


def row_dict(cursor):
    row = cursor.fetchone()
    return prepare(row) if row else None


def prepare(row):
    result = dict(row)
    for name in ("attributes", "raw_payload"):
        if name in result and isinstance(result[name], (str, bytes)):
            result[name] = json.loads(result[name])
    for name in ("scraped_at", "details_observed_at"):
        if result.get(name) is not None and result[name].tzinfo is None:
            result[name] = result[name].replace(tzinfo=timezone.utc)
    return result


def get_listing(connection, listing_id):
    cursor = connection.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute("""SELECT l.*, r.retailer_key, r.name AS retailer_name
            FROM listings l JOIN retailers r ON r.id = l.retailer_id
            WHERE l.id = %s""", (listing_id,))
        return row_dict(cursor)
    finally:
        cursor.close()


def get_latest_observation(connection, listing_id):
    cursor = connection.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute("""SELECT * FROM listing_observations
            WHERE listing_id = %s ORDER BY scraped_at DESC LIMIT 1""", (listing_id,))
        return row_dict(cursor)
    finally:
        cursor.close()


def get_price_history(connection, listing_id):
    cursor = connection.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute("""SELECT * FROM listing_observations
            WHERE listing_id = %s ORDER BY scraped_at ASC""", (listing_id,))
        return [prepare(row) for row in cursor.fetchall()]
    finally:
        cursor.close()


def find_listings(connection, brand, model_number):
    cursor = connection.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute("""SELECT l.*, r.retailer_key, r.name AS retailer_name,
            o.price, o.shipping_cost, o.currency, o.`condition`, o.seller,
            o.availability, o.scraped_at
            FROM listings l JOIN retailers r ON r.id = l.retailer_id
            LEFT JOIN listing_observations o ON o.listing_id = l.id AND o.scraped_at =
                (SELECT MAX(newest.scraped_at) FROM listing_observations newest
                 WHERE newest.listing_id = l.id)
            WHERE l.brand = %s AND l.model_number = %s ORDER BY r.retailer_key, l.id""",
            (brand, model_number))
        return [prepare(row) for row in cursor.fetchall()]
    finally:
        cursor.close()


def get_current_offers(connection):
    """Read latest MySQL offers, including optional descriptions preserved in raw JSON."""
    cursor = connection.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute("""SELECT l.*, r.retailer_key, o.scraped_at, o.price, o.shipping_cost,
            o.currency, o.`condition`, o.seller, o.availability, o.raw_payload
            FROM listings l JOIN retailers r ON r.id=l.retailer_id
            JOIN listing_observations o ON o.listing_id=l.id AND o.scraped_at=
                (SELECT MAX(newest.scraped_at) FROM listing_observations newest WHERE newest.listing_id=l.id)
            ORDER BY l.id""")
        rows = [prepare(row) for row in cursor.fetchall()]
        for row in rows:
            row["description"] = row.get("raw_payload", {}).get("raw", {}).get("description")
        return rows
    finally:
        cursor.close()
