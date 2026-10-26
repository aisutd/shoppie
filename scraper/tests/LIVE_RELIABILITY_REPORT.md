# Live scraper production fixes — 2026-10-26

Branch: `Raiyan-Branch`. No database reads/writes, commits or pushes.
Required validation remains strict. No CAPTCHA solving, stealth settings or
retailer protection bypasses were added.

## What was broken

- Amazon's explicit `$` main-product price did not establish currency, so browser
  readiness could never complete despite a real price being present.
- Some primary price accessibility spans are blank; the visible price is split
  into symbol, whole amount and cents. A second primary module can also contain
  the complete accessibility amount.
- New and Used offers reuse the same element IDs. Comparing every module
  incorrectly treats inactive/hidden alternative offers as main-price conflicts.
- The HP page has a hidden input and a visible span both named `productTitle`.
  Reading both made the visible title appear ambiguous. Its URL slug mentions
  Intel, but the actual selected product is AMD Ryzen; extraction uses the page,
  not the slug.
- Default CLI operation did not automatically recover from incomplete HTTP
  pages. Every rendered URL launched a separate Chrome process.
- Raw query equality rejected harmless tracking changes. Walmart `/blocked`
  and Amazon `/checkpoint/continue` are verification gates, not product URLs.

## Production changes

| File | Change and reason |
| --- | --- |
| `scraper/main.py` | Add bounded automatic HTTP-to-browser collection, per-attempt events, `--http-only`, a lazy batch browser session and correct final-attempt counters. Preserve `--keep-html` for fetched pages even when validation rejects them. |
| `scraper/scraper.py` | Reuse Chrome with isolated pages, close resources, retry one observed protocol/reset navigation failure, preserve identity during readiness, allow known tracking canonicalization, recognize terminal checkpoints, scope Amazon content and visible titles, and reject explicit mismatched JSON-LD identities/offer conditions. |
| `scraper/product_fields.py` | New pure helpers for one selected primary price, explicit dollar evidence, exact amount agreement, active/hidden offer checks, availability and source-bound optional specifications. No whole-page price or title-based specification guessing. |
| `scraper/validator.py` | Add nullable brand, model, CPU, RAM, storage, screen size, color and condition. Required price, USD, laptop-title and product-identity rules remain unchanged. |
| `scraper/diagnostics.py` | Share the recovery policy between normal CLI behavior and benchmark probes. Wrong identities, challenges and invalid currencies are terminal. |

Matching JSON-LD Product/Offer remains preferred. Missing Amazon currency/price
can be completed only with agreeing selected-product dollar evidence. Ambiguous
offers, conflicting primary prices, installment text and non-USD prices remain
rejections. Structured specifications retain source units; unknown/conflicting
optional values remain null. No unsupported embedded retailer data paths were
invented. New fields are returned in product JSON; database mapping/schema was
not changed.

Only recognized tracking parameters are ignored during redirects. Unknown,
seller, condition and other selection parameters remain protected. Target's
`preselect` may move into a direct child path only when `identify_product()`
resolves both URLs to that same selected TCIN.

## Supporting files

| File | Change |
| --- | --- |
| `scraper/tests/run_reliability_benchmark.py` | Probe HTTP with `--http-only`; obey production fallback eligibility; preserve stage/navigation events and archive page evidence. |
| `scraper/tests/test_live_reliability.py` | 45 focused cases for captured Amazon DOM, dollar evidence, selected New/Used offers, hidden content, title collisions, identity, safe fallback, checkpoints, bounded retry, browser reuse and HTML archival. |
| `scraper/tests/test_reliability_benchmark.py` | Add terminal-fallback and navigation-event regressions; preserve existing attempt/timeout evidence tests. |
| `scraper/tests/test_commands.py` | Use `--http-only` in tests specifically measuring HTTP rejection/continuation behavior. Default automatic collection has separate tests. |
| `scraper/tests/test_pipeline.py` | Keep the HTTP-only rejected-record/no-write test isolated from rendering. |
| `scraper/tests/test_diagnostics.py` | Isolate HTTP stage classification using `--http-only`. |
| `scraper/tests/test_parser.py` | Replace the generic Walmart blocked-route parameter with an explicit challenge/no-fallback regression in the new suite. Other wrong-product/retailer redirect tests remain. |
| `scraper/tests/fixtures/amazon_B0GR6935ZS_2026-10-26_excerpt.html` and `.json` | Public captured main-product DOM excerpt and dated expected price/currency. Scripts, styles and telemetry attributes removed. |
| `scraper/tests/fixtures/amazon_B0GR6KJ72L_2026-10-26_excerpt.html` and `.json` | Public captured Neo price/specification excerpt and dated metadata. These are offline evidence, not current price guarantees. |
| `scraper/tests/RELIABILITY.md` | Document current CLI/fallback, grouping, evidence and benchmark behavior. |
| `scraper/tests/reliability_results.json` and `reliability_summary.json` | Generated final live evidence. Reviewed `reliability_cases.json` was not changed. |

Unrelated pre-existing local edits were preserved.

## Before versus after

Both benchmark runs used the same 12 distinct URLs from 13 input lines.
Counts below refer to executed attempts unless marked as URL-level totals.

| Metric | Before | After |
| --- | ---: | ---: |
| URLs tested | 12 | 12 |
| Accepted URLs | 0 | 6 |
| Rejected URLs | 12 | 6 |
| Validated HTTP successes | 0 | 1 |
| HTTP fetch/extraction completions | 8 | 8 |
| Browser fallback attempts | 12 | 9 |
| Browser fallback recoveries | 0 | 5 |
| Extraction failures | 0 | 0 |
| Validation failures (HTTP incomplete candidates) | 8 | 7 |
| Redirect identity rejections | 7 | 0 |
| Readiness timeouts | 5 | 0 |
| Transport failures | 4 | 4 |
| Explicit checkpoint/challenge rejections | 0 | 4 |

The lower redirect count partly reflects correct checkpoint classification; it
does not mean retailer blocking was solved. HTTP fetch/extraction completion is
not proof of a valid record. Fallback now skips terminal HTTP failures rather
than unconditionally rendering every rejected URL. No ground-truth accuracy was
calculated: source cases are not marked reviewed.

| Retailer | URLs | Accepted before | Accepted after | Remaining failures |
| --- | ---: | ---: | ---: | --- |
| Amazon | 8 | 0 | 6 | Two checkpoint pages in the final run |
| Best Buy | 2 | 0 | 0 | HTTP request timeouts and Chrome HTTP/2 protocol errors despite the controlled retry |
| Walmart | 2 | 0 | 0 | Verification redirects to `/blocked`; no bypass attempted |

There are still 9 identity groups and 3 additional same-product URL observations.
Six accepted URL observations represent five unique product IDs. Grouping never
merges seller/condition/offer data automatically.

## Accepted-product checks

Every accepted result was checked against its exact archived HTML for visible
title, selected ASIN, canonical identity, primary price and explicit dollar
currency. Browser records include a confirmed final URL and preserved selection
parameters. The HTTP success used a direct ASIN URL with no variant query; its
archived ASIN and canonical agree, and HTTP redirects are guarded by production
identity/selection checks. Its actual final HTTP URL was not separately recorded.

| Product ID | Product | Verified USD price | Accepted URL observations |
| --- | --- | ---: | ---: |
| B0GR1493ZV | MacBook Air M5, Sky Blue, selected New offer | 1149.00 | 1 |
| B0GR6935ZS | MacBook Air M5, Sky Blue, AppleCare+ bundle | 1364.00 | 1 |
| B0GR1JTFP8 | MacBook Air M5, Midnight, selected New offer | 1149.00 | 1 |
| B0GR6KJ72L | MacBook Neo A18 Pro, Blush | 689.00 | 2 |
| B0HBXNSNCJ | HP Ryzen 5 7430U business laptop | 638.99 | 1 |

Evidence is local and timestamped; these are observed prices, not future price
guarantees. The independent DOM review is
`data/reliability-production/live_verification.json` (**6 accepted, 6 verified**).
It includes exact titles, snapshot hashes, visible price evidence and checks.
The original baseline is preserved under
`data/reliability-production/before_results.json` and `before_summary.json`.

## Tests and default CLI smoke run

| Check | Before | Final |
| --- | ---: | ---: |
| Scraper suite | 205 passed | 251 passed |
| Full configured repository suite | 259 passed | 305 passed |

Focused tests passed throughout; `git diff --check` passed. Existing tests were
not weakened to accept incorrect data.

A separate live default-mode two-URL batch validated both products, rejected
zero, saved zero, launched Chrome once and created/closed two isolated pages.
No `--browser` flag was supplied. Evidence:
`data/reliability-production/automatic_batch.json` and `automatic_batch.log`.
This smoke run is separate from the 12-URL benchmark totals.

## Current flow and limits

`URL → HTTP → browser fallback if recoverable → extract selected product → validate → product`

Run from the repository root:

```powershell
.venv/Scripts/python.exe scraper/main.py --urls tests/reliability_urls.txt
```

The two Best Buy URLs still fail at transport/navigation. Both Walmart URLs and
two Amazon URLs hit verification gates in the final run. One gated Amazon URL
shares a Neo ASIN with successful observations: this is intermittent retrieval,
not permission to substitute a different URL's data. No larger retry loops or
longer timeouts were added. Target identity behavior is tested offline, but the
live benchmark contains no Target URLs.

A temporary inspector initially printed a checkpoint query value; subsequent
inspection redacts those values. Production diagnostics do not publish checkpoint
query tokens. No account or Supabase credentials were accessed.

Verified, accepted records are suitable for a gated normalizer/SBERT/search
pilot. Normalize units and preserve unknown specifications, offer identity and
source timestamps. Broader unattended retailer coverage is not established.
No normalizer, SBERT, embedding or search implementation was started here.
