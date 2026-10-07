# Product Listing Data Dictionary

This data dictionary defines the standard fields that each product listing should contain. Keeping the same structure across different retailers will make it easier to compare products, match similar listings, and track prices.

## Product Listing Fields

- `id`
  - **Type:** String
  - **Description:** Unique ID for the product listing.
  - **Example:** `"listing_001"`

- `source`
  - **Type:** String
  - **Description:** Retailer or website where the product listing came from.
  - **Example:** `"Amazon"`

- `source_url`
  - **Type:** String
  - **Description:** Direct URL to the original product listing.
  - **Example:** `"https://www.amazon.com/example-product"`

- `title`
  - **Type:** String
  - **Description:** Full name or title of the product.
  - **Example:** `"Apple AirPods Pro 2nd Generation"`

- `brand`
  - **Type:** String
  - **Description:** Brand or manufacturer of the product.
  - **Example:** `"Apple"`

- `model`
  - **Type:** String or Null
  - **Description:** Model name or model number of the product, if available.
  - **Example:** `"AirPods Pro 2"`

- `category`
  - **Type:** String
  - **Description:** General category the product belongs to.
  - **Example:** `"Electronics"`

- `color`
  - **Type:** String or Null
  - **Description:** Color of the product, if listed.
  - **Example:** `"White"`

- `price`
  - **Type:** Number
  - **Description:** Current listed price of the product.
  - **Example:** `189.99`

- `currency`
  - **Type:** String
  - **Description:** Currency used for the listed price.
  - **Example:** `"USD"`

- `original_price`
  - **Type:** Number or Null
  - **Description:** Original price before a sale or discount, if available.
  - **Example:** `249.99`

- `condition`
  - **Type:** String
  - **Description:** Current condition of the product.
  - **Example:** `"New"`
  - **Possible values:** `"New"`, `"Used"`, `"Refurbished"`, or `"Open Box"`

- `availability`
  - **Type:** String
  - **Description:** Whether the product is currently available to purchase.
  - **Example:** `"In Stock"`

- `image_url`
  - **Type:** String or Null
  - **Description:** URL of the main product image.
  - **Example:** `"https://example.com/product-image.jpg"`

- `rating`
  - **Type:** Number or Null
  - **Description:** Average customer rating for the product, if available.
  - **Example:** `4.7`

- `review_count`
  - **Type:** Integer or Null
  - **Description:** Number of customer reviews for the product, if available.
  - **Example:** `12540`

- `last_updated`
  - **Type:** String (Date/Time)
  - **Description:** Date and time when the listing information was last collected or updated.
  - **Example:** `"2026-10-06T20:30:00Z"`

## Example Product Listing

```json
{
  "id": "listing_001",
  "source": "Amazon",
  "source_url": "https://www.amazon.com/example-product",
  "title": "Apple AirPods Pro 2nd Generation",
  "brand": "Apple",
  "model": "AirPods Pro 2",
  "category": "Electronics",
  "color": "White",
  "price": 189.99,
  "currency": "USD",
  "original_price": 249.99,
  "condition": "New",
  "availability": "In Stock",
  "image_url": "https://example.com/product-image.jpg",
  "rating": 4.7,
  "review_count": 12540,
  "last_updated": "2026-10-06T20:30:00Z"
}
```

## General Rules

- Use the same field names for listings from every retailer.
- Use `null` when optional information is not available instead of guessing a value.
- Store prices as numbers instead of including `$` in the value.
- Use `"USD"` as the currency value for prices in U.S. dollars.
- Keep condition values consistent whenever possible.
- Each listing should have its own unique `id`.