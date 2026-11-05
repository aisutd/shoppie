# Shoppie frontend

The React frontend lives at the repository root and runs independently from the
Python scraper. It uses Vite and Tailwind CSS 3.

## Start the development server

Install Node.js, then run these commands from the repository root:

```powershell
npm install
npm run dev
```

Open the local URL printed by Vite. To create and preview a production build:

```powershell
npm run build
npm run preview
```

## Local AI product search

Each `/api/search` request searches Best Buy and Walmart and selects up to eight
distinct candidates across both retailers. Best Buy candidates are collected
from their product pages; Walmart candidates use the title, current price,
image, and product URL shown in Walmart's search result cards. The collector
validates records and upserts them into `public.products`. The current matching
logic then ranks this request's collected candidates, so a five-minute catalog
cache cannot hide new listings. No additional database tables are required.

When discovery is blocked, fails, or returns no products, the API searches the
stored catalog instead. The response's `collection` object and the result-page
notice explicitly identify live vs. stored results and partial collection/save
failures. A failed save can still return a validated fresh result, but its save
is not reported as confirmed. Existing products are never deleted by a search.

Ollama is used as a slower fallback when no direct matches are found. For fresh
candidates, model-expanded matching remains restricted to those candidates; it
does not introduce unrelated catalog rows. Price phrases such as
`under $1,000`, `at most 500`, `over $200`, and `between $100 and $300` filter
the catalog by its stored product price.
When a query names a category present in the catalog, results are restricted
to matching categories so description keywords do not surface unrelated items.
Memory requests such as `at least 16 GB RAM` are checked against memory values
associated with `memory` or `RAM` in each product's title or description; a
matching number elsewhere in the name or a storage capacity does not satisfy it.
Queries using `cheap`, `affordable`, or similar terms return the lowest-priced
subset of the products that match the query and any explicit filters.
Keep `SUPABASE_URL` and `SUPABASE_SECRET_KEY` in `scraper/.env`; the key is
read only by the local Python API and is never sent to the browser.

The homepage's “Lowest current prices,” “Deep discounts,” and “Recently observed”
sections load catalog rows through the local `/api/deals` endpoint. The same
endpoint searches Best Buy and Walmart for laptops, monitors, phones,
headphones, gaming controllers, toys, and kitchen items. Retailer shelves show
the current search-card listings, and the deep-discounts shelf includes only
offers where a retailer explicitly provides a higher regular price. These live
homepage picks are not written to the catalog. Search results are grouped by
Best Buy and Walmart source, with up to eight products from each retailer.

The catalog stores current prices and observation times, not price history,
regular prices, or release dates. Accordingly, the first section ranks current
catalog prices, verified discounts use only retailer comparison prices, and the
last section shows recently observed products rather than claiming a verified
release date.

1. Install Ollama, then download the model with `ollama pull qwen2.5-coder:1.5b`.
2. Install the Python dependencies with `python -m pip install -r requirements.txt`.
3. Start the API from the repository root with `python local_search_api.py`.
4. In another terminal, start the frontend with `npm run dev`.

Ollama must be running on its default local address (`127.0.0.1:11434`). The
search API binds only to `127.0.0.1:8001` and the Vite development server
forwards `/api` requests to it.

## Live discovery and collection

Transport recovery: when a Best Buy product detail request fails at the network
layer, the collector searches the observed URL's model-name keywords on Best
Buy's public search endpoint. It accepts a fallback only when a card has the
same product ID/variant and a single explicit current customer price. React
streamed fragments are linked using their explicit boundary/segment IDs; no
JavaScript is executed and no page-wide first price is guessed. Walmart records
are taken from product cards in its public search results, avoiding a separate
detail-page request that may redirect to Walmart's `/blocked` route. Both
retailers' products use the same record validation, specification filtering,
and Supabase upserts. Missing or ambiguous prices are rejected; CAPTCHA and
HTTP rejections are not retried. Search cards may omit specs, so some exact
requests can still legitimately return no verified matches.

Product-type intent is now recognized independently of database contents by
`scraper/search_intent.py`. Monitor searches cannot return laptops just because
the catalog has no monitors. Title evidence takes priority over category tags;
compatibility mentions in descriptions cannot establish a product's type.
Screen size (inches) and refresh rate (Hz) are hard numeric checks, not fuzzy
keywords. Bare values mean exact matches; `at least`, `up to`, `under`, and
`over` express bounds. Missing/ambiguous evidence is excluded. Title specs take
priority over labeled description specs; generic description prose is not used
as specification evidence. These checks apply to live, catalog and AI fallback
results. The API returns parsed `collection.requirements` for inspection. This
is a bounded rules-based improvement, not unrestricted natural-language reasoning.

- `scraper/bestbuy_search.py`: constructs the encoded keyword search URL and
  extracts Best Buy product links from product cards or JSON-LD ItemList data.
- `scraper/walmart_search.py`: extracts validated Walmart product URLs and
  current listing details from rendered search-result cards.
- `scraper/live_search.py`: coordinates bounded collection, validates records
  with a tech-product model, infers categories from collected titles, and saves
  using `tech_scraper.upload_to_supabase()` without terminal prompts.
- `local_search_api.search_response()`: collects first, invalidates the catalog
  cache after confirmed saves, and runs existing matching/filters on candidates.
- `SearchSection.jsx` and `SearchResults.jsx`: show loading, collection outcome,
  errors, source links, and observation timestamps.

Keep the same local API/frontend startup commands. Restart the Python API after
updating. Confirm `curl_cffi==0.13.0` from scraper/requirements.txt is installed in
the SAME Python environment that runs local_search_api.py. Discovery deliberately
reports a missing dependency instead of silently switching to a different HTTP
client. The response contains a specific failure_code when discovery fails.
Confirm the
Supabase products table already has description/image_url, as used by the current
catalog search. No migration or new cloud account is introduced by this feature.

Explicit Apple chip/family constraints (e.g. MacBook Air M5) are enforced against
the selected listing title before fuzzy matching AND after AI fallback. M4 or
unknown-chip listings cannot satisfy M5. Memory in the title takes precedence
over generic descriptions that mention other configurations.

Discovery combines the original keyword search, two additional results pages,
and (for MacBooks without a specified screen size) 13-inch/15-inch searches.
This addresses search HTML that exposes just one listing. Up to three secondary
searches run concurrently; duplicate product IDs are removed before collection.
Alternate searches discover candidates only: original chip, RAM and budget
filters still determine which cards appear. Multiple results are not guaranteed
when the retailer exposes only one compatible product or blocks collection.

The flow is synchronous and limited to eight distinct product candidates, with
request timeouts and a scheduling budget of 55 seconds for collection. Timeouts
are not a hard wall-clock guarantee; optional Ollama processing can add up to 90 seconds.
One collector runs at a time per API process; a concurrent request receives
stored catalog results with a busy notice. The original request remains the
source for RAM/budget checks even when budget words are removed for discovery.

Best Buy and Walmart discovery are implemented. Their adapters must be adjusted
if retailer markup changes. Blocked pages and unexpected layouts are failures,
not fabricated listings; the collector does not try to bypass retailer
verification. Existing product extraction and fuzzy matching retain their
limitations; this change does not guarantee exact specification matching or
that a source price remains available. A browser-rendered search adapter,
durable jobs and additional retailers are separate extensions.

Offline verification:

```bash
python -m pytest -q scraper/tests
npm run build
```

The tests mock retailer and database requests; they never upload sample prices.

## Tailwind setup

- `tailwind.config.js` scans `index.html` and files in `src/`.
- `postcss.config.js` connects Tailwind to Vite's CSS processing.
- `src/index.css` loads Tailwind's base, component, and utility layers.
- `tailwind.config.js` defines the `animate-fade-in` and `animate-fade-up`
  utilities used by the starter page.

The current page is a minimal navy blue front page with the title “Shoppie”.
