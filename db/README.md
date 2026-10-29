# Local listing pipeline (MySQL)

The local flow is `scraper → schema_version 1 JSON → db.normalize → db.ingest → db.queries`.
`db/example_product.json` is synthetic data and validates without a database.
The database tables are **retailers**, **listings**, and **listing_observations**.
A listing belongs to one retailer and one selected URL/variant. Every distinct
observation time adds history. There is no canonical product table yet.

The SQLite exercise in `db/start_here.py` uses `db/shoppie.db` independently.
The Supabase teaching uploader in `scraper/database.py` uses `sql/schema.sql`
(`public.products`, latest row only). `db/legacy_lesson_schema.sql` preserves the
older PostgreSQL lesson. None of those tables is interchangeable with this schema.
The team must choose a shared database architecture before any production ingestion.

## JSON contract

The envelope is `{"schema_version": 1, "listings": [...]}`. Each listing has:

| Field | Meaning |
| --- | --- |
| `retailer_key` | `amazon`, `walmart`, `target`, or `best_buy` |
| `retailer_sku` | Retailer product ID, or `null` |
| `source_url` | Exact selected product URL; its query stays intact |
| `scraped_at` | ISO 8601 observation time with timezone |
| `raw` | Original extracted fields: `title`, `price`, `currency`, `brand`, `model`, `gtin`, `category`, `attributes`, `availability`, and optional `seller` / `shipping_cost` |

`db.normalize.normalize` requires the retailer, URL, timestamp, and raw object.
It validates optional fields when present. Missing facts remain `null`; zero is
allowed only when the source explicitly says zero. Prices and shipping amounts
must be exact, finite, nonnegative USD with at most two decimals. An unknown
price remains `null`. The full input row is copied into observation `raw_payload`.
The example's `.example` hosts are fictional; real supported hosts must agree
with the retailer key.

The scraper's `bestbuy` name maps to `best_buy` in this envelope. Its
`observed_at`, `product_url`, and `product_id` map to `scraped_at`, `source_url`,
and `retailer_sku`. JSON-LD brand, model, category, GTIN and explicitly labeled
variant attributes map into `raw`. The source parser may leave them `null`.
Unknown/ambiguous availability maps to `null`. The scraper currently accepts
only laptop pages with an exact price and explicit USD. Database ingestion also
supports unknown prices from other validated JSON sources.

## Offline rehearsal

From the repository root, with dependencies installed:

```bash
python3 -m pip install -r requirements.txt
python3 -m scraper.main --url 'https://www.bestbuy.com/product/synthetic-test-laptop/TEST123' --html tests/fixtures/synthetic_product.html --output /tmp/shoppie-local-batch.json
python3 -m pytest -q
```

The HTML and price above are synthetic fixtures. The command writes only a local
JSON file and does not contact Best Buy or any database. The tests use an
isolated in-memory SQL stand-in; they do not verify a MySQL server.

## Optional throwaway local MySQL check

Use a **new local MySQL 8.0.16+ database only**, with a local user and no shared
credentials. Inspect `db/schema.sql` before applying it. Set `DB_HOST`, `DB_PORT`
(optional; default 3306), `DB_NAME`, `DB_USER`, and `DB_PASSWORD` in your shell.
The `.env` files are not loaded automatically. `mysql-connector-python` is
required by `db.connection` and listed in root `requirements.txt`.

```bash
mysql -h "$DB_HOST" -P "${DB_PORT:-3306}" -u "$DB_USER" -p "$DB_NAME" < db/schema.sql
python3 -m db.ingest --input db/example_product.json
```

The importer commits each valid row separately. Repeating a row skips an identical
observation. A conflicting row at the same listing/time is rejected. Database
errors stop the batch and report counts already committed. `db.queries` exposes
listing details, latest observation, complete history, and brand/model candidate
retrieval. A real MySQL run has **not** been performed here.

## Matching and team verification

`normalizer/matching.py` keeps model-only matches separate. `db/similarity.py`
reports explicit identifier/variant agreements or contradictions; equal GTIN can
confirm an otherwise consistent identity. Brand/model-only candidates remain
uncertain. `db/embeddings.py` now loads pinned MiniLM, creates normalized 384-dimensional
vectors in batches, and reuses matching hashes/configurations. See SETUP_MACOS.md
for the local dashboard, vector schema, and separate review-only PostgreSQL adapter. No uncertain match is merged and no untested score cutoff is used.

Before anyone populates a shared database:

- [ ] Check fresh pages and selected variants at Amazon, Walmart, Target, and Best Buy; record actual fields and retailer access limits.
- [ ] Agree on `schema_version 1`, field names, nulls, retailer keys, and URL identity.
- [ ] Choose MySQL listings/history or a reviewed PostgreSQL equivalent; do not treat Supabase `public.products` as the same schema.
- [ ] Review table creation, keys, checks, foreign keys, and any migration against existing data.
- [ ] Run local ingestion and retrieval with synthetic data, including duplicate and invalid rows.
- [ ] Confirm newest listing details, latest unknown price, and full price history.
- [ ] Review ambiguous product matches and variant specifications manually.
- [ ] Get team and mentor approval before production migrations or ingestion.

Live retailer access, real MySQL behavior, and production migration compatibility
still need verification by the team. No live database is written by these steps.
