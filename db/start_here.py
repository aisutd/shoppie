
import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).resolve().parent / "shoppie.db"


def main() -> None:
    # Connection creates the database file if it does not already exist
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    # this will show the title of the row rather than show "row[2]" it just makes it a lil easier for us to view

    try:
        with connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS listings (
                    id INTEGER PRIMARY KEY,
                    retailer TEXT NOT NULL,
                    title TEXT NOT NULL,
                    model TEXT,
                    price_cents INTEGER
                )
                """
            )

            example = (
                "Best-Buy",
                "Apple AirPods Pro Max",
                "Airpods Pro Max",
                59999,
            )

            # This is a team convience not our future listing identity rule
            # checks for duplicates or if object already exists
            existing = connection.execute(
                """
                SELECT id FROM listings
                WHERE retailer = ? AND title = ? AND model = ? AND price_cents = ?
                LIMIT 1
                """,
                example,
            ).fetchone()

            # creates now listing to store into the database
            if existing is None:
                # Placeholders keep values seperate from the SQL command, preventing SQL instructions
                connection.execute(
                    """
                    INSERT INTO listings (retailer, title, model, price_cents)
                    VALUES (?, ?, ?, ?)
                    """,
                    example,
                )
                print("Saved the example listing.")
            else:
                print("The example is already saved.")

        # At this point the transaction has saved any changes
        rows = connection.execute(
            """
            SELECT id, retailer, title, model, price_cents
            FROM listings ORDER BY id
            """
        ).fetchall()

        print(f"Database: {DATABASE_PATH}")
        print(f"Stored listings: {len(rows)}")
        for row in rows:
            cents = row["price_cents"]
            # Money is stored as integer cents, formatting is only for display
            price = "Unknown" if cents is None else f"${cents // 100}.{cents % 100:02d}"
            model = row["model"] if row["model"] is not None else "Unknown"
            print(f"  [{row['id']}] {row['retailer']} | {row['title']} | {model} | {price}")
    finally:
        # release the connection to the db even if a statement fails so we're not stuck there
        connection.close()


if __name__ == "__main__":
    main()
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

