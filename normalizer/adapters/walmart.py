from normalizer.adapters.base import extract_records
from normalizer.models import ExtractedListing


class WalmartAdapter:
    def extract(self, payload: object) -> list[ExtractedListing]:
        return extract_records(
            payload,
            retailer="walmart",
            field_map={
                "name": "productName",
                "brand": "brand",
                "model_number": "modelNumber",
                "gtin": "gtin",
                "category": "productType",
                "attributes": "specifications",
                "url": "productUrl",
            },
        )