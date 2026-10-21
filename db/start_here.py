"""Create and connect to Shoppie's local SQLite database.

Money is stored as integer minor units (for example, 34999 cents for USD
349.99). The importer is responsible for converting a decimal price using
the exponent for its currency. Timestamps are ISO 8601 strings in UTC.
JSON values are stored as text so this schema works across SQLite builds.
"""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
from pathlib import Path


DEFAULT_DATABASE_PATH = Path(__file__).resolve().with_name("shoppie.sqlite3")

SCHEMA = """
CREATE TABLE IF NOT EXISTS retailers (
    id           INTEGER PRIMARY KEY,
    retailer_key TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS listings (
    id              INTEGER PRIMARY KEY,
    retailer_id     INTEGER NOT NULL,
    retailer_sku    TEXT,
    source_url      TEXT NOT NULL,
    source_url_hash TEXT NOT NULL CHECK (length(source_url_hash) = 64),
    title           TEXT,
    brand           TEXT,
    model_number    TEXT,
    gtin            TEXT,
    category        TEXT,
    attributes_json TEXT,

    UNIQUE (retailer_id, source_url_hash),
    FOREIGN KEY (retailer_id) REFERENCES retailers (id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS ix_listings_gtin ON listings (gtin);
CREATE INDEX IF NOT EXISTS ix_listings_brand_model
    ON listings (brand, model_number);

CREATE TABLE IF NOT EXISTS listing_observations (
    id                 INTEGER PRIMARY KEY,
    listing_id         INTEGER NOT NULL,
    scraped_at         TEXT NOT NULL,
    price_minor_units  INTEGER CHECK (
        price_minor_units IS NULL OR price_minor_units >= 0
    ),
    currency           TEXT CHECK (currency IS NULL OR length(currency) = 3),
    availability       TEXT,
    raw_payload_json   TEXT NOT NULL,

    UNIQUE (listing_id, scraped_at),
    FOREIGN KEY (listing_id) REFERENCES listings (id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS listing_embeddings (
    listing_id       INTEGER NOT NULL,
    model_name       TEXT NOT NULL,
    model_revision   TEXT NOT NULL,
    template_version TEXT NOT NULL,
    input_text       TEXT NOT NULL,
    input_hash       TEXT NOT NULL CHECK (length(input_hash) = 64),
    dimensions       INTEGER NOT NULL CHECK (dimensions > 0),
    vector_json      TEXT NOT NULL,
    created_at       TEXT NOT NULL,

    PRIMARY KEY (
        listing_id,
        model_name,
        model_revision,
        template_version
    ),
    FOREIGN KEY (listing_id) REFERENCES listings (id)
        ON DELETE CASCADE
);
"""


def connect(database_path: str | Path = DEFAULT_DATABASE_PATH) -> sqlite3.Connection:
    """Open the database and enable foreign-key enforcement for this connection."""
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
    """Create the schema if it does not already exist."""
    connection = connect(database_path)
    try:
        with connection:
            connection.executescript(SCHEMA)
    finally:
        connection.close()


def hash_source_url(source_url: str) -> str:
    """Return the SHA-256 hex digest used by the listing identity constraint.

    Callers should pass the same stable, variant-specific URL representation
    on every import. URL normalization, if needed, should happen before this.
    """
    if not source_url:
        raise ValueError("source_url must not be empty")
    return hashlib.sha256(source_url.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize Shoppie's SQLite database.")
    parser.add_argument(
        "database",
        nargs="?",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help=f"database file (default: {DEFAULT_DATABASE_PATH})",
    )
    args = parser.parse_args()

    initialize_database(args.database)
    print(f"SQLite database is ready: {args.database}")


if __name__ == "__main__":
    main()
