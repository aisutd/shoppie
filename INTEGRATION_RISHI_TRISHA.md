# Rishi–Trisha local integration

Branch: integration/rishi-trisha. Backend reference: abb53fa6a.
All changes are local, unstaged, and uncommitted. No shared database operations,
Gemini requests, or retailer requests were performed during integration.

## Combined behavior

The restored FastAPI/Streamlit/backend modules remain the shared business layer.
Scraper records pass through Pydantic, the schema_version 1 envelope, normalization,
local listing/history storage, pinned all-MiniLM-L6-v2 embeddings (384 normalized
values), exact variant filtering, semantic/keyword search, and deal comparison.
Supabase remains a separate read-only app source; its existing public.products
contract is not replaced by the richer proposed shoppie schema.

Overlapping scraper files use the backend contract from abb53fa6a, with compatible
Trisha improvements integrated:

- BlockError, synchronized request pacing, and remembering blocked retailers.
  Denials stop further requests to that retailer in this process. Restart the
  process for a later legitimate run; do not retry to circumvent a restriction.
- Selected-TCIN Target layout extraction for title and explicit price/currency/
  availability. Other variants cannot fill missing fields. Fulfillment objects
  do not imply stock; absent currency is never defaulted to USD. Conflicting
  selected fields fail validation.
- Availability spelling aliases and rejection of future observation timestamps.
- Trisha's generate_product_embedding entry point now delegates to db.embeddings,
  retaining one cached model, one identity template, normalized vectors, and no
  import-time model download.
- Optional Ollama planning delegates to ShoppingService.collect/deals. It can
  select only user-supplied, allowlisted product URLs, and cannot invent links,
  decide compatibility, write shared records, or determine recommendation prices.
  Missing package/server or invalid responses return an unavailable result.

Removed from active fetching: curl_cffi/TLS browser impersonation and fabricated
browser identity headers. Requests and installed Playwright Chromium handle real
pages without challenge solving. Visible mode remains --browser --headed.
The old scraper/test_scraper.py is now an explicit manual command, so test
collection never makes its former import-time retailer request.

The uploader again maps to the documented public.products columns (source,
product_url, title, price, currency, category, scraped_at). It does not fabricate
seller domains or assume retailer/product_id/availability columns exist.
The separate legacy --save command remains explicitly opt-in, outside the main
read-only dashboard/API path; it was never executed against a shared database.

The MySQL db/schema.sql scaffold was restored; the branch's PostgreSQL lesson SQL
is preserved byte-for-byte in db/legacy_lesson_schema.sql. No SQL was executed.

Trisha's scraped_laptops.txt and scraped_report.md were left unchanged. They
contain Python.org page text/report content, not validated laptop offers. They
are not loaded as product evidence or relabeled live.

Pre-edit copies of overlapping source files are in the ignored
.local/integration-backup directory. Existing restored backend files and tests
were preserved. Original tests were not removed or weakened. Offline test fixtures
reset the new process-level pacing state and disable delays for mocked requests.

## Tests actually run

Initial state: 13 collection errors (curl_cffi missing and incompatible imports).
After integration:

    SHOPPIE_RUNTIME_TESTS=1 .venv-ai/bin/python -m pytest -q
    315 passed

This includes 304 existing tests and 11 added combined-pipeline cases. The full
runtime suite uses cached SBERT, controlled Chromium pages in visible/headless
modes, and Streamlit AppTest. Gemini, Ollama, and hosted database behavior are
mocked. New checks cover selected Target prices/variants, missing currency/stock,
conflicts, denial memory, availability aliases, the shared embedding entry point,
and optional Ollama failure/URL restrictions/delegation.

Also checked: compileall, pip check, git diff --check. No new mandatory dependency
was installed. Real Ollama inference, fresh retailer extraction, and hosted
Supabase integration were not reverified in this integration task. Gemini remains
disabled by default. Existing schema-approval and retailer-permission requirements
still apply; there is no verified live two-retailer milestone.

## Run on this Mac

    cd /Users/rishibadal/Documents/shoppie
    source .venv-ai/bin/activate
    python -m pip install -r requirements-ai.lock.txt
    SHOPPIE_RUNTIME_TESTS=1 python -m pytest -q
    python -m backend browser-check --headed
    python -m backend search --query 'Apple MacBook Air M5 16GB RAM 512GB SSD'

Terminal 1 (offline API by default):

    python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000

Terminal 2 (activate .venv-ai there too):

    python -m streamlit run dashboard.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false

Open http://127.0.0.1:8501 and use Demo/Find offers. Demo prices are synthetic.
The dashboard does not require the API server. Control+C stops each server.

For optional local Ollama only, install requirements-ollama.txt separately and run
an existing locally installed qwen2.5 model/server. Nothing auto-installs a model.
Call scraper.ai_scraper_agent.run_ecommerce_agent(query, urls=[...]) with real,
permitted product URLs. The app works without this package/server. There is no
automatic Ollama discovery: grounded Gemini discovery remains separately opt-in.
Do not enable SHOPPIE_ALLOW_GEMINI or the consent checkbox if avoiding API charges.

Read-only Supabase configuration/inspection commands remain:

    python -m backend config-check
    python -m backend supabase-check

The latter contacts the configured shared service only when explicitly run.
Never apply proposed SQL or use the legacy uploader without team approval.

## Files changed in this integration

- .gitignore: protects restored environment/cache/backup directories.
- README.md: links this current integration guide without replacing prior content.
- db/schema.sql: restores MySQL scaffold; existing lesson schema remains separate.
- requirements.txt: restores MySQL dependency and full-environment guidance.
- scraper/scraper.py: combines safe full-field extraction with pacing/blocking and
  selected-TCIN parsing; restores Chromium rendering and exact spec checks.
- scraper/validator.py: combines full backend fields with availability aliases and
  future-time validation; preserves nullable unavailable observations.
- scraper/database.py: restores the actual public.products upload mapping.
- scraper/main.py: restores JSON-envelope output and visible Chromium flags.
- scraper/embeddings.py: delegates Trisha's entry point to the shared model.
- scraper/ai_scraper_agent.py: optional, bounded Ollama selection using shared workers.
- scraper/test_scraper.py: import-safe explicit manual command.
- scraper/requirements.txt: corrects browser installation instructions.
- scraper/tests/conftest.py: isolates mocked request pacing/block state.

New files:
- requirements-ollama.txt: optional dependency set, separate from core requirements.
- tests/conftest.py: isolates pacing/block state in backend tests.
- tests/test_rishi_trisha_integration.py: eleven integration cases.
- INTEGRATION_RISHI_TRISHA.md: this verification and setup record.

Previously restored backend/dashboard/database/normalizer/tests remain untracked
as they were at the beginning of this request. No staging or Git-history action
was performed.
