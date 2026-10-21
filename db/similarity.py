"""Explain candidate identity; this module never merges retailer listings."""

import math

VARIANT_FIELDS = ("ram_gb", "storage_gb", "color", "size", "screen_inches",
                  "pack_quantity", "cpu", "resolution")


def cosine_similarity(left, right):
    if not left or len(left) != len(right):
        raise ValueError("vectors must have the same nonzero dimensions")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
           for value in list(left) + list(right)):
        raise ValueError("vectors must contain finite numbers")
    left_length = math.sqrt(sum(value * value for value in left))
    right_length = math.sqrt(sum(value * value for value in right))
    if not math.isfinite(left_length) or not math.isfinite(right_length) or left_length == 0 or right_length == 0:
        raise ValueError("vectors must have finite nonzero lengths")
    return sum(a * b for a, b in zip(left, right)) / (left_length * right_length)


def comparable(value):
    return " ".join(value.casefold().split()) if isinstance(value, str) else value


def assess_identity(left, right):
    reasons = []
    conflicts = []
    for field in ("gtin", "brand", "model_number", "category"):
        a, b = left.get(field), right.get(field)
        if a is not None and b is not None:
            if comparable(a) != comparable(b):
                conflicts.append(f"{field} differs")
            else:
                reasons.append(f"{field} agrees")
    left_attrs = left.get("attributes") or {}
    right_attrs = right.get("attributes") or {}
    for field in VARIANT_FIELDS:
        a, b = left_attrs.get(field), right_attrs.get(field)
        if a is not None and b is not None:
            if comparable(a) != comparable(b):
                conflicts.append(f"{field} differs")
            else:
                reasons.append(f"{field} agrees")
    if conflicts:
        return {"status": "rejected", "reasons": conflicts}
    if left.get("gtin") and right.get("gtin") and comparable(left["gtin"]) == comparable(right["gtin"]):
        return {"status": "confirmed", "reasons": reasons}
    if left.get("brand") and left.get("model_number") and right.get("brand") and right.get("model_number"):
        reasons.append("brand and model identify a candidate; missing variant data needs review")
    else:
        reasons.append("insufficient exact identifiers")
    return {"status": "uncertain", "reasons": reasons}
