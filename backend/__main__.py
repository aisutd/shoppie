"""Local model initialization, indexing, search, and evaluation commands."""

import argparse
import json
from pathlib import Path

from backend.models import SearchRequest
from backend.service import ShoppingService
from backend.storage import LocalStore
from db.embeddings import index_store, load_model
from scraper.evaluate import evaluate_fixtures
from backend.gemini import allow_calls
from backend.settings import configuration_status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["init-model", "index", "search", "evaluate", "evaluate-search", "discover", "collect-live", "browser-check", "config-check", "supabase-check", "supabase-search", "supabase-vector"])
    parser.add_argument("--query", default="Apple MacBook Air M5 16GB RAM 512GB SSD")
    parser.add_argument("--provider", choices=["gemini"], default="gemini")
    parser.add_argument("--allow-gemini", action="store_true", help="Explicit opt-in to potentially billed API calls")
    parser.add_argument("--ai-review", action="store_true", help="Optional bounded AI review per nonconflicting live product")
    parser.add_argument("--explain", action="store_true", help="Optional Gemini evidence selection after verified retrieval")
    parser.add_argument("--url", action="append", help="Permitted product URL; repeat up to eight times")
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    with allow_calls(args.allow_gemini):
        return run(args, parser)


def run(args, parser):
    if args.command == "config-check":
        print(json.dumps(configuration_status(), indent=2))
        return 0
    if args.command.startswith("supabase-"):
        from backend.supabase import SupabaseStore
        try:
            store = SupabaseStore()
            inspection = store.inspect()
            if args.command == "supabase-check":
                result = {"schema": inspection, "read": store.refresh()}
            elif args.command == "supabase-vector":
                from db.embeddings import generate_embedding
                result = {"candidates": store.vector_candidates(generate_embedding(load_model(), args.query), SearchRequest(q=args.query)), "writes": 0}
            else:
                service = ShoppingService(store, mode="live", storage="supabase")
                read = service.refresh_shared()
                result = {"read": read, "search": service.deals(SearchRequest(q=args.query), args.explain)}
        except ValueError as error:
            print(json.dumps({"error": str(error), "writes": 0}, indent=2))
            return 1
        print(json.dumps(result, indent=2, default=str))
        return 0
    if args.url and len(args.url) > 8:
        parser.error("provide at most eight product URLs")
    if args.command == "browser-check":
        from scraper.browser_check import check_browser
        print(json.dumps(check_browser(args.headed), indent=2))
        return 0
    if args.command == "discover":
        from backend.discovery import discover_report
        try:
            result = discover_report(args.query, provider=args.provider)
        except ValueError as error:
            print(json.dumps({"provider": args.provider, "error": str(error), "live_offers_verified": 0}, indent=2))
            return 1
        print(json.dumps(result, indent=2))
        return 0
    if args.command == "collect-live":
        if args.headed and not args.browser:
            parser.error("--headed requires --browser for collection")
        service = ShoppingService(mode="live")
        status = service.collect(args.query, browser=args.browser, headed=args.headed,
                                 provider=args.provider, urls=args.url, ai_review=args.ai_review)
        result = {"collection": status}
        if status["stage"] == "ready":
            result["search"] = service.deals(SearchRequest(q=args.query), args.explain)
        print(json.dumps(result, indent=2, default=str))
        return 0 if status["stage"] == "ready" else 1
    if args.command == "init-model":
        load_model(local_files_only=False)
        print("Pinned MiniLM model cached locally (384 dimensions).")
    elif args.command == "evaluate":
        print(json.dumps(evaluate_fixtures(), indent=2))
    else:
        service = ShoppingService()
        service.ensure_demo()
        if args.command == "index":
            result = index_store(service.store)
        elif args.command == "evaluate-search":
            from backend.evaluation import evaluate_search
            result = evaluate_search(service)
        else:
            result = service.deals(SearchRequest(q=args.query))
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    raise SystemExit(main())
