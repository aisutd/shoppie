# Gemini, workers, and read-only Supabase implementation report

Verified October 28, 2026 in `/Users/rishibadal/Documents/shoppie`, on the existing
`Rishi-Test` branch. All previous modified/untracked files were preserved. Changes
remain unstaged/uncommitted. No branch switch, pull, merge, rebase, stage, commit,
push, pull request, shared write, or migration was performed.

## What works

- Gemini-only automatic discovery through the maintained `google-genai` SDK and
  Google Search grounding. Only grounding evidence URLs are used; generated facts
  and URLs are ignored. Candidate links are validated, bounded, deduplicated, and
  handed to the existing worker pipeline. Opaque Google citations are resolved
  conservatively, without following arbitrary destinations.
- Missing keys, cost consent, authentication errors, rate limits, temporary errors,
  timeouts, absent grounding, and unusable sources have clear failure behavior.
  One generation plus at most one temporary-HTTP retry; successful discovery cache
  lasts three minutes. The Google-internal query count is reported, not guaranteed
  capped: the prompt requests two searches, but the API controls actual searches.
- Optional AI validation flags incomplete/contradictory data for review. It cannot
  change extracted facts, fill missing values, or override hard configuration
  conflicts. AI failures do not crash the pipeline. Independent unexpected worker
  failures are recorded and later candidates continue.
- The existing Pydantic → schema-version 1 envelope → normalization → local
  history → reusable SBERT embeddings → hybrid matching/search → deal comparison
  pipeline remains intact. Chromium visible/headless and local JavaScript
  rendering pass. Changed-product browser navigations are aborted before loading.
- Recommendations exclude unavailable, stale, unverified, incompatible, and
  review-required observations. Unknown shipping is never zero. Known equivalent
  totals rank in price order; lower-known-total and historical claims are generated
  from deterministic evidence. Gemini can select existing evidence sentence IDs,
  with a deterministic fallback. It never writes new unchecked price claims.
- Streamlit retains its existing layout, Demo mode, live monitoring, and shared
  business logic. It adds consent, AI review, Gemini discovery, safe connection
  status, read-only Supabase source selection, source timestamps, shipping, URLs,
  archived-capture evaluation, and accurate failure/review counters.
- FastAPI endpoints remain compatible. `/storage/status` shows booleans only.
  `SHOPPIE_API_SOURCE=demo|live|supabase` selects demo, local live, or shared read-only
  retrieval. There is no unrestricted scraping or shared-upload endpoint.

## Retired providers

Brave Search, Best Buy Products API, and Best Buy sitemap discovery are absent
from the CLI and dashboard. Their old implementations are preserved only in
`backend/legacy_discovery.py` for earlier mocked regression checks. Their key
variables were removed from `.env.example`. Ordinary Best Buy retailer parsing
and all four supported retailer identities remain.

## Actual external verification

**Gemini:** no key is configured. No chargeable Gemini generation/search/review/
explanation call was made. Gemini behavior is verified with mocks only.

**Supabase:** the existing backend URL and secret key are read from the ignored
`scraper/.env`, with environment/root `.env` overrides. No values are displayed.
Read-only Data API inspection and retrieval succeeded:

- `public.products`: eight columns — `id`, `title`, `price`, `currency`,
  `product_url`, `source`, `category`, `scraped_at`.
- Two existing records retrieved and serialized through the v1 listing contract.
- Two 384-dimensional embeddings generated and stored in the local cache only.
- Zero eligible offers for the requested Apple M5 16GB/512GB configuration.
- `shoppie` schema: unavailable through the Data API, HTTP 406. This proves it is
  not exposed/available to this request; it does not prove the tables do not exist.
- PostgreSQL DSN is not configured. SQL constraints, extension location/version,
  vector RPC execution, and PostgreSQL hosted history are not verified.
- Project purpose is not independently verified as development/test; no writes
  are enabled. Existing records lack source-validation/stock evidence and remain
  unverified. Brand/description/model/stock/history are not guessed.

`backend/supabase.py` is a read-only Data API store. Public-schema mapping is
separate from the proposed listing/history schema. It preserves retailer identity,
uses title specs as explicit evidence, rejects contradictory attributes, deduplicates
exact URL identities, isolates invalid rows, and mirrors only selected product
fields locally. Newly generated embeddings always go to the local cache. It can
read approved `shoppie` listing/current-offer/history/vector metadata and call the
fixed read-only cosine RPC once that schema is approved/exposed. Matching and
hardware rejection still run in Python. Shared vector retrieval/RPC behavior is
mock-tested, not claimed hosted success. The prototype reads a bounded first 1,000
records; a full large-catalog pagination strategy remains future work.

`backend/postgres.py` preserves the parameterized psycopg adapter. Connections are
read-only by default. Writes require explicit `allow_writes=True`,
`SHOPPIE_DATABASE_WRITES=1`, `SHOPPIE_DATABASE_ENV=development|test`, and
`SHOPPIE_SCHEMA_APPROVED=1`, followed by a schema-presence check. These are human
attestations, not proof of a project's purpose; do not enable before mentor review.
No write entry point is connected to the dashboard/API/CLI. Existing uploader and
MySQL/SQLite lesson functionality remain separate and unchanged.

### SQL awaiting mentor approval

1. Run/review `sql/inspect_backend.sql` in the intended development/test project;
   it uses a read-only transaction and reports columns, constraints, policies,
   and pgvector extension location. Do not send credentials or results publicly.
2. Review the existing `sql/shoppie_backend.sql`: separate retailer/listing/history
   tables, current-offer view, vector(384), model/revision/template/hash metadata,
   uniqueness/FKs, invoker cosine function, and no anonymous access. This file was
   not executed or modified in this milestone.
3. Review additive `sql/shoppie_data_api.sql` for backend-only SELECT and read-only
   RPC grants. Supabase's owner separately chooses whether to expose `shoppie`.
   No anonymous/browser grants or shared insert/update/delete grants are added.
4. Validate exact project identity, TLS/pooler/role settings, vector extension
   schema, and existing table compatibility before approving any migration.

## Measured quality and search results

| Dataset | Attempted | Extracted | Accepted | Rejected | Incorrect accepted / checked accepted |
| --- | ---: | ---: | ---: | ---: | --- |
| Labeled synthetic fixtures | 10 | 8 | 7 | 3 | 0/7 = 0% |
| Archived partial Target captures, October 14 | 2 | 2 | 0 | 2 | 0/0 = unmeasured |

Synthetic acceptance is 70%, rejection 30%, invalid record rate 1/8 = 12.5%.
Present labeled field/price accuracy is 100% for this small controlled set; missing
RAM is counted separately. One blocked fixture and one missing-price extracted
record are counted. Fault-injection tests measure an incorrect accepted
price/model/variant/stock record at 1/7; another test catches invented values where
human labels explicitly state null. This verifies the metric, not real reliability.
Archived captures have no usable prices and cannot establish a real bad-data rate.

`bad_data_rate = incorrect_accepted_records / manually_checked_accepted_records`.
No labels/zero checked accepted records → null. Missing expected fields are
separate from wrong present values. Explicitly labeled missing source values
become incorrect if the extractor invents a value. Duplicate and infrastructure
counts are separate from correctness. Live acceptance is validation success,
not human-verified price accuracy.

Three synthetic labeled SBERT searches have macro Precision@K **1.0**. Real cached
MiniLM inference produces finite, normalized 384-dimensional vectors. This small
synthetic result is not a real-world search-quality benchmark or calibrated
identity confidence. No uncertain listings are merged.

## Tests and environment

Initial baseline: **249 passed** with `SHOPPIE_RUNTIME_TESTS=1`. The initial
restricted browser-launch attempt failed two tests due to macOS process-launch
permissions; rerunning with permission to launch Chromium passed all 249.

Final complete suite: **304 passed** (55 additional cases), no remaining failures.
All original tests remain, with old-provider tests pointed at the retired module
and SDK-era mocks updated. Six runtime tests use local Chromium, cached SBERT,
and Streamlit's tester; external services stay mocked.

```bash
SHOPPIE_RUNTIME_TESTS=1 .venv-ai/bin/python -m pytest -q
.venv-ai/bin/python -m pytest -q tests/test_gemini.py tests/test_supabase_backend.py tests/test_worker_quality.py
.venv-ai/bin/python -m compileall -q backend scraper dashboard.py tests
.venv-ai/bin/python -m pip check
git diff --check
```

The default suite also passed with runtime checks skipped: 298 passed, 6 skipped.
Syntax checks passed, dependencies are consistent, and whitespace checks passed.
Local HTTP smoke checks passed for dashboard `/`, API `/health`, `/storage/status`,
and `/scraper/status`. The actual browser shows missing Gemini configuration and
no fabricated live offers. The dashboard and API were started on localhost ports
8501 and 8000 for review. Default startup makes no external-service call.

The maintained SDK installation added these packages to `.venv-ai`; existing
packages were not upgraded:

- google-genai **2.33.0**, google-auth **2.62.0**
- cryptography **50.0.2**, cffi **2.1.1**, pycparser **3.12**
- distro **1.9.0**, sniffio **1.3.1**, tenacity **9.1.4**
- pyasn1 **0.6.5**, pyasn1-modules **0.4.2**

Python 3.11.15, python-dotenv 1.2.4, Playwright 1.64.1 / Chromium 156.0.8078.4,
Sentence Transformers 5.7.0, torch 2.15.0, NumPy 2.4.6, and the pinned MiniLM model
were reused. `requirements-ai.lock.txt` records the complete environment.

## Try it

Full commands are in [LIVE_DISCOVERY.md](LIVE_DISCOVERY.md), including environment,
secure configuration, consent, visible browser, two server terminals, source
restrictions, stopping, and default Demo behavior. Quick safe checks:

```bash
cd /Users/rishibadal/Documents/shoppie
source .venv-ai/bin/activate
python -m backend config-check
python -m backend browser-check --headed
python -m backend supabase-check
python -m backend supabase-search --query 'Apple MacBook Air M5 16GB RAM 512GB SSD'
python -m scraper.evaluate --output .local/synthetic-quality.json
python -m scraper.evaluate --real-captures --output .local/capture-quality.json
```

After configuring Gemini and obtaining permitted retailer page access:

```bash
python -m backend discover --allow-gemini --query 'Apple MacBook Air M5 16GB RAM 512GB SSD'
python -m backend collect-live --allow-gemini --browser --headed --ai-review --explain \
  --query 'Apple MacBook Air M5 16GB RAM 512GB SSD'
```

`supabase-vector` is implemented but deliberately fails on legacy public.products;
it needs the approved/exposed shoppie pgvector RPC. Do not apply SQL just to make
that command pass without mentor review.

## Mentor demonstration and remaining decisions

For the working offline demonstration, open Demo, use the sample exact query,
and click Find offers. It compares the two clearly synthetic Best Buy/Target
16GB/512GB offers at USD 999/1049 with known zero shipping. Conflicting RAM,
storage, and CPU variants are excluded; missing RAM needs review. Use Scraper
monitoring to show separate synthetic and archived-capture reports.

**The real two-retailer milestone has not passed.** Gemini credentials and an
explicit billed-call opt-in are needed first; retailer automated access must be
permitted next. No fresh real offers were collected. Do not bypass restrictions.
The team must also approve the additive shared listing/history/vector schema and
confirm the intended test project before shared ingestion. Add more independently
labeled permitted real captures before making accuracy claims. Larger-catalog
pagination/server-side candidate recall and real Google Search attribution/model
behavior still need evaluation. No fake live offers were created to fill these gaps.

## Files changed in this request

The inventory below is relative to a filesystem snapshot at the start of this
request; earlier uncommitted changes remain intact. Several existing files were
already Git-untracked, so Git's `??` does not mean they were newly created now.

### Existing files modified

| Path | Change/purpose |
| --- | --- |
| `.env.example` | Removes retired keys; documents Gemini consent, existing Supabase settings, and disabled shared writes. |
| `LIVE_DISCOVERY.md` | Replaces obsolete provider instructions with current secure setup, commands, metrics, and blockers. |
| `LOCAL_IMPLEMENTATION_REPORT.md` | Marks the earlier report as historical and links this current report. |
| `README.md` | Links the current Gemini/Supabase workflow and honest live limitations. |
| `SETUP_MACOS.md` | Updates discovery, configuration loading, dependency, and shared-read guidance. |
| `backend/__main__.py` | Adds Gemini consent/review/explanation and config/Supabase read/search/vector commands; removes old provider choices. |
| `backend/access.py` | Reads permitted retailer settings from existing local configuration as well as environment. |
| `backend/api.py` | Adds safe configuration status and source selection; prevents Demo ingestion in shared/live mode. |
| `backend/coordinator.py` | Connects optional AI review, progress, duplicate/blocked/worker counters, and per-candidate failure isolation. |
| `backend/discovery.py` | Replaces active discovery with bounded, cached Gemini grounding citation extraction and safe redirect confirmation. |
| `backend/explanations.py` | Uses the maintained SDK to select deterministic verified evidence, with price/history comparison and safe fallback. |
| `backend/models.py` | Exposes blocked, AI-review, rejection-rate, and worker-failure metrics. |
| `backend/postgres.py` | Makes connections read-only by default, gates writes, adds inspection, preserves raw provenance, and redacts connection errors. |
| `backend/provenance.py` | Carries optional AI-review status without changing synthetic/live source evidence. |
| `backend/search.py` | Keeps AI-flagged candidates in manual review; deterministic variant rejection remains final. |
| `backend/service.py` | Shares read-only Supabase refresh/local indexing with dashboard/API and blocks shared collection writes. |
| `dashboard.py` | Retains the design; adds Gemini consent/review, shared read mode, status/evidence, attribution, and expanded quality reports. |
| `requirements-ai.lock.txt` | Records the installed SDK and its transitive dependencies. |
| `requirements-ai.txt` | Adds the maintained google-genai SDK requirement. |
| `scraper/evaluate.py` | Adds explicit bad-data denominators, invented-value checks, error categories, and separate archived-capture evaluation. |
| `scraper/scraper.py` | Aborts changed-product browser navigation and checks identity/access after the final render wait. |
| `tests/test_backend.py` | Updates SDK mocks/missing-key expectations and keeps retired-provider URL regression coverage. |
| `tests/test_live_runtime.py` | Adds an isolated shared-products dashboard test while preserving existing runtime tests. |
| `tests/test_live_workflow.py` | Points old-provider regression checks to the explicitly retired module; existing workflow assertions remain. |

### New files

| Path | Change/purpose |
| --- | --- |
| `GEMINI_SUPABASE_REPORT.md` | Current implementation, actual hosted-read evidence, test results, decisions, commands, and exact file inventory. |
| `backend/ai_validation.py` | Structured optional AI review that can only withhold offers for review. |
| `backend/gemini.py` | Shared bounded SDK request, timeout/retry, consent, and structured-response helpers. |
| `backend/legacy_discovery.py` | Archives old providers for regression tests, outside all active app/CLI paths. |
| `backend/settings.py` | Reads ignored local settings safely, with redacted status booleans and environment precedence. |
| `backend/supabase.py` | Read-only existing-products/proposed-schema adapter, contract mapping, local vector cache, history and fixed cosine RPC support. |
| `sql/inspect_backend.sql` | Read-only mentor inspection queries for columns, constraints, policies, and pgvector. |
| `sql/shoppie_data_api.sql` | Unexecuted additive backend-only read/RPC grants for an approved shoppie schema. |
| `tests/fixtures/real_captures.json` | Labels existing dated real Target captures separately from synthetic fixtures. |
| `tests/test_gemini.py` | Mocked discovery/citations/errors/consent, optional review, explanations, and worker integration checks. |
| `tests/test_supabase_backend.py` | Isolated configuration, retrieval, schema boundaries, vector cache/RPC, duplicate, error, write-gate, and API checks. |
| `tests/test_worker_quality.py` | Checks bad-data denominators, invented values, archived/missing fields, duplicate reporting, and worker isolation. |

### Full Git working-tree status

```text
 M .gitignore
 M README.md
 M data_dictionary.md
 M db/README.md
 M db/embeddings.py
 M db/normalize.py
 M db/queries.py
 M normalizer/matching.py
 M requirements.txt
 M scraper/envelope.py
 M scraper/main.py
 M scraper/requirements.txt
 M scraper/scraper.py
 M scraper/validator.py
?? .env.example
?? GEMINI_SUPABASE_REPORT.md
?? LIVE_DISCOVERY.md
?? LOCAL_IMPLEMENTATION_REPORT.md
?? SETUP_MACOS.md
?? backend/
?? dashboard.py
?? db/embeddings_schema.sql
?? requirements-ai.lock.txt
?? requirements-ai.txt
?? scraper/browser_check.py
?? scraper/evaluate.py
?? sql/inspect_backend.sql
?? sql/shoppie_backend.sql
?? sql/shoppie_data_api.sql
?? tests/fixtures/
?? tests/test_backend.py
?? tests/test_gemini.py
?? tests/test_live_runtime.py
?? tests/test_live_workflow.py
?? tests/test_runtime.py
?? tests/test_supabase_backend.py
?? tests/test_worker_quality.py
```

Branch: `Rishi-Test`. Staged files: none.
