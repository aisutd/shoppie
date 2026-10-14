# Target lesson readiness review — October 14, 2026

**Decision: not ready for a promised automatic Target-to-Supabase demonstration.**
The explicitly labeled offline extraction/validation lesson is usable after
the instructor distributes the required non-secret files and rehearses setup.
This review was executed on the existing Windows computer, not another machine.

## Checks actually executed

Commands below used the existing fresh integration environment's Python:

```powershell
$python = '.\data\integration-20261014-1952\venv\Scripts\python.exe'
& $python -m pip check
& $python -m pytest -q scraper/tests tests
& $python -u scraper/main.py --urls target_urls.txt
& $python -u scraper/main.py --urls target_urls.txt --browser
& $python scraper/main.py --check-db
git diff --check
git check-ignore .env scraper/.env
git ls-files
```

| Check | Actual outcome |
| --- | --- |
| Dependency consistency | Exit 0; no broken requirements. |
| Initial automated suite | 183 passed in 2.13s. |
| Final suite after review fix | **184 passed in 2.22s**, exit 0. |
| Target HTTP automatic validation | Exit 1; fetched=1, extracted=1, validated=0, rejected=1; missing price/currency. |
| Target Chrome automatic validation | Exit 1; fetched=1, extracted=1, validated=0, rejected=1; invalid title and missing price/currency. |
| Real Supabase read check | Exit 0; configured products table readable. Connectivity only. |
| Saved real fixture extraction | Exit 0; expected title/ID and null commerce fields; explicitly LOCAL HTML. |
| Git whitespace check | Exit 0; Windows line-ending advisory only. |
| Secret tracking | Both .env paths ignored; neither tracked. Contents were not inspected. |
| Clone distribution | Fails readiness: only README.md and requirements.txt are tracked. Required code, tests, SQL and templates are still untracked. |

The saved fixture command actually executed was:

```powershell
& $python scraper/main.py --url 'https://www.target.com/p/lenovo-legion-5-15-1-oled-wqxga-165hz-gaming-notebook-amd-ryzen-7-260-16gb-ram-512gb-ssd-nvidia-geforce-rtx-5060-eclipse-black/-/A-1004661132' --html tests/fixtures/target_1004661132_2026-10-14.html --stage extract
```

## Independent architecture review

A separate agent reviewed the repository from a senior software architect's
perspective, without reading secrets or making writes. This describes the review
role; it does not claim a human reviewer with a specific employment history.

The reviewer identified a reproducible parser bug: the main title could be
combined with unscoped recommendation itemprop price/currency tags. The fix
removes that global microdata fallback and Walmart's global itemprop price
selector. A new regression asserts that accessory microdata cannot produce an
accepted laptop price. The full suite passed after this change. No prices or
currency defaults were fabricated to make the live source pass.

The reviewer also identified the fixed five-second Chrome delay as insufficient
to establish page readiness, absent student Chrome prerequisite guidance, and
untracked required files. Chrome prerequisites are now stated in the student
run card. Explicit retailer readiness handling remains future retrieval work.

Existing strengths: explicit --save, lazy database configuration, no import-time
network access, rejected missing values, separate save-failure counts, bounded
write attempts, and upsert by exact product_url.

## What remains before a live mentee demonstration

- [ ] Obtain explicit price/currency and the correct variant from live Target
  automatically; compare values to the displayed page. Current attempts failed.
- [ ] Replace the fixed browser delay with verified product-readiness and
  challenge/failure handling; do not bypass challenges or invent missing data.
- [ ] Save one verified real product and read it back.
- [ ] Repeat the exact URL; confirm count=1, same id, and advancing scraped_at.
- [ ] Review and commit/distribute the non-secret required files. No commits were
  made during this task, per the user's instruction.
- [ ] Rehearse installation and commands on the intended classroom machine.

No live writes were attempted because no real record validated. Read success and
mocked write tests do not prove insert/update permissions or real duplicate
prevention. No synthetic records were written to the shared products table.

For a session held before retrieval is fixed, use STUDENT_LESSON.md and the dated
real capture to teach extraction, missing values, validation and failure handling.
Label the database tests as mocked rehearsal and the real save/upsert checks as
unfinished. Do not advertise this restricted session as a working automatic
product collection demonstration.
