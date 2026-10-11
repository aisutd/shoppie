"""Step 5: coordinate file reading, normalization, and database writes.

Intended command once implemented:
python -m db.ingest --input db/example_product.json
Use mysql-connector placeholders (%s), never scraped text inside SQL strings.
"""

from pathlib import Path


def load_batch(path: Path) -> list[dict]:
    """Read the agreed JSON envelope before touching the database."""
    # TODO: Read UTF-8 JSON; require schema_version == 1 and listings array.
    # A malformed envelope stops the batch; malformed rows are reported later.
    raise NotImplementedError("Mentee TODO: load batch")


def get_retailer_id(connection, retailer_key: str) -> int:
    """Find a configured retailer; a typo must not create another retailer."""
    # TODO: SELECT id FROM retailers WHERE retailer_key = %s.
    # Raise ValueError for unknown retailer; schema.sql seeds known retailers.
    raise NotImplementedError("Mentee TODO: look up retailer")


def find_or_create_listing(connection, retailer_id: int, record: dict) -> int:
    """Keep a stable listing ID while refreshing newer descriptive details."""
    # TODO: Look up retailer_id + source_url_hash; compare full URL as well.
    # TODO: Insert if absent; otherwise update only when scraped_at is newer
    # than details_observed_at. Store attributes as JSON via json.dumps().
    # Preserve unknown fields as NULL; do not borrow specs from another store.
    # A newer missing field remains missing; originals remain in observations.
    # TODO: Lock an existing row for update inside the caller's transaction.
    # Leave commit/rollback to import_file(); always close cursors.
    raise NotImplementedError("Mentee TODO: save listing details")


def add_observation(connection, listing_id: int, record: dict) -> str:
    """Save price history without duplicating an already imported observation."""
    # TODO: Look up listing_id + scraped_at before insertion.
    # Same normalized observation AND original payload -> return 'skipped'.
    # Same identity/time but different data -> raise ValueError (conflict).
    # Otherwise insert price/currency/shipping/condition/seller/availability
    # and original raw_payload; return 'imported'. Never overwrite history.
    # SQL UTC DATETIME: convert aware UTC datetime to naive UTC at SQL boundary.
    # Store JSON with json.dumps(); compare parsed JSON, not key ordering.
    raise NotImplementedError("Mentee TODO: save observation")


def import_file(path: Path) -> dict:
    """Run the pipeline and return counts and record-specific error messages."""
    # TODO: load_batch(), then connection.connect().
    # For each row: normalize.normalize(), start transaction, look up retailer,
    # find/create listing, add observation, then commit both changes together.
    # ValueError: rollback this row, record its index/URL and reason, continue.
    # Unexpected database/infrastructure error: rollback and stop with summary
    # of rows already committed. Do not mislabel an outage as invalid data.
    # Counts: imported, skipped, rejected; errors: [{index, source_url, reason}].
    # TODO: Close connection in finally. No embeddings run during ingestion.
    raise NotImplementedError("Mentee TODO: import listings")


def main() -> None:
    """Let students import a chosen file without changing source code."""
    # TODO: argparse --input, call import_file(Path(...)), print concise summary.
    # Use package imports (from db.connection import connect, etc.).
    raise NotImplementedError("Mentee TODO: add importer command")


if __name__ == "__main__":
    main()
