import pytest

from normalizer.normalization.values import normalize_value


@pytest.mark.parametrize("value", ["16 GB", "16GB", 16])
def test_equivalent_ram_values(value):
    assert normalize_value("ram_gb", value) == 16


def test_decimal_storage_units():
    assert normalize_value("storage_gb", "1 TB") == 1000


def test_unknown_units_raise_error():
    with pytest.raises(ValueError):
        normalize_value("storage_gb", "1 TiB")


def test_false_is_preserved():
    assert normalize_value("wireless", "No") is False