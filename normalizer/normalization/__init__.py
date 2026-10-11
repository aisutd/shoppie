from normalizer.models import (
    ExtractedListing,
    NormalizedListing,
    ProcessingIssue,
)
from normalizer.normalization.categories import normalize_category
from normalizer.normalization.fields import normalize_field
from normalizer.normalization.values import normalize_value


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None

    return " ".join(value.split()) or None


def normalize_listing(
    listing: ExtractedListing,
) -> tuple[NormalizedListing, list[ProcessingIssue]]:
    category = normalize_category(listing.category)
    specs = {}
    unmapped = {}
    issues = []
    rejected_fields = set()

    for raw_name, raw_value in listing.attributes.items():
        if raw_value is None:
            continue

        field_name = normalize_field(category, raw_name)

        if field_name is None:
            unmapped[raw_name] = raw_value
            continue

        try:
            value = normalize_value(field_name, raw_value)
        except ValueError as error:
            unmapped[raw_name] = raw_value
            issues.append(
                ProcessingIssue(
                    source=listing.source,
                    field=raw_name,
                    message=str(error),
                )
            )
            continue

        # Don't silently overwrite contradictory aliases in one listing.
        if field_name in rejected_fields:
            unmapped[raw_name] = raw_value
            continue

        if field_name in specs and specs[field_name] != value:
            unmapped[raw_name] = raw_value
            unmapped[f"previous_normalized:{field_name}"] = specs.pop(field_name)
            rejected_fields.add(field_name)

            issues.append(
                ProcessingIssue(
                    source=listing.source,
                    field=field_name,
                    message="Conflicting values within the same listing.",
                )
            )
            continue

        specs[field_name] = value

    normalized = NormalizedListing(
        source=listing.source,
        name=listing.name,
        brand=clean_text(listing.brand),
        model_number=clean_text(listing.model_number),
        gtin=clean_text(listing.gtin),
        category=category,
        specs=specs,
        unmapped_attributes=unmapped,
    )

    return normalized, issues