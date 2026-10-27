from normalizer.embeddings import semantic_score


def matches_filters(product, filters):
    if filters.get("brand"):
        if product.get("brand", "").lower() != filters["brand"].lower():
            return False

    if filters.get("cpu"):
        product_cpu = product.get("cpu", "").lower()
        if filters["cpu"].lower() not in product_cpu:
            return False

    if filters.get("ram_gb") is not None:
        if product.get("ram_gb") != filters["ram_gb"]:
            return False

    if filters.get("storage_gb") is not None:
        if product.get("storage_gb") != filters["storage_gb"]:
            return False

    if filters.get("max_price") is not None:
        price = product.get("price")

        if price is None or price > filters["max_price"]:
            return False

    return True


def search_products(query, products, filters=None):
    filters = filters or {}

    results = []

    for product in products:
        if not matches_filters(product, filters):
            continue

        score = semantic_score(query, product)

        results.append({
            "product": product,
            "semantic_score": score
        })

    results.sort(
        key=lambda result: result["semantic_score"],
        reverse=True
    )

    return results