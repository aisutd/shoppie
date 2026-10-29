"""Bounded collection with per-URL outcomes and separate validation/match counts."""

from datetime import datetime, timezone
import json
import os
from time import perf_counter
from urllib.parse import urlsplit
from uuid import uuid4

from scraper.scraper import clean_url, extract_product, fetch_page, fetch_rendered_page, identify_product
from scraper.validator import validate_record
from scraper.envelope import listing_from_product
from scraper.evaluate import FIXTURE_DIR, error_type, FIELDS, field_value
from backend.access import fetch_robots, robots_permit, permitted_page_retailers
from backend.discovery import discover, discover_report
from backend.models import SearchRequest
from backend.search import requirements, family_in
from backend.storage import listing_id
from normalizer.matching import check_requirements
from db.normalize import normalize
from backend.ai_validation import review_product


def robots_allowed(url):
    retailer = identify_product(url)[0]
    if retailer not in permitted_page_retailers():
        return False
    parts = urlsplit(url)
    try:
        return robots_permit(fetch_robots("https://" + parts.hostname), url)
    except ValueError:
        return False


def collect(store, query, mode="demo", browser=False, headed=False, progress=None,
            provider=None, urls=None, request=None, ai_review=False):
    if mode not in {"demo", "live"}:
        raise ValueError("mode must be demo or live")
    if headed and not browser:
        raise ValueError("headed mode requires browser rendering")
    request = request or SearchRequest(q=query)
    wanted = requirements(request)
    status = {"run_id": str(uuid4()), "started_at": datetime.now(timezone.utc).isoformat(),
              "stage": "discovery", "source": mode, "discovery_provider": provider or "gemini",
              "discovered": 0, "processed": 0, "attempted": 0, "fetched": 0, "extracted": 0,
              "accepted": 0, "rejected": 0, "invalid_records": 0, "failed_scrapes": 0,
              "skipped": 0, "duplicate_urls": 0, "invalid_urls": 0, "saved": 0, "unchanged": 0,
              "compatible": 0, "incompatible": 0, "manual_review": 0, "unavailable": 0,
              "unknown_availability": 0, "nonpriced_unavailable": 0, "storage_failures": 0,
              "blocked_pages": 0, "ai_reviews": 0, "ai_review_required": 0,
              "worker_failures": 0,
              "missing_fields": {}, "failures": {},
              "errors": [], "events": [], "stored_ids": []}
    started = perf_counter()
    def update():
        if progress:
            progress(json.loads(json.dumps(status)))
    def finish(stage):
        status["stage"] = stage
        status["finished_at"] = datetime.now(timezone.utc).isoformat()
        status["elapsed_seconds"] = perf_counter() - started
        status["acceptance_rate"] = status["accepted"] / status["attempted"] if status["attempted"] else None
        status["invalid_record_rate"] = status["invalid_records"] / status["extracted"] if status["extracted"] else None
        status["rejection_rate"] = status["rejected"] / status["attempted"] if status["attempted"] else None
        status["average_seconds_per_page"] = sum(event.get("seconds", 0) for event in status["events"] if event.get("attempted")) / status["attempted"] if status["attempted"] else None
        # correctness percentages need human labels; validation alone cannot measure them
        status["incorrect_data_rate"] = None
        update()
        return status
    update()
    fixtures = {}
    if mode == "demo":
        manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text())
        pages = [item for item in manifest["pages"] if item["catalog"]]
        candidates = [item["url"] for item in pages]
        fixtures = {item["url"]: item for item in pages}
        status["discovery_provider"] = "synthetic_manifest"
    else:
        try:
            if urls is not None:
                candidates = list(urls)[:8]
                status["discovery_provider"] = "provided_urls"
            elif provider is not None:
                status["discovery"] = discover_report(query, provider=provider)
                status["duplicate_urls"] = status["discovery"].get("duplicate_sources", 0)
                candidates = status["discovery"]["urls"]
            else:
                candidates = discover(query)
        except ValueError as error:
            status["errors"].append(str(error))
            return finish("failed")
    selected, seen = [], set()
    for value in candidates:
        try:
            url = clean_url(value)
        except (ValueError, AttributeError, TypeError):
            status["invalid_urls"] += 1
            continue
        if url in seen:
            status["duplicate_urls"] += 1
            continue
        selected.append(url)
        seen.add(url)
    status["discovered"] = len(selected)
    blocked = set()
    for url in selected:
        status["processed"] += 1
        status["stage"] = "collection"
        retailer = identify_product(url)[0]
        event = {"url": url, "retailer": retailer, "attempted": False, "accepted": False}
        page_start, stage = perf_counter(), "fetch"
        try:
            # access denials are skips, not failed product-page fetches
            if mode == "live" and (retailer in blocked or not robots_allowed(url)):
                status["skipped"] += 1
                event.update(outcome="skipped", error_type="access", reason="Retailer page access is not enabled, robots rules denied it, or this retailer already blocked the run.")
                status["events"].append(event)
                update()
                continue
            event["attempted"] = True
            status["attempted"] += 1
            if mode == "demo":
                html = (FIXTURE_DIR / fixtures[url]["file"]).read_text()
            else:
                html = fetch_rendered_page(url, headless=not headed) if browser else fetch_page(url)
            status["fetched"] += 1
            stage = "extraction"
            candidate = extract_product(html, url)
            status["extracted"] += 1
            for field in FIELDS:
                if field_value(candidate, field) is None:
                    status["missing_fields"][field] = status["missing_fields"].get(field, 0) + 1
            stage = "validation"
            status["stage"] = stage
            update()
            row = listing_from_product(validate_record(candidate, allow_unavailable=mode == "live"))
            if mode == "demo":
                row["scraped_at"] = manifest["observed_at"]
                row["raw"]["data_source"] = "synthetic"
            else:
                row["raw"]["data_source"] = "live"
                row["raw"]["verification"] = {"status": "source_validated", "url": url,
                    "observed_at": row["scraped_at"], "method": candidate["extraction_method"],
                    "run_id": status["run_id"], "provider": status["discovery_provider"]}
            record = normalize(row)
            status["accepted"] += 1
            event["accepted"] = True
            event["availability"] = record["availability"]
            event["price_known"] = record["price"] is not None
            if record["availability"] == "out_of_stock":
                status["unavailable"] += 1
                if record["price"] is None:
                    status["nonpriced_unavailable"] += 1
            elif record["availability"] is None or record["availability"] == "unknown":
                status["unknown_availability"] += 1
            match = check_requirements({**record, "family": family_in(record["title"])}, wanted)
            # AI may request review, but cannot change data or reverse a hard mismatch
            if mode == "live" and ai_review and match["status"] != "rejected":
                status["stage"] = "ai_review"
                update()
                review = review_product(record, wanted)
                status["ai_reviews"] += 1
                row["raw"]["ai_review"] = review
                event["ai_review"] = review["status"]
                if review["status"] != "consistent":
                    status["ai_review_required"] += 1
                    match = {"status": "manual_review", "reasons": match["reasons"] + ["optional AI review flagged incomplete or inconsistent evidence"]}
            event.update(match_status=match["status"], reasons=match["reasons"])
            status[{"exact": "compatible", "manual_review": "manual_review", "rejected": "incompatible"}[match["status"]]] += 1
            # different configurations can be valid source data without matching this request
            if mode == "live" and match["status"] == "rejected":
                event["outcome"] = "incompatible"
            else:
                stage = "storage"
                result = store.ingest(row)
                status["saved" if result == "imported" else "unchanged"] += 1
                status["stored_ids"].append(listing_id(record))
                event["outcome"] = "stored" if result == "imported" else "unchanged"
        except (ValueError, OSError) as error:
            kind = error_type(error, stage)
            if stage == "storage":
                status["storage_failures"] += 1
            else:
                status["rejected"] += 1
                status["invalid_records" if stage == "validation" else "failed_scrapes"] += 1
            status["errors"].append(f"{retailer}: {error}")
            key = f"{retailer}:{kind}"
            status["failures"][key] = status["failures"].get(key, 0) + 1
            event.update(outcome="rejected", error_type=kind, reason=str(error))
            if kind == "blocked":
                status["blocked_pages"] += 1
                blocked.add(retailer)
        except Exception:
            status["worker_failures"] += 1
            if stage == "storage":
                status["storage_failures"] += 1
            event.update(outcome="failed", error_type="infrastructure")
            event["seconds"] = perf_counter() - page_start
            status["events"].append(event)
            status["errors"].append(f"Infrastructure failed during {stage}; this candidate failed without relabeling it as invalid product data.")
            update()
            continue
        event["seconds"] = perf_counter() - page_start
        status["events"].append(event)
        update()
    if not status["stored_ids"]:
        status["errors"].append("No matching or reviewable offer was stored in this run; the live milestone has not passed.")
        return finish("no_matches" if status["incompatible"] else "failed")
    return finish("collected")
