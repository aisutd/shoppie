# Offline test results — October 14, 2026

## Commands actually executed

All commands were run from the repository root using its virtual environment.
Final results after the changes:

```powershell
.\.venv\Scripts\python.exe -m pytest -q scraper/tests/test_validator.py scraper/tests/test_parser.py
```

**61 passed in 0.83s.** Focused validation and source-parser tests.

```powershell
.\.venv\Scripts\python.exe -m pytest -q scraper/tests/test_commands.py -k "real_fixture or failed_fetch or non_confirmed or write_failure or failed_write"
```

**9 passed, 20 deselected in 0.52s.** Targeted extraction/failure/save accounting checks.

```powershell
.\.venv\Scripts\python.exe -m pytest -q scraper/tests tests
```

**173 passed in 2.09s.** Full regression suite, including the preserved earlier
lesson tests. Every command above returned exit code 0.

## Requested validation coverage

| Case | Executed assertion |
| --- | --- |
| Correct record | Accepted with exact Decimal price, USD and matching retailer/URL. |
| Empty title | Empty and whitespace-only values rejected on title. |
| Missing price | Both absent field and explicit None rejected on price. |
| Nonnumeric price | Text such as `not a number` rejected on price. |
| Zero/negative prices | Rejected on price. |
| NaN/infinity | String, float and Decimal forms rejected, including negative infinity. |
| Missing/unsupported currency | Absent, None, dollar symbol and CAD rejected on currency. |
| Wrong source domain | Retailer/URL mismatch and unapproved/spoofed domains rejected. Source in the upload is derived from this validated retailer. |
| Database precision | Excess decimals and too many whole digits rejected; `9999999999.99`, the numeric(12,2) maximum, accepted without rounding. |

## Requested parser coverage

- The real Target excerpt, captured **October 14, 2026**, extracts the expected
  title, retailer, TCIN, URL and source-field values. The adjacent JSON records
  its source URL, original-file hash, excerpt hash, capture method and expected
  fields. The fixture checksum normalizes line endings for Windows checkouts.
- This real response has no usable price/currency. It correctly fails validation
  for exactly those fields. It is **not** evidence of a complete accepted live
  laptop price, and no missing values were inserted into the capture.
- Saved synthetic fixtures isolate missing product information, multiple exact
  offers, ambiguous variants and an Offer with missing commerce fields.
  Tests assert clear errors or the exact failing field names.
- Missing price, currency, availability, seller and discount remain None. A bare
  dollar symbol does not become USD. Recommendation prices do not fill missing data.

All parser fixtures and their provenance are documented in
[fixtures/README.md](fixtures/README.md). Synthetic test inputs are labeled as
synthetic, not retailer captures or fallback observations.

## Offline and pipeline guarantees exercised

The autouse fixture in `conftest.py` removes Supabase environment variables,
blocks socket connections, and prevents reads of the real `scraper/.env` for
scraper tests. Configuration tests use temporary files. HTTP integration checks
use mocks, not the internet or a Supabase project. No dependencies are downloaded
by a test run.

Executed checks verify that:

- A real saved page extracts without credentials, config loading or HTTP calls.
- A failed first URL is rejected and the later URLs still validate.
- HTTP failures/unconfirmed responses never print `SAVED:` or increment saved.
- A timeout counts as a failed/unknown save; no credential text is echoed.
- Partial write failures remain separate from successful validation and saves,
  and make the save run return nonzero.
- `--limit 1 --save` makes at most one write attempt, including a failed attempt.

No production changes were needed: this task adds tests, fixtures and test docs.
No live request, Supabase write or commit was made during this task.

## Checks still to run against real services

These were **not executed as live checks in this task**:

```powershell
# Current project/table access; read-only.
.\.venv\Scripts\python.exe scraper/main.py --check-db
# Current retailer responses; no database access.
.\.venv\Scripts\python.exe scraper/main.py --limit 1
# Instructor's controlled first write, only after live validation succeeds.
.\.venv\Scripts\python.exe scraper/main.py --limit 1 --save
```

A read-only success does not prove write grants, table constraints or upserts.
For the controlled write, confirm a real accepted page produces `SAVED:`, then
inspect `public.products`. Save that same URL again and verify its ID and row count
stay unchanged while the observation updates. If no live page validates, the
write has not been tested. Current access/price extraction for all four retailers
remains a separate live check.
