from normalizer.adapters.base import extract_records
from normalizer.models import ExtractedListing


class BestBuyAdapter:
    def extract(self, payload: object) -> list[ExtractedListing]:
        return extract_records(
            payload,
            retailer="bestbuy",
            field_map={
                "name": "title",
                "brand": "manufacturer",
                "model_number": "modelNumber",
                "gtin": "upc",
                "category": "category",
                "attributes": "details",
                "url": "url",
            },
        )