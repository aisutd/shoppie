from normalizer.embeddings import semantic_score


products = [
    {
        "title": "Apple MacBook Air M5 13-inch",
        "brand": "Apple",
        "category": "laptop",
        "cpu": "Apple M5",
        "ram_gb": 16,
        "storage_gb": 512,
    },
    {
        "title": "HP Laptop Ryzen 5",
        "brand": "HP",
        "category": "laptop",
        "cpu": "Ryzen 5",
        "ram_gb": 16,
        "storage_gb": 512,
    },
    {
        "title": "Dell Latitude 5420",
        "brand": "Dell",
        "category": "laptop",
        "cpu": "Intel i5",
        "ram_gb": 8,
        "storage_gb": 256,
    }
]

query = "apple laptop with m5 and 16gb ram"

results = []

for product in products:
    score = semantic_score(query, product)
    results.append((score, product["title"]))

results.sort(reverse=True)

for score, title in results:
    print(f"{score:.3f} - {title}")