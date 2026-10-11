from normalizer.adapters.base import extract_records
from normalizer.models import ExtractedListing


class TargetAdapter:
    def extract(self, payload: object) -> list[ExtractedListing]:
        return extract_records(
            payload,
            retailer="target",
            field_map={
                "name": "name",
                "brand": "brand",
                "model_number": "model",
                "gtin": "upc",
                "category": "category",
                "attributes": "specs",
                "url": "url",
            },
        )