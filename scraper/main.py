"""Run from any directory using this file's path, or python -m scraper.main."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

# Direct execution needs the repository root on Python's module search path.
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bs4 import BeautifulSoup
from pydantic import ValidationError

from scraper import config, scraper
from scraper.validator import validate_record


def main(argv=None):
    parser = argparse.ArgumentParser(description="Real laptop pages: extraction only unless --save is supplied.")
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--url", action="append", help="One product URL; repeat to process several")
    inputs.add_argument("--urls", help="URL file relative to scraper/ (default: urls.txt)")
    parser.add_argument("--stage", choices=["fetch", "extract", "validate"], default="validate")
    parser.add_argument("--browser", action="store_true", help="Optional background Chromium rendering for JavaScript pages")
    parser.add_argument("--manual", action="store_true", help="Enter a human-verified real observation instead of fetching HTML; requires one --url")
    parser.add_argument("--html", help="Local public HTML path relative to scraper/, for one --url only")
    parser.add_argument("--keep-html", action="store_true", help="Archive public HTML in scraper/data/pages/")
    parser.add_argument("--save", action="store_true", help="Use instructor backend credentials to upsert accepted live records")
    parser.add_argument("--check-db", action="store_true", help="Read-only connectivity check of the configured products table")
    parser.add_argument("--limit", type=int, help="Maximum validated records/write attempts; rejections do not consume the limit")
    args = parser.parse_args(argv)
    if args.manual and (args.check_db or args.html or args.browser or args.keep_html or args.stage != "validate" or not args.url or len(args.url) != 1):
        parser.error("--manual requires exactly one --url and cannot use browser/HTML/checkpoint flags")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be a positive integer")
    if args.check_db:
        if args.save or args.url or args.urls or args.html or args.browser or args.keep_html or args.limit is not None or args.stage != "validate":
            parser.error("--check-db runs alone; it cannot be combined with scraping or saving flags")
        try:
            from scraper.database import check_database, connect
            check_database(connect(config.load_database_config()))
        except ValueError as error:
            print("DB CHECK FAILED:", error)
            return 1
        print("DB CHECK OK: the configured project's products table is accessible for a read.")
        print("Connectivity only. A separate controlled write test is still needed to verify inserts/upserts.")
        return 0
    if args.save and (args.stage != "validate" or args.html):
        parser.error("--save requires live pages and --stage validate (the default)")
    if args.html and (args.browser or not args.url or len(args.url) != 1):
        parser.error("--html requires exactly one --url and cannot be combined with --browser")
    try:
        urls = args.url or config.load_urls(args.urls or "urls.txt")
    except ValueError as error:
        print("ERROR:", error)
        return 1

    unique = scraper.unique_urls(urls)
    if len(unique) != len(urls):
        print(f"Skipped {len(urls) - len(unique)} duplicate input URL(s).")
    urls = unique
    counts = {"fetched": 0, "extracted": 0, "validated": 0, "rejected": 0, "saved": 0, "failed_saves": 0}
    database = None
    saving_unavailable = False
    for index, source_url in enumerate(urls, start=1):
        completed = counts[{"fetch": "fetched", "extract": "extracted", "validate": "validated"}[args.stage]]
        if args.limit is not None and completed >= args.limit:
            print(f"Limit reached: {args.limit} successfully completed record(s) for this stage.")
            break
        print(f"\nPage {index}/{len(urls)}")
        try:
            url = scraper.clean_url(source_url)
            retailer, product_id = scraper.identify_product(url)
            print(f"{retailer}: {product_id}")
            if args.manual:
                from scraper.manual import collect_product
                candidate = collect_product(url)
            elif args.html:
                html = config.script_path(args.html).read_text(encoding="utf-8")
                print("LOCAL HTML: rehearsal only; observed_at is parsing time, not a live price check.")
            elif args.browser:
                html = scraper.fetch_rendered_page(url)
            else:
                html = scraper.fetch_page(url)
            if not args.manual:
                scraper.check_page(html)
                counts["fetched"] += 1
            if args.keep_html:
                folder = config.SCRIPT_DIR / "data" / "pages"
                folder.mkdir(parents=True, exist_ok=True)
                # Query variants must not overwrite each other's rehearsal archives.
                suffix = "-" + hashlib.sha256(url.encode()).hexdigest()[:12] if "?" in url else ""
                filename = f"{retailer}-{product_id}{suffix}.html"
                (folder / filename).write_text(html, encoding="utf-8")
                print(f"Archived in scraper/data/pages/{filename}")
            if args.stage == "fetch":
                soup = BeautifulSoup(html, "html.parser")
                print("Page title:", soup.title.get_text(strip=True) if soup.title else "(missing)")
                continue
            if not args.manual:
                candidate = scraper.extract_product(html, url)
                counts["extracted"] += 1
            if args.stage == "extract":
                print(json.dumps(candidate, indent=2, ensure_ascii=True))
                print("Candidate is unvalidated.")
                continue
            product = validate_record(candidate)
            counts["validated"] += 1
            print(product.model_dump_json(indent=2))
            print("ACCEPTED")
        except ValidationError as error:
            counts["rejected"] += 1
            print("REJECTED: required fields failed validation; no database write.")
            for issue in error.errors():
                field = ".".join(str(part) for part in issue["loc"])
                # Explain missing source data without echoing untrusted inputs.
                if issue["loc"] in [("title",), ("price",), ("currency",)] and candidate.get(field) is None:
                    reason = "not found in the retrieved product data"
                elif issue["loc"] == ("currency",):
                    reason = "must be explicitly USD; a bare $ does not establish currency"
                elif issue["loc"] == ("price",):
                    reason = "must be a finite positive number fitting numeric(12,2)"
                elif issue["loc"] == ("title",):
                    reason = "must describe a laptop and contain at least five characters"
                else:
                    reason = issue["type"]
                print(" -", field + ":", reason)
            continue
        except (ValueError, OSError) as error:
            counts["rejected"] += 1
            print("REJECTED:", str(error) if isinstance(error, ValueError) else "Could not read/write local HTML.")
            continue

        if args.save:
            if saving_unavailable:
                counts["failed_saves"] += 1
                print("SAVE FAILED: database configuration failed earlier in this run.")
                continue
            try:
                # Importing, configuring and connecting happen only after acceptance.
                from scraper.database import connect, upsert_product
                if database is None:
                    database = connect(config.load_database_config())
                upsert_product(database, product)
                counts["saved"] += 1
                print("SAVED: shared product row inserted or updated.")
            except ValueError as error:
                counts["failed_saves"] += 1
                saving_unavailable = database is None
                print("SAVE FAILED:", error)

    print("\nResults:", ", ".join(f"{name}={count}" for name, count in counts.items()))
    if not args.save:
        print("Extraction only. No Supabase settings read, connections opened or database writes.")
    return 1 if counts["rejected"] or counts["failed_saves"] else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EOFError, KeyboardInterrupt):
        print("Cancelled.")
        raise SystemExit(1)
