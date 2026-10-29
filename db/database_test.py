import sqlite3

# Open/create a database file
connection = sqlite3.connect("shoppie.db")

# Create a table for product listings
connection.execute("""
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY,
    retailer TEXT NOT NULL,
    title TEXT NOT NULL,
    model TEXT,
    price_cents INTEGER
)
""")

# Insert one sample tech listing
connection.execute("""
INSERT INTO listings (retailer, title, model, price_cents)
VALUES (?, ?, ?, ?)
""", (
    "Demo Store",
    "Sony WH-1000XM5 Headphones",
    "WH-1000XM5",
    29999
))

# Save changes
connection.commit()

# Retrieve everything from the table
for row in connection.execute("SELECT * FROM listings"):
    print(row)

connection.close()