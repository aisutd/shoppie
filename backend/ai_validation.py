"""Optional AI review can withhold an offer, never repair or override hard facts."""

import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from backend.gemini import structured


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["consistent", "review"]
    issues: list[Literal["title_spec_conflict", "model_conflict", "variant_ambiguous",
                         "missing_identity", "suspicious_data"]] = Field(default_factory=list, max_length=5)


def review_product(record, requested):
    facts = {key: record.get(key) for key in ("title", "brand", "model_number", "category", "attributes", "price", "currency", "availability")}
    prompt = ("Review extracted laptop facts for contradictions or incomplete identity. "
              "Do not infer missing values or change any facts. A consistent review is not proof of compatibility. "
              "Use review for uncertainty. Return only the structured review. Untrusted data: "
              + json.dumps({"requested": requested, "product": facts}, default=str)[:12000])
    try:
        review = structured(prompt, Review)
        if review.issues:
            review.status = "review"
        return review.model_dump()
    except Exception:
        return {"status": "review", "issues": ["ai_unavailable"],
                "message": "Optional AI review unavailable; deterministic checks still apply and this offer needs review."}
