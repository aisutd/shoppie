"""Later stage: retrieve candidate matches; do not automatically merge records.

JSON vectors loaded into Python are sufficient for a small beta catalog.
MySQL JSON storage is not a vector-search index.
"""


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Measure description similarity; the score is not a match probability."""
    # TODO: Require equal dimensions, finite values and nonzero vectors.
    # Compute dot product / (norm(left) * norm(right)).
    raise NotImplementedError("Mentee TODO later: calculate similarity")


def assess_identity(left: dict, right: dict) -> dict:
    """Explain whether explicit identifiers/specifications support a match."""
    # TODO: Return {status: confirmed/rejected/uncertain, reasons: [...]}.
    # Check GTIN, brand/model, category, storage, RAM, color and pack quantity.
    # Contradictions reject; missing specifications do not prove agreement.
    # Model-level agreement without variant evidence may remain uncertain.
    # Condition differs from physical product identity, but it must be exposed
    # and filtered when users ask for equivalent offers (e.g. new only).
    raise NotImplementedError("Mentee TODO later: assess candidate identity")


def find_candidates(connection, listing_id: int, model_name: str,
                    model_revision: str, template_version: str,
                    limit: int = 5) -> list[dict]:
    """Return similar listings from other retailers with scores and reasons."""
    # TODO: Load target; narrow by category and other retailers.
    # Use embeddings from identical model/revision/template configuration.
    # Check stored input_hash against current build_text() for ALL vectors.
    # Exclude stale/missing vectors; score and attach assess_identity output.
    # Return top candidates; do not persist matches or use arbitrary threshold.
    raise NotImplementedError("Mentee TODO later: retrieve candidates")
