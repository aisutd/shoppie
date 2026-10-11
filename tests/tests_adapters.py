import pytest

from normalizer.adapters import ADAPTERS
from normalizer.loader import load_json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("retailer", ["target", "walmart", "bestbuy"])
def test_adapter_extracts_example(retailer):
    payload = load_json(ROOT / "data/input" / f"{retailer}.json")
    listings = ADAPTERS[retailer].extract(payload)

    assert len(listings) == 1
    assert listings[0].source.retailer == retailer
    assert listings[0].model_number == "EX14-16-512"
    assert listings[0].attributes