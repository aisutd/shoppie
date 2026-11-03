# Trisha-Test / main integration

The branches changed the same files, but also changed the scraper interface.
main.py expects fetch_page(url) to return HTML and extract_product(html, url)
to return a Laptop-compatible record. Trisha's standalone collector returns
(html, final_url) and produces a database-shaped tech record instead.

The resolution retains main's scraper.py interface and Amazon improvements.
Trisha's standalone collector is preserved in scraper/tech_scraper.py:

```bash
python -m scraper.main --url PRODUCT_URL
python scraper/tech_scraper.py PRODUCT_URL --category headphones
```

The standalone collector still asks before uploading. Its curl_cffi dependency
is loaded only when fetching. Environment loading happens only for its uploader.
Its broad extraction heuristics remain experimental and need separate review.

Validator changes retain Trisha's laptop-family keywords, availability aliases
and future-time check, while unknown availability still raises a validation error.
The shared uploader uses source and only columns declared in sql/schema.sql;
availability/seller/product_id columns require a separate schema migration.

This merge fixes a malformed description selector. It does not deploy schema
changes, perform live scraping/uploads, or enable the experimental AI agent.
That agent's imports/tool wiring need separate integration work.

The source branch already tracks node_modules and executable/build outputs.
Those were preserved, not removed, during conflict resolution. Clean them up
in a separately reviewed change rather than deleting student work in this merge.
