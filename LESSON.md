# Shoppie AIM: from SQLite to shared laptop observations

> The current implementation and instructions are in [README.md](README.md),
> `scraper/`, and `sql/schema.sql`. This document and `lesson/` are retained as the
> earlier observation-based lesson. They use different tables and append records;
> the new scraper upserts shared current product rows. Use the new README for class.

We will fetch a real laptop page, read its data into a Python dictionary, validate
that dictionary, and optionally insert an accepted observation into Supabase.
The updated lesson covers **Amazon, Best Buy, Target, and Walmart**. Start the
live explanation with one page, then repeat the exact checkpoints for the other three.
Allow two sessions (about 90–120 minutes total) with the browser/database extensions.

## What existed before this lesson

On October 14, 2026, `shiv-test-branch` was clean and contained only:

- `README.md`: the larger Shoppie vision and earlier Docker instructions.
- `requirements.txt`: Pydantic 2 and pytest 8.

Commit `032ba66` had already removed the earlier implementation. The IDE's
`db/legacy_lesson_schema.sql` tab was stale. This lesson adds a new, separate SQL schema;
it does not restore or overwrite the earlier implementation. Existing README
content and requirement entries are preserved. No commits are made for this lesson.

## Setup in VS Code — checkpoint 0

Open this repository folder. Install the Microsoft Python extension if needed.
Use **Ctrl+Shift+P → Python: Select Interpreter** to select Python 3.11 or newer.
Open **Terminal → New Terminal** (PowerShell).

On this machine Python was found at `C:\ProgramData\anaconda3\python.exe`,
although `python` and `py` were not on PATH. An isolated `.venv` has been created.
For a fresh setup on this machine:

```powershell
& 'C:\ProgramData\anaconda3\python.exe' -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m lesson --help
```

On another machine, use `python -m venv .venv` with its installed Python.
Select `.venv\Scripts\python.exe` as the VS Code interpreter. The commands below
use the full relative interpreter path, so PowerShell activation is unnecessary.
Success: `--help` lists the three stages, optional browser mode, and `--save`.

## Choose real pages

These are real product URLs, not a practice store. Product URLs can expire;
open them before class and substitute another current laptop from the same retailer
if needed. Their specs differ: we are teaching collection, not matching equivalents.
We deliberately do not hard-code any price or availability.

```powershell
$amazon = 'https://www.amazon.com/dp/B0DZDC3WW5'
$bestbuy = 'https://www.bestbuy.com/product/apple-macbook-air-13-inch-laptop-apple-m4-chip-built-for-apple-intelligence-16gb-memory-512gb-ssd-sky-blue/JJGCQGFL5H'
$target = 'https://www.target.com/p/-/A-1004661132'
$walmart = 'https://www.walmart.com/ip/20103908054'
$url = $target
```

Sources: [Amazon MacBook](https://www.amazon.com/dp/B0DZDC3WW5),
[Best Buy MacBook](https://www.bestbuy.com/product/apple-macbook-air-13-inch-laptop-apple-m4-chip-built-for-apple-intelligence-16gb-memory-512gb-ssd-sky-blue/JJGCQGFL5H),
[Target Lenovo](https://www.target.com/p/-/A-1004661132),
[Walmart Lenovo](https://www.walmart.com/ip/20103908054).

Retailers change layouts and vary prices by location/seller. A browser-visible
price may be absent from the HTTP response. These are conservative extractors,
not guaranteed access to every listing. Check each retailer's terms and robots
instructions before class, make only a few manual requests, and stop on bot checks.
We do not work around access controls or use internal retailer APIs.

## Checkpoint 1 — get one page (10–15 minutes)

Read `lesson/pages.py`, starting with `fetch_page`. Explain `requests.get`,
status codes, timeout, the returned HTML string, and a function's return value.
URL validation is a supporting helper; you do not need to write the regex live.

```powershell
.\.venv\Scripts\python.exe -m lesson --url $url --stage fetch --keep-html
```

Success: character count and page title. The optional `--keep-html` writes the
public HTML under `data/pages/`, which Git ignores. No Supabase access occurs.
HTTP errors and redirects stop the checkpoint rather than silently changing pages.

If the page uses JavaScript, install the optional browser dependencies once:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-browser.txt
.\.venv\Scripts\python.exe -m lesson --url $url --browser --stage fetch --keep-html
```

This requires installed Google Chrome. It runs a temporary, signed-out browser
in the background, waits five seconds for page scripts, and captures rendered HTML.
It does not load your normal Chrome profile. A slow/incomplete page can still
have missing fields; that is a rejection, not a reason to fill in a value.

## Checkpoint 2 — extract a dictionary (15–20 minutes)

Read `lesson/extract.py`: start with the `record` dictionary in `extract_product`.
Show `None`, `.get()`, JSON, a single Offer, and BeautifulSoup selectors.
JSON-LD is structured data embedded inside an HTML script tag. The same Product
and Offer vocabulary can be used across all four retailers when present.

```powershell
.\.venv\Scripts\python.exe -m lesson --url $url --stage extract
# For a page that needs JavaScript:
.\.venv\Scripts\python.exe -m lesson --url $url --browser --stage extract
```

Success: a **candidate** dictionary, possibly containing `null` (Python `None`).
It has not passed validation. Explain why a price from a recommendation or a
monthly installment must not become the laptop price. The helper matches the main
Product to the requested URL and rejects ambiguous products and multiple offers.
HTML fallbacks use main-product selectors; they do not scan the whole page for prices.

Repeat with `$url = $amazon`, `$url = $bestbuy`, and `$url = $walmart`.
Different retailers can produce different missing fields or failures.

## Checkpoint 3 — accept or reject (15–20 minutes)

Read `lesson/validate.py`. Relate Pydantic constraints to the SQL `NOT NULL`
and `CHECK` constraints mentees know from SQLite.

```powershell
.\.venv\Scripts\python.exe -m lesson --url $url
# Or:
.\.venv\Scripts\python.exe -m lesson --url $url --browser
```

Success: `ACCEPTED` plus the validated record, or a clear rejection with field
names/error codes. A failure exits with status 1. Neither command reads Supabase
credentials or writes to a database, even if credentials are set in the environment.

Rules:

- Required: supported retailer/product URL, matching product ID, clearly laptop
  title, positive finite exact price, explicit `USD`, timezone-aware observation time.
- Accessories, aggregates/ranges, multiple offers, unknown currencies and missing
  prices are rejected. This first lesson only accepts explicitly identified US dollars.
- A bare `$` is ambiguous and does not establish `USD`.
- Availability and seller are optional. Missing stays `None`/SQL `NULL`.
  Recognized Schema.org availability names are retained, including out-of-stock.
- Discount is always unknown (`None`/`NULL`) in this lesson. We do not infer a
  discount, use a made-up list price, or treat unknown as zero.
- `Decimal` stores exact money. `observed_at` records when this run parsed the page;
  it is not the retailer's last-updated timestamp or a checkout guarantee.

For offline rehearsal, reuse an actual archived public page from checkpoint 1:

```powershell
.\.venv\Scripts\python.exe -m lesson --url $target --html data/pages/target-1004661132.html --stage extract
.\.venv\Scripts\python.exe -m lesson --url $target --html data/pages/target-1004661132.html
```

Local HTML is explicitly marked as practice, may be stale, and cannot be used with
`--save`. Tests use synthetic data only; they are never a fallback product source.

## Mentor setup — one shared Supabase project

1. Create or choose **one** Supabase project for the class. Students all use that
   project's URL and publishable key; they do not each create a database.
2. Run `db/legacy_lesson_schema.sql` once in its SQL Editor. It adds only `lesson_members` and
   `lesson_laptop_observations`. It intentionally fails rather than replacing an
   existing lesson table; do not repeatedly run it or drop existing project tables.
3. In Authentication, create/invite each student's email/password user and ensure
   their account is confirmed. Each student keeps their own password private.
4. Copy each student's UUID from Authentication → Users. Add it to `lesson_members`
   using the commented SQL example at the bottom of the schema.
5. In the project's API settings, locate the project URL and **publishable** key
   (`sb_publishable_...`). Do not distribute a secret or `service_role` key.

RLS is enabled. Class members can insert their own observations and read the shared
class observations. They cannot update/delete rows, impersonate another student,
or add themselves to `lesson_members`. Nonmembers cannot access lesson observations.
The membership list is managed by the mentor in SQL Editor.

This follows Supabase's [API key guidance](https://supabase.com/docs/guides/getting-started/api-keys),
[password sign-in](https://supabase.com/docs/guides/auth/passwords), and
[RLS documentation](https://supabase.com/docs/guides/database/postgres/row-level-security).

## Checkpoint 4 — explicitly save an accepted record (15–20 minutes)

SQLite previously opened a local file. Here, Python sends one HTTP request to
Supabase's Data API, which inserts into a shared PostgreSQL table. Read
`lesson/database.py` and compare its JSON row to the SQL column names.

Set the project URL/key in the **current terminal only**. This works in Windows
PowerShell 5.1 and PowerShell 7; the key prompt hides your input:

```powershell
$env:SUPABASE_URL = Read-Host 'Shared Supabase project URL'
$lessonKey = Read-Host 'Publishable key' -AsSecureString
$env:SUPABASE_PUBLISHABLE_KEY = [System.Net.NetworkCredential]::new('', $lessonKey).Password
Remove-Variable lessonKey
.\.venv\Scripts\python.exe -m lesson --url $url --save
# If the successful extraction required Chrome, use the same mode:
.\.venv\Scripts\python.exe -m lesson --url $url --browser --save
```

Choose **one** save command, after checking that extraction accepts the page.
Only an accepted live record triggers a student email prompt and hidden password
prompt. Success prints `SAVED`. No password or access token is printed or persisted.
There is no `.env` loader and no need to put credentials into a file or command text.
No Supabase writes were performed while building this lesson.

Each successful run appends an observation, with the student's ID assigned by
Supabase. A later price check is another observation; this is not a current-price
upsert or a scheduler. The database rejects an identical observation identity.
A network timeout after posting can leave save status unknown: check the table
before retrying. There are no automatic database retries.

Use Supabase's Table Editor or the SELECT query at the bottom of `db/legacy_lesson_schema.sql`
to see the shared rows. Before class, verify with one member and one nonmember:
the member can insert/read, the nonmember cannot, and neither can update/delete.
These remote policy checks require your actual project and accounts.

Clear terminal configuration when finished:

```powershell
Remove-Item Env:SUPABASE_URL, Env:SUPABASE_PUBLISHABLE_KEY -ErrorAction SilentlyContinue
```

## File guide and live-writing order

| File | Purpose |
| --- | --- |
| `README.md` | Original project context plus a link to this lesson. |
| `requirements.txt` | Small core dependencies; retains Pydantic and pytest. |
| `requirements-browser.txt` | Optional Playwright dependency, plus core requirements. |
| `.gitignore` | Keeps credentials, environments, caches and downloaded data out of Git. |
| `lesson/__init__.py` | Marks `lesson` as a Python package. |
| `lesson/pages.py` | Checkpoint 1: validate a URL and fetch plain/rendered HTML. |
| `lesson/extract.py` | Checkpoint 2: extract explicit Product/Offer fields into a dictionary. |
| `lesson/validate.py` | Checkpoint 3: define accepted laptop records and validate data. |
| `db/legacy_lesson_schema.sql` | Mentor's shared PostgreSQL tables, constraints, grants and RLS. |
| `lesson/database.py` | Checkpoint 4: hidden sign-in and insertion of a validated record. |
| `lesson/__main__.py` | Connects the stages, prints results, and enforces `--save`. |
| `tests/test_lesson.py` | Offline checks for unsafe data, page identity and the save boundary. |

Use `__main__.py` as supplied scaffolding during live coding; teach the other files
in checkpoint order. After each file's explanation, stop and run its checkpoint.
The URL/JSON-LD helpers and tests are prepared support code, not a typing exercise.

Run local checks:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
git status --short
```

Tests never contact retailers or Supabase. Actual retailer access is checked
separately and can change between rehearsals. No frontend, embeddings, scheduler,
product matching, or automated discovery is included.

### Verification on October 14, 2026

41 offline tests passed in the repository's `.venv`. The help command and the
fetch/extract/validate checkpoints were exercised against a real, locally retained
Target page. That page was rejected at validation because its price and currency
were absent. The real page is in ignored `data/pages/target-1004661132.html` on this
machine; it is not a synthetic example or a file staged for Git.

| Retailer | Actual live result in this environment |
| --- | --- |
| Amazon | Plain HTTP returned a bot check; Chrome redirected away from the requested ASIN. |
| Best Buy | Plain HTTP timed out; Chrome could not complete the page load. |
| Target | Plain and rendered HTML provided the laptop title but omitted price/currency. |
| Walmart | Plain HTTP returned a 307 redirect; Chrome left the product route. |

**No live page reached ACCEPTED during verification.** The code handles all four
retailer URL formats, main-product JSON-LD and conservative HTML fallbacks, but
successful live price collection across these four sites is not yet verified.
Rehearse with accessible current laptop URLs on the classroom network before
using this as an end-to-end data collection demo. If required fields are still
absent, teach the rejection checkpoint; do not bypass blocks or fabricate values.

The save boundary, authenticated request and credential handling passed mocked
tests. A real Supabase insert and the remote RLS policies have **not** been tested:
the shared project's configuration and confirmed student accounts are still needed.
No credentials were requested, printed, written to files, or committed during setup.

## Discussion prompts

- Why should missing currency reject a record while missing availability can stay NULL?
- How is a Python dictionary like one SQL row? Where do their types differ?
- Why does validation need to happen before a write? Why also use SQL constraints?
- Why should each student sign in instead of sharing the mentor's administrator key?
- What evidence would we need before adding a discount field or comparing two products?
