# Mentor guide: building Shoppie's database

## Teaching approach

Use the existing synthetic JSON so progress does not depend on a live scraper.
Build one small piece, demonstrate it, and have the mentee explain it before
continuing. The function bodies are intentionally empty. This guide uses manual
completion checks; a formal test suite is a later task.

## Step 1 — Understand the data (whole team)

Open example_product.json and trace one row. Find the retailer, selected product,
specifications, observed price and scraped_at. Read the normalized contract in
README.md. Explain listing vs observation and retailer SKU vs manufacturer model.

Mentor asks: 'If this price changes tomorrow, what stays the same?'

Completed when: students can map one raw row to normalized fields and explain
why two retailers need two listings even if the physical product is identical.

## Step 2 — Create tables (schema pair; mentor provisions MySQL)

Mentor creates the shoppie database and application user, chooses MySQL 8.0.16+
and gives students local configuration instructions. Each local server has its
own data. Workbench is a viewing/query tool, not the database server itself.

Students implement schema.sql blocks A, B and C, in that order. Explain primary
keys, foreign keys, NULL, DECIMAL and UNIQUE as each appears. Seed amazon,
walmart, target and best_buy. Document the manual schema execution command or
Workbench steps. Defer listing_embeddings until the core pipeline is complete.

Completed when: Workbench shows three tables with the specified columns/keys,
retailers contains four rows, and students can draw retailer -> listings ->
observations. SELECT queries show the currently empty child tables.

## Step 3 — Connect Python (connection pair)

Implement read_config(), connect() and describe_connection(). Install the MySQL
connector in the team's selected Python environment and record the dependency.
Explain host, port, database, user and password. Implement explicit environment
loading if using .env; add placeholder .env.example and ignore real credentials.

Completed when: a small manual Python call returns database name/server version,
then closes the connection. Student can explain why every script reuses connect().

## Step 4 — Normalize one record (normalization pair)

Implement clean_text(), parse_money(), parse_timestamp(), normalize_attributes(),
then normalize(). Start with the first example row and print its output. Use
the exact README return contract. Keep all basic normalization in this file.
Preserve raw_payload and distinguish missing values from invalid values.

Completed when: '$349.99' becomes Decimal('349.99'), timestamps are UTC, IDs
remain text, condition is explicit, numeric specs have consistent types, and
missing price stays None. Student explains what changed and what was preserved.

Steps 2-3 and Step 4 can be worked on by separate pairs after Step 1.

## Step 5 — Import a first record, then the fixture (ingestion pair)

Implement load_batch() and the three database helpers. Use queries with %s
placeholders. Implement import_file() to call normalization and the helpers,
with one transaction per record. Implement main() with --input.

First use a temporary JSON file containing one existing fixture row. Then use
the full fixture. Print imported/skipped/rejected counts and useful errors.
Database failures should stop the import rather than silently skipping data.

Completed when: one fixture record becomes one listing plus one observation;
the full 40-row fixture can be imported with no unexplained rejection, and
missing fields appear as NULL. Students show foreign-key relationships in SQL.

## Step 6 — Read what was stored (query pair)

Implement get_listing(), get_latest_observation(), get_price_history(), then
find_listings(). Use dictionary cursors and join retailer names to results.
Use observed time to choose the latest row; return UTC timestamps explicitly.

Completed when: students retrieve headphones at multiple retailers, inspect
their color/condition, and show price with its source/time. Unknown prices and
shipping remain visibly unknown; candidates are not claimed as exact matches.

## Step 7 — Demonstrate persistence (whole team)

Reimport the original file: counts should report skipped observations and row
counts should stay unchanged. Make a COPY of one row with a later timestamp
and changed price: it adds history without creating another listing. Import
an older observation: it adds history without overwriting current descriptions.
Use get_price_history() to explain the sequence. Preserve the original fixture.

Completed when: students can demonstrate these behaviors and explain which
information belongs in listings versus listing_observations. This is the core
database milestone. No live scraper or embedding model is required.

## Step 8 — Later: embeddings and candidate similarity

Only start after Step 7. Implement schema block D and build_text() first.
Then load one chosen embedding model once, generate normalized vectors and
store model revision/template/input hashes. Finally implement candidate retrieval
and identity explanations. Evaluate matching quality in a subsequent phase.

Completed when: a stored description generates a reproducible vector, and a
listing retrieves cross-retailer candidates with scores plus explicit identity
reasons. Students explain why similarity alone does not establish a match.

## Mentor progress board

| Stage | Student output | Ready to move on when |
| --- | --- | --- |
| Contract | Explanation of one normalized row | Everyone uses the same fields |
| Schema | SQL tables and retailer seeds | Tables/keys visible in MySQL |
| Connection | Working connect() | Python identifies the intended database |
| Normalization | normalize(record) output | Money/specs/time/missing values explained |
| Import | Ingestion command and summary | Fixture creates listings and observations |
| Retrieval | Four query functions | Latest data/history can be shown |
| Persistence | Manual walkthrough | Reimports/history behave as agreed |
| ML later | Vectors and candidates | Configuration and uncertainty are explained |

Keep pull requests small: table schema, connection, normalization helpers,
record normalization, ingestion, queries. Ask students to show their function's
input and output, state why it exists, and explain who calls it.
