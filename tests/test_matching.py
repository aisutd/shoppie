from normalizer.matching import group_listings, same_product
from normalizer.models import NormalizedListing, Source


def listing(retailer, specs):
    return NormalizedListing(
        source=Source(retailer=retailer),
        name="Example Laptop",
        brand="Example",
        model_number="EX14",
        category="laptop",
        specs=specs,
    )


def test_different_variants_do_not_match():
    a = listing("target", {"ram_gb": 8})
    b = listing("walmart", {"ram_gb": 16})

    assert not same_product(a, b)


def test_missing_specs_do_not_bridge_conflicting_variants():
    a = listing("target", {"ram_gb": 8})
    b = listing("walmart", {})
    c = listing("bestbuy", {"ram_gb": 16})

    groups = group_listings([a, b, c])

    assert len(groups) == 2
    assert not any(a in group and c in group for group in groups)