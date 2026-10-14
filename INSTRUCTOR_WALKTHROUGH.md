# Shoppie AIM: Target-only 90-minute instructor walkthrough

Teach one pipeline: **page → dictionary → validated record → shared database**.
Students already know SQLite: connect `NOT NULL`, `CHECK`, and `UNIQUE` to Python
validation, then explain that Supabase runs PostgreSQL on a shared server.
Use only Target laptop pages in this lesson. The code still supports four
retailers; leave that implementation and the original URL list intact for later.
Do not type the entire parser live: use the working helpers
as scaffolding and write/explain one function at a time in a teaching copy.
Preserve the working files as the reference implementation.

**Current limitation:** the latest local integration run passed 173 offline tests
and a real Supabase read check, but accepted none of three live pages. No real
upsert has been verified. See [the actual integration results](scraper/tests/INTEGRATION_RESULTS.md).
Do not promise a live save unless the pre-class checks below succeed.

## How to teach this repository

**Give students the working `scraper/` files as scaffolding. Do not teach from
the old `lesson/` directory or ask them to recreate the whole repository in
90 minutes.** That directory and `LESSON.md` describe an earlier database model.
The current path is `scraper/main.py` → `scraper/scraper.py` →
`scraper/validator.py` → `scraper/database.py` → `sql/schema.sql`.

Keep this guide on your instructor screen; give students
[STUDENT_LESSON.md](STUDENT_LESSON.md). Show the VS Code Explorer once, explain
the current-versus-legacy directories, then close unrelated tabs. Start with
only `scraper/target_urls.txt`, `scraper/main.py`, `scraper/scraper.py` and
`scraper/validator.py` visible. Keep `.env` closed throughout screen sharing.

Use the same teaching cycle every time: **predict → run → inspect → explain →
make one small change → run again**. Ask students what should happen before
pressing Enter. Their task is to understand data flowing through functions,
not memorize Playwright setup or long CSS selectors.

| File | What students do | What you provide/explain |
| --- | --- | --- |
| `target_urls.txt` | Inspect the selected Target variant and edit an input URL. | Why one URL identifies one observation target. |
| `config.py` | Read `script_path` and `load_urls`; do not rewrite backend settings. | Paths, lists, comments and reading a text file. |
| `scraper.py` | Follow `fetch_page`/`fetch_rendered_page`, then `extract_product`; identify dictionary keys. | Provide network/identity/JSON-LD helpers as scaffolding; zoom in on one selector and `.get()`. |
| `validator.py` | Explain one rule and add one focused test; optionally change a rule in a disposable teaching copy. | Show the existing model first: required fields, Decimal, USD, aware timestamp. |
| `main.py` | Trace the loop and predict counters after success/failure. | Provide orchestration; explain function calls, `try/except`, `continue`, and explicit saving. |
| Tests and fixture | Run, read one assertion, add an edge case. | Real capture versus synthetic test; no network/credentials in tests. |
| `database.py` and `sql/schema.sql` | Read payload mapping and compare to SQLite constraints. | Instructor alone runs real connection/save checks; students do not handle the secret. |

Do not live-type complete files in table order. The file-by-file reference below
is your preparation checklist and explanation order. In class, live-type only
one small assertion or function change at a time, with the original available
to restore. Do not change price/currency defaults to make acceptance happen.

## Target-only run card and lesson readiness

After the shared setup below, use this explicit URL file for every class batch:

```powershell
.\.venv\Scripts\python.exe scraper/main.py --urls target_urls.txt
```

`target_urls.txt` resolves inside `scraper/`. Running the bare command still reads
the preserved four-retailer `urls.txt`; avoid it for this class.

For the live one-product demonstrations, set:

```powershell
$url = 'https://www.target.com/p/apple-macbook-neo-a18-pro-2026-laptop-with-touch-id-512gb-citrus/-/A-91122087'
.\.venv\Scripts\python.exe scraper/main.py --url $url --stage fetch --keep-html
.\.venv\Scripts\python.exe scraper/main.py --url $url --stage extract
.\.venv\Scripts\python.exe scraper/main.py --url $url
```

Optional rendered comparison:

```powershell
.\.venv\Scripts\python.exe scraper/main.py --url $url --browser --stage extract
```

**Readiness gate:** this exact variant previously yielded a title but no
price/currency, including after rendering. Target automatic collection is not
fixed by this teaching plan. If it still rejects, teach live retrieval plus
honest rejection and the dated saved sample. Do not announce a complete live
scrape/save lesson. Reserve real save/upsert demonstrations for a verified
accepted live record; otherwise label the database portion a mocked rehearsal.
Manual entry is optional background material, not the solution to the automatic
collection goal and not required in this Target lesson.

At 42 minutes, ask each pair to explain the handoff: “What did the page supply?
What did Python extract? What did validation refuse?” At 58 minutes connect the
same rules to SQL. At 75 minutes stop adding concepts and let pairs practice.

## Timing and pair rotation

| Minutes | Activity |
| --- | --- |
| 0–10 | Open VS Code, select interpreter, check setup; explain pipeline and credentials. |
| 10–18 | Demo 1: inspect a real page and its exact selected variant. |
| 18–26 | Pair round 1: A source inspection, B extraction, C validation. |
| 26–34 | Pair round 2: A extraction, B validation, C source inspection. |
| 34–42 | Pair round 3: A validation, B source inspection, C extraction. |
| 42–50 | Debrief; demos 2–3: extract a dictionary, reject an invalid record. |
| 50–58 | Demo 6: failed URL does not stop later URLs; explain counters and loop. |
| 58–65 | Explain SQL constraints, unique URL, RLS, and read-only connection check. |
| 65–75 | Demos 4–5: one controlled save, read back, rerun, confirm same row. |
| 75–86 | Student exercise, pair review, run focused tests. |
| 86–90 | Share findings and distinguish what was live, saved, or mocked. |

Each pair has a driver and navigator; swap roles halfway through each round.
At the source station, compare exact model/variant, displayed price, explicit
currency evidence, product identity and missing fields. At extraction, trace
`extract_product` and run the saved sample. At validation, predict acceptance
before running tests. Each station leaves a three-line handoff: evidence found,
unknown fields, and next check. No station needs database credentials.

## Shared terminal setup

All commands below run in PowerShell **at the repository root**, without
activation. Install Python 3.14, VS Code, and Microsoft's Python extension.
Open **File > Open Folder**, then **Terminal > New Terminal**.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r scraper/requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Use the installed Python's full path if `py` is unavailable. Select
`.venv\Scripts\python.exe` with **Ctrl+Shift+P > Python: Select Interpreter**.
Expected: installation succeeds, then `No broken requirements found.`
The tested version was Python 3.14.6 on the development computer; a different
fresh computer has not been tested.

Set `$url` to the exact laptop URL verified before class; keep variant query
parameters. For the dated fallback, define its original source URL separately:

```powershell
$sampleUrl = 'https://www.target.com/p/lenovo-legion-5-15-1-oled-wqxga-165hz-gaming-notebook-amd-ryzen-7-260-16gb-ram-512gb-ssd-nvidia-geforce-rtx-5060-eclipse-black/-/A-1004661132'
$sample = 'tests/fixtures/target_1004661132_2026-10-14.html'
```

Do not set `$url` to a guessed product. If no complete live product is available,
announce the fallback and use `$sampleUrl` only with `$sample` as shown below.

## File-by-file teaching order

The numbered order is the order to introduce/write code, not permission to
overwrite the reference implementation. Run each checkpoint immediately after
its change. The two scraper passes keep the first runnable step small.

| Order and file | Why it exists; write in this order | Beginner explanation | Immediate checkpoint and expected result | Common error → fix |
| --- | --- | --- | --- | --- |
| 1. `README.md` | Write prerequisites, root-directory commands, then credential boundary. | A repeatable recipe lets another person run our work. | `Get-Location` → folder containing this README. | Wrong terminal folder → open the repository root. |
| 2. `.gitignore` | Ignore secrets, environments, caches and archives; allow `.env.example`. | Files can exist locally without belonging in Git. | `git check-ignore scraper/.env .venv` → both paths reported. | Template also ignored → retain the `!.env.example` exception. |
| 3. `scraper/requirements.txt` | Explain package names, then reproducible pins; keep verified pins. | A virtual environment is this project's own toolbox. | Install command above, then `pip check` → no broken requirements. | Package missing → install using the same `.venv` executable. |
| 4. `scraper/__init__.py` | Keep the package marker before imports. | A package groups related Python files. | `.\.venv\Scripts\python.exe -c "import scraper; print('package OK')"` → package OK. | Import fails → use repository root and correct interpreter. |
| 5. `scraper/urls.txt` | Add one verified URL, then a small list; preserve queries. | One line is one input; a URL identifies a selected product. | `.\.venv\Scripts\python.exe -c "from scraper.config import load_urls; print(len(load_urls()), 'input URLs')"` → count. | Empty list → add supported HTTPS product URLs. |
| 6. `scraper/.env.example` | Keep blank backend names and safety comments. Copy only if absent. | A template describes settings; it is not a real key. | Conditional copy below → file exists, no contents printed. | Overwriting local settings → guard with `Test-Path`. |
| 7. `scraper/config.py` | `SCRIPT_DIR`, `script_path`, `load_urls`; later dataclass and lazy backend loader. | Relative paths start beside the script, regardless of terminal location. | URL-count command above → reads `scraper/urls.txt` without credentials. | Editing root `.env` → uploader reads `scraper/.env`, not root `.env`. |
| 8a. `scraper/scraper.py` | URL cleaning/identity, deduplication, page checks, then fetch/redirect safety. | Getting HTML is different from getting trustworthy product information. | `.\.venv\Scripts\python.exe scraper/main.py --url $url --stage fetch --keep-html` → title/fetched count, or honest rejection. | Bot check/timeout → stop, use the labeled capture; do not bypass it. |
| 8b. `scraper/scraper.py` | Main product selection, one explicit offer, then scoped HTML fallback; optional rendering last. | A page contains recommendations too; choose only the requested product. Missing means `None`. | Saved extraction command below → Target title/ID, null price/currency, unvalidated candidate. | Several offers → reject ambiguity instead of selecting a convenient price. |
| 9. `scraper/validator.py` | Required fields/types, Decimal bounds, currency/time, identity, then cleaning wrapper. | Validation is the door guard; cleaning fixes formatting, not missing facts. | `.\.venv\Scripts\python.exe -m pytest -q scraper/tests/test_validator.py` → passing cases, including deliberate invalid inputs. | Rounding a three-decimal price → reject it; do not silently alter source values. |
| 10. `scraper/main.py` | CLI flags, URL loop, fetch/extract/validate, per-URL exceptions/counters; saving branch last. | Catch an individual failure inside the loop so the next URL still runs. | Saved validation and continuation commands below → rejection counts, later page attempted. | One failure ends batch → keep per-record handling inside the loop. |
| 11. `scraper/tests/fixtures/` | Read real HTML and metadata together; keep synthetic adversarial files distinctly labeled. | A saved input makes tests repeatable; it is not today's product price. | Saved extraction command below → `LOCAL HTML: rehearsal only`. | Calling synthetic HTML a retailer capture → use provenance labels and metadata. |
| 12. `scraper/tests/test_parser.py` | Real capture fields, missing fields, ambiguous offers/variants, identity checks. | An assertion says what must stay true after edits. | `.\.venv\Scripts\python.exe -m pytest -q scraper/tests/test_parser.py` → pass, no internet. | Guessing a default currency → assert missing currency remains missing. |
| 13. `scraper/tests/test_validator.py` | Valid candidate first, then one invalid field per case. | Isolate a rule so a failed assertion has a clear cause. | Validator command above → pass. | Testing multiple unrelated errors at once → change one field per example. |
| 14. `sql/inspect_products.sql` | Relation existence, columns, constraints, grants and RLS inspection. | Inspect a shared database before changing its structure. | Instructor runs this file in Supabase SQL Editor → existing relation/metadata, or NULL for no table. | Empty table confused with missing table → inspect the relation result, not product rows. |
| 15. `sql/schema.sql` | Columns, checks, unique URL, RLS, revoke/grant; transaction wrapper. | PostgreSQL enforces rules even if a Python client has a bug. | Instructor runs only for a confirmed absent products table → success, no rows returned. | Already exists → stop and use inspection/migration guidance; do not drop tables. |
| 16. `sql/PRODUCTS.md` | Field mapping, access model, then compatible migration guidance. | Explain Python `observed_at` → SQL `scraped_at`; one URL owns one latest row. | Run the read-back SQL below → mapped fields for the chosen URL. | Expecting history → this table overwrites the latest observation. |
| 17. `scraper/database.py` | Config object/headers, sanitized errors, read check, payload, then upsert. | Importing a file must not connect; only explicit functions send requests. | `.\.venv\Scripts\python.exe scraper/main.py --check-db` → DB CHECK OK or classified failure. | Missing/wrong credentials → instructor fixes local configuration; never display the key. |
| 18. `scraper/tests/test_database_check.py`, `test_pipeline.py`, `test_commands.py` | Read-only behavior, mocked upsert mapping, then limits/failures/dedup counts. | A mock rehearses a response without touching a real service. | `.\.venv\Scripts\python.exe -m pytest -q scraper/tests` → pass; no credentials/network needed. | Treating a mocked save as real → label it a test, not a Supabase confirmation. |
| 19. `scraper/tests/conftest.py`, `scraper/tests/fixtures/README.md`, capture `.json` | Explain test isolation and provenance; provide these as scaffolding. | Tests block network and secret-file access; metadata records where saved evidence came from. | Full suite below → offline pass. | Depending on ignored local archives → use repository fixtures. |

Conditional template copy (mentees leave both backend fields blank):

```powershell
if (-not (Test-Path -LiteralPath scraper/.env)) {
    Copy-Item scraper/.env.example scraper/.env
}
```

Supporting reference files are not rewritten in this lesson: root
`requirements.txt` and `requirements-browser.txt` forward dependencies;
`LESSON.md`, `lesson/`, `tests/`, `db/schema.sql`, and
`sql/legacy_scraper_schema.sql` preserve the earlier classroom implementation.
Explain why two schemas exist, then use only `sql/schema.sql` for this uploader.
Checkpoint for preserved code: run the full suite below. Common error: running
`db/schema.sql` expecting `products`; fix: inspect first, then use current SQL.
`scraper/tests/RESULTS.md` and `INTEGRATION_RESULTS.md` are evidence reports;
read their executed-versus-blocked distinctions rather than treating them as
test programs. Update reports only after actually executing their checks.

## Demo 1: inspect a real product (10–18 minutes)

Open the preverified `$url` in a browser. Ask: “Which exact laptop is selected?
Which price buys that laptop, rather than an installment or accessory?” Compare
model, RAM/storage/color, seller and availability. Inspect page source/JSON-LD
for explicit `price` and `priceCurrency`; explain that visible content and
downloaded HTML can differ. Missing source data is a valid finding.
Do not solve bot challenges automatically. If blocked, announce the saved demo.

## Demos 2–3: extraction and rejection, with honest offline fallback

Say: **“We are now using a real response captured October 14, 2026, not the
current retailer page. This excerpt has no price or currency.”** The prepared
sample is the existing HTML fixture with its adjacent provenance JSON; no new
price or field has been added.

```powershell
.\.venv\Scripts\python.exe scraper/main.py --url $sampleUrl --html $sample --stage extract
.\.venv\Scripts\python.exe scraper/main.py --url $sampleUrl --html $sample
```

First command: `LOCAL HTML`, identified Target laptop title/ID, null price and
currency, `Candidate is unvalidated.` Second: rejection for price/currency,
validated=0, rejected=1, saved=0, exit 1. Explain dictionary keys, `.get()`, and
why `None` must not turn into zero or USD. For a deliberately invalid price:

```powershell
.\.venv\Scripts\python.exe -m pytest -q scraper/tests/test_validator.py -k 'bad_or_missing_fields or correct_record'
```

Label these inputs **synthetic unit tests**, not captured product prices. Point
out zero, negative, NaN, unsupported currency and excessive precision cases.
Never save synthetic fixtures to `public.products`. Local HTML is blocked from
`--save` by the CLI, even if an archive later contains a complete record.

## Demo 6: one failed URL, later URLs still run

Run the live continuation example without `--save` or a limit:

```powershell
.\.venv\Scripts\python.exe scraper/main.py --url 'https://unsupported.invalid/product' --url $sampleUrl
```

First URL is intentionally unsupported and rejected before retrieval. Students
should then see `Page 2/2`; its request may succeed or fail depending on the
retailer. Do not claim that second URL validated merely because it ran.
For a deterministic **mocked fetch-failure** demonstration if offline:

```powershell
.\.venv\Scripts\python.exe -m pytest -q scraper/tests/test_commands.py -k failed_fetch_continues
```

Open that test and show the later fetch assertion. Explain that this proves
loop behavior under a simulated network failure, not real retailer connectivity.

## Demos 4–5: instructor-only save and duplicate check (65–75 minutes)

**Optional separate manual exercise, outside this automatic Target lesson:**
run `.\.venv\Scripts\python.exe scraper/main.py --manual --url $url` and enter
only the observed title, full price and explicitly verified currency. Announce
“This is manual collection from the real page, not automatic extraction.” Unknown
fields must remain blank. After validating and checking the database, the
instructor may repeat with `--limit 1 --save`, then use the read-back queries below.
Repeat that manual command for the same URL to demonstrate upsert, using the
actual current source values. This makes the classroom write exercise possible
without claiming an automated scrape succeeded. If source facts themselves
cannot be verified, use the mocked fallback instead.

Only the instructor configures `SUPABASE_URL` and `SUPABASE_SECRET_KEY` locally
or in environment variables. Do not project `.env`, print headers, or give
mentees the backend secret. Database administration needs project access too.
Extraction and offline tests need none of these credentials.

First run a fresh live extraction and compare its values against the exact
displayed variant. If any required field is missing or ambiguous, stop this
live write segment and use the mocked fallback below.

```powershell
.\.venv\Scripts\python.exe scraper/main.py --url $url
.\.venv\Scripts\python.exe scraper/main.py --check-db
```

After both checks succeed, read the exact URL's current count in the SQL Editor
using the query below. Then run:

```powershell
.\.venv\Scripts\python.exe scraper/main.py --url $url --limit 1 --save
```

Expected only on confirmed success: `ACCEPTED`, then `SAVED:`, validated=1,
saved=1, failed_saves=0. `ACCEPTED` alone does not mean saved. A failed or unknown
write must not be counted as saved; after a timeout inspect the table before
retrying. Do not continue just to fill the time slot.

In Supabase SQL Editor replace the placeholder with the exact emitted
`product_url` (double any single quote inside a SQL string):

```sql
select count(*) as url_row_count
from public.products
where product_url = 'EXACT_VERIFIED_PRODUCT_URL';

select id, title, price, currency, product_url, source, category, scraped_at
from public.products
where product_url = 'EXACT_VERIFIED_PRODUCT_URL';
```

Record the returned id, count and timestamp. Rerun the **same** one-product save
command after a later observation, then repeat these queries. Students should
see count=1 after each confirmed save, the same id, and a later `scraped_at`.
If the URL existed before the first save, it should remain one row throughout.
The unique URL chooses the conflict; upsert updates that row. Other URL aliases
are not automatically the same row, and variant query parameters are preserved.
This is latest-observation storage, not price history. Never change a real price
just to demonstrate an update.

**If no verified live record is available:** explicitly say “The real save and
duplicate check are blocked. This next command is a mocked rehearsal.” Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q scraper/tests/test_commands.py -k 'save_uploads_validated or limit_one_stops_after_first_confirmed_save'
.\.venv\Scripts\python.exe -m pytest -q scraper/tests/test_pipeline.py
```

Inspect the mocked payload/conflict-key assertions. Do not announce a real saved
row, unchanged database count, or advanced database timestamp. Arrange the real
demo after retrieval is fixed. Synthetic write/update/constraint experiments
belong only in an isolated test table or disposable project.

## Student exercise (75–86 minutes)

Each pair chooses a supported laptop URL and records product identity, evidence
for each field, and unknowns. If offline, use the dated real sample and state
which fields cannot be established. Extract, predict the validation result, then
run it. Add one focused validator test for an edge case and explain why the
record should pass or fail; do not modify real source values or synthetic-price
fixtures to make a live demonstration succeed.

```powershell
.\.venv\Scripts\python.exe -m pytest -q scraper/tests/test_validator.py scraper/tests/test_parser.py
.\.venv\Scripts\python.exe -m pytest -q scraper/tests tests
```

Deliver a short handoff: exact input, live/saved/synthetic label, expected versus
actual result, and one unanswered question. Success means explaining evidence
and safe rejection, not obtaining a database write. Finish by asking why the
same URL updates one row and why a missing price must never become zero.

## Pre-class readiness checklist

- [ ] Review Git tracking: code, tests, real fixture/metadata, SQL, dependency pins,
  `.env.example` and `.gitignore` must be available to mentees. Currently many
  required files remain untracked; no commits are made by this walkthrough.
- [ ] Check actual `.env` files are ignored and untracked, without displaying
  contents. Project no credentials in editor tabs, logs or screen sharing.
- [ ] On the classroom machine, create a fresh environment, install pinned
  requirements, run `pip check` and the full tests; record actual outcomes.
- [ ] Verify VS Code uses the intended `.venv` interpreter. Activation optional.
- [ ] Inspect the selected variant and explicit source fields immediately before
  class; run extraction-only and compare the result. Review Amazon redirects.
- [ ] Test the Target-only URL file and one selected variant; expect bot blocks
  or missing fields. All stations use Target, not different retailers.
- [ ] Run the prepared saved extraction/rejection commands offline; announce the
  October 14 capture date and absent price/currency. Keep synthetic tests labeled.
- [ ] Instructor inspects `products`, preserves existing data, checks grants/RLS,
  and runs `--check-db`. Successful reads alone do not verify writes.
- [ ] Rehearse the one verified real save and repeat-save read-back checks if
  retrieval permits. Record count/id/timestamps; do not alter prices.
- [ ] If live saving remains blocked, reserve its slot for the explicitly mocked
  rehearsal and list the real checks as unfinished.
- [ ] Prepare three pairs, station handoffs and eight-minute rotation timer.

These are readiness tasks, not claims that another machine, a current live
product upload, or every retailer has already passed.
