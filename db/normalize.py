# PURPOSE
# Validate one scraper record and create a normalized representation.
# Preserve the original record separately.
#
# INPUT
# One listing object from example_products.json.
#
# OUTPUT
# A normalized record, or a clear validation error.
#
# MISSING VALUES
# JSON null becomes Python None.
# Python None becomes SQL NULL for nullable scalar columns.
# Do not replace missing prices with zero.
# Do not replace missing brands with guesses.
#
# TEXT
# Remove surrounding whitespace.
# Collapse repeated whitespace.
# Preserve the meaning of the observed title.
# Keep identifiers as strings, including leading zeros.
#
# PRICE
# Preserve the original price text.
# Parse only explicitly supported formats.
# Example: "$99.99" with confirmed USD becomes Decimal("99.99").
# A dollar symbol alone does not establish the currency.
# Financing payments and "starting at" prices need separate handling.
#
# RETAILER
# Use the retailer_key supplied by a configured scraper.
# Do not guess the retailer from a product title.
#
# TIMESTAMP
# Require a timezone-aware scraped_at value.
# Convert it to UTC before storing.
# Keep observation time separate from import time.
#
# ATTRIBUTES
# Use agreed attribute names and units.
# Preserve distinctions such as capacity, color, condition, and pack size.
# Missing specifications remain missing.
#
# TODO
# Implement normalize(record).
# Decide which malformed records should be rejected.
# Return errors that identify the record and problematic field.
#
# EXAMPLES TO CHECK
# Missing price stays None.
# SKU "001234" keeps its leading zeros.
# Unexpected price text produces a clear error.
# A timestamp without a timezone is rejected.
# The original record remains unchanged.