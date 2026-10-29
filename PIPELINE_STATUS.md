# Scraper/database verification — October 21, 2026

The existing scraper architecture is preserved. Offline behavior is tested;
automatic live Target collection and a real Supabase insert/update/readback remain
unverified. No hosted database writes, commits, pushes, branch changes, or
dependency pin changes were made. Work stayed on `Raiyan-Branch`.

## Environment

- `.venv/Scripts/python.exe`: Python **3.13.15**, 64-bit Windows.
- pip upgraded from 26.2.1 to **26.2.2**; pytest **8.4.2** available.
- Installed root `requirements.txt`, including its existing `-r scraper/requirements.txt`.
  All 22 pinned packages installed, including pyee 14.0.0, Playwright 1.64.0,
  Pydantic 2.14.1, requests, BeautifulSoup, python-dotenv and their dependencies.
  `pip check`: no broken requirements.
- Playwright launched existing Google Chrome with `channel="chrome"`, loaded
  synthetic local HTML with `set_content`, and read its heading successfully.
  No browser download was necessary. On another machine, install Google Chrome
  separately; this code does not launch Playwright's bundled Chromium.
- The initial backup move encountered directory permission errors and was stopped.
  Files from the old environment remain in ignored `.venv-backup-311/` and
  `.venv-311-remainder/`. A permitted rename isolated the remainder before the
  fresh `.venv` was created. These backups were deliberately not deleted.
- Use the explicit Windows executable or activate `.venv/Scripts/Activate.ps1`;
  another terminal's existing PATH/interpreter selection is not changed automatically.

## Reproduction and verification

Before functional changes:

| Command/check | Outcome |
| --- | --- |
| `python -m pytest -q scraper/tests tests` | 195 passed |
| Full discovery with explicit ignores for old environments, `db/database_test.py` and `sbert_test.py` | 195 passed |
| `python -m pip check` | No broken requirements |
| Two new parser regressions, before production fix | 2 failed: accessory metadata and named price accepted as main-product price |

Unrestricted baseline discovery was unsafe: the user's untracked
`db/database_test.py` inserts a demo row into local SQLite at import time;
`sbert_test.py` loads an embedding model. Neither was executed or modified.
`pytest.ini` now scopes discovery to maintained `scraper/tests` and `tests` and
includes the existing `tests_adapters.py` filename.

After fixes (all commands use `.venv/Scripts/python.exe`):

| Command/check | Outcome |
| --- | --- |
| `python -m pytest -q scraper/tests tests` | **218 passed**, 0 failed |
| `python -m pytest -q` | **218 passed**, 0 failed |
| `python -m pytest -q scraper/tests` | 164 passed |
| `python -m pytest -q tests` | 54 passed |
| `python -m pytest -q tests/tests_adapters.py` | 3 passed (also included in final runs) |
| `python -m pip check` | No broken requirements |
| `python --version` / `python -m pytest --version` | 3.13.15 / 8.4.2 |
| `git diff --check` | Passed |
| Ignore checks | Actual env files, environments/backups, IDE and local DB ignored |

The final count includes 20 added cases plus 3 existing adapter cases newly
included in discovery. Existing tests were preserved. New tests cover scoped
metadata/prices, ambiguity, browser readiness/challenge/timeout/redirect handling,
URL whitespace rejected before SQL, exact-URL reads and updated upsert payloads.
Browser readiness tests mock Playwright; the separate real Chrome smoke test
checks local launch/rendering only.

Executed the documented real Target saved-fixture command twice, with
`--url` from the adjacent fixture JSON and
`--html tests/fixtures/target_1004661132_2026-10-14.html`:

- `--stage extract`: exit 0, expected Lenovo title/ID, null price/currency.
- Default validation: exit 1, rejected specifically for missing price/currency.
- Both commands explicitly print LOCAL HTML; neither saves or contacts a retailer.

No current live retailer request, live Supabase read, schema migration or live
upsert was attempted. Historical Target failures are in CLASSROOM_READINESS.md.

## Files changed and reasons

| File | Change and purpose |
| --- | --- |
| `.gitignore` | Ignore old environment backups, IDE settings, SQLite files and browser outputs; preserve local files. |
| `pytest.ini` | Limit discovery to maintained suites and include existing adapter tests; avoid executing unrelated scratch scripts. |
| `scraper/scraper.py` | Scope HTML prices to main content, remove secondary regions, reject conflicting matches, restrict product metadata to head; reject URL whitespace; fail browser readiness explicitly and check redirect identity during polling. |
| `scraper/database.py` | Add `get_product` using existing authenticated requests/error handling and exact normalized URL; no schema or upsert redesign. |
| `scraper/tests/test_parser.py` | Reproduce recommendation contamination and verify correct scoped price, supported head metadata and ambiguous-price handling. |
| `scraper/tests/test_validator.py` | Verify raw URL whitespace cannot reach the SQL URL constraint. |
| `scraper/tests/test_browser.py` | Verify readiness without network traffic, including immediate success, delayed success, bounded timeout, challenge/source failure and redirect rejection. |
| `scraper/tests/test_product_retrieval.py` | Test retrieval/error responses and repeat-upsert mapping with newer timestamp and omitted ID. |
| `README.md` | Correct Python/root requirements setup and browser readiness/prerequisites. |
| `STUDENT_LESSON.md` | Match Python 3.13/root requirements setup. |
| `CLASSROOM_READINESS.md` | Add dated follow-up; preserve historical live evidence. |
| `PIPELINE_STATUS.md` | This verification record and function guide. |

## Functions to understand

| Function | Input → output | Responsibility and pipeline position |
| --- | --- | --- |
| `main.main(argv)` | CLI argument list → exit status 0/1 | Orchestrates URL loading, fetch/extract checkpoints, validation, optional saving and counters. Errors for one record do not stop later records. |
| `scraper.identify_product(url)` | HTTPS retailer product URL → `(retailer, product_id)` | Enforces supported routes and selected Target preselect identity before collection. |
| `scraper.clean_url(url)` | URL string → normalized URL | Trims edges, lowercases host, drops fragment, rejects raw whitespace; preserves the entire query and variant selection. |
| `scraper.unique_urls(urls)` | URL sequence → ordered unique list | Deduplicates identical normalized inputs without merging query variants. |
| `scraper.same_requested_product(original, destination)` | Two URLs → bool | Checks retailer/product identity and unchanged query during redirects. |
| `scraper.check_page(html)` | HTML → None or ValueError | Detects visible challenge/access-denied pages before extracting data. |
| `scraper.fetch_page(url)` | Product URL → HTML | HTTP retrieval with bounded, identity-preserving redirects, status/content checks and challenge detection. |
| `scraper.fetch_rendered_page(url)` | Product URL → HTML or ValueError | Fresh headless Chrome; polls extraction for title/price/currency, stops on challenge/source failure, rejects redirects and incomplete readiness. Presence is checked here; full validity comes later. |
| `scraper.product_nodes(value)` | Parsed JSON-LD → Product iterator | Walks top-level/graph/mainEntity only, avoiding arbitrary recommendation traversal. |
| `scraper.main_product(soup, url)` | Parsed HTML + URL → one Product dict, None or error | Selects matching JSON-LD identity and refuses ambiguity. |
| `scraper.target_embedded_title(soup, product_id)` | HTML + selected TCIN → title or None | Reads only the documented TCIN-bound Target title modules. Does not invent commerce data. |
| `scraper.text(context, selector)` / `meta(soup, field)` | Scoped HTML/field → unique text/value or None | Reject conflicting matches; product metadata comes only from head. |
| `scraper.extract_product(html, url)` | HTML + exact URL → unvalidated candidate dict | Verifies canonical/selected identity; prefers matching Product + one exact Offer, otherwise conservative HTML fallback; records UTC parsing time. |
| `validator.validate_record(record)` | Candidate dict → `Laptop` or validation error | Cleans a copy (whitespace, currency case, valid thousands separators), then enforces the contract without filling missing source values. |
| `validator.Laptop` validators | Field/model values → validated values or error | Enforce finite positive numeric(12,2) price, explicit USD, laptop title, known availability, timezone and URL/retailer/ID agreement. SQL mapping supplies source/category from the validated retailer/laptop contract. |
| `config.script_path(path)` / `load_urls(path)` | Path → resolved path / URL list | Resolve local inputs relative to scraper, handle comments/blank lines and duplicates. |
| `config.load_database_config()` | Environment + optional scraper/.env → DatabaseConfig | Lazy configuration; environment wins even when empty. Missing/invalid config errors name settings without exposing values. |
| `database.connect(config)` | DatabaseConfig → Database | Prepares settings only, with no network or sign-in. |
| `database.request_headers(database)` | Database → HTTP headers | Places modern backend secret in apikey; callers must keep headers private. |
| `database.raise_response_error(response)` | HTTP response → DatabaseError | Classifies known auth/permission/schema/request failures without raw bodies/secrets. |
| `database.check_database(database)` | Database → None or error | One read-only ID query; connectivity only, no returned product or writes. |
| `database.upsert_product(database, product)` | Database + validated Laptop → None or error | Maps to products columns; POST conflict key product_url, merge duplicates, omit ID, send observed_at as scraped_at. No automatic write retry. |
| `database.get_product(database, product_url)` | Database + exact URL → row dict or None | GET latest saved row; preserves query variants, rejects malformed/multiple/wrong-URL responses. Backend helper, not a frontend endpoint. |
| `manual.collect_product(url)` | URL + confirmed human input → candidate dict | Explicit manual source collection; same later validation/upsert, no fetch or invented defaults. |

## End-to-end flow and limits

URL → identify/normalize → HTTP or fresh Chrome HTML → reject challenges/identity
changes → select main product/one offer or scoped HTML fields → clean and validate
Laptop → only with `--save`, load backend config → map to public.products and
upsert on product_url → backend `get_product` retrieves that exact URL's row.

The database schema's unique URL and omitted upload ID preserve one row/ID on
conflict. The upload supplies the newer observation time, not upload time. Unit
tests prove request construction, not hosted PostgreSQL execution. As documented
in sql/PRODUCTS.md, this is last-write-wins; upload current observations in order.
There is no history table or older-event guard.

**Fixed and tested offline:** dependency compatibility/setup, safer extraction,
bounded browser failure/readiness, URL/validation contract, current upsert mapping,
retrieval helper, configuration failure behavior and repository ignores/discovery.

**Partially verified:** real Chrome launch works locally; retailer rendering is
covered with mocked pages. Supabase writes/reads are covered with HTTP mocks.

**Live source limitation:** historical Target captures lack commerce fields;
current live availability/anti-bot behavior was not tested. No valid live product
was obtained in this task. Do not promise automatic live collection based on this
report. The scraper deliberately rejects incomplete data.

**Remaining integration work:** on authorized test infrastructure, inspect actual
schema, collect a verified real product, save/read it, then repeat the exact URL
and verify count=1, same ID and advancing scraped_at. No application/frontend
exists in this lesson; the retrieval helper is ready for a backend caller.

**Separate future work:** SBERT/hybrid matching and the TODO scaffolds under db/
are the older MySQL/observation lesson, not this Supabase pipeline. They remain
unchanged. Extraction still depends on explicit retailer-provided evidence;
unsupported page layouts require new fixtures and focused parser changes.
