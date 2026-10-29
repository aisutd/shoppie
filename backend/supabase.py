"""Read-only Supabase Data API adapter with a local vector cache; no shared writes."""

from dataclasses import dataclass, field
import json
import re

import requests

from backend.settings import setting
from backend.storage import LocalStore, ROOT, json_value, listing_id
from db.embeddings import MODEL_NAME, MODEL_REVISION, TEMPLATE_VERSION, validate_vector, build_text, metadata_for
from db.normalize import normalize
from scraper.scraper import clean_url, identify_product, extract_specs


@dataclass
class SupabaseConfig:
    url: str = field(repr=False)
    key: str = field(repr=False)
    schema: str = "public"


def configuration():
    url = setting("SUPABASE_URL").rstrip("/")
    key = setting("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise ValueError("Set SUPABASE_URL and SUPABASE_SECRET_KEY in the existing scraper/.env, root .env, or environment. Values are never displayed.")
    if not re.fullmatch(r"https://[a-z0-9-]+\.supabase\.co", url):
        raise ValueError("SUPABASE_URL must identify an HTTPS Supabase project without a path")
    if not key.startswith("sb_secret_") or any(char.isspace() for char in key):
        raise ValueError("Use the existing backend SUPABASE_SECRET_KEY, never a frontend key")
    schema = setting("SUPABASE_SCHEMA", "public")
    if schema not in {"public", "shoppie"}:
        raise ValueError("SUPABASE_SCHEMA must be public (existing products) or shoppie (approved additive schema)")
    return SupabaseConfig(url, key, schema)


def envelope_for(values, evidence):
    # maps shared records to the existing version 1 raw-field contract
    raw = {key: values.get(key) for key in ("title", "brand", "description", "gtin", "category", "price", "currency", "shipping_cost", "availability", "seller")}
    raw["model"] = values.get("model_number")
    raw["attributes"] = dict(values.get("attributes") or {})
    if values.get("condition"):
        raw["attributes"]["condition"] = values["condition"]
    raw.update(evidence)
    return {key: values.get(key) for key in ("retailer_key", "retailer_sku", "source_url", "scraped_at")} | {"raw": raw}


class SupabaseStore:
    def __init__(self, config=None, cache=None):
        self.config = config or configuration()
        self.cache = cache or LocalStore(ROOT / ".local/supabase-cache.sqlite3")
        self.rows = None
        self.schema_report = None
        self.remote_vectors = {}
        self.read_report = {"stage": "not_checked", "read_only": True}

    def request(self, path, params=None, payload=None):
        headers = {"apikey": self.config.key, "Accept-Profile": self.config.schema,
                   "Accept": "application/openapi+json" if path == "" else "application/json"}
        try:
            if payload is None:
                response = requests.get(self.config.url + "/rest/v1/" + path,
                    headers=headers, params=params, timeout=25, allow_redirects=False)
            else:
                # this single known RPC is STABLE/SECURITY INVOKER in the review-only SQL
                if path != "rpc/vector_candidates" or self.config.schema != "shoppie":
                    raise ValueError("Only the reviewed read-only vector RPC is supported")
                headers["Content-Profile"] = self.config.schema
                response = requests.post(self.config.url + "/rest/v1/" + path,
                    headers=headers, json=payload, timeout=25, allow_redirects=False)
            if response.status_code not in {200, 206}:
                labels = {401: "authentication rejected", 403: "permission denied", 404: "table or function not exposed", 406: "schema unavailable", 429: "rate limited"}
                raise ValueError("Supabase " + labels.get(response.status_code, "request failed") + f" (HTTP {response.status_code}); no write or fallback was attempted.")
            if len(response.content) > 8_000_000:
                raise ValueError("Supabase response exceeded the local read limit")
            return response.json()
        except (requests.RequestException, json.JSONDecodeError):
            raise ValueError("Supabase read failed or timed out; check backend configuration and network. Credentials and server details were withheld.") from None

    def inspect(self):
        schema = self.request("")
        definitions = schema.get("definitions", {}) if isinstance(schema, dict) else {}
        tables = {}
        for name in ("products", "listings", "observations", "current_offers", "embeddings", "retailers"):
            columns = definitions.get(name, {}).get("properties", {})
            if columns:
                tables[name] = sorted(columns)
        needed = {"id", "title", "price", "currency", "product_url", "source", "category", "scraped_at"}
        compatible = needed <= set(tables.get("products", [])) if self.config.schema == "public" else all(name in tables for name in ("listings", "current_offers", "observations", "embeddings"))
        self.schema_report = {"connected": True, "schema": self.config.schema, "tables": tables,
            "compatible": compatible, "read_only": True,
            "environment_verified": setting("SHOPPIE_DATABASE_ENV") in {"development", "test"},
            "schema_inspection": "Data API exposed columns only; SQL constraints/extensions require mentor inspection",
            "vector_storage": "shared shoppie.embeddings + local cache" if self.config.schema == "shoppie" else "local cache only; legacy products has no assumed vector/history contract"}
        return self.schema_report

    def refresh(self):
        report = self.schema_report or self.inspect()
        if not report["compatible"]:
            raise ValueError("Configured Supabase schema is not compatible or not exposed. Review sql/inspect_backend.sql; no migrations were executed.")
        if self.config.schema == "public":
            columns = report["tables"]["products"]
            selected = [field for field in ("id", "title", "price", "currency", "product_url", "source", "category", "scraped_at", "brand", "model_number", "description", "attributes", "availability", "shipping_cost", "condition") if field in columns]
            source = self.request("products", {"select": ",".join(selected), "order": "id", "limit": "1000"})
        else:
            source = self.request("listings", {"select": "*", "order": "id", "limit": "1000"})
            offers = self.request("current_offers", {"select": "*", "order": "listing_id", "limit": "1000"})
            latest = {item["listing_id"]: item for item in offers}
            source = [{**item, **latest[item["id"]], "id": item["id"]} for item in source if item["id"] in latest]
            embeddings = self.request("embeddings", {"select": "listing_id,model_name,model_revision,template_version,input_hash,input_text,dimensions,embedding,created_at",
                "model_name": "eq." + MODEL_NAME, "model_revision": "eq." + MODEL_REVISION,
                "template_version": "eq." + TEMPLATE_VERSION, "order": "listing_id", "limit": "1000"})
            self.remote_vectors = {item["listing_id"]: item for item in embeddings}
        if not isinstance(source, list):
            raise ValueError("Supabase returned an unexpected product response")
        rows, errors, seen, duplicates = [], [], set(), 0
        for item in source:
            try:
                envelope = self.to_envelope(item)
                record = normalize(envelope)
                identity = listing_id(record)
                if identity in seen:
                    duplicates += 1
                    continue
                # only the local cache is written; shared data is never updated
                self.cache.ingest(envelope)
                rows.append({**record, "id": identity})
                seen.add(identity)
            except (ValueError, TypeError, KeyError, AttributeError):
                errors.append("A shared product failed the local identity/data contract and was excluded.")
        self.rows = json.loads(json.dumps(rows, default=json_value))
        self.read_report = {"stage": "read", "read_only": True, "retrieved": len(source),
            "accepted": len(rows), "rejected": len(errors), "duplicates": duplicates,
            "limit": 1000, "possibly_truncated": len(source) == 1000, "errors": errors}
        return self.read_report

    def to_envelope(self, item):
        if self.config.schema == "public":
            url = clean_url(item["product_url"])
            retailer, sku = identify_product(url)
            if item.get("source") != retailer + ".com":
                raise ValueError("Shared retailer disagrees with product URL")
            title = item.get("title")
            attrs = dict(item.get("attributes") or {})
            # title evidence can fill specs, but contradictory explicit attributes fail closed
            inferred = extract_specs(title or "")
            from normalizer.matching import variant_key
            for key, value in inferred.items():
                if key in attrs and variant_key(key, attrs[key]) != variant_key(key, value):
                    raise ValueError("Shared title conflicts with explicit attributes")
                attrs[key] = value
            values = {"retailer_key": "best_buy" if retailer == "bestbuy" else retailer,
                "retailer_sku": sku, "source_url": url, "title": title,
                "brand": item.get("brand"), "model_number": item.get("model_number"),
                "description": item.get("description"), "category": "laptop" if item.get("category") == "laptops" else item.get("category"),
                "attributes": attrs, "price": item.get("price"), "currency": item.get("currency"),
                "shipping_cost": item.get("shipping_cost"), "condition": item.get("condition"),
                "availability": item.get("availability"), "scraped_at": item["scraped_at"]}
            return envelope_for(values, {"shared_source": "supabase_public_products", "shared_id": item["id"]})
        fields = ("retailer_key", "retailer_sku", "source_url", "title", "brand", "model_number", "gtin", "description", "category", "attributes", "price", "currency", "shipping_cost", "availability", "condition", "seller", "scraped_at")
        result = {key: item.get(key) for key in fields}
        if listing_id(result) != item["id"]:
            raise ValueError("Shared listing ID conflicts with its retailer URL")
        payload = item.get("raw_payload") or {}
        raw = payload.get("raw", {}) if isinstance(payload, dict) else {}
        # only provenance fields may leave the shared raw payload
        evidence = {key: raw[key] for key in ("data_source", "verification", "ai_review") if isinstance(raw, dict) and key in raw}
        return envelope_for(result, evidence)

    def listings(self):
        if self.rows is None:
            self.refresh()
        return self.rows

    def ingest(self, row):
        raise ValueError("Shared Supabase writes are disabled. Collect locally and request mentor approval before any upload.")

    def history(self, identity):
        if self.config.schema == "public":
            return []
        values = self.request("observations", {"select": "scraped_at,price,currency,shipping_cost,availability", "listing_id": "eq." + identity, "order": "scraped_at", "limit": "1000"})
        return values if isinstance(values, list) else []

    def get_embedding(self, identity):
        cached = self.cache.get_embedding(identity)
        row = next((row for row in (self.rows or []) if row["id"] == identity), None)
        if row:
            expected = metadata_for(build_text(row) or "")
            keys = ("model_name", "model_revision", "template_version", "input_hash", "dimensions")
            if cached and all(cached.get(key) == expected[key] for key in keys):
                return cached
            saved = self.remote_vectors.get(identity)
            if saved and all(saved.get(key) == expected[key] for key in keys):
                try:
                    value = dict(saved)
                    vector = value.pop("embedding")
                    value["vector"] = validate_vector(json.loads(vector) if isinstance(vector, str) else vector)
                    self.cache.put_embedding(identity, value)
                    return value
                except (ValueError, TypeError):
                    pass
        return cached

    def put_embedding(self, identity, data):
        self.cache.put_embedding(identity, data)

    def vector_candidates(self, query_vector, request):
        if self.config.schema != "shoppie":
            raise ValueError("Legacy public.products has no assumed pgvector RPC. Approve the separate shoppie schema first.")
        # fixed function name and typed JSON arguments cannot interpolate SQL
        return self.request("rpc/vector_candidates", payload={"query_vector": validate_vector(query_vector),
            "wanted_revision": MODEL_REVISION, "wanted_template": TEMPLATE_VERSION,
            "wanted_category": request.category, "minimum_price": str(request.min_price) if request.min_price is not None else None,
            "maximum_price": str(request.max_price) if request.max_price is not None else None,
            "wanted_availability": request.availability, "wanted_brand": request.brand, "result_limit": request.limit})
