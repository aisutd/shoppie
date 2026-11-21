"""MiniLM embeddings for query-to-listing relevance, not spec verification."""

from functools import lru_cache
from math import fsum

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

@lru_cache(maxsize=1)
def _model():
    # Keyword search can start without importing torch or downloading weights.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME, device="cpu", local_files_only=True)


def build_product_text(product):
    parts = []

    if product.get("title"):
        parts.append(product["title"])

    if product.get("brand"):
        parts.append(f"Brand: {product['brand']}")

    if product.get("category"):
        parts.append(f"Category: {product['category']}")

    if product.get("description"):
        parts.append(product["description"])

    if product.get("cpu"):
        parts.append(f"CPU: {product['cpu']}")

    if product.get("ram_gb"):
        parts.append(f"RAM: {product['ram_gb']}GB")

    if product.get("storage_gb"):
        parts.append(f"Storage: {product['storage_gb']}GB")

    return " | ".join(parts)


def embed_product(product):
    return _model().encode(
        build_product_text(product),
        normalize_embeddings=True
    )


def embed_query(query):
    return _model().encode(
        query,
        normalize_embeddings=True
    )


def semantic_score(query, product):
    return semantic_scores(query, [product])[0]


def semantic_scores(query, products):
    """Encode the query once and batch listings; return scores in input order."""
    texts = [query, *(build_product_text(product) for product in products)]
    if len(texts) == 1:
        return []
    vectors = _model().encode(texts, normalize_embeddings=True, show_progress_bar=False)
    # Unit-length vectors make the dot product equivalent to cosine similarity.
    return [fsum(float(a) * float(b) for a, b in zip(vectors[0], row, strict=True))
            for row in vectors[1:]]
