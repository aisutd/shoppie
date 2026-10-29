"""Small validated request and response types shared by API and dashboard."""

from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q: str = Field(min_length=1, max_length=500)
    category: str | None = "laptop"
    brand: str | None = None
    min_price: Decimal | None = Field(default=None, ge=0)
    max_price: Decimal | None = Field(default=None, ge=0)
    availability: Literal["in_stock", "out_of_stock", "unknown"] | None = None
    ram_gb: int | None = Field(default=None, gt=0)
    storage_gb: int | None = Field(default=None, gt=0)
    cpu: str | None = None
    color: str | None = None
    screen_inches: float | None = Field(default=None, gt=0, le=30)
    model_number: str | None = None
    limit: int = Field(default=10, ge=1, le=50)

    @model_validator(mode="after")
    def price_range(self):
        if not self.q.strip():
            raise ValueError("query must not be blank")
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError("minimum price must not exceed maximum price")
        return self


class Offer(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    title: str | None
    retailer_key: str
    source_url: str
    attributes: dict
    price: Decimal | None
    currency: str | None
    availability: str | None
    match_status: str
    reasons: list[str]
    semantic_score: float
    keyword_score: float


class SearchResponse(BaseModel):
    source: str
    results: list[Offer]
    indexed: int
    search_seconds: float
    model_name: str
    dimensions: int
    explanation: str = ""
    collection_run_id: str | None = None
    latest_collection_stage: str | None = None


class HealthResponse(BaseModel):
    status: str
    source: str
    model_name: str
    dimensions: int


class StatusResponse(BaseModel):
    stage: str
    source: str
    discovered: int = 0
    attempted: int = 0
    accepted: int = 0
    run_id: str | None = None
    discovery_provider: str | None = None
    discovery: dict | None = None
    processed: int = 0
    skipped: int = 0
    duplicate_urls: int = 0
    invalid_urls: int = 0
    saved: int = 0
    unchanged: int = 0
    compatible: int = 0
    incompatible: int = 0
    manual_review: int = 0
    unavailable: int = 0
    unknown_availability: int = 0
    nonpriced_unavailable: int = 0
    storage_failures: int = 0
    blocked_pages: int = 0
    ai_reviews: int = 0
    ai_review_required: int = 0
    worker_failures: int = 0
    rejection_rate: float | None = None
    events: list[dict] = Field(default_factory=list)
    started_at: str | None = None
    finished_at: str | None = None
    elapsed_seconds: float | None = None
    acceptance_rate: float | None = None
    invalid_record_rate: float | None = None
    incorrect_data_rate: float | None = None
    fetched: int = 0
    extracted: int = 0
    rejected: int = 0
    invalid_records: int = 0
    failed_scrapes: int = 0
    missing_fields: dict[str, int] = Field(default_factory=dict)
    failures: dict[str, int] = Field(default_factory=dict)
    average_seconds_per_page: float | None = None
    embeddings: dict[str, int] | None = None
    errors: list[str] = Field(default_factory=list)


class ProductInfo(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    title: str | None
    retailer_key: str
    source_url: str
    attributes: dict
    price: Decimal | None


class ProductPage(BaseModel):
    source: str
    products: list[ProductInfo]


class DealResponse(SearchResponse):
    offers: list[Offer]
    excluded: list[dict]
    retailers: int
    comparison_basis: str
    live_two_retailer_milestone: bool
    comparison_as_of: str
