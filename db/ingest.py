"""Import a schema_version 1 JSON batch into local MySQL listings and history."""

import argparse
import json
from pathlib import Path

from db.connection import connect
from db.normalize import normalize


class ImportFailure(RuntimeError):
    """A database failure with counts for rows already committed."""

    def __init__(self, message, summary):
        super().__init__(message)
        self.summary = summary


class RecordError(ValueError):
    """A valid JSON row that conflicts with configured database identity."""


def load_batch(path):
    try:
        batch = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read JSON batch: {error}") from None
    if not isinstance(batch, dict) or type(batch.get("schema_version")) is not int or batch["schema_version"] != 1:
        raise ValueError("Batch needs schema_version: 1")
    if not isinstance(batch.get("listings"), list):
        raise ValueError("Batch needs a listings array")
    return batch["listings"]


def utc_sql(value):
    return value.replace(tzinfo=None)


def get_retailer_id(connection, retailer_key):
    cursor = connection.cursor(buffered=True)
    try:
        cursor.execute("SELECT id FROM retailers WHERE retailer_key = %s", (retailer_key,))
        row = cursor.fetchone()
        if row is None:
            raise RecordError(f"retailer_key {retailer_key!r} is not configured")
        return row[0]
    finally:
        cursor.close()


def find_or_create_listing(connection, retailer_id, record):
    cursor = connection.cursor(dictionary=True, buffered=True)
    try:
        cursor.execute("""SELECT id, source_url, details_observed_at FROM listings
                          WHERE retailer_id = %s AND source_url_hash = %s FOR UPDATE""",
                       (retailer_id, record["source_url_hash"]))
        existing = cursor.fetchone()
        details = (record["retailer_sku"], record["source_url"], record["source_url_hash"],
                   record["title"], record["brand"], record["model_number"], record["gtin"],
                   record["category"], json.dumps(record["attributes"]), utc_sql(record["scraped_at"]))
        if existing:
            if existing["source_url"] != record["source_url"]:
                raise RecordError("source_url hash collision or inconsistent listing identity")
            if utc_sql(record["scraped_at"]) > existing["details_observed_at"]:
                cursor.execute("""UPDATE listings SET retailer_sku = %s, source_url = %s,
                    source_url_hash = %s, title = %s, brand = %s, model_number = %s,
                    gtin = %s, category = %s, attributes = %s, details_observed_at = %s
                    WHERE id = %s""", details + (existing["id"],))
            return existing["id"]
        cursor.execute("""INSERT INTO listings
            (retailer_id, retailer_sku, source_url, source_url_hash, title, brand,
             model_number, gtin, category, attributes, details_observed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (retailer_id,) + details)
        return cursor.lastrowid
    finally:
        cursor.close()


def decoded_json(value):
    return json.loads(value) if isinstance(value, (str, bytes)) else value


def add_observation(connection, listing_id, record):
    cursor = connection.cursor(dictionary=True, buffered=True)
    fields = ("price", "shipping_cost", "currency", "condition", "seller", "availability")
    try:
        cursor.execute("""SELECT price, shipping_cost, currency, `condition`, seller,
            availability, raw_payload FROM listing_observations
            WHERE listing_id = %s AND scraped_at = %s FOR UPDATE""",
            (listing_id, utc_sql(record["scraped_at"])))
        existing = cursor.fetchone()
        if existing:
            same_values = all(existing[field] == record[field] for field in fields)
            if same_values and decoded_json(existing["raw_payload"]) == record["raw_payload"]:
                return "skipped"
            raise RecordError("observation conflicts with existing listing and scraped_at")
        cursor.execute("""INSERT INTO listing_observations
            (listing_id, scraped_at, price, shipping_cost, currency, `condition`,
             seller, availability, raw_payload)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (listing_id, utc_sql(record["scraped_at"]))
            + tuple(record[field] for field in fields)
            + (json.dumps(record["raw_payload"]),))
        return "imported"
    finally:
        cursor.close()


def import_file(path, connection=None):
    rows = load_batch(path)
    summary = {"imported": 0, "skipped": 0, "rejected": 0, "errors": []}
    owns_connection = connection is None
    database = connection
    try:
        for index, row in enumerate(rows, start=1):
            try:
                record = normalize(row)
            except ValueError as error:
                summary["rejected"] += 1
                summary["errors"].append({"index": index,
                    "source_url": row.get("source_url") if isinstance(row, dict) else None,
                    "reason": str(error)})
                continue
            try:
                if database is None:
                    database = connect()
                database.start_transaction()
                retailer_id = get_retailer_id(database, record["retailer_key"])
                listing_id = find_or_create_listing(database, retailer_id, record)
                result = add_observation(database, listing_id, record)
                database.commit()
                summary[result] += 1
            except RecordError as error:
                if database is not None:
                    try:
                        database.rollback()
                    except Exception as rollback_error:
                        raise ImportFailure(f"Rollback failed at row {index}", summary) from rollback_error
                summary["rejected"] += 1
                summary["errors"].append({"index": index, "source_url": record["source_url"],
                                          "reason": str(error)})
            except Exception as error:
                if database is not None:
                    try:
                        database.rollback()
                    except Exception:
                        pass
                raise ImportFailure(f"Database failed at row {index}: {type(error).__name__}", summary) from error
        return summary
    finally:
        if owns_connection and database is not None:
            database.close()


def main():
    parser = argparse.ArgumentParser(description="Import a local JSON batch into local MySQL")
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = import_file(args.input)
    except (ValueError, ImportFailure) as error:
        print(f"IMPORT FAILED: {error}")
        if isinstance(error, ImportFailure):
            print("Rows committed before failure:", error.summary)
        return 1
    print(json.dumps(summary, indent=2))
    return 1 if summary["rejected"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
