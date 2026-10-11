# Shoppie database build scaffold

This folder contains intentionally unfinished function skeletons. Each TODO
is student work; calling an unfinished function raises NotImplementedError.
schema.sql contains table instructions, not executable SQL. Follow MENTOR_GUIDE.md.

## Responsibility and flow

Scraper JSON -> ingest.load_batch -> normalize.normalize -> MySQL listings
and observations -> queries. Embeddings and similarity run separately later.

| File | Purpose |
| --- | --- |
| example_product.json | Existing synthetic input fixture; preserve originals |
| schema.sql | Tables, types, keys and relationships students implement |
| connection.py | Read settings and open a shared MySQL connection |
| normalize.py | Basic cleaning/validation; no SQL or product merging |
| ingest.py | Coordinate import, transactions, duplicates and error reporting |
| queries.py | Retrieve descriptions, latest offers and history |
| embeddings.py | Later: generate vectors from product descriptions |
| similarity.py | Later: retrieve candidates and explain identity evidence |

## Input contract (schema_version 1)

Use the exact envelope and field names in example_product.json:
`{"schema_version": 1, "listings": [...]}`. Each row has retailer_key,
retailer_sku, source_url, scraped_at, and raw. raw contains title, price,
currency, brand, model, gtin, category, attributes and availability.
Optional additions raw.shipping_cost and raw.seller default to null.
Condition is read from raw.attributes.condition.

Known retailer keys: amazon, walmart, target, best_buy. The fixture's 40 tech
listings are fictional observations: URLs, prices and identifiers are demo data.
One row represents ONE selected retailer offer/variant at ONE observation time.

## Exact normalize(record) output contract

Return a Python dictionary with these keys (not JSON yet):

| Key | Python type / rule |
| --- | --- |
| retailer_key | str, one of the four configured keys |
| retailer_sku | str or None |
| source_url | str, stable absolute HTTP(S) URL |
| source_url_hash | str, SHA-256 hex of that URL |
| title, brand, model_number, gtin, category | str or None; raw.model maps to model_number |
| attributes | dict, normalized tech specs; condition removed into its own field |
| scraped_at | timezone-aware UTC datetime |
| price, shipping_cost | Decimal or None; nonnegative finite amount, at most 2 decimal places |
| currency | USD or None; required when either amount is known |
| condition | new, used, refurbished, open_box or None |
| seller | str or None |
| availability | in_stock, out_of_stock, unknown or None |
| raw_payload | dict, deep copy of the original full input row |

Missing data stays None. Incorrect types/formats raise ValueError naming the
field. Do not mutate the raw input. Do not guess product specifications.
Normalize category labels consistently (e.g. laptops -> laptop) and document
the small alias map in normalize.py. Preserve unknown categories/attributes.

## Storage decisions

- MySQL 8.0.16+; decimal money, JSON specs, DATETIME(6) timestamps in UTC.
- Connection session uses UTC. Convert aware UTC timestamps to naive UTC
  only at the connector boundary, and label returned timestamps as UTC.
- Latest descriptive information lives in listings; observation values/history
  live in listing_observations. Newer missing details are still missing.
- Identity: retailer + stable URL hash, with full URL checked for consistency.
  URL must distinguish variant/selected offer; URL cleanup is a scraper contract.
- Same observation twice: skip. Same listing/time with different data: reject
  as conflict. New time: append an observation. Older data cannot replace newer
  listing details. Keep original input in raw_payload.
- Per-record transaction covers listing updates and observation insertion.
  Invalid rows are reported; infrastructure failures stop the import.
- An unknown latest price stays unknown; display older prices as history only.
- Condition and seller belong to the observed offer. Matching a model is only
  candidate retrieval; capacity/color/condition still matter for comparison.

## Setup to implement

Mentor provisions database/user. Students implement the first three schema
tables and retailer seeds. Add mysql-connector-python when implementing the
connection. Set DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD through the shell
or explicitly load an ignored .env file. A .env file alone is not loaded.
Commit an .env.example with placeholders, not credentials.

From repository root, intended command after implementation:
`python -m db.ingest --input db/example_product.json`.

First finish storage and retrieval. Formal tests and live scraping follow later;
manual demonstrations in the guide establish whether each build step works.
