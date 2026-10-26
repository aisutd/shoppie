"""Checkpoint 3: turn untrusted strings into a validated Python record."""

import re
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from scraper.scraper import clean_url, identify_product


AVAILABILITY = {"InStock", "OutOfStock", "PreOrder", "PreSale", "BackOrder",
                "LimitedAvailability", "SoldOut", "Discontinued", "OnlineOnly", "InStoreOnly"}


class Laptop(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    retailer: Literal["amazon", "bestbuy", "target", "walmart"]
    product_id: str = Field(min_length=1)
    product_url: str
    title: str = Field(min_length=5, max_length=1000)
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2, allow_inf_nan=False)
    currency: Literal["USD"]
    availability: str | None = None
    seller: str | None = Field(default=None, max_length=300)
    discount: None = None  # Not extracted in this lesson. Unknown is not zero.
    observed_at: datetime
    extraction_method: Literal["json-ld", "html", "manual"]
    brand: str | None = Field(default=None, max_length=300)
    model: str | None = Field(default=None, max_length=300)
    cpu: str | None = Field(default=None, max_length=300)
    ram: str | None = Field(default=None, max_length=300)
    storage: str | None = Field(default=None, max_length=300)
    screen_size: str | None = Field(default=None, max_length=300)
    color: str | None = Field(default=None, max_length=300)
    condition: str | None = Field(default=None, max_length=300)

    @field_validator("title")
    @classmethod
    def laptop_title(cls, value):
        if not re.search(r"\b(laptop|notebook|chromebook|macbook)\b", value, re.I):
            raise ValueError("title must clearly describe a laptop")
        if re.search(r"\b(adapter|charger|sleeve|case|bag|replacement|stand)\b", value, re.I):
            raise ValueError("accessories are outside this lesson")
        return value

    @field_validator("price", mode="before")
    @classmethod
    def exact_price(cls, value):
        if isinstance(value, bool):
            raise ValueError("price must be a number, not a boolean")
        return value

    @field_validator("availability")
    @classmethod
    def explicit_availability(cls, value):
        if value is None:
            return None
        name = re.sub(r"^https?://schema\.org/", "", value)
        if name not in AVAILABILITY:
            raise ValueError("unrecognized availability; do not guess")
        return name

    @field_validator("observed_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("observation time needs a timezone")
        return value

    @model_validator(mode="after")
    def same_product(self):
        if identify_product(self.product_url) != (self.retailer, self.product_id):
            raise ValueError("URL, retailer and product ID must agree")
        return self


def validate_record(record):
    """Clean formatting on a copy, then apply the required-field rules."""
    cleaned = dict(record)
    for name, value in cleaned.items():
        if isinstance(value, str):
            cleaned[name] = value.strip()
    if isinstance(cleaned.get("title"), str):
        cleaned["title"] = " ".join(cleaned["title"].split())
    if isinstance(cleaned.get("currency"), str):
        cleaned["currency"] = cleaned["currency"].upper()
    if isinstance(cleaned.get("price"), str) and re.fullmatch(
        r"\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?", cleaned["price"]
    ):
        # This removes a thousands separator; it does not create a price/currency.
        cleaned["price"] = cleaned["price"].replace(",", "")
    if cleaned.get("seller") == "":
        cleaned["seller"] = None
    if isinstance(cleaned.get("product_url"), str):
        cleaned["product_url"] = clean_url(cleaned["product_url"])
    return Laptop.model_validate(cleaned)

