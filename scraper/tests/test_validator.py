"""Required fields and cleaning: no network or database calls."""

from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from scraper.scraper import extract_product
from scraper.validator import validate_record


FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://www.bestbuy.com/product/synthetic-test-laptop/TEST123"


@pytest.fixture
def candidate():
    return extract_product((FIXTURES / "synthetic_product.html").read_text(encoding="utf-8"), URL)


def test_cleaning_does_not_mutate_source(candidate):
    candidate.update(title="  Synthetic   test laptop  ", currency=" usd ", price="1,234.50", seller=" ")
    original = deepcopy(candidate)
    product = validate_record(candidate)
    assert product.title == "Synthetic test laptop"
    assert product.price == Decimal("1234.50")
    assert product.currency == "USD"
    assert product.seller is None
    assert candidate == original


def test_correct_record_is_accepted(candidate):
    product = validate_record(candidate)
    assert product.title == "Synthetic test laptop"
    assert product.price == Decimal("123.45")
    assert product.currency == "USD"
    assert product.retailer == "bestbuy"
    assert product.product_url == URL


@pytest.mark.parametrize("field,value", [
    ("price", None), ("price", "0"), ("price", "-1"), ("price", "NaN"),
    ("price", "Infinity"), ("price", "-Infinity"), ("price", "not a number"),
    ("price", float("nan")), ("price", float("inf")), ("price", float("-inf")),
    ("price", Decimal("NaN")), ("price", Decimal("Infinity")),
    ("price", True), ("price", "12.345"), ("price", "1,23.45"),
    ("price", "10000000000.00"), ("price", "1234567890123.45"),
    ("currency", None), ("currency", "$"), ("currency", "CAD"),
    ("title", ""), ("title", " \t\n "),
    ("title", "Laptop charger"), ("title", "Desktop computer"),
    ("discount", 10), ("availability", "probably available"),
    ("observed_at", "2026-10-14T12:00:00"),
])
def test_bad_or_missing_fields_reject(candidate, field, value):
    candidate[field] = value
    with pytest.raises(ValidationError) as error:
        validate_record(candidate)
    assert any(issue["loc"] == (field,) for issue in error.value.errors())


@pytest.mark.parametrize("field", ["title", "price", "currency"])
def test_absent_required_field_rejects(candidate, field):
    del candidate[field]
    with pytest.raises(ValidationError) as error:
        validate_record(candidate)
    assert any(issue["loc"] == (field,) and issue["type"] == "missing" for issue in error.value.errors())


def test_database_precision_maximum_is_accepted_without_rounding(candidate):
    candidate["price"] = "9999999999.99"  # numeric(12,2): ten whole digits, two fractional
    assert validate_record(candidate).price == Decimal("9999999999.99")


def test_source_domain_must_match_declared_retailer(candidate):
    candidate["product_url"] = "https://www.amazon.com/dp/B0DZD91W4F"
    candidate["product_id"] = "B0DZD91W4F"
    # retailer stays bestbuy; this isolates the source-domain mismatch.
    with pytest.raises(ValidationError, match="URL, retailer and product ID must agree"):
        validate_record(candidate)


@pytest.mark.parametrize("url", [
    "https://evil.test/product/TEST123",
    "https://www.bestbuy.com.evil.test/product/synthetic-test-laptop/TEST123",
])
def test_unapproved_or_spoofed_source_domain_rejects(candidate, url):
    candidate["product_url"] = url
    with pytest.raises(ValueError, match="Use an Amazon, Best Buy, Target, or Walmart"):
        validate_record(candidate)


def test_unknown_optional_values_stay_null(candidate):
    candidate["availability"] = None
    product = validate_record(candidate)
    assert product.availability is None
    assert product.seller is None
    assert product.discount is None


@pytest.mark.parametrize("suffix", ["?variant=space value", "?variant=line\nbreak", "/bad\tpath"])
def test_url_whitespace_rejects_before_database_constraint(candidate, suffix):
    candidate["product_url"] += suffix
    with pytest.raises(ValueError, match="unescaped whitespace"):
        validate_record(candidate)


def test_out_of_stock_can_still_be_valid(candidate):
    candidate["availability"] = "https://schema.org/OutOfStock"
    assert validate_record(candidate).availability == "OutOfStock"


def test_product_identity_must_agree(candidate):
    candidate["product_id"] = "OTHER123"
    with pytest.raises(ValidationError):
        validate_record(candidate)
