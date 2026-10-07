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
    matching_model = bool(
        left_brand
        and left_model
        and left_brand == right_brand
        and left_model == right_model
    )

    return matching_gtin or matching_model


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