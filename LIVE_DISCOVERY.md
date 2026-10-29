# Gemini discovery and permitted live collection

Updated October 28, 2026. Gemini Google Search grounding is now the only active
automatic discovery provider. The earlier Brave, Best Buy API, and sitemap
implementations are retired in `backend/legacy_discovery.py` for regression tests;
the CLI and dashboard do not call them. Ordinary Best Buy product parsing remains,
along with Amazon, Target, and Walmart support.

## Setup on this Mac

```bash
cd /Users/rishibadal/Documents/shoppie
source .venv-ai/bin/activate
python -m pip install -r requirements-ai.lock.txt
python -m backend config-check
python -m backend browser-check --headed
```

Chromium is already installed. Only on a fresh environment/missing browser:

```bash
PLAYWRIGHT_BROWSERS_PATH="$PWD/.local/browsers" python -m playwright install chromium
python -m backend init-model
```

Use VS Code to create/edit the ignored root `.env`. Add `GEMINI_API_KEY` and
optionally `GEMINI_MODEL=gemini-3.8-flash`. Do not replace `scraper/.env`, which
already contains your Supabase URL and backend secret key. No credentials were
printed or copied. Environment variables take priority, then nonempty root `.env`
settings, then the existing `scraper/.env`; dotenv interpolation is disabled.
An explicitly empty environment variable disables that setting.

For a temporary Gemini key without placing it in shell history (zsh):

```zsh
read -s 'GEMINI_API_KEY?Gemini API key: '
export GEMINI_API_KEY
```

A configured key does not authorize billing by itself. Every CLI discovery run
needs `--allow-gemini`, or explicit `SHOPPIE_ALLOW_GEMINI=1` in backend settings.
The dashboard has a per-action consent checkbox. No Gemini API call was made in
this implementation; all Gemini tests use mocks. Check your account's model,
grounding quota, billing, and current Google terms before opting in.

## Discover without scraping

This command makes a potentially billed Gemini request only after your opt-in:

```bash
python -m backend discover --allow-gemini \
  --query 'Apple MacBook Air M5 16GB RAM 512GB SSD'
```

Only URLs from actual `grounding_chunks.web.uri` evidence are used. Generated
answer URLs and all generated prices/specifications are ignored. The parser
accepts only supported HTTPS retailer product paths. Accessories, search pages,
invalid hosts, and duplicate exact URLs are excluded. Query parameters selecting
variants are preserved. Google's opaque citation redirect endpoint is resolved
with at most three manual redirects; arbitrary redirectors/private destinations
are never followed and no retailer product is fetched during discovery.

One generation request is made per discovery run, with at most one one-second
backoff retry on HTTP 429/500/502/503/504. Authentication/invalid requests and
ambiguous network timeouts are not retried. At most 24 source chunks and eight
product links are processed. Successful discovery is cached in memory for three
minutes (up to 16 requests). Cache scope includes model, query, limit, and a key
hash. No keys or generated answers are logged.

The prompt requests at most two underlying Google searches. The SDK does not
provide a strict per-generation search-count cap, so Google can execute more;
actual reported search count is returned. This is not a guaranteed cost ceiling.
The dashboard shows source links and Google's returned Search attribution snippet
inside a separate frame with scripts/network disabled except Google image assets.
A citation is a discovery lead, not proof of a real offer.

## Collect only permitted pages

`SHOPPIE_PAGE_RETAILERS` defaults to empty. Enable only retailers for which your
team actually has automated access permission. Values are `amazon`, `bestbuy`,
`target`, `walmart`. Allowlisting is not permission and does not bypass robots,
CAPTCHAs, HTTP denials, rate limits, login, or retailer terms.

After obtaining permission, configure the applicable value in your root `.env`
or shell. For example, **only if Best Buy page access is permitted**:

```bash
export SHOPPIE_PAGE_RETAILERS='bestbuy'
python -m backend collect-live --allow-gemini --browser --headed \
  --query 'Apple MacBook Air M5 16GB RAM 512GB SSD'
```

Optional AI validation and verified-evidence explanation (also potentially billed):

```bash
python -m backend collect-live --allow-gemini --browser --headed \
  --ai-review --explain \
  --query 'Apple MacBook Air M5 16GB RAM 512GB SSD'
```

Discovery performs at most one generation; optional validation performs at most
one generation per nonconflicting candidate (maximum eight); explanation performs
at most one generation. Each has at most one temporary-HTTP retry. Unknown data
is never filled by AI. A deterministic RAM/storage/CPU/model contradiction always
wins. AI uncertainty or failure sends an offer to review. Explanation selects
existing evidence sentence IDs; invalid output uses deterministic text, without
changing prices or rankings. Demo data is never sent to Gemini for explanations.

You may test a known permitted URL without discovery or Gemini. Set `PRODUCT_URL`
to an actual observed product URL; this command does not invent one:

```bash
read 'PRODUCT_URL?Paste an actual permitted retailer product URL: '
python -m backend collect-live --url "$PRODUCT_URL" --browser --headed
```

Repeat `--url` up to eight times. Requests reads ordinary HTML; `--browser` uses
installed Chromium for dynamic content; `--headed` shows the browser. All paths
stop on blocked pages. Changed-product navigations are aborted. Requests never
follow a redirect changing product identity or variant query parameters.

## Dashboard and API

Terminal 1:

```bash
cd /Users/rishibadal/Documents/shoppie
source .venv-ai/bin/activate
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```bash
cd /Users/rishibadal/Documents/shoppie
source .venv-ai/bin/activate
python -m streamlit run dashboard.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

Terminal 3:

```bash
open http://127.0.0.1:8501
open http://127.0.0.1:8000/docs
curl --get 'http://127.0.0.1:8000/deals' \
  --data-urlencode 'q=Apple MacBook Air M5 16GB RAM 512GB SSD'
```

The API defaults to Demo; it never offers unrestricted remote scraping. Set
`SHOPPIE_API_SOURCE=live` for local collected observations or `supabase` for
read-only shared products before starting the API. `/storage/status` returns
configuration booleans only. `/demo/collect` refuses Live/shared mode.

In the dashboard choose **Live · permitted sources → Local live collection**.
Enter the exact query, opt in to Gemini API calls, and click **Discover candidate
links only** or **Find offers**. Add optional exact filters/AI review/browser
rendering as appropriate. Missing keys, denied access, and incomplete identity
remain visible. Old observations are not counted as successes of a failed new run.

The independent shared-data workflow is **Live → Supabase · read only → Read
shared products**. Set Availability to **Any** to inspect old rows with missing
stock evidence. Existing records are not automatically labeled verified live.
See `GEMINI_SUPABASE_REPORT.md` for the verified schema boundaries.

Press Control+C in each server terminal and run `deactivate` to stop.

## Metrics and evidence

- `attempted`: actual product reader calls; access skips are separate.
- `fetched` / `extracted`: successful page loads / candidate records.
- `accepted`: records passing deterministic validation, including valid unavailable
  observations or configurations incompatible with the user's request.
- `rejected`: known collection/extraction/validation failures.
- `invalid_records`: validation failures, separate from infrastructure/storage.
- `incompatible` / `manual_review`: hardware contradictions / incomplete evidence.
- `blocked_pages`: observed HTTP/challenge denials; `skipped` also covers disabled
  access, robots denial, and later URLs at an already-blocked retailer.
- `saved` / `unchanged`: local observation import outcomes; duplicates do not
  create additional listing identities. Historical observations are preserved.
- `worker_failures` / `storage_failures`: infrastructure problems, not bad data.

Acceptance = accepted / attempted. Rejection = rejected / attempted. Invalid record
rate = invalid_records / extracted. Zero denominators produce null. Live incorrect
accepted data cannot be measured without human truth labels.

```bash
python -m scraper.evaluate --output .local/synthetic-quality.json
python -m scraper.evaluate --real-captures --output .local/capture-quality.json
python -m backend evaluate-search
SHOPPIE_RUNTIME_TESTS=1 python -m pytest -q
```

Synthetic evaluation: ten pages, seven accepted, three rejected; zero incorrect
accepted records out of seven checked (0%). A fault-injection test deliberately
introduces one incorrect accepted record and measures 1/7. These are controlled
fixture results, not real retailer accuracy. Explicit null truth labels catch
invented prices as incorrect data. Missing known fields are counted separately.

Two archived, partial real Target captures from October 14 have missing prices;
both are rejected. Real bad-data rate is **unmeasured**, because zero real captured
records pass validation. Archived titles are not current live offers.

## Current milestone blockers

- No Gemini key configured, so grounded discovery/AI review/explanation have only
  been verified with mocks; no chargeable Gemini call was run.
- No fresh product-page requests or two-retailer live comparison were verified.
  Retailer access restrictions and permission requirements remain in force.
- Supabase public.products was read successfully (two existing records), but its
  eight-column schema has no stock/hardware/vector/history contract. It cannot
  prove the exact current laptop offer milestone.
- The additive shoppie schema is unavailable through the Data API (HTTP 406).
  Schema changes, exposure, backend-only grants, extension location, and explicit
  development/test project identification need mentor approval. No shared writes
  or migrations were performed.

## Official references consulted

- [Gemini grounding and citation metadata](https://ai.google.dev/gemini-api/docs/generate-content/google-search)
- [Structured outputs and supported combinations](https://ai.google.dev/gemini-api/docs/structured-output)
- [Maintained Google Gen AI Python SDK](https://googleapis.github.io/python-genai/)
- [Supabase custom schemas](https://supabase.com/docs/guides/api/using-custom-schemas)
- [Supabase pgvector](https://supabase.com/docs/guides/database/extensions/pgvector)
