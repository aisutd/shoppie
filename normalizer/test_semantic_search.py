from normalizer.semantic_search import search_products


products = [
    {
        "title": "Apple MacBook Air M5 13-inch",
        "brand": "Apple",
        "category": "laptop",
        "cpu": "Apple M5",
        "ram_gb": 16,
        "storage_gb": 512,
        "price": 1149.00,
    },
    {
        "title": "Apple MacBook Air M5 13-inch 8GB",
        "brand": "Apple",
        "category": "laptop",
        "cpu": "Apple M5",
        "ram_gb": 8,
        "storage_gb": 512,
        "price": 999.00,
    },
    {
        "title": "HP Laptop Ryzen 5",
        "brand": "HP",
        "category": "laptop",
        "cpu": "Ryzen 5",
        "ram_gb": 16,
        "storage_gb": 512,
        "price": 638.99,
    },
]


query = "apple laptop with m5 and 16gb ram"

filters = {
    "brand": "Apple",
    "cpu": "M5",
    "ram_gb": 16,
    "max_price": 1200,
}


results = search_products(
    query,
    products,
    filters
)


for result in results:
    product = result["product"]
    score = result["semantic_score"]

    print(
        f"{score:.3f} - "
        f"{product['title']} - "
        f"${product['price']}"
    )