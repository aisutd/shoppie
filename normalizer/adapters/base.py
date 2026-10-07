from typing import Any, Protocol

from normalizer.models import ExtractedListing, Source


class RetailerAdapter(Protocol):
    def extract(self, payload: object) -> list[ExtractedListing]:
        ...


def extract_records(
    payload: object,
    retailer: str,
    field_map: dict[str, str],
) -> list[ExtractedListing]:
    records = payload if isinstance(payload, list) else [payload]
    listings = []

    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Each product must be a JSON object.")

        def get(field: str) -> Any:
            return record.get(field_map[field])

        name = get("name")

        if not isinstance(name, str) or not name.strip():
            raise ValueError("Product name must be a nonempty string.")

        attributes = get("attributes")
        if attributes is None:
            attributes = {}

        if not isinstance(attributes, dict):
            raise ValueError("Product attributes must be a JSON object.")

        gtin = get("gtin")

        # Identifiers should be strings, preserving leading zeros.
        if gtin is not None and not isinstance(gtin, str):
            raise ValueError("GTIN must be a string.")

        listings.append(
            ExtractedListing(
                source=Source(
                    retailer=retailer,
                    url=get("url"),
                ),
                name=name.strip(),
                brand=get("brand"),
                model_number=get("model_number"),
                gtin=gtin,
                category=get("category"),
                attributes=attributes,
            )
        )

    return listings