"""Run from the repository root: python -m lesson --help."""

import argparse
import json
from pathlib import Path

from bs4 import BeautifulSoup
from pydantic import ValidationError

from lesson.extract import extract_product
from lesson.pages import check_page, clean_url, fetch_page, fetch_rendered_page, identify_product
from lesson.validate import Laptop


def main():
    parser = argparse.ArgumentParser(description="Collect one real laptop page; extract only by default.")
    parser.add_argument("--url", required=True, help="US retailer product URL (not search/category)")
    parser.add_argument("--stage", choices=["fetch", "extract", "validate"], default="validate")
    parser.add_argument("--html", type=Path, help="Read a locally saved public HTML page, without network")
    parser.add_argument("--browser", action="store_true", help="Optional: fetch rendered HTML using background Chrome")
    parser.add_argument("--keep-html", action="store_true", help="Keep a public page in ignored data/pages for offline teaching")
    parser.add_argument("--save", action="store_true", help="Sign in and write one accepted record to Supabase")
    args = parser.parse_args()
    if args.save and (args.stage != "validate" or args.html):
        parser.error("--save requires live fetching and --stage validate (the default)")
    if args.html and args.browser:
        parser.error("Choose --html or --browser, not both")

    try:
        url = clean_url(args.url)
        if args.html:
            html = args.html.read_text(encoding="utf-8")
        elif args.browser:
            html = fetch_rendered_page(url)
        else:
            html = fetch_page(url)
        check_page(html)
        if args.keep_html:
            retailer, product_id = identify_product(url)
            folder = Path("data/pages")
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{retailer}-{product_id}.html"
            path.write_text(html, encoding="utf-8")
            print(f"Kept public HTML: {path}")
        if args.stage == "fetch":
            soup = BeautifulSoup(html, "html.parser")
            print(f"Loaded {len(html):,} characters.")
            print("Page title:", soup.title.get_text(strip=True) if soup.title else "(missing)")
            print("Checkpoint 1 complete. No database writes.")
            return 0
        candidate = extract_product(html, url)
        if args.html:
            print("LOCAL HTML: practice extraction; observed_at is parsing time, not a live price check.")
        if args.stage == "extract":
            print(json.dumps(candidate, indent=2, ensure_ascii=True))
            print("Checkpoint 2 complete. Candidate is unvalidated. No database writes.")
            return 0
        product = Laptop.model_validate(candidate)
        print(product.model_dump_json(indent=2))
        print("ACCEPTED: required fields passed validation.")
        if args.save:
            from lesson.database import save_product
            save_product(product)
            print("SAVED: one observation in the shared Supabase table.")
        else:
            print("Extraction only. No Supabase credentials read; no database writes.")
        return 0
    except ValidationError as error:
        # Only field names and error codes; never dump arbitrary inputs.
        print("REJECTED: validation failed; no database write.")
        for issue in error.errors():
            print(" -", ".".join(str(part) for part in issue["loc"]), issue["type"])
    except (ValueError, OSError) as error:
        # Our ValueErrors are curated; OS errors may include private paths.
        print("ERROR:", str(error) if isinstance(error, ValueError) else "Could not read the local HTML file.")
    except (EOFError, KeyboardInterrupt):
        print("Cancelled.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
