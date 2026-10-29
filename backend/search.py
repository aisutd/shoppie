"""Explainable semantic ranking after exact filters and hardware checks."""

from decimal import Decimal
import re
from time import perf_counter

from db.embeddings import (DIMENSIONS, MODEL_NAME, MODEL_REVISION, TEMPLATE_VERSION,
                           build_text, generate_embedding, load_model, metadata_for, validate_vector)
from db.similarity import cosine_similarity
from normalizer.matching import check_requirements, variant_key
from scraper.scraper import extract_specs
from backend.provenance import source_evidence


def family_in(text):
    text = (text or "").casefold()
    for family in ("macbook air", "macbook pro", "ideapad", "thinkpad"):
        if family in text:
            return family
    return None


def requirements(request):
    inferred = extract_specs(request.q)
    for key in ("ram_gb", "storage_gb", "cpu", "color", "screen_inches"):
        explicit = getattr(request, key)
        if explicit is not None:
            if key in inferred and variant_key(key, inferred[key]) != variant_key(key, explicit):
                raise ValueError(f"query and exact {key} filter disagree")
            inferred[key] = explicit
    if "color" not in inferred:
        for color in ("sky blue", "space gray", "midnight", "starlight", "silver", "black", "blue", "white", "red", "green"):
            if re.search(rf"\b{color}\b", request.q, re.I):
                inferred["color"] = color
                break
    inferred["model_number"] = request.model_number
    inferred["family"] = family_in(request.q)
    inferred["brand"] = request.brand
    if not inferred["brand"]:
        for brand in ("Apple", "Lenovo", "Dell", "HP", "Asus", "Acer"):
            if re.search(rf"\b{brand}\b", request.q, re.I):
                inferred["brand"] = brand
                break
    return {key: value for key, value in inferred.items() if value is not None}


def search(store, request, model=None, source=None):
    started = perf_counter()
    required = requirements(request)
    listings = store.listings()
    if source == "live":
        listings = [row for row in listings if source_evidence(row)["data_source"] != "synthetic"]
    elif source == "demo":
        listings = [row for row in listings if source_evidence(row)["data_source"] == "synthetic"]
    if not listings:
        return {"results": [], "indexed": 0, "search_seconds": perf_counter() - started,
                "model_name": MODEL_NAME, "dimensions": DIMENSIONS}
    for field in ("model_number", "gtin", "retailer_sku"):
        values = {row[field] for row in listings if row.get(field) and
                  re.search(r"(?<![a-z0-9])" + re.escape(str(row[field])) + r"(?![a-z0-9])", request.q, re.I)}
        if len(values) == 1:
            exact_value = next(iter(values))
            if field in required and variant_key(field, required[field]) != variant_key(field, exact_value):
                raise ValueError(f"query and exact {field} filter disagree")
            required[field] = exact_value
    query_vector = generate_embedding(model or load_model(), request.q)
    results, indexed = [], 0
    tokens = set(re.findall(r"[a-z0-9]+", request.q.casefold()))
    seen = set()
    for listing in listings:
        vector = store.get_embedding(listing["id"])
        metadata = metadata_for(build_text(listing) or "")
        keys = ("model_name", "model_revision", "template_version", "input_hash", "dimensions")
        if not vector or any(vector.get(key) != metadata[key] for key in keys):
            continue
        indexed += 1
        if request.category and listing.get("category") != request.category:
            continue
        if request.brand and (listing.get("brand") or "").casefold() != request.brand.casefold():
            continue
        if request.availability and listing.get("availability") != request.availability:
            continue
        price = Decimal(str(listing["price"])) if listing.get("price") is not None else None
        if request.min_price is not None and (price is None or price < request.min_price):
            continue
        if request.max_price is not None and (price is None or price > request.max_price):
            continue
        candidate = {**listing, "family": family_in(listing.get("title"))}
        status = check_requirements(candidate, required)
        if status["status"] == "rejected":
            continue
        # model and retailer identifiers are evidence, not semantic score bonuses
        identifiers = [listing.get(key) for key in ("model_number", "gtin", "retailer_sku")]
        identifier_match = any(value and str(value).casefold() in request.q.casefold() for value in identifiers)
        words = set(re.findall(r"[a-z0-9]+", (build_text(listing) or "").casefold()))
        keyword = len(tokens & words) / len(tokens) if tokens else 0
        score = cosine_similarity(query_vector, validate_vector(vector["vector"]))
        identity = (listing["retailer_key"], listing["source_url"])
        if identity in seen:
            continue
        seen.add(identity)
        public = {key: value for key, value in listing.items() if key not in {"raw_payload", "source_url_hash"}}
        public.update(source_evidence(listing))
        if source == "live" and not public["source_verified"]:
            status = {"status": "manual_review", "reasons": status["reasons"] + ["stored source evidence is incomplete; recollect this offer"]}
        if public["ai_review_required"]:
            status = {"status": "manual_review", "reasons": status["reasons"] + ["optional AI validation requires review"]}
        results.append({**public, "match_status": status["status"], "reasons": status["reasons"],
                        "semantic_score": score, "keyword_score": keyword,
                        "ranking_score": (score + keyword) / 2,
                        "identifier_match": identifier_match})
    # exact compatibility and identifier evidence outrank semantics; no probability cutoff
    results.sort(key=lambda row: (row["match_status"] == "exact", row["identifier_match"],
                                 row["ranking_score"], row["semantic_score"]), reverse=True)
    return {"results": results[:request.limit], "indexed": indexed,
            "search_seconds": perf_counter() - started, "model_name": MODEL_NAME,
            "dimensions": DIMENSIONS}
