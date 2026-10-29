from normalizer.models import NormalizedListing


VARIANT_FIELDS = {
    "color",
    "ram_gb",
    "storage_gb",
    "cpu",
    "screen_inches",
    "resolution",
    "refresh_rate_hz",
    "switch_type",
    "layout",
}


def identity_key(value: str | None) -> str | None:
    if value is None:
        return None

    return " ".join(value.casefold().split()) or None


def same_product(
    left: NormalizedListing,
    right: NormalizedListing,
) -> bool:
    left_gtin = identity_key(left.gtin)
    right_gtin = identity_key(right.gtin)

    if left_gtin and right_gtin:
        if left_gtin != right_gtin:
            return False

    left_brand = identity_key(left.brand)
    right_brand = identity_key(right.brand)
    left_model = identity_key(left.model_number)
    right_model = identity_key(right.model_number)

    if left_brand and right_brand and left_brand != right_brand:
        return False

    if left_model and right_model and left_model != right_model:
        return False

    if (
        left.category != "generic"
        and right.category != "generic"
        and left.category != right.category
    ):
        return False

    for field in VARIANT_FIELDS:
        a = left.specs.get(field)
        b = right.specs.get(field)

        if a is not None and b is not None:
            if isinstance(a, str) and isinstance(b, str):
                if identity_key(a) != identity_key(b):
                    return False
            elif a != b:
                return False

    matching_gtin = bool(left_gtin and left_gtin == right_gtin)
    # a shared model can include different configurations; review those candidates.
    return matching_gtin


def group_listings(
    listings: list[NormalizedListing],
) -> list[list[NormalizedListing]]:
    groups: list[list[NormalizedListing]] = []

    for listing in listings:
        compatible_groups = [
            group
            for group in groups
            if all(same_product(listing, member) for member in group)
        ]

        if len(compatible_groups) == 1:
            compatible_groups[0].append(listing)
        else:
            # Missing identity or multiple possible matches: keep separate.
            groups.append([listing])

    return groups


def variant_key(field, value):
    if value is None:
        return None
    if field in {"ram_gb", "storage_gb"}:
        return float(value)
    text = identity_key(str(value))
    if field == "cpu":
        import re
        text = re.sub(r"^(apple|intel|amd)\s+", "", text)
    return text


def check_requirements(listing, required):
    """Unknown facts require review; known hardware contradictions reject."""
    import re
    reasons, missing = [], []
    for field, expected in required.items():
        if expected is None:
            continue
        actual = listing.get("attributes", {}).get(field) if field in VARIANT_FIELDS else listing.get(field)
        if field == "cpu" and actual is not None:
            complete = re.search(r"\bm\d+\b|i[3579]-\d{4,5}|ryzen\s+[3579]\s+\d{4}", str(actual), re.I)
            if not complete:
                missing.append("cpu generation")
                continue
        if actual is None:
            missing.append(field)
        elif variant_key(field, actual) != variant_key(field, expected):
            return {"status": "rejected", "reasons": [f"{field} differs from request"]}
        else:
            reasons.append(f"{field} agrees with request")
    if missing:
        return {"status": "manual_review", "reasons": reasons + ["missing: " + ", ".join(missing)]}
    if required.get("family") and not listing.get("model_number"):
        return {"status": "manual_review", "reasons": reasons + ["manufacturer model number is missing"]}
    # exact offers require model identity plus an explicit hardware configuration
    has_identity = required.get("model_number") or required.get("family")
    exact = has_identity and all(required.get(key) is not None for key in ("ram_gb", "storage_gb", "cpu"))
    return {"status": "exact" if exact else "manual_review", "reasons": reasons}
