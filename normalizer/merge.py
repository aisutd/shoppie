from normalizer.models import (
    CanonicalProduct,
    FieldConflict,
    FieldEvidence,
    NormalizedListing,
)


RETAILER_PRIORITY = {
    "amazon": 0,
    "target": 1,
    "walmart": 2,
    "bestbuy": 3,
}


def merge_field(
    field_name: str,
    observations: list[FieldEvidence],
) -> tuple[object | None, FieldConflict | None]:
    if not observations:
        return None, None

    first_value = observations[0].value

    def comparison_key(value: object) -> object:
        if isinstance(value, str):
            return " ".join(value.casefold().split())
        return value

    if all(
        comparison_key(item.value) == comparison_key(first_value)
        for item in observations
    ):
        return first_value, None

    return None, FieldConflict(
        field=field_name,
        observations=observations,
    )


def merge_group(
    listings: list[NormalizedListing],
) -> CanonicalProduct:
    if not listings:
        raise ValueError("Cannot merge an empty group.")

    ordered = sorted(
        listings,
        key=lambda item: (
            RETAILER_PRIORITY.get(item.source.retailer, 999),
            item.source.retailer,
            item.source.url or "",
            item.name,
        ),
    )

    product = CanonicalProduct(
        name=ordered[0].name,
        sources=[listing.source for listing in ordered],
    )

    product.evidence["name"] = [
        FieldEvidence(source=item.source, value=item.name)
        for item in ordered
    ]

    for field in ("brand", "model_number", "gtin", "category"):
        observations = []

        for listing in ordered:
            value = getattr(listing, field)

            if value is None or (field == "category" and value == "generic"):
                continue

            observations.append(
                FieldEvidence(source=listing.source, value=value)
            )

        if observations:
            product.evidence[field] = observations

        value, conflict = merge_field(field, observations)

        if conflict:
            product.conflicts.append(conflict)
        else:
            setattr(product, field, value)

    spec_names = sorted({
        name
        for listing in ordered
        for name in listing.specs
    })

    for name in spec_names:
        observations = [
            FieldEvidence(
                source=listing.source,
                value=listing.specs[name],
            )
            for listing in ordered
            if name in listing.specs
        ]

        field_path = f"specs.{name}"
        product.evidence[field_path] = observations
        value, conflict = merge_field(field_path, observations)

        if conflict:
            product.conflicts.append(conflict)
        else:
            product.specs[name] = value

    for listing in ordered:
        for name, value in listing.unmapped_attributes.items():
            product.unmapped_attributes.setdefault(name, []).append(
                FieldEvidence(source=listing.source, value=value)
            )

    return product