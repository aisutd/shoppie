"""Later stage: enrich stored listings after Steps 1-6 work.

Run as a separate batch; ingestion and SQL retrieval never require a model.
Use a single-vector SentenceTransformer and record its exact revision.
"""


def build_text(listing: dict) -> str | None:
    """Describe identity only; offers and retailer metadata stay out."""
    parts = [listing.get("brand"), listing.get("title"), listing.get("model_number")]
    attributes = listing.get("attributes") or {}
    if not isinstance(attributes, dict):
        raise ValueError("attributes must be an object")
    identity_fields = {"color", "ram_gb", "storage_gb", "screen_inches",
                       "cpu", "resolution", "pack_quantity", "size"}
    for key in sorted(identity_fields & attributes.keys()):
        value = attributes[key]
        if value is not None:
            parts.append(f"{key}: {value}")
    text = " | ".join(str(part).strip() for part in parts if part is not None and str(part).strip())
    return text or None


def generate_embedding(model, text: str) -> list[float]:
    """Turn one description into a normalized numerical vector."""
    # TODO: Encode with normalize_embeddings=True; convert output to list.
    # Validate finite values/dimensions; derive dimension from chosen model.
    raise NotImplementedError("Mentee TODO later: generate vector")


def save_embedding(connection, listing_id: int, metadata: dict, vector: list[float]) -> None:
    """Store a reproducible vector and replace an outdated one for this config."""
    # metadata: model_name, model_revision, template_version, input_text,
    # input_hash (SHA-256), dimensions, created_at (UTC).
    # TODO: Parameterized insert/update, JSON vector, caller owns transaction.
    raise NotImplementedError("Mentee TODO later: store embedding")


def refresh_embeddings(connection, model, model_name: str, model_revision: str,
                       template_version: str) -> dict:
    """Generate only missing/changed descriptions using one loaded model."""
    # TODO: Read listings; build_text; hash text; compare saved configuration.
    # Reuse unchanged vectors; generate/save changed vectors; commit each row.
    # Price-only updates do not change input text. Return created/reused/skipped.
    raise NotImplementedError("Mentee TODO later: refresh embeddings")
