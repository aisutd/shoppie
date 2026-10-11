# Shoppie Database Learning Scaffold

These files explain what the database pipeline should do.
The Python and SQL files contain comments only and do not run yet.

## Our goal

Take product listings from the scraper, clean the data, store it in
MySQL, generate embeddings, and find potentially matching products.

## How the database pipeline works

```text
Retailer product pages
        |
        v
Python scraper collects product information
        |
        v
Save the original records in a JSON file
        |
        v
Validate and clean the records
(missing values stay null; invalid values are flagged)
        |
        v
Store listings and price observations in MySQL
        |
        v
Build a text description for each listing
(brand + title + model + important specifications)
        |
        v
Use an embedding model to turn the text into a vector
        |
        v
Store the vector and model information in MySQL
        |
        v
Use Python to compare vectors with cosine similarity
        |
        v
Find potentially matching listings across retailers
        |
        v
Check identifiers and specifications
        |
        v
Confirm a match, reject it, or leave it uncertain
```

Each new scrape adds an observation so we can track price history.
Embeddings help find candidates; they do not prove two listings are
the same product.

->
Scraper JSON
→ validation and normalization
→ MySQL listings and price observations
→ embedding text
→ embedding model
→ vectors stored in MySQL
→ similarity search

## Read the files in this order

1. example_products.json — what the scraper sends us
2. schema.sql — how we organize the data
3. connection.py — how Python connects to MySQL
4. normalize.py — how we clean and validate records
5. ingest.py — how records enter the database
6. embeddings.py — how product descriptions become vectors
7. similarity.py — how we find candidate matches

## Important distinctions

### Dummy retailer listings

`example_product.json` contains 40 synthetic tech listings: 10 each for
Amazon (`amazon`), Walmart (`walmart`), Target (`target`), and Best Buy
(`best_buy`). Product names reference real product families, but prices,
SKUs, availability, specifications, and timestamps are illustrative, not
scraped or verified retailer data. The `.example` URLs are placeholders.
The fixture includes matching products across retailers, different storage
sizes, refurbished items, an out-of-stock item, and missing fields.

GTIN means Global Trade Item Number: a product identifier commonly encoded
in a barcode, such as a 12-digit UPC or 13-digit EAN. Store it as text to
preserve leading zeros. The same product variant can share a GTIN across
retailers, while a retailer SKU identifies a listing within that retailer.
All fixture GTINs are `null` because no identifiers have been verified.

- A product is different from a retailer's listing for that product.
- A retailer SKU is different from a universal product identifier.
- A missing value is different from an invalid value.
- Similar descriptions do not prove two listings are the same product.
- Storing vectors does not automatically create a vector-search index.

## Team A: Database and ingestion

Implement schema.sql, connection.py, normalize.py, and ingest.py.

## Team B: Embeddings and matching

Implement embeddings.py and similarity.py.
Create examples of correct matches and misleading similarities.

## Shared decisions

Before implementation, agree on:
- JSON field names and types.
- What identifies a listing.
- Required versus optional fields.
- Supported price formats and currencies.
- Attribute names and units.
- What counts as the same product variant.

## First demonstration

Import the example file.
Show the listings and prices in MySQL.
Import the same file again without creating duplicates.
Add a later observation with a different price.
Generate embeddings and retrieve candidate matches.
