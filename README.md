Current combined backend/dashboard setup and verified integration results: [INTEGRATION_RISHI_TRISHA.md](INTEGRATION_RISHI_TRISHA.md).

# Shoppie

## Description

Shoppie is an AI-powered smart shopping platform that collects product listings across retailers and turns them into a price-comparison experience. It uses semantic matching to identify equivalent products, tracks historical prices, and recommends whether users should buy now or wait.

## Planned Technologies

- Python, TypeScript/JavaScript, and SQL
- React, TypeScript, and Tailwind CSS
- FastAPI, Pandas, BeautifulSoup, Playwright, and PyTorch
- Gemini API, embeddings, PostgreSQL or Supabase, and price history data

## Docker Setup

Make sure Docker Desktop is installed and running.

```bash
docker compose up -d
docker compose down
docker compose ps
```

This is a generic starter configuration. The team can add project-specific dependencies and startup commands later.

## Beginner Python lesson: real laptop data

### Classroom option when automated retrieval fails

Use a real page you can inspect in your browser and enter only its verified
fields. This is **manual source collection**, not successful automatic scraping:

```powershell
.\.venv\Scripts\python.exe scraper/main.py --manual --url 'EXACT_PRODUCT_URL'
```

The command asks for title, full product price, explicit currency code, and
confirmation of the exact selected variant. Unknown values must stay blank and
will be rejected. A bare dollar sign does not establish USD. No database access
occurs by default. Counters stay fetched=0/extracted=0 for manual entry, and the
printed record says extraction_method=manual.

The instructor can add `--limit 1 --save` after verifying the source and database
configuration. Repeat the exact URL to update the same latest-observation row.
The SQL table does not store collection method; keep the printed record for
teaching provenance. Never enter synthetic fixture prices into the real database.
This mode uses the same validation and upsert path; it cannot make unavailable
source facts known. Automatic retailer collection remains unreliable.

For the timed teaching plan, pair rotations, demo commands and honest offline
fallback, see the [90-minute instructor walkthrough](INSTRUCTOR_WALKTHROUGH.md).
The current class plan uses **Target only**, with
`--urls target_urls.txt`; the original four-retailer list is preserved.
Give mentees the [student run card](STUDENT_LESSON.md). This scope change does
not imply that live Target price extraction has been fixed.

The current Python lesson is in **`scraper/`**, using instructor-backend-only
**`public.products`** in **`sql/schema.sql`**. See
[the field mapping, access model and migration guide](sql/PRODUCTS.md).
The original uploader schema is preserved in `sql/legacy_scraper_schema.sql`.
The scraper covers laptop pages from Amazon, Best Buy, Target, and
Walmart. It runs without Supabase configuration by default; database writes
require `--save`. The earlier [LESSON.md](LESSON.md), `lesson/`, `tests/`, and
`db/schema.sql` are preserved as the original observation-based version.

Repository inspection on October 14, 2026: this branch contained only this README
and `requirements.txt` (Pydantic and pytest), after commit `032ba66`. The previous
`db/schema.sql`, collectors, tests and Docker configuration were absent from the
working tree. The Docker commands above describe the earlier project plan;
there is currently no `docker-compose.yml`. The new lesson does not require Docker.

### Files and responsibilities

```text
scraper/
    __init__.py
    requirements.txt
    .env.example
    urls.txt
    config.py
    scraper.py
    validator.py
    database.py
    main.py
    tests/
        test_validator.py
        test_parser.py
        test_pipeline.py
        fixtures/
sql/
    schema.sql
```

| File | What it does |
| --- | --- |
| `scraper/config.py` | Resolves `.env`, URL files and local input paths relative to `scraper/`. Loads Supabase settings only for `--save` or `--check-db`. Environment variables override `.env`. |
| `scraper/scraper.py` | Retrieves plain or rendered HTML, checks page/product identity, and extracts explicit source fields. |
| `scraper/validator.py` | Cleans formatting without changing the source dictionary, then validates a `Laptop` record. |
| `scraper/database.py` | Prepares instructor backend access, checks connectivity with a read, and upserts validated records. No import-time connection. |
| `scraper/main.py` | Runs checkpoints, processes URLs one by one, reports acceptance/rejection/save counts, and enforces `--save`. |
| `scraper/urls.txt` | Editable list of real laptop product pages; blank lines and comments are ignored. |
| `scraper/.env.example` | Blank configuration template. No passwords or administrator keys belong here. |
| `scraper/requirements.txt` | Exact direct and transitive versions verified in the virtual environment. |
| `scraper/tests/test_validator.py` | Required-field, cleaning, money, currency and availability checks. |
| `scraper/tests/test_parser.py` | Main-product extraction, identity checks, bot checks and safe redirects. |
| `scraper/tests/test_pipeline.py` | Script-relative configuration, no import-time connections, explicit saving and upsert requests. |
| `scraper/tests/test_database_check.py` | Read-only query behavior, error classification, credential redaction and command isolation. |
| `scraper/tests/test_commands.py` | Command behavior, limits, per-record failure counts, confirmed writes and variant-safe URL deduplication. |
| `scraper/tests/fixtures/` | Clearly labeled synthetic **test inputs**. Never a live data fallback. |
| `sql/schema.sql` | Instructor-backend-only `products` table; unique URL, constraints, RLS and upsert grants. |
| `sql/inspect_products.sql` | Read-only inspection of an existing `products` table before proposing a migration. |
| `sql/legacy_scraper_schema.sql` | Preserved schema for the earlier student-sign-in uploader. |
| `.gitignore` | Excludes actual `.env` files, virtual environments, caches and public HTML archives. Allows `.env.example`. |

### Windows PowerShell setup — checkpoint 0

Use **64-bit Python 3.14** for this lesson. The pinned dependencies were actually
verified with **Python 3.14.6 on this Windows computer**; other Python versions and
a separate fresh Windows computer have not been tested.

Install Python, VS Code, and Microsoft's Python extension for VS Code.
Download or clone the repository, then choose **File > Open Folder** in VS Code
and select the repository folder containing this README. Choose
**Terminal > New Terminal**, using PowerShell at the repository root.

Create a virtual environment before selecting its interpreter:

```powershell
# Use your installed Python to create the environment once.
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r scraper/requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scraper/main.py --help
```

If `py` is unavailable, use your Python 3.14 executable's full path instead.
For example, the installed interpreter on this computer is:

```powershell
& 'C:\ProgramData\anaconda3\python.exe' -m venv .venv
```

All remaining commands use the virtual environment's executable directly.
Activation is optional. The versions were verified on Windows with Python 3.14.6;
the requirements also pin dependencies used by tests and optional Chrome rendering.
The root requirements files forward to these pins for earlier lesson commands.

Press **Ctrl+Shift+P**, run **Python: Select Interpreter**, choose **Enter
interpreter path** if necessary, and select `.venv\Scripts\python.exe` inside
this repository. Do not select the system Python for lesson debugging.

For extraction-only mode, edit **`scraper/urls.txt`** with supported HTTPS laptop
product URLs, one per line. Supported source domains are `amazon.com`,
`bestbuy.com`, `target.com`, and `walmart.com`. There is no `ALLOWED_DOMAINS`
environment setting. No Supabase URL, key, account, or database setup is needed.

The optional local configuration template can be copied without overwriting an
existing file:

```powershell
if (-not (Test-Path -LiteralPath scraper/.env)) {
    Copy-Item scraper/.env.example scraper/.env
}
```

Mentees should leave its Supabase fields blank. Extraction does not read `.env`;
only source URLs need configuring. Run extraction and offline tests from the root:

```powershell
.\.venv\Scripts\python.exe scraper/main.py
.\.venv\Scripts\python.exe -m pytest -q scraper/tests tests
```

Expected extraction output includes accepted records or `REJECTED:` messages,
then `fetched`, `extracted`, `validated`, `rejected`, `saved`, and `failed_saves`
counts. Without `--save`, saved counts stay zero and the final message confirms
extraction only. A rejection is a safe failure, not proof that a laptop is free
or unavailable. Current live collection is blocked as described below.

| Common setup error | What to do |
| --- | --- |
| `py`/`python` is not recognized | Install Python 3.14 or use its executable's full path. Reopen the terminal after installation. |
| `.venv\\Scripts\\python.exe` is not found | Open the terminal at the repository root and create the environment first. |
| `ModuleNotFoundError` | Install requirements with the same `.venv` Python used to run the script; check VS Code's selected interpreter. |
| PowerShell blocks activation | Activation is optional; use the executable commands above. |
| URL file missing/empty | Edit `scraper/urls.txt`; relative `--urls` paths start inside `scraper/`. |
| Timeout, bot check, or missing price/currency | Stop on challenges; inspect the real page and choose an accessible supported product. Do not invent values. |

Only the instructor needs Supabase credentials for **`--check-db` and `--save`**.
Creating/inspecting the shared database in the Supabase dashboard also requires
the instructor's project access. Mentees do not need the instructor's backend
secret key for setup, extraction, archived-page rehearsal, or automated tests.

**Distribution review (October 14, 2026):** Git currently tracks only README.md
and requirements.txt. The lesson code, tests, SQL, `.env.example`, and `.gitignore`
exist locally but are untracked, so a fresh clone cannot run this lesson yet.
The README/requirements edits are also uncommitted. No commits were made during
this review. Actual `.env` files are ignored and not tracked; their contents were
not inspected. Before distribution, the instructor must review and commit the
required non-secret lesson files, including fixtures and dependency files.

### Product URL corrections

The latest browser check also redirected
[ASIN B0DZD91W4F](https://www.amazon.com/dp/B0DZD91W4F) to a different ASIN and
selected variant. This input still needs review before class. Walmart uses its
[full product URL](https://www.walmart.com/ip/Lenovo-IdeaPad-1-15-6-FHD-Laptop-AMD-Ryzen-5-7520U-8GB-RAM-1TB-SSD-Windows-11-Home-Blue/20103908054)
instead of the short redirecting link. Target also uses a full product URL.
The [Best Buy page](https://www.bestbuy.com/product/apple-macbook-air-13-inch-laptop-apple-m4-chip-built-for-apple-intelligence-16gb-memory-512gb-ssd-sky-blue/JJGCQGFL5H)
was found in the retailer's product pages.

These identify actual products; they do **not** guarantee that a retailer will
serve accessible current prices to this script. Open the URLs before class and
replace discontinued products with current laptop pages. We do not hard-code
any prices or guess values from search results. Check retailer terms/robots rules,
make a few manual requests, and stop on bot checks. No internal retailer APIs or
access-control workarounds are used.

### Fetch one page — checkpoint 1

Pick a URL from `scraper/urls.txt` and explain `fetch_page` in `scraper/scraper.py`.
Start with one page before running all four.

```powershell
$url = 'https://www.target.com/p/lenovo-legion-5-15-1-oled-wqxga-165hz-gaming-notebook-amd-ryzen-7-260-16gb-ram-512gb-ssd-nvidia-geforce-rtx-5060-eclipse-black/-/A-1004661132'
.\.venv\Scripts\python.exe scraper/main.py --url $url --stage fetch --keep-html
```

Success reports the page title and `fetched=1`. Bot checks, HTTP failures and
product-changing redirects are rejected. A redirect can expand a short URL only
if the retailer and product ID stay the same. Archives go into ignored
`scraper/data/pages/`. No Supabase settings are read.

If JavaScript is needed and Google Chrome is installed, try the optional mode:

```powershell
.\.venv\Scripts\python.exe scraper/main.py --url $url --browser --stage fetch --keep-html
```

This runs a fresh signed-out Chrome session in the background and waits five
seconds for page scripts. It does not load your Chrome profile or solve bot checks.
Rendering may still leave required fields missing.

### Extract fields — checkpoint 2

Explain the dictionary in `extract_product`, `.get()`, `None`, JSON-LD and the
main-product selectors in `scraper/scraper.py`.

```powershell
.\.venv\Scripts\python.exe scraper/main.py --url $url --stage extract
```

Success prints an **unvalidated candidate**, possibly with `null` fields.
The parser prefers a matching JSON-LD Product with one exact Offer. It rejects
ambiguous products, price ranges and multiple offers. HTML fallback selectors
avoid using recommendation prices or monthly installment amounts.
Add `--browser` if it was needed in checkpoint 1.

### Validate — checkpoint 3

Explain `validate_record` and `Laptop` in `scraper/validator.py`. Relate the
constraints to SQLite's `NOT NULL` and `CHECK` constraints.

```powershell
.\.venv\Scripts\python.exe scraper/main.py --url $url
# Repeat for every URL in scraper/urls.txt:
.\.venv\Scripts\python.exe scraper/main.py
```

The default URL file is resolved beside the script, even when your terminal is in
another folder. `--urls another-file.txt` also resolves inside `scraper/`; absolute
paths are supported. Repeat `--url` to supply a few explicit pages instead.
One rejected page does not stop later pages. Any rejection/save failure produces
exit code 1; a completely successful chosen checkpoint produces exit code 0.

Accepted records require a supported URL, matching product ID, clearly laptop
title, positive finite price with at most two decimal places, explicit `USD`, and
a timezone-aware observation time. Cleaning trims whitespace and valid thousands
separators; it never supplies a missing price or currency. A bare `$` does not
identify `USD`. Availability and seller may stay `None`; discount remains `None`
because this lesson does not extract discounts. Unknown values do not become zero.
Money uses `Decimal`, and `observed_at` is this run's parsing time.

For offline rehearsal using your own archived **real** public page:

```powershell
.\.venv\Scripts\python.exe scraper/main.py --url $url --html data/pages/target-1004661132.html
```

`--html` paths also resolve inside `scraper/`. Local files are labeled as rehearsal,
may be stale, and **cannot** be used with `--save`. Test fixtures are never a fallback.

### Instructor Supabase configuration and read-only connection check

If `--check-db` reports `MISSING TABLE`, the selected `db/schema.sql` is the
**older** lesson schema: it does not create `products`. Run
`sql/inspect_products.sql` in the same Supabase project's SQL Editor. If its first
result is NULL, run `sql/schema.sql`, then rerun the check below. Keep any earlier
lesson tables. If products exists, inspect its schema/exposure instead of dropping
it or rerunning a different table-creation script.

Use one shared Supabase project. Run `sql/inspect_products.sql` before
`sql/schema.sql`; the creation script refuses to change an existing products table.
See [sql/PRODUCTS.md](sql/PRODUCTS.md) for constraints and migration guidance.

The current scraper uses **SUPABASE_URL** and **SUPABASE_SECRET_KEY** from
`scraper/.env`, or from environment variables.
Environment variables take precedence, including explicitly empty values.
The root `.env` and `.env-example` are not loaded. Extraction-only commands do
not load database settings or need any credentials.

Create the local configuration file only if it does not exist:

```powershell
if (-not (Test-Path -LiteralPath scraper/.env)) {
    Copy-Item scraper/.env.example scraper/.env
}
```

Edit `scraper/.env` locally in VS Code. Use the project's HTTPS URL and modern
`sb_secret_...` key. Keep the key on the instructor's controlled machine/backend;
do not distribute it to mentees, commit it, paste it into chat, or print it.
No student email/password prompts or publishable key are used by this uploader.
This follows Supabase's [backend API-key guidance](https://supabase.com/docs/guides/getting-started/api-keys).

From the repository root, using the virtual environment without activation:

```powershell
.\.venv\Scripts\python.exe scraper/main.py --check-db
```

From inside `scraper/`, the same command is:

```powershell
..\.venv\Scripts\python.exe main.py --check-db
```

With Python already on PATH or the environment activated, `python main.py --check-db`
also works inside `scraper/`.

The command runs one GET query for `products`, selecting only `id` with `limit=1`.
It does not print the returned row, fetch retailer pages, load `urls.txt`, sign in,
create tables or perform any writes. An empty table is a successful read.
It cannot be combined with `--save` or scraping flags.

| Result | Meaning |
| --- | --- |
| `DB CHECK OK` | The configured project and products read are accessible. |
| `MISSING CONFIGURATION` | URL and/or secret key is absent; no request was made. |
| `INVALID CONFIGURATION` | URL or key format is invalid; values are not echoed. |
| `AUTHENTICATION FAILURE` | HTTP 401 or a recognized authentication error; check the key/project pairing. |
| `PERMISSION FAILURE` | Access denied; check the backend role's table grants. |
| `MISSING TABLE` | PostgREST cannot find products; the table may be missing or not exposed/in its schema cache. |
| `SCHEMA FAILURE` | A requested column is missing; inspect the existing table. |
| `CONNECTION/REQUEST/RESPONSE FAILURE` | Timeout, network/TLS issue, unavailable project, unexpected response or other HTTP failure. |

Known PostgREST codes distinguish missing tables from generic endpoint errors;
unknown errors are not guessed to mean a missing table. See the
[PostgREST error reference](https://docs.postgrest.org/en/stable/references/errors.html).
Exit code is 0 for a successful read and 1 for a failed check.

**A successful read verifies connectivity only. A separate controlled write test
is still needed** to check the mapped payload, INSERT/UPDATE grants, constraints,
and conflict behavior. The connection-check command never performs that test.

### Explicit saving - checkpoint 4

These are the four command modes. From the repository root in PowerShell:

```powershell
# Scrape, validate and print. No Supabase configuration or database access.
.\.venv\Scripts\python.exe scraper/main.py
# Read-only products connectivity check; no scraping or writes.
.\.venv\Scripts\python.exe scraper/main.py --check-db
# Scrape, validate and upload accepted live records.
.\.venv\Scripts\python.exe scraper/main.py --save
# First controlled write check: at most one validated product/write attempt.
.\.venv\Scripts\python.exe scraper/main.py --limit 1 --save
```

Inside `scraper/`, use `..\.venv\Scripts\python.exe main.py` followed by the
same flags. With the environment activated or its Python on PATH, these are
`python main.py`, `python main.py --check-db`, `python main.py --save`, and
`python main.py --limit 1 --save`.

`--limit` must be positive. In a save run it caps **validated products and write
attempts**, not successful saves alone. Rejected pages do not consume the limit,
so later URLs are tried until a record validates. A failed/unknown write does
consume the limit: `--limit 1 --save` cannot try a second product after a timeout.
Extraction-only limits cap validated records; in fetch/extract checkpoints they
cap successfully completed records for that stage.

The summary reports `validated`, `rejected`, `saved` and `failed_saves` separately,
plus fetch/extraction counts. Validation success is not counted as save success.
`SAVED:` appears only after Supabase confirms HTTP 200, 201 or 204. Scrape failures
and individual save failures do not stop later URLs unless the limit is reached.
Write failures produce exit code 1; rejected pages also produce exit code 1.
PowerShell exposes the result as `$LASTEXITCODE`.

Repeated input URLs are deduplicated in first-seen order, for both `urls.txt` and
repeated `--url` flags. Normalization only trims surrounding whitespace, lowercases
the hostname and removes the browser fragment. The entire query string, including
order, encoding, repeated parameters and blank values, is preserved through
fetching, validation and upload. No retailer-specific parameter removal has been
verified, so even apparently tracking-only parameters remain. `www`/path aliases
are not automatically merged. Redirects that change/drop query parameters are
rejected rather than risking selection of a different variant.

Once live extraction accepts a real record, the instructor can explicitly save it:

```powershell
.\.venv\Scripts\python.exe scraper/main.py --url $url --save
# Or process the URL file, saving only accepted live records:
.\.venv\Scripts\python.exe scraper/main.py --save
```

Add `--browser` if rendering is required. Credentials are loaded only after an
accepted live record needs saving, and `--save` is still blocked with local HTML.
Importing `database.py` or calling `connect` makes no request; actual requests
happen only in the explicit read-check/upsert functions. No credentials or raw
server error bodies are printed. Database requests do not follow redirects.

`database.py` maps validated fields to `public.products`: retailer becomes the
source domain, category is laptops, and observed_at becomes scraped_at. The
conflict key is **product_url**. A repeated canonical URL updates the existing
row without changing its generated ID. This is the latest observation, not price
history. No automatic write retry occurs; after a timeout check the table before
retrying. Earlier lesson files and schemas remain preserved for reference.

### Checks and current limits

```powershell
.\.venv\Scripts\python.exe -m pytest -q scraper/tests tests
.\.venv\Scripts\python.exe -m pip check
git status --short
```

173 tests pass. Exact dependency versions remain recorded in
`scraper/requirements.txt`. Tests cover configuration, parsing, validation, import
safety, explicit saving, limits, duplicate/variant handling, confirmed mocked
upserts and read-only database checks.
The focused offline validation/parser results, fixture provenance and remaining
live checks are recorded in [scraper/tests/RESULTS.md](scraper/tests/RESULTS.md).
The later [real integration report](scraper/tests/INTEGRATION_RESULTS.md) records
a fresh local environment install, 173 passing tests, and a successful real
Supabase read check. Real uploads remain unverified. This was this computer,
not a test on another fresh Windows machine.
They do not contact retailers or Supabase. No commits are made.

The corrected URL list was rechecked on October 14, 2026 with the new fetch pipeline:

| Retailer | Actual result on this machine |
| --- | --- |
| Amazon | HTTP returned generic `Amazon.com` HTML; extraction found no product title, price or currency. |
| Best Buy | Product-page request timed out. |
| Target | Returned the identified laptop title, but the downloaded page omitted price and currency. |
| Walmart | Redirected away from the requested product route; the scraper stopped. |

The batch reported two fetched pages and two fetch rejections. Target's archived
page also correctly failed validation for missing price/currency. **No live record
has reached acceptance.** Correcting URL identity does not fix bot blocks or
missing currency/price data.
Successful live collection from all four retailers and a real Supabase upsert still
need verification on the classroom network and shared project. No Supabase writes
have been performed during development.

There is no frontend, embedding pipeline, scheduler, automated discovery or product
matching in this lesson. For live coding, supply `main.py` and the URL/JSON-LD helpers
as scaffolding and teach fetch → extract → validate → save in that order.
