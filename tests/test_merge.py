from normalizer.merge import merge_group
from normalizer.models import NormalizedListing, Source


def listing(retailer, specs):
    return NormalizedListing(
        source=Source(retailer=retailer),
        name="Example Headphones",
        brand="Example",
        model_number="HP1",
        category="headphones",
        specs=specs,
    )


def test_complementary_specs_merge():
    result = merge_group([
        listing("target", {"wireless": True}),
        listing("walmart", {"noise_cancelling": False}),
    ])

    assert result.specs == {
        "wireless": True,
        "noise_cancelling": False,
    }
    assert not result.conflicts


def test_conflicting_specs_remain_unresolved():
    result = merge_group([
        listing("target", {"wireless": True}),
        listing("walmart", {"wireless": False}),
    ])

    assert "wireless" not in result.specs
    assert result.conflicts[0].field == "specs.wireless"
    assert len(result.conflicts[0].observations) == 2