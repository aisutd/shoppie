# Reliability benchmark workflow

Run commands from the repository root with `.venv/Scripts/python.exe`.

1. Edit `scraper/tests/reliability_urls.txt` to select live URLs. Exact duplicate
   lines run once; distinct URLs remain separate observations.
2. Run `scraper/tests/build_reliability_cases.py`. This adds missing cases to
   `reliability_cases.json`; it preserves existing cases, expectations, notes,
   review flags and custom fields, including cases removed from the URL list.
   New cases have unknown expectations, never assumed acceptance.
3. Review the real product and fill in `expected`. Set `needs_review: false`
   only after checking the expected values. Preserve date/source in notes.
   `expected.should_accept` is an explicit boolean for acceptance evaluation.
   A null expected field is unknown unless listed in `reviewed_fields` (useful
   for explicitly reviewed null availability). Legacy top-level `should_accept`
   is also supported. Old observation fields in existing cases are historical;
   they are not ground truth.
4. Run `scraper/tests/run_reliability_benchmark.py`. It reads expectations and
   writes only generated `reliability_results.json`, checkpointed after each URL.
   A generated `reliability_summary.json` contains counts by retailer and mode,
   failure categories, fallback recoveries and reviewed comparisons when present.
   It never updates case reviews. Results contain the real CLI stdout/stderr,
   return code, counters and sanitized diagnostics for each executed attempt.
   An HTTP acceptance skips browser fallback; a one-element attempts list means
   browser was not run. A terminal HTTP identity/challenge/invalid-data failure
   also skips browser. Every executed attempt is retained.

The runner retains subprocess integration to exercise the real orchestration,
isolate Chrome lifetimes and preserve its existing 90-second process deadline.
It uses the current interpreter, repository-root cwd, unbuffered UTF-8 output,
the production identity/validation functions, actual CLI counters and JSON
decoding. It never uses `--save`, database flags, or private configuration.
The HTTP probe explicitly uses `--http-only`; browser fallback follows the
production diagnostic `fallback_allowed` decision. This prevents automatic
fallback from being mislabeled as HTTP success or being executed twice.
`--keep-html` archives successful page snapshots for checking accepted records.
Stage events include confirmed final browser URLs and protocol-retry counts.
See `LIVE_RELIABILITY_REPORT.md` for the 2026-10-26 production-fix results,
limitations, accepted-product checks and default-CLI smoke test.

Normal CLI usage now automatically tries the browser for recoverable HTTP or
incomplete-field failures. `--browser` forces rendering; `--http-only` isolates
HTTP diagnostics. A normal multi-URL CLI batch lazily reuses one Chrome process,
with a fresh isolated page/context per URL, and closes all resources afterward.
Only one retry is allowed for the observed HTTP/2/reset/closed-connection errors;
challenges, wrong identities, malformed inputs and invalid currencies do not
trigger that retry or browser fallback.

For US Amazon main-product prices, an explicit `$` or `US$` establishes USD.
No symbol or currency evidence means unknown currency. Conflicting primary
prices, metadata conflicts, list prices and installment text are rejected.
Optional specifications come from matching JSON-LD and product-bound Amazon
tables; they retain source units, stay null when unknown/conflicting, and never
come from recommendations or guesses based on titles.
New/Used price modules must belong to the explicitly active offer; hidden or
inactive offer modules cannot supply the main price or availability. Amazon's
visible title elements are read separately from hidden form inputs with the same
ID. Target preselect-to-child canonicalization is allowed only when the resolved
child TCIN agrees; different children and offer/variant query changes are rejected.

Stage success means the CLI completed that stage, not that a network connection
merely opened. Browser fetch includes readiness and internal extraction checks;
an extraction rejection inside readiness is explicitly classified as extraction.
Unknown process failures/timeouts remain unknown rather than guessed. A process
deadline is separate from request/navigation/readiness timeouts. Final statuses
describe the last attempt; earlier attempt statuses are retained separately.

Product keys come from `identify_product()`, including selected Target TCINs.
Grouping is metadata only. It never merges exact URL observations or treats
seller, condition, configuration, price or query variants as interchangeable.

Do not interpret collection acceptance as accuracy. Accuracy requires reviewed
expectations; false accepts and accepted records with incorrect reviewed fields
are the highest-severity outcomes. Live prices can change: review timestamps
matter. Keep source and generated evidence local if URLs contain private data.
Transport diagnostics publish only static descriptions and allowlisted network
codes, never exception call logs, headers, cookies or configuration values.
