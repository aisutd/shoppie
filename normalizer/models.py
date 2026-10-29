from typing import Any

from pydantic import BaseModel, Field


class Source(BaseModel):
    retailer: str
    url: str | None = None


class ExtractedListing(BaseModel):
    source: Source
    name: str
    brand: str | None = None
    model_number: str | None = None
    gtin: str | None = None
    category: str | None = None

    # Original attribute names and values from the retailer.
    attributes: dict[str, Any] = Field(default_factory=dict)


class NormalizedListing(BaseModel):
    source: Source
    name: str
    brand: str | None = None
    model_number: str | None = None
    gtin: str | None = None
    category: str

    specs: dict[str, Any] = Field(default_factory=dict)
    unmapped_attributes: dict[str, Any] = Field(default_factory=dict)


class FieldEvidence(BaseModel):
    source: Source
    value: Any


class FieldConflict(BaseModel):
    field: str
    observations: list[FieldEvidence]


class CanonicalProduct(BaseModel):
    name: str
    brand: str | None = None
    model_number: str | None = None
    gtin: str | None = None
    category: str | None = None

    specs: dict[str, Any] = Field(default_factory=dict)
    sources: list[Source] = Field(default_factory=list)
    evidence: dict[str, list[FieldEvidence]] = Field(default_factory=dict)
    conflicts: list[FieldConflict] = Field(default_factory=list)

    # Preserve attributes we don't yet know how to normalize.
    unmapped_attributes: dict[str, list[FieldEvidence]] = (
        Field(default_factory=dict)
    )


class ProcessingIssue(BaseModel):
    source: Source
    field: str
    message: str


class NormalizationResult(BaseModel):
    products: list[CanonicalProduct] = Field(default_factory=list)
    issues: list[ProcessingIssue] = Field(default_factory=list)