"""Pinned MiniLM inference and reusable product vectors; no training or API key."""

from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
import json
import math
from pathlib import Path

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
TEMPLATE_VERSION = "identity-v2"
DIMENSIONS = 384
CACHE_DIR = Path(__file__).resolve().parents[1] / ".local" / "models"


def build_text(listing):
    """Keep stable identity facts ahead of descriptions, which may be truncated."""
    parts = [listing.get("brand"), listing.get("title"), listing.get("model_number"),
             listing.get("category")]
    attributes = listing.get("attributes") or {}
    if not isinstance(attributes, dict):
        raise ValueError("attributes must be an object")
    identity_fields = {"color", "ram_gb", "storage_gb", "screen_inches",
                       "cpu", "resolution", "pack_quantity", "size"}
    for key in sorted(identity_fields & attributes.keys()):
        if attributes[key] is not None:
            parts.append(f"{key}: {attributes[key]}")
    parts.append(listing.get("description"))
    text = " | ".join(str(part).strip() for part in parts if part is not None and str(part).strip())
    return text or None


@lru_cache(maxsize=2)
def load_model(revision=MODEL_REVISION, local_files_only=True):
    # loads one CPU model for predictable macOS inference; MPS is optional later
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_NAME, revision=revision, cache_folder=str(CACHE_DIR),
                               device="cpu", trust_remote_code=False,
                               local_files_only=local_files_only)


def validate_vector(vector):
    values = list(vector)
    if len(values) != DIMENSIONS:
        raise ValueError("embedding must contain exactly 384 values")
    if any(isinstance(value, bool) or not isinstance(value, (int, float))
           or not math.isfinite(value) for value in values):
        raise ValueError("embedding values must be finite numbers")
    length = math.sqrt(sum(value * value for value in values))
    if not math.isfinite(length) or length == 0:
        raise ValueError("embedding must have a finite nonzero length")
    return [float(value / length) for value in values]


def generate_batch(model, texts):
    if any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError("embedding text must not be empty")
    if not texts:
        return []
    vectors = model.encode(texts, batch_size=32, normalize_embeddings=True,
                           convert_to_numpy=True, show_progress_bar=False)
    if len(vectors) != len(texts):
        raise ValueError("model returned the wrong batch size")
    return [validate_vector(vector.tolist() if hasattr(vector, "tolist") else vector)
            for vector in vectors]


def generate_embedding(model, text):
    return generate_batch(model, [text])[0]


def metadata_for(text, revision=MODEL_REVISION, template=TEMPLATE_VERSION):
    return {"model_name": MODEL_NAME, "model_revision": revision,
            "template_version": template, "input_text": text,
            "input_hash": sha256(text.encode("utf-8")).hexdigest(),
            "dimensions": DIMENSIONS, "created_at": datetime.now(timezone.utc).isoformat()}


def index_store(store, model=None):
    pending, stats = [], {"created": 0, "reused": 0, "skipped": 0}
    for listing in store.listings():
        text = build_text(listing)
        if not text:
            stats["skipped"] += 1
            continue
        metadata = metadata_for(text)
        saved = store.get_embedding(listing["id"])
        keys = ("model_name", "model_revision", "template_version", "input_hash", "dimensions")
        if saved and all(saved.get(key) == metadata[key] for key in keys):
            validate_vector(saved["vector"])
            stats["reused"] += 1
        else:
            pending.append((listing["id"], metadata))
    # encodes only changed descriptions, never every product during a search
    if pending:
        vectors = generate_batch(model or load_model(), [item[1]["input_text"] for item in pending])
        for (listing_id, metadata), vector in zip(pending, vectors):
            store.put_embedding(listing_id, {**metadata, "vector": vector})
            stats["created"] += 1
    return stats


def save_embedding(connection, listing_id, metadata, vector):
    vector = validate_vector(vector)
    cursor = connection.cursor(buffered=True)
    try:
        cursor.execute("""INSERT INTO listing_embeddings
            (listing_id, model_name, model_revision, template_version, input_text,
             input_hash, dimensions, vector, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE input_text=VALUES(input_text), input_hash=VALUES(input_hash),
            dimensions=VALUES(dimensions), vector=VALUES(vector), created_at=VALUES(created_at)""",
            (listing_id, metadata["model_name"], metadata["model_revision"], metadata["template_version"],
             metadata["input_text"], metadata["input_hash"], DIMENSIONS, json.dumps(vector),
             datetime.fromisoformat(metadata["created_at"]).astimezone(timezone.utc).replace(tzinfo=None)))
    finally:
        cursor.close()


def refresh_embeddings(connection, model, model_name=MODEL_NAME, model_revision=MODEL_REVISION,
                       template_version=TEMPLATE_VERSION):
    if model_name != MODEL_NAME:
        raise ValueError("this milestone uses all-MiniLM-L6-v2 only")
    cursor = connection.cursor(dictionary=True, buffered=True)
    try:
        from db.queries import get_current_offers
        listings = get_current_offers(connection)
        stats = {"created": 0, "reused": 0, "skipped": 0}
        for listing in listings:
            if isinstance(listing["attributes"], str):
                listing["attributes"] = json.loads(listing["attributes"])
            text = build_text(listing)
            if not text:
                stats["skipped"] += 1
                continue
            metadata = metadata_for(text, model_revision, template_version)
            cursor.execute("""SELECT input_hash FROM listing_embeddings WHERE listing_id=%s
                AND model_name=%s AND model_revision=%s AND template_version=%s""",
                (listing["id"], model_name, model_revision, template_version))
            existing = cursor.fetchone()
            if existing and existing["input_hash"] == metadata["input_hash"]:
                stats["reused"] += 1
                continue
            try:
                save_embedding(connection, listing["id"], metadata, generate_embedding(model, text))
                connection.commit()
                stats["created"] += 1
            except Exception:
                connection.rollback()
                raise
        return stats
    finally:
        cursor.close()
