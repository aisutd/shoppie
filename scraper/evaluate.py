"""Measure labeled fixture accuracy separately from collection failures."""

import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
from time import perf_counter

from scraper.scraper import extract_product, identify_product
from scraper.validator import validate_record
from scraper.envelope import listing_from_product
from db.normalize import normalize

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "tests/fixtures/catalog"
FIELDS = ("title", "brand", "model", "category", "description", "price", "currency",
          "availability", "gtin", "shipping_cost", "attributes.color", "attributes.screen_inches",
          "attributes.ram_gb", "attributes.storage_gb", "attributes.cpu")


def field_value(record, name):
    value = record
    for key in name.split("."):
        value = value.get(key) if isinstance(value, dict) else None
    return value


def equal_field(field, value, expected):
    if field in {"price", "shipping_cost"} and value is not None and expected is not None:
        try:
            return Decimal(str(value)) == Decimal(str(expected))
        except Exception:
            return False
    return value == expected


def error_type(error, stage):
    text = str(error).lower()
    if any(word in text for word in ("bot check", "access-denied", "http 401", "http 403", "http 429", "http 451")):
        return "blocked"
    if "redirect" in text or "different product" in text:
        return "identity"
    if any(word in text for word in ("conflicting", "multiple configurations", "cannot safely identify")):
        return "ambiguous_source"
    return stage


def evaluate_fixtures(extractor=extract_product, manifest_path=None):
    path = Path(manifest_path or FIXTURE_DIR / "manifest.json")
    manifest = json.loads(path.read_text())
    counts = Counter(attempted=0, fetched=0, extracted=0, validated=0, rejected=0)
    missing, wrong, failures = Counter(), Counter(), Counter()
    correct = present = accepted_wrong = accepted_incomplete = 0
    price_correct = price_present = variant_correct = variant_present = 0
    checked_accepted = 0
    seen = set()
    quality = Counter(incorrect_accepted_records=0, manually_checked_accepted_records=0,
                      missing_prices=0, incorrect_prices=0, incorrect_model_numbers=0,
                      hardware_mismatches=0, availability_errors=0, duplicate_listings=0, blocked_pages=0)
    rows, started = [], perf_counter()
    for item in manifest["pages"]:
        counts["attempted"] += 1
        if item["url"] in seen:
            quality["duplicate_listings"] += 1
        seen.add(item["url"])
        stage, record, accepted = "fetch", None, False
        retailer = identify_product(item["url"])[0]
        row = {"fixture": item["id"], "retailer": retailer, "missing": [], "incorrect": []}
        page_start = perf_counter()
        try:
            html = (path.parent / item["file"]).read_text(encoding="utf-8")
            counts["fetched"] += 1
            stage = "extraction"
            record = extractor(html, item["url"])
            counts["extracted"] += 1
            row["missing"] = [field for field in FIELDS if field_value(record, field) is None]
            missing.update(row["missing"])
            quality["missing_prices"] += record.get("price") is None
            stage = "validation"
            normalize(listing_from_product(validate_record(record)))
            counts["validated"] += 1
            accepted = True
        except (ValueError, OSError) as error:
            counts["rejected"] += 1
            kind = error_type(error, stage)
            failures[f"{retailer}:{kind}"] += 1
            row["error_type"], row["error"] = kind, str(error)
            quality["blocked_pages"] += kind == "blocked"
        # compares only labeled, present values; missing data is reported separately
        if record:
            expected_missing = False
            variant_values = []
            for field, expected in item["expected"].items():
                value = field_value(record, field)
                if value is None:
                    expected_missing |= expected is not None and value is None
                    continue
                # a present value with an explicit null label is invented data
                agrees = equal_field(field, value, expected)
                present += 1
                correct += agrees
                if not agrees:
                    row["incorrect"].append(field)
                    wrong[field] += 1
                if field == "price":
                    price_present += 1
                    price_correct += agrees
                if field == "model" or field.startswith("attributes."):
                    variant_values.append(agrees)
            if variant_values:
                variant_present += 1
                variant_correct += all(variant_values)
            accepted_wrong += accepted and bool(row["incorrect"])
            accepted_incomplete += accepted and expected_missing
            checked_accepted += accepted and bool(item["expected"])
            quality["incorrect_prices"] += "price" in row["incorrect"]
            quality["incorrect_model_numbers"] += "model" in row["incorrect"]
            quality["hardware_mismatches"] += any(field in row["incorrect"] for field in ("attributes.ram_gb", "attributes.storage_gb", "attributes.cpu"))
            quality["availability_errors"] += "availability" in row["incorrect"]
        row["accepted"] = accepted
        row["seconds"] = perf_counter() - page_start
        rows.append(row)
    total = counts["attempted"]
    quality["incorrect_accepted_records"] = accepted_wrong
    quality["manually_checked_accepted_records"] = checked_accepted
    ratio = lambda a, b: a / b if b else None
    return {"source": manifest.get("provenance", "labeled fixtures; not live reliability"), "counts": dict(counts),
            "quality_counts": dict(quality),
            "metrics": {"acceptance_rate": ratio(counts["validated"], total),
                "invalid_record_rate": ratio(counts["extracted"] - counts["validated"], counts["extracted"]),
                "field_accuracy_present_labeled": ratio(correct, present),
                "exact_price_accuracy_present_labeled": ratio(price_correct, price_present),
                "model_variant_accuracy_present_labeled": ratio(variant_correct, variant_present),
                "incorrect_data_rate_among_accepted": ratio(accepted_wrong, checked_accepted),
                "bad_data_rate": ratio(accepted_wrong, checked_accepted),
                "rejection_rate": ratio(counts["rejected"], total),
                "average_seconds_per_page": (perf_counter() - started) / total if total else None},
            "denominators": {"labeled_present_fields": present, "labeled_present_prices": price_present,
                             "labeled_variant_records": variant_present,
                             "manually_checked_accepted_records": checked_accepted},
            "accepted_incomplete_records": accepted_incomplete,
            "missing_fields": dict(missing), "incorrect_fields": dict(wrong),
            "failures_by_retailer_and_type": dict(failures), "pages": rows}


def evaluate_captures():
    return evaluate_fixtures(manifest_path=FIXTURE_DIR.parent / "real_captures.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--real-captures", action="store_true")
    args = parser.parse_args()
    report = evaluate_captures() if args.real_captures else evaluate_fixtures()
    text = json.dumps(report, indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")


if __name__ == "__main__":
    main()
