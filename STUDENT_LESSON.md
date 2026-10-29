# Target laptops: student run card

Today we follow one real Target laptop page through **fetch → extract →
validate → optionally save**. You already know SQLite; Python validation and
PostgreSQL constraints enforce similar rules. We use the existing `scraper/`
code. `lesson/`, `LESSON.md` and `db/schema.sql` are older reference material.

## Get ready

Use Python 3.13 and VS Code with Microsoft's Python extension. Open the repository
folder, open a PowerShell terminal at its root, and run:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

If `py` is unavailable, use the installed Python's full executable path. Select
`.venv\Scripts\python.exe` with **Ctrl+Shift+P > Python: Select Interpreter**.
Activation is optional. Extraction and tests need no Supabase credentials;
you do not need to create `.env` for these activities.
The optional `--browser` mode requires Google Chrome installed on the computer.
Installing the Python requirements alone does not install Chrome. The ordinary
HTTP mode and offline fixture tests do not require Chrome.

## Run and explain

Open `scraper/target_urls.txt` and inspect the exact selected variant in your
browser. Record its title, model/storage/color, full price and currency evidence.
A bare `$` does not establish USD. Missing information stays unknown.

```powershell
.\.venv\Scripts\python.exe scraper/main.py --urls target_urls.txt
```

Watch the record travel through `scraper.py`, `validator.py`, then `main.py`.
You may see a safe rejection: Target currently does not reliably supply price
and currency to this scraper. `ACCEPTED` means validated, not saved. The default
run never accesses Supabase. Explain the summary counters rather than assuming
a page title means collection succeeded.

## Three pair stations

1. **Source inspection:** which exact Target variant is selected? Which fields
   have evidence? Which are unknown?
2. **Extraction:** find `extract_product`; trace HTML into a dictionary. Why
   might a value be `None`? Run the dated sample below.
3. **Validation:** read `Laptop` and one validator test. Predict which inputs
   fail and explain why. Run the focused tests.

Rotate every eight minutes: A source/extraction/validation; B
extraction/validation/source; C validation/source/extraction. Swap driver and
navigator halfway through each round. Leave your findings for the next pair.

## Offline sample: explicitly saved data

This real Target excerpt was captured **October 14, 2026**. It describes a Lenovo
laptop, not the live MacBook used above. Price/currency were absent at capture.
The adjacent fixture JSON records provenance. No values have been invented.

```powershell
$sampleUrl = 'https://www.target.com/p/lenovo-legion-5-15-1-oled-wqxga-165hz-gaming-notebook-amd-ryzen-7-260-16gb-ram-512gb-ssd-nvidia-geforce-rtx-5060-eclipse-black/-/A-1004661132'
.\.venv\Scripts\python.exe scraper/main.py --url $sampleUrl --html tests/fixtures/target_1004661132_2026-10-14.html --stage extract
.\.venv\Scripts\python.exe scraper/main.py --url $sampleUrl --html tests/fixtures/target_1004661132_2026-10-14.html
```

Expect `LOCAL HTML`, a title and product ID, null price/currency, then a rejection
on validation. Exit 1 is expected for this rejection. Saved HTML cannot be used
with `--save`. This demonstrates parser behavior, not current pricing.

```powershell
.\.venv\Scripts\python.exe -m pytest -q scraper/tests/test_validator.py scraper/tests/test_parser.py
```

Passing invalid-input tests means the program correctly refused bad data.
Synthetic fixtures test rules; they are not real observations to upload.

## Watch the instructor database demonstration

Only the instructor uses backend credentials and `--save`. Watch the mapping to
`public.products`, then the unique `product_url` conflict key: repeating the same
URL updates one row's latest observation, rather than creating price history.
The instructor must read back the count, id and timestamp to prove a real upsert.
If no real product validates, this segment is a labeled mocked test demonstration;
it is not evidence of a successful upload.

## Your exercise

Add one focused invalid-input test to `scraper/tests/test_validator.py`, following
the existing examples. Explain the expected failure before running it. Do not
alter real product prices or add defaults for missing fields. Submit your exact
input URL, live/saved/synthetic label, expected and actual result, and one reason
validation protects the shared database. Finish by explaining why one failed URL
should not prevent the next URL from being processed.
