# Shoppie local backend and dashboard

## Environment used

Verified October 28, 2026 on macOS 27.0.1 arm64 with Python **3.11.15**. The existing
Python 3.14.7 `.venv` and `scraper/venv` were preserved. The new `.venv-ai` uses
Python 3.11 to provide an independent, tested inference environment. Python 3.14
was not proven incompatible; using 3.11 avoided changing the working scraper env.
No system-wide packages were installed.

Direct versions installed: Sentence Transformers 5.7.0, PyTorch 2.15.0, NumPy
2.4.6, Pydantic 2.14.1, Playwright 1.64.1, FastAPI 0.162.0, Uvicorn 0.54.0,
Streamlit 1.66.1, psycopg/psycopg-binary 3.3.6, HTTPX 0.28.1, Requests 2.34.2,
BeautifulSoup 4.15.0, python-dotenv 1.2.4, pytest 8.4.2, MySQL Connector 9.7.0.
`requirements-ai.lock.txt` records the full tested environment, including transitive
packages. `requirements-ai.txt` contains readable dependency bounds. Use the lock
for this tested Mac environment; other Python/OS combinations need verification.
The older scraper requirement pins remain available for its existing environment.

Chromium 156.0.8078.4 / Playwright build 1248 is installed in `.local/browsers`.
The model is `sentence-transformers/all-MiniLM-L6-v2`, pinned to revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, with **384-dimensional** L2-normalized
vectors. Inference uses CPU on this Mac; no CUDA or MPS setup is needed.
Model and browser caches are ignored by Git. The model is loaded once per process,
and application inference uses cached files only. Initial setup needs Internet.

## Terminal 1: setup, tests, indexing, and API

```bash
cd /Users/rishibadal/Documents/shoppie
source .venv-ai/bin/activate
python -m pip install -r requirements-ai.lock.txt
PLAYWRIGHT_BROWSERS_PATH="$PWD/.local/browsers" python -m playwright install chromium
python -m backend init-model
python -m pytest -q
SHOPPIE_RUNTIME_TESTS=1 python -m pytest -q tests/test_runtime.py
python -m backend index
python -m backend search --query 'Apple MacBook Air M5 16GB RAM 512GB SSD'
python -m scraper.evaluate --output .local/scraper-quality.json
python -m backend evaluate-search
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

If `.venv-ai` needs creating on a fresh checkout, before activation run:

```bash
/opt/homebrew/bin/python3.11 -m venv .venv-ai
```

Use your installed Python 3.11 path if Homebrew is elsewhere. In VS Code choose
**Python: Select Interpreter → .venv-ai/bin/python**. Do not replace the older env.
The default tests use mocked vectors and an isolated local store. The opt-in runtime
tests use the real cached model, installed Chromium, controlled local HTML, and
Streamlit's application tester. They make no retailer or database network calls.

## Terminal 2: website

```bash
cd /Users/rishibadal/Documents/shoppie
source .venv-ai/bin/activate
python -m streamlit run dashboard.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

The dashboard calls the same Python business functions as the API; it does not
require the API process to be running. Both services bind to localhost.

## Terminal 3: open and inspect

```bash
open http://127.0.0.1:8501
open http://127.0.0.1:8000/docs
curl --get 'http://127.0.0.1:8000/deals' --data-urlencode 'q=Apple MacBook Air M5 16GB RAM 512GB SSD'
curl 'http://127.0.0.1:8000/health'
```

Press **Control+C** in each server terminal to stop that process, then run
`deactivate` in each activated terminal. If a port is occupied, stop its previous
server or choose another localhost port. No public deployment is configured.

## Mentor demonstration

1. Open the dashboard in **Demo · synthetic fixtures** mode.
2. Leave the sample query: `Apple MacBook Air M5 16GB RAM 512GB SSD`.
3. Click **Find offers**. The coordinator reads explicit saved fixtures, runs the
   scraper/validator/envelope/normalizer, saves observations locally, and indexes
   only changed embedding text.
4. Show the two exact offers: fictional Best Buy USD 999 and Target USD 1049,
   both with explicit zero shipping, displayed in total-price order. The cheaper
   8 GB, 256 GB, and M4 variants are excluded. The missing-RAM candidate needs review.
5. Expand **All relevant candidates and review reasons**. No products are merged.
6. Set maximum price to USD 1000 to filter Target's USD 1049 offer.
7. In **Scraper monitoring**, run the labeled reliability evaluation. Show blocked,
   missing, and conflicting-price failures and the separate accuracy denominators.
8. In **Search & embeddings**, show the model, revision, dimensions, source, and
   product count. Repeat the search/index command to demonstrate vector reuse.

These offers and prices are synthetic. Demo freshness uses the fixture timestamp
October 28, 2026 at 12:00 UTC; live mode uses actual current time. A successful demo
is not evidence that the live two-retailer milestone has passed.

## Live Gemini discovery and Supabase reads

See [LIVE_DISCOVERY.md](LIVE_DISCOVERY.md) for the current Gemini-only discovery,
per-action cost consent, read-only shared-data workflow, configuration loading,
and visible Chromium commands. Google GenAI 2.33.0 is installed in `.venv-ai`.
The old Brave, Best Buy API, and sitemap providers are retired from the app.

See [GEMINI_SUPABASE_REPORT.md](GEMINI_SUPABASE_REPORT.md) for the current tested
results and file inventory. Gemini calls were mocked because no key is configured.
The existing Supabase public.products table was safely read, with no shared writes.

## Database boundaries and mentor approval

- Existing MySQL: `db/schema.sql`, `db/ingest.py`, `db/queries.py` remain the local
  listing/history implementation. Optional `raw.description` stays in raw JSON;
  `get_current_offers` retrieves it for embeddings. `db/embeddings_schema.sql` adds
  an optional local embedding table, without changing existing tables automatically.
- Demo store: `.local/demo.sqlite3` is an isolated application fixture store,
  separate from the original `db/start_here.py` SQLite lesson and MySQL. Local/live
  records use a different file. No Supabase credentials are required.
- Existing Supabase uploader: `scraper/database.py` and `sql/schema.sql` still use
  `public.products` (latest row only). The new app never calls this uploader.
- Proposed Supabase/PostgreSQL backend: `sql/shoppie_backend.sql` creates a separate
  `shoppie` namespace with retailers, listings, observations, current-offer view,
  vector(384) embeddings, version metadata, and an invoker cosine query. Its vector
  query excludes stale input hashes; exact hardware checks still run in Python.
  There is no HNSW index until catalog performance is measured.
- `backend/postgres.py` implements the same listing/history/vector methods as the
  local store through parameterized psycopg queries. It is only instantiated
  explicitly with a backend DSN; the dashboard and API default to local demo data.

The proposed shoppie PostgreSQL SQL/adapter have not been tested against a hosted
shoppie schema. The separate read-only Data API adapter successfully retrieved two
existing public.products records; its missing attributes/stock remain unknown. **Do not apply them to a shared database yet.** Mentor review
must confirm extension location/version, schema naming, backend role grants/RLS,
connection pooling/TLS, migration compatibility, and table relationships in a test
project. No production migration or upload was made. Shared reads use backend-only
credentials from the existing ignored scraper/.env or root .env.
No browser/anonymous grants are provided. A dedicated backend role and reviewed
policies are required; do not put a privileged key or DSN in the frontend.

## Search and recommendation rules

Explicit model/GTIN/SKU matches take priority over semantics. Known RAM, storage,
CPU, color, and screen contradictions are excluded. Unknown requested fields or
missing manufacturer models require review. Multiple conflicting models/variants
that fit a broad query are not compared as equivalent deals; refine the request.
Brand/category/price/availability filters apply before ranking. Then exact status,
identifiers, and an equal-weight cosine/keyword score determine relevance. This
small heuristic is explainable and tested on synthetic labels, not a calibrated
confidence probability or a general search-quality benchmark.

Price comparison is a separate step: only fresh (48 hours), explicitly in-stock,
exact-compatible USD offers qualify. Known shipping contributes to total price;
unknown shipping does not become zero and cannot establish the lowest total.
Historical observations are shown only when stored. No discount, market average,
or predicted savings is fabricated. URL deduplication preserves unknown query
parameters; unverified tracking aliases are not collapsed.

## Official references

- [MiniLM model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
- [Sentence Transformers encoding API](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html)
- [Playwright browser installation](https://playwright.dev/python/docs/browsers)
- [Supabase vector columns](https://supabase.com/docs/guides/ai/vector-columns)
- [Gemini REST API](https://ai.google.dev/api/generate-content)

If you are using the review servers started by this chat and have no attached
terminal to interrupt, this stops the listeners on the two local development ports:

```bash
kill -INT $(lsof -tiTCP:8000 -sTCP:LISTEN) $(lsof -tiTCP:8501 -sTCP:LISTEN)
```

Use that command only for the Shoppie development servers on these ports.
