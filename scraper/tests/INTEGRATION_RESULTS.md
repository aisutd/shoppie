# Real integration checks — October 14, 2026

Executed from the repository root using the configured local environment.
No credentials were printed, no commits were made, and no database writes were
attempted. This report is separate from the offline test results in RESULTS.md.

## Commands actually executed, in order

### 1. Fresh environment and dependency installation: passed

The destination did not exist before creation. The existing .venv was preserved.

```powershell
& 'C:\ProgramData\anaconda3\python.exe' -m venv data/integration-20261014-1952/venv
.\data\integration-20261014-1952\venv\Scripts\python.exe -m pip install -r scraper/requirements.txt
```

Both commands exited 0. All pinned dependencies installed in the fresh
environment (Python 3.14.6). Activation was not required.

### 2. Dependency consistency: passed

```powershell
.\data\integration-20261014-1952\venv\Scripts\python.exe -m pip check
```

Exit 0: `No broken requirements found.`

### 3. Automated tests: passed

```powershell
.\data\integration-20261014-1952\venv\Scripts\python.exe -m pytest -q scraper/tests tests --junitxml=data/integration-20261014-1952/pytest.xml
```

Exit 0: **173 passed in 2.68s**. These are deterministic offline tests; mocked
writes are not evidence of a successful real Supabase upsert.

### 4. Three live pages, extraction only: failed acceptance

```powershell
.\data\integration-20261014-1952\venv\Scripts\python.exe -u scraper/main.py --url 'https://www.amazon.com/dp/B0DZD91W4F' --url 'https://www.bestbuy.com/product/apple-macbook-air-13-inch-laptop-apple-m4-chip-built-for-apple-intelligence-16gb-memory-512gb-ssd-sky-blue/JJGCQGFL5H' --url 'https://www.target.com/p/lenovo-legion-5-15-1-oled-wqxga-165hz-gaming-notebook-amd-ryzen-7-260-16gb-ram-512gb-ssd-nvidia-geforce-rtx-5060-eclipse-black/-/A-1004661132' --keep-html
```

Exit 1:

```text
Results: fetched=2, extracted=2, validated=0, rejected=3, saved=0, failed_saves=0
Extraction only. No Supabase settings read, connections opened or database writes.
```

| Source | Actual scraper result |
| --- | --- |
| Amazon B0DZD91W4F | HTML archived; required title, price and currency missing/invalid. Rejected. |
| Best Buy JJGCQGFL5H | Request failed or timed out. Rejected; execution continued to Target. |
| Target 1004661132 | HTML archived; title present, price and currency absent. Rejected. |

Fresh responses are under scraper/data/pages. Earlier Amazon/Target captures
were copied into data/integration-20261014-1952/previous-pages before the run.
These local data directories are ignored by Git.

### 5. Displayed-page comparison: incomplete; not passed

Opened the same three URLs in the connected Chrome browser, without interacting
with purchase controls or human-verification challenges.

- Amazon redirected to `https://www.amazon.com/dp/B0DZDBHQPQ?th=1`, a different
  ASIN. Displayed a Midnight M4 MacBook Air with 24GB/512GB and a **used**
  $1,499.55 offer. This does not verify a record for the original input ASIN.
- Best Buy displayed the requested Sky Blue M4 MacBook Air 16GB/512GB,
  model Z1H81LL/A, SKU 6571026: clearance **$1,139.99**, **Sold Out**.
  The scraper returned no record to compare. The displayed dollar symbol was
  not substituted for missing explicit source currency data.
- Target displayed a human-verification challenge. Price/currency comparison
  was blocked; the challenge was not completed or bypassed.

No complete extracted record was verified. Browser observations were not used
to fill missing scraper fields or manufacture an upload candidate.

### 6. Read-only Supabase connection check: passed

```powershell
.\data\integration-20261014-1952\venv\Scripts\python.exe scraper/main.py --check-db
```

Exit 0:

```text
DB CHECK OK: the configured project's products table is accessible for a read.
Connectivity only. A separate controlled write test is still needed to verify inserts/upserts.
```

The locally configured credentials and network were available for this check.
It does not establish write permissions, constraints, or upsert behavior.

## Checks not executed

Steps 7–10 are blocked by the lack of an accepted, verified real product:

7. One-product `--limit 1 --save` upload.
8. Read back and confirm the saved row.
9. Rerun the same product with `--limit 1 --save`.
10. Confirm the exact URL's row count stays unchanged and scraped_at advances.

No real price was changed. No synthetic record, constraint test, test table,
or disposable project was written during this run.

## Remaining fixes and continuation

- Replace or explicitly review the Amazon input URL: the displayed page changed
  ASIN. Preserve variant-identifying query parameters.
- Resolve Best Buy retrieval and verify its actual source price/currency fields.
- Target remains blocked by human verification/incomplete product data.
- Obtain one complete real source record and compare its title, exact variant,
  price and explicit currency to the displayed page before saving.
- Then run the two controlled one-product save commands, reading back the exact
  product_url after each. Compare its id, exact row count and scraped_at values.
  A timeout leaves a write outcome unknown: inspect before retrying.
- Run any synthetic update/constraint checks only in an explicitly isolated test
  table or disposable project, never by editing a real product price.

For the remaining CLI checks, replace VERIFIED_URL with the exact verified URL:

```powershell
.\data\integration-20261014-1952\venv\Scripts\python.exe scraper/main.py --url 'VERIFIED_URL' --limit 1 --save
```

Execute this only after the extraction problem is resolved. Successful automated
tests and the successful read-only check do not substitute for steps 7–10.
