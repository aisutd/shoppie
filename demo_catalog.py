"""Local product references for the search demo."""

DEMO_LABEL = "DEMO / SAMPLE — NOT A VERIFIED LIVE OFFER"

# keep only product identities and reference links from the candidate review
TARGET = [
    ("91122075", "Apple MacBook Neo A18 Pro 512GB Silver", "laptops"),
    ("1011111206", "Lenovo V15 G4 Ryzen 5 Laptop", "laptops"),
    ("1009557360", "ASUS Vivobook 18 Ryzen 7 Laptop", "laptops"),
    ("1014632643", "Samsung Odyssey G5 G53F 27-inch Monitor", "monitors"),
    ("1005912679", "LG UltraGear 34-inch OLED Monitor", "monitors"),
    ("94998817", "Samsung Galaxy Tab A11+ 128GB Tablet", "tablets"),
    ("95285678", "Apple iPad Air M4 Wi-Fi Tablet (Product Family)", "tablets"),
    ("94649372", "Sony WH-1000XM6 Headphones Black", "headphones"),
    ("93606140", "Apple AirPods 4 Earbuds", "headphones"),
    ("93215986", "Samsung 990 PRO 2TB SSD", "storage"),
]

AMAZON = [
    ("B0GR6FHGXX", "Apple MacBook Neo A18 Pro 256GB Indigo", "laptops"),
    ("B0GR1493ZV", "Apple MacBook Air M5 13-inch 16GB RAM 512GB SSD Sky Blue", "laptops"),
    ("B0FWD726XF", "Apple MacBook Pro M5 14-inch 24GB RAM 1TB SSD Space Black", "laptops"),
    ("B0FV4B883Y", "ASUS TUF Gaming A16 Laptop", "laptops"),
    ("B0G3J1V3TW", "Lenovo Legion 5 Ryzen 7 Gaming Laptop", "laptops"),
    ("B0GQVPX1PJ", "Apple iPad Air M4 11-inch 128GB Tablet Space Gray", "tablets"),
    ("B0DFZZHK6X", "LG UltraGear 27GS75Q-B 27-inch Monitor", "monitors"),
    ("B0F3QJLD3B", "Sony WH-1000XM6 Headphones Silver", "headphones"),
    ("B0C8PWSW7T", "Beats Studio Pro Headphones Navy", "headphones"),
    ("B0BHJJ9Y77", "Samsung 990 PRO 2TB SSD", "storage"),
]


def load_demo_catalog():
    products = []
    for source, path, entries in (
        ("target.com", "p/-/A-", TARGET),
        ("amazon.com", "dp/", AMAZON),
    ):
        for product_id, title, category in entries:
            products.append({
                "id": f"demo-{source}-{product_id}",
                "source": source,
                "title": title,
                "category": category,
                "product_url": f"https://www.{source}/{path}{product_id}",
                "price": None,
                "is_demo": True,
                "demo_label": DEMO_LABEL,
            })
    return products
