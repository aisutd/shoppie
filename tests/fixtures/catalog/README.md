# Labeled synthetic laptop fixtures

These files are deliberately synthetic classroom examples, not downloaded retailer
pages, actual retailer product URLs, or live offers. They are only loaded in Demo
mode and tests. Do not upload them to a shared database.

`manifest.json` records each page's URL, fixed observation time, expected fields,
and whether the page is allowed into the demo catalog. The expected specifications
were checked against the authored JSON-LD and the visible labeled examples:

- 01 / 02: same fictional manufacturer model, M5 CPU, 16 GB RAM, 512 GB SSD;
  Best Buy USD 999 and Target USD 1049, with explicit zero shipping.
- 03: 256 GB storage; 04: 8 GB RAM; 05: M4 CPU/model. These are real differences
  within the synthetic dataset and must not match the requested M5 configuration.
- 06: visible table says 16 GB, but the supported title/JSON-LD extraction paths
  omit RAM. This measures missing data separately and requires manual review.
- 07: unrelated Lenovo/AMD configuration.
- 08: missing price/currency, rejected by validation; not indexed.
- 09: visible main price is USD 1099, but JSON-LD says USD 109. The parser rejects
  the contradiction; not indexed. A test-only faulty extractor separately proves
  that the evaluation metrics catch an incorrect price that passes validation.
- `blocked.html`: challenge page; extraction must stop. No challenge is solved.

`search_labels.json` defines three tiny relevance checks and Precision@K
denominators. These labels are examples for future evaluation work. They do not
establish reliability across real retailers, laptop models, or broad search queries.

Missing values are recorded separately from incorrect present values. Price and
variant accuracy use only present, explicitly labeled comparisons. Transport fetch
success includes a readable challenge page; it does not imply product extraction.
