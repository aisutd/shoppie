"""Ensure both scraper entry points remain usable after integrating main."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from scraper import scraper, tech_scraper
from scraper.validator import validate_record


URL = "https://www.bestbuy.com/product/synthetic-test-laptop/TEST123"


def fixture_html():
    return (Path(__file__).parent / "fixtures/synthetic_product.html").read_text()


def test_staged_pipeline_still_returns_a_validated_laptop():
    product = validate_record(scraper.extract_product(fixture_html(), URL))
    assert product.retailer == "bestbuy"
    assert str(product.price) == "123.45"


def test_tech_collector_keeps_its_separate_database_shaped_record():
    record = tech_scraper.extract_product(fixture_html(), URL, category="Headphones")
    assert record["source"] == "bestbuy.com"
    assert record["category"] == "headphones"
    assert record["description"] is None
    assert record["product_url"] == URL


def test_availability_aliases_do_not_accept_unknown_values():
    candidate = scraper.extract_product(fixture_html(), URL)
    candidate["availability"] = "in stock"
    assert validate_record(candidate).availability == "InStock"
    candidate["availability"] = "probably available"
    with pytest.raises(ValidationError):
        validate_record(candidate)
