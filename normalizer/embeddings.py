from sentence_transformers import SentenceTransformer, util

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

model = SentenceTransformer(MODEL_NAME)


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
    return model.encode(
        build_product_text(product),
        normalize_embeddings=True
    )


def embed_query(query):
    return model.encode(
        query,
        normalize_embeddings=True
    )


def semantic_score(query, product):
    query_embedding = embed_query(query)
    product_embedding = embed_product(product)

    score = util.cos_sim(
        query_embedding,
        product_embedding
    )

    return float(score[0][0])