# Parser fixtures

`target_91122087_embedded_2026-10-14.html` is a reduced real public-page
`__NEXT_DATA__` excerpt inspected October 14, 2026, from
https://www.target.com/p/apple-macbook-neo-a18-pro-2026-laptop-with-touch-id-512gb-citrus/-/A-91122087.
It retains only layout modules' title and TCIN values for 91122087. No values
were added or changed; price/currency are absent. It tests selected-variant
title recovery when rendering removes the heading. It is not a complete offer.

## Real saved response

`target_1004661132_2026-10-14.html` is a minimized excerpt of a **real Target
response captured on October 14, 2026** using the earlier HTTP fetch checkpoint.
The adjacent JSON records its retailer URL, capture method, original-response
SHA-256, fixture SHA-256, expected parser fields and reduction method. The
reduction was checked against the full saved response: all extracted source
fields match. Only parser-relevant tags remain; unrelated scripts and tracking
are excluded. No product fields were added or changed.

This is a genuine but **incomplete** laptop response: title and TCIN are present;
price and currency are absent. Its test checks the actual title/identity and then
expects validation rejection. It does not claim a complete accepted live-price
record. `observed_at` is parsing time, so tests do not assert a fixed value for it.

The full original remains in ignored `scraper/data/pages/` on the development
machine. Running the tests requires only the repository excerpt and metadata,
never that local archive, Supabase credentials, or internet access.

## Synthetic adversarial inputs

`synthetic_product.html`, `missing_price.html`, and `bot_check.html` are deliberately
synthetic **unit-test inputs**, not current products, practice-store observations,
or fallback data. Their prices never enter the live URL list or Supabase.

`multiple_offers.html`, `ambiguous_variants.html`,
`missing_product_information.html`, and `missing_offer_fields.html` are synthetic
adversarial cases authored on October 14, 2026, not retailer captures. Their HTML
comments label that distinction. They isolate missing data and ambiguous sources
without altering the real Target capture or inventing historical retailer values.

Use `--keep-html` on a real accessible public page to create your own rehearsal
archive under ignored `scraper/data/pages/`. Local HTML can be parsed and validated
but is explicitly blocked from `--save`.
