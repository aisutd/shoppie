"""Checkpoint 3: turn untrusted strings into a validated Python record."""

import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from scraper.scraper import clean_url, identify_product


AVAILABILITY = {"InStock", "OutOfStock", "PreOrder", "PreSale", "BackOrder",
                "LimitedAvailability", "SoldOut", "Discontinued", "OnlineOnly", "InStoreOnly"}
AVAILABILITY_ALIASES = {
    "instock": "InStock", "in stock": "InStock", "in_stock": "InStock",
    "outofstock": "OutOfStock", "out of stock": "OutOfStock", "out_of_stock": "OutOfStock",
    "preorder": "PreOrder", "pre-order": "PreOrder", "pre order": "PreOrder",
    "presale": "PreSale", "pre-sale": "PreSale",
    "backorder": "BackOrder", "back order": "BackOrder", "back-order": "BackOrder",
    "limitedavailability": "LimitedAvailability", "limited availability": "LimitedAvailability",
    "soldout": "SoldOut", "sold out": "SoldOut", "sold_out": "SoldOut",
    "discontinued": "Discontinued",
    "onlineonly": "OnlineOnly", "online only": "OnlineOnly",
    "instoreonly": "InStoreOnly", "in store only": "InStoreOnly", "in-store only": "InStoreOnly",
}
FUTURE_TOLERANCE = timedelta(minutes=5)

class Product(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    retailer: Literal["amazon", "bestbuy", "target", "walmart"]
    product_id: str = Field(min_length=1)
    product_url: str
    title: str = Field(min_length=5, max_length=1000)
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2, allow_inf_nan=False)
    currency: Literal["USD"]
    image_url: str | None = None
    description: str | None = None
    availability: str | None = None
    seller: str | None = Field(default=None, max_length=300)
    discount: None = None  # Not extracted in this lesson. Unknown is not zero.
    observed_at: datetime
    extraction_method: Literal["json-ld", "html", "manual"]

    @field_validator("price", mode="before")
    @classmethod
    def exact_price(cls, value):
        if isinstance(value, bool):
            raise ValueError("price must be a number, not a boolean")
        return value

    @field_validator("image_url", mode="before")
    @classmethod
    def secure_image_url(cls, value):
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise ValueError("image_url must be an HTTPS URL or null")
        try:
            parts = urlsplit(value)
        except ValueError:
            raise ValueError("image_url must be an HTTPS URL or null") from None
        if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
                or any(char.isspace() for char in value)):
            raise ValueError("image_url must be an HTTPS URL or null")
        return value

    @field_validator("availability", mode="before")
    @classmethod
    def explicit_availability(cls, value):
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("availability must be text or null")
        name = re.sub(r"^https?://schema\.org/", "", value.strip(), flags=re.I)
        if name in AVAILABILITY: 
            return name
        normalized = AVAILABILITY_ALIASES.get(name.lower())
        if normalized is None:
            raise ValueError("unrecognized availability; do not guess")
        return normalized
        

    @field_validator("observed_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("observation time needs a timezone")
        if value > datetime.now(timezone.utc) + FUTURE_TOLERANCE:
            raise ValueError("observation time cannot be in the future")
        return value

    @model_validator(mode="after")
    def same_product(self):
        if identify_product(self.product_url) != (self.retailer, self.product_id):
            raise ValueError("URL, retailer and product ID must agree")
        if self.retailer in {"target", "amazon"} and self.availability in {"OutOfStock", "SoldOut", "Discontinued"}:
            raise ValueError("Selected product is unavailable")
        return self


class Laptop(Product):
    @field_validator("title")
    @classmethod
    def laptop_title(cls, value):
        if not re.search(r"\b(laptop|notebook|chromebook|macbook|thinkpad|thinkbook|ideapad|zenbook|vivobook)\b", value, re.I):
            raise ValueError("title must clearly describe a laptop")
        if re.search(r"\b(adapter|charger|sleeve|case|bag|backpack|replacement|stand|battery|"
                     r"docking|dock|cover|protector|skin|cooling)\b", value, re.I):
            raise ValueError("accessories are outside this lesson")
        return value


def validate_record(record, product_type=Laptop):
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
    return product_type.model_validate(cleaned)

