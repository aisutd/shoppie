"""Bounded, request-scoped discovery -> extraction -> validation -> persistence.

No prompts, no model-generated URLs, no deletion of catalog rows. Every request
attempts discovery; a lock prevents simultaneous browser/network fan-out.
"""

import logging
import re
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

from scraper.bestbuy_search import (
    DiscoveryError,
    MAX_PRODUCTS,
    discover_bestbuy_urls,
    recover_search_card,
)
from scraper.walmart_search import (
    WalmartDiscoveryError,
    discover_walmart_products,
)
from scraper import tech_scraper


logger = logging.getLogger(__name__)
_collection_lock = threading.Lock()
COLLECTION_SECONDS = 55
NON_TECH_CATEGORIES = {
    "toys-games", "kitchen-dining", "home-garden", "clothing", "office-supplies",
    "toys", "apparel", "furniture", "groceries", "beauty", "sports-outdoors",
    "toys-and-games", "kitchen", "kitchenware", "home-decor", "home-goods",
}
OBVIOUS_NON_TECH = re.compile(
    r"\blego\b.*\b(?:building|bricks?|sets?)\b|"
    r"\bbarbie\s+(?:dreamhouse|dolls?)\b|"
    r"\bkitchenaid\b.*\bmixers?\b", re.I,
)


def is_tech_product(product):
    """Reject clear non-tech evidence; retain unknown and recognized tech items."""
    category = str(product.get("category") or "").strip().lower().replace("_", "-")
    title = str(product.get("title") or "")
    # LEGO/Barbie video games remain eligible; these rules target physical goods.
    obvious_non_tech = OBVIOUS_NON_TECH.search(title) and not re.search(r"\bvideo\s+games?\b", title, re.I)
    return not obvious_non_tech and category not in NON_TECH_CATEGORIES and infer_category(title) not in NON_TECH_CATEGORIES


class CollectedProduct(BaseModel):
    """Validate tech records before a web request is allowed to save them."""

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
    )

    title: str = Field(
        min_length=5,
        max_length=1000,
    )
    description: str | None = None
    image_url: str | None = None

    price: Decimal = Field(
        gt=0,
        max_digits=12,
        decimal_places=2,
        allow_inf_nan=False,
    )

    currency: Literal["USD"]
    product_url: str

    source: Literal[
        "bestbuy.com",
        "walmart.com",
    ]

    category: str
    scraped_at: datetime

    @field_validator("price", mode="before")
    @classmethod
    def reject_boolean(cls, value):
        if isinstance(value, bool):
            raise ValueError(
                "Price must be a monetary amount."
            )
        return value

    @field_validator("product_url")
    @classmethod
    def valid_product_url(cls, value):
        value = tech_scraper.clean_url(value)

        retailer = tech_scraper.identify_product(value)[0]

        if retailer not in {
            "bestbuy",
            "walmart",
        }:
            raise ValueError(
                "Expected a supported Best Buy or Walmart product page."
            )

        return value

    @field_validator("image_url")
    @classmethod
    def https_image(cls, value):
        if value is None:
            return None

        parts = urlsplit(value)

        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.username
            or parts.password
            or any(c.isspace() for c in value)
        ):
            raise ValueError(
                "Expected an HTTPS image URL."
            )

        return value

    @field_validator("category")
    @classmethod
    def category_slug(cls, value):
        return tech_scraper.normalize_category(value)

    @field_validator("scraped_at")
    @classmethod
    def aware_time(cls, value):
        if value.utcoffset() is None:
            raise ValueError(
                "Collection timestamp must include a timezone."
            )

        return value.astimezone(timezone.utc)


def infer_category(title):
    """Classify from title evidence; unknown products are not assumed electronic."""

    import re

    for category, pattern in (
        (
            "toys-games",
            r"\b(?:toys?|shopkins|dolls?|action figures?|playsets?|plush|"
            r"stuffed animals?|board games?|puzzles?)\b",
        ),
        (
            "kitchen-dining",
            r"\b(?:mugs?|cups?|tumblers?|drinkware|cookware|dinnerware|"
            r"plates?|bowls?|kitchen)\b",
        ),
        (
            "home-garden",
            r"\b(?:furniture|bedding|garden|patio|decor|lamps?|rugs?|curtains?)\b",
        ),
        (
            "clothing",
            r"\b(?:shirts?|jackets?|shoes|sneakers|clothing|apparel)\b",
        ),
        (
            "office-supplies",
            r"\b(?:spiral notebooks?|binders?|pens?|paper|office supplies)\b",
        ),
        (
            "gaming",
            r"\b(?:video games?|game controllers?|playstation|xbox|"
            r"nintendo switch)\b",
        ),
        (
            "headphones",
            r"headphones?|earbuds?|airpods",
        ),
        (
            "phones",
            r"iphone|smartphones?|(?:cell|mobile)\s+phones?|"
            r"galaxy\s+s\d|pixel\s+\d",
        ),
        (
            "tablets",
            r"ipad|tablet",
        ),
        (
            "monitors",
            r"monitor",
        ),
        (
            "laptop-accessories",
            r"\b(?:laptop|notebook|macbook)\s+"
            r"(?:cases?|sleeves?|bags?|covers?|stands?)\b",
        ),
        (
            "laptops",
            r"laptop|notebook|macbook|chromebook|thinkpad|"
            r"zenbook|vivobook|ideapad",
        ),
        (
            "televisions",
            r"television|\btv\b",
        ),
        (
            "keyboards",
            r"keyboard",
        ),
        (
            "mice",
            r"\b(?:mouse|mice)\b",
        ),
        (
            "cameras",
            r"\bcameras?\b",
        ),
        (
            "speakers",
            r"\b(?:speakers?|soundbars?)\b",
        ),
        (
            "storage",
            r"\b(?:ssds?|hard drives?|flash drives?)\b",
        ),
        (
            "computer-accessories",
            r"\b(?:chargers?|adapters?|docks?|hubs?|webcams?)\b",
        ),
    ):
        if re.search(
            pattern,
            title or "",
            re.I,
        ):
            return category

    return "other"


def collect_live_products(
    query,
    database,
    limit=MAX_PRODUCTS,
    match_record=None,
):
    """Discover, validate, and save Best Buy and Walmart products."""

    report = {
        "source": "bestbuy.com,walmart.com",
        "status": "failed",
        "discovered": 0,
        "collected": 0,
        "saved": 0,
        "failed": 0,
        "failed_saves": 0,
        "errors": [],
        "failure_code": None,
        "result_source": "live",
        "message": "",
        "recovered": 0,
    }

    if not _collection_lock.acquire(
        blocking=False
    ):
        report.update(
            status="busy",
            message=(
                "Live retailer collection is busy. "
                "No live results are available; "
                "try again shortly."
            ),
        )

        return [], report

    started = time.monotonic()
    products = []

    try:
        urls = []
        bestbuy_urls = []
        walmart_urls = []
        walmart_records = []
        discovery_errors = []

        result_limit = max(1, min(limit, MAX_PRODUCTS))
        result_budget = result_limit * 2

        #
        # BEST BUY DISCOVERY
        #
        try:
            bestbuy_urls = discover_bestbuy_urls(
                query,
                limit=result_limit,
            )

        except Exception as error:
            code = (
                error.code
                if isinstance(
                    error,
                    DiscoveryError,
                )
                else "unexpected_error"
            )

            logger.warning(
                "Best Buy discovery failed (%s)",
                code,
            )
            report["failure_code"] = code

            discovery_errors.append(
                str(error)
                if isinstance(
                    error,
                    DiscoveryError,
                )
                else (
                    "Best Buy discovery encountered "
                    "an unexpected error."
                )
            )

        #
        # WALMART DISCOVERY
        #
        try:
            walmart_records = discover_walmart_products(
                query,
                limit=result_limit,
            )
            walmart_urls = [
                product["product_url"]
                for product in walmart_records
            ]

        except Exception as error:
            code = (
                error.code
                if isinstance(error, WalmartDiscoveryError)
                else "unexpected_error"
            )

            logger.warning(
                "Walmart discovery failed (%s)",
                code,
            )

            discovery_errors.append(
                str(error)
                if isinstance(error, WalmartDiscoveryError)
                else "Walmart discovery encountered an unexpected error."
            )
            if report["failure_code"] is None:
                report["failure_code"] = code

        #
        # Alternate retailers so one can fill the result budget if the other
        # has few or no matches.
        #
        seen_urls = set()
        for index in range(max(len(bestbuy_urls), len(walmart_urls))):
            for retailer_urls in (bestbuy_urls, walmart_urls):
                if index >= len(retailer_urls):
                    continue
                candidate_url = retailer_urls[index]
                if candidate_url in seen_urls:
                    continue
                seen_urls.add(candidate_url)
                urls.append(candidate_url)
                if len(urls) >= result_budget:
                    break
            if len(urls) >= result_budget:
                break

        report["discovered"] = len(urls)
        walmart_records_by_url = {
            product["product_url"]: product
            for product in walmart_records
        }
        report["errors"].extend(
            discovery_errors
        )

        #
        # Neither retailer returned anything.
        #
        if not urls:
            report.update(
                status="no_results",
                message=(
                    "Best Buy and Walmart returned "
                    "no usable product links. "
                    "No live results are available."
                ),
            )

            return [], report

        #
        # PROCESS EACH PRODUCT URL
        #
        for index, url in enumerate(urls):
            remaining = (
                COLLECTION_SECONDS
                - (
                    time.monotonic()
                    - started
                )
            )

            if remaining <= 2:
                report["failed"] += (
                    len(urls) - index
                )

                report["errors"].append(
                    "Collection time budget reached; "
                    "remaining pages were not checked."
                )

                break

            retailer, _ = (
                tech_scraper.identify_product(
                    url
                )
            )

            retailer_name = {
                "bestbuy": "Best Buy",
                "walmart": "Walmart",
            }.get(
                retailer,
                retailer,
            )

            try:
                recovered = False

                if url in walmart_records_by_url:
                    raw = dict(
                        walmart_records_by_url[url]
                    )
                else:
                    #
                    # Fetch the actual product page.
                    #
                    try:
                        html, final_url = (
                            tech_scraper.fetch_page(
                                url,
                                timeout=min(
                                    10,
                                    remaining,
                                ),
                                warmup=False,
                            )
                        )

                    except ValueError as fetch_error:
                        #
                        # Only Best Buy currently has
                        # exact-product search-card recovery.
                        #
                        if (
                            retailer != "bestbuy"
                            or (
                                "Page request failed or timed out:"
                                not in str(fetch_error)
                            )
                        ):
                            raise

                        remaining = (
                            COLLECTION_SECONDS
                            - (
                                time.monotonic()
                                - started
                            )
                        )

                        if remaining <= 2:
                            raise

                        raw = recover_search_card(
                            url,
                            timeout=min(
                                8,
                                remaining,
                            ),
                        )

                        recovered = True

                    #
                    # Normal detail-page extraction.
                    #
                    if not recovered:
                        if (
                            tech_scraper.identify_product(
                                final_url
                            )
                            != tech_scraper.identify_product(
                                url
                            )
                            or urlsplit(
                                final_url
                            ).query
                            != urlsplit(
                                url
                            ).query
                        ):
                            raise ValueError(
                                "Redirect changed the "
                                "requested product/variant."
                            )

                        raw = (
                            tech_scraper.extract_product(
                                html,
                                final_url,
                            )
                        )

                #
                # Correct category from product title.
                #
                if not is_tech_product(raw):
                    continue
                raw["category"] = (
                    infer_category(
                        raw.get("title")
                    )
                )

                #
                # Validate normalized record.
                #
                record = (
                    CollectedProduct
                    .model_validate(raw)
                    .model_dump(
                        mode="json"
                    )
                )

                report["collected"] += 1

                if not is_tech_product(record) or (match_record is not None and not match_record(record)):
                    continue

                if recovered:
                    report["recovered"] += 1

            except Exception as error:
                if isinstance(
                    error,
                    ValidationError,
                ):
                    fields = sorted(
                        {
                            ".".join(
                                map(
                                    str,
                                    issue["loc"],
                                )
                            )
                            for issue
                            in error.errors()
                        }
                    )

                    reason = (
                        "invalid or missing "
                        + ", ".join(fields)
                    )

                elif isinstance(
                    error,
                    ImportError,
                ):
                    reason = (
                        "a required scraper "
                        "dependency is missing"
                    )

                elif isinstance(
                    error,
                    ValueError,
                ):
                    message = str(error)

                    if message.startswith(
                        "Public model search"
                    ):
                        reason = (
                            "the detail-page request "
                            "failed and exact-product "
                            "search-card recovery was "
                            "unavailable"
                        )

                    elif (
                        "timed out" in message
                        or "request failed" in message
                    ):
                        reason = (
                            "the product-page request "
                            "failed or timed out"
                        )

                    elif (
                        "bot check" in message
                        or "access-denied" in message
                    ):
                        reason = (
                            "the retailer returned "
                            "a verification page"
                        )

                    elif (
                        "extract product title or price"
                        in message
                    ):
                        reason = (
                            "the page did not contain "
                            "an extractable title "
                            "and price"
                        )

                    elif (
                        "Redirect changed"
                        in message
                    ):
                        reason = (
                            "a redirect changed "
                            "the selected product "
                            "or variant"
                        )

                    else:
                        reason = (
                            "the product page "
                            "could not be parsed"
                        )

                else:
                    reason = (
                        "an unexpected scraper "
                        "error occurred"
                    )

                logger.warning(
                    "%s candidate %d: %s (%s)",
                    retailer_name,
                    index + 1,
                    reason,
                    type(error).__name__,
                )

                report["failed"] += 1

                report["errors"].append(
                    f"{retailer_name} candidate "
                    f"{index + 1}: {reason}."
                )

                continue

            #
            # SAVE VALID PRODUCT
            #
            try:
                remaining = max(
                    1,
                    COLLECTION_SECONDS
                    - (
                        time.monotonic()
                        - started
                    ),
                )

                tech_scraper.upload_to_supabase(
                    record,
                    database=database,
                    timeout=min(
                        10,
                        remaining,
                    ),
                )

                report["saved"] += 1
                products.append(record)

            except Exception:
                logger.warning(
                    "%s candidate %d "
                    "could not be saved",
                    retailer_name,
                    index + 1,
                )

                report["failed_saves"] += 1

                report["errors"].append(
                    f"{retailer_name} candidate "
                    f"{index + 1} was collected "
                    "but its database save "
                    "was not confirmed."
                )

        #
        # FINAL REPORT
        #
        if report["collected"]:
            partial = (
                report["failed"]
                or report["failed_saves"]
                or discovery_errors
            )

            report.update(
                status=(
                    "partial"
                    if partial
                    else "complete"
                ),
                result_source="live",
            )

            bestbuy_count = sum(
                1
                for product in products
                if product.get("source")
                == "bestbuy.com"
            )

            walmart_count = sum(
                1
                for product in products
                if product.get("source")
                == "walmart.com"
            )

            report["message"] = (
                f"Validated {report['collected']} "
                f"live listing(s); {len(products)} eligible saved listing(s): "
                f"{bestbuy_count} Best Buy and "
                f"{walmart_count} Walmart; "
                f"{report['saved']} database "
                "save(s) confirmed."
            )

            if partial:
                report["message"] += (
                    " Some retailer pages, discovery "
                    "requests, or saves failed; "
                    "coverage is incomplete."
                )

            if report["recovered"]:
                report["message"] += (
                    f" {report['recovered']} "
                    "Best Buy listing(s) were "
                    "recovered from exact-product "
                    "search cards because their "
                    "detail-page requests failed."
                )

        else:
            report["message"] = (
                "No Best Buy or Walmart pages "
                "could be validated. "
                "No live results are available."
            )

        return products, report

    finally:
        _collection_lock.release()
