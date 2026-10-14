"""Checkpoint 3: turn untrusted strings into a validated Python record."""

import re
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from lesson.pages import identify_product


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
    extraction_method: Literal["json-ld", "html"]

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
