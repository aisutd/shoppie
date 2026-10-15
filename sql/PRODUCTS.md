# public.products: latest laptop observations

Run `inspect_products.sql` in the **existing shared Supabase project** first.
If `existing_products_relation` is NULL, run `schema.sql` to create the table.
The creation script stops and rolls back if `public.products` already exists.
It does not hide mismatches behind `CREATE TABLE IF NOT EXISTS`, drop tables,
or erase data.

No live schema was inspected during this change: there was no connected SQL
session available. The repository previously defined `scraped_laptops`, not
`products`. That SQL is preserved as `legacy_scraper_schema.sql`.

Verification: 45 checks passed against an isolated, in-memory PostgreSQL engine
(PGlite), using synthetic rows and simulated Supabase roles/default grants. They
covered constraints, UUID generation, timestamp offsets, URL uniqueness, upsert
identity/row count, RLS/grants, and preserving data when the creation script is run
again. No hosted Supabase schema or data was changed. Hosted role configuration
and API access still need verification in the actual shared project.

## Python field mapping

| Column | Current validated Python value | Notes |
| --- | --- | --- |
| `id` | Omit | PostgreSQL generates a UUID on insert; keep it on update. |
| `title` | `product.title` | SQL requires at least 3 non-whitespace characters. The current laptop validator is stricter. |
| `price` | `str(product.price)` | Exact Decimal serialization; stored as `numeric(12,2)`. |
| `currency` | `product.currency` | Required, explicitly USD; no SQL fallback/default. |
| `product_url` | `product.product_url` | Cleaned HTTPS product URL; unique upsert key. |
| `source` | `f"{product.retailer}.com"` | Known retailer becomes its domain: `amazon` → `amazon.com`, etc. Must match the URL host, ignoring `www.`. |
| `category` | `"laptops"` | Explicit tag for this validated laptop-only lesson. |
| `scraped_at` | `product.observed_at.isoformat()` | Includes a UTC offset; the actual observation time. |

`product_id`, availability, seller, discount and extraction method have no columns
here. The instructor backend maps an already validated record as follows:

```python
row = {
    "title": product.title,
    "price": str(product.price),
    "currency": product.currency,
    "product_url": product.product_url,
    "source": f"{product.retailer}.com",
    "category": "laptops",
    "scraped_at": product.observed_at.isoformat(),
}
```

`timestamptz` represents an instant and displays it in the session timezone; it
does not preserve the original timezone name. PostgreSQL interprets an input with
no offset using its session timezone, so Python must continue requiring an aware
datetime and sending the offset. `numeric(12,2)` can round excess decimal places;
Python must continue rejecting prices with more than two fractional digits.

## Uniqueness, upserts and latest observation

`UNIQUE (product_url)` allows one row for each identical URL string. A duplicate
plain INSERT fails. An upsert on **`product_url`** inserts a new URL or replaces
the existing row's title, price, currency, source, category and observation time.
Omit `id` from the update so the product keeps its generated identity.

For the existing HTTP Data API style, the instructor backend would POST the mapped
payload to `/rest/v1/products?on_conflict=product_url` using
`Prefer: resolution=merge-duplicates,return=minimal`.
The current `scraper/database.py` uses this mapped payload and conflict target.

Uniqueness compares strings, not product identity across aliases. Tracking query
parameters, `www` variants or different paths can still describe the same product
with different strings. Use one consistent URL when collecting a particular
variant. The scraper preserves all query parameters: no source-specific removal
rule has been verified. It does not merge `www`/path aliases or distinct queries.
Review variant changes instead of merging unrelated items.

Updates replace the previous values: **this is the latest-observation table, not
price history**. The backend must upload current observations in order and avoid
replaying stale records, because a basic upsert is last-write-wins. History or an
older-event guard would be separate work.

## Backend access

RLS is enabled and the new table has **no policies**. `anon`, `authenticated` and
`PUBLIC` have no table privileges. There are no anonymous insert/update/delete
policies. Supabase's existing `service_role` is the instructor backend role and
bypasses RLS. Its table grants are only SELECT, INSERT and UPDATE, plus schema
USAGE. UUID generation requires no sequence grant. DELETE and DDL are not granted.

The service-role/secret key remains privileged across the project; these grants
do not turn it into a narrowly scoped student credential. Keep it on the instructor
backend, never in the repository, student environment or chat.

`scraper/database.py` now reads `SUPABASE_URL` and `SUPABASE_SECRET_KEY` through
the script-relative configuration loader. It uses the secret only in the API-key
header, without student sign-in. `--check-db` reads at most one products ID and
never writes or prints a row/key. A successful read proves connectivity only;
separately verify a controlled write before relying on uploads. The original
student uploader's schema is preserved separately.

## Existing-table migration proposal

Use the inspection output to design an explicit ALTER migration. A concrete live
migration cannot be certified compatible until the real columns, constraints,
types, grants, policies and references are known. Preserve rows and extra columns.

1. Keep an existing generated primary key if it meets the requirement, including
   an identity integer. Do not replace IDs or break foreign keys to match the
   new-table UUID choice.
2. Add missing columns as nullable first. If old `retailer`/`observed_at` columns
   exist, propose mapped backfills into `source`/`scraped_at`, retaining old columns.
   Confirm an old naive timestamp's actual timezone before conversion; never
   label missing historical observation times as `now()`.
3. Inspect data before tightening constraints: NULL required values, short titles,
   nonpositive/nonfinite prices, excess price precision, non-USD currencies,
   non-laptop categories, invalid URLs, domain mismatches and duplicate URLs.
   Start with counts and retain original records.
4. Never invent missing prices/currencies/timestamps or round historical money to
   make it fit. Report incompatible rows and propose a preservation/remediation
   plan. Leave enforcement incomplete until those records are resolved.
5. Add named CHECK constraints with `NOT VALID`, then `VALIDATE CONSTRAINT` after
   remediation. Set NOT NULL only after all rows satisfy it. Explicitly review
   type changes for precision loss, timezone assumptions and table locks.
6. UNIQUE cannot be added NOT VALID. Add URL uniqueness after duplicate handling
   is approved. Do not auto-delete duplicates: identify a survivor and preserve
   the other observations before consolidation. For a large table, plan a unique
   index built CONCURRENTLY outside a transaction, then attach the constraint.
7. Review existing grants and policies before changing access: enabling RLS or
   revoking current rights can affect existing applications. Propose those access
   changes explicitly and do not silently drop existing policies.
8. Verify an insert, repeated-URL upsert with unchanged ID and row count, invalid
   value rejections, and denied anonymous writes. Confirm newest values remain.

References: PostgreSQL [constraints](https://www.postgresql.org/docs/current/ddl-constraints.html),
[ON CONFLICT and privileges](https://www.postgresql.org/docs/current/sql-insert.html),
[timestamp semantics](https://www.postgresql.org/docs/current/datatype-datetime.html),
and Supabase [RLS/service roles](https://supabase.com/docs/guides/database/postgres/row-level-security).
