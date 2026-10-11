from pathlib import Path

from normalizer.adapters import ADAPTERS
from normalizer.loader import load_json, save_result
from normalizer.matching import group_listings
from normalizer.merge import merge_group
from normalizer.models import NormalizationResult
from normalizer.normalization import normalize_listing


def normalize_files(
    inputs: dict[str, Path],
    output_path: Path,
) -> NormalizationResult:
    listings = []
    issues = []

    for retailer, path in inputs.items():
        adapter = ADAPTERS.get(retailer)

        if adapter is None:
            raise ValueError(f"No adapter registered for {retailer!r}")

        payload = load_json(path)
        extracted_listings = adapter.extract(payload)

        for extracted in extracted_listings:
            listing, listing_issues = normalize_listing(extracted)
            listings.append(listing)
            issues.extend(listing_issues)

    products = [
        merge_group(group)
        for group in group_listings(listings)
    ]

    result = NormalizationResult(
        products=products,
        issues=issues,
    )

    save_result(result, output_path)
    return result