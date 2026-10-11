# PURPOSE
# Load the scraper's JSON output into MySQL.
#
# INPUT
# A file following our agreed JSON schema.
#
# OUTPUT
# Stored listings and timestamped observations.
# A summary showing imported, skipped, and rejected records.
#
# PLANNED STEPS
# 1. Open and read the JSON file.
# 2. Check schema_version and the listings array.
# 3. Validate and normalize records.
# 4. Connect to MySQL.
# 5. Look up each configured retailer.
# 6. Find or create each listing using our identity rule.
# 7. Update current listing information when the observation is newer.
# 8. Add the observation if it does not already exist.
# 9. Preserve the original record in raw_payload.
# 10. Commit successful changes.
# 11. Close the connection.
#
# DUPLICATES
# Importing the same observation twice must not create two rows.
# A later scrape of the same listing should create a new observation.
#
# TRANSACTIONS
# A transaction groups related changes.
# Commit saves those changes.
# Rollback cancels uncommitted changes after an error.
#
# SQL PARAMETERS
# Use parameterized queries.
# Never concatenate scraped text into SQL commands.
#
# FAILURE HANDLING
# Choose and document either:
# - Reject the entire batch when a record is invalid.
# - Import valid records and save rejected records with explanations.
#
# SCRAPER INTEGRATION
# The scraper writes a completed JSON file.
# This importer reads that file.
# The scraper does not need database credentials for this approach.
#
# TODO
# Implement a command that accepts an input file path.
# Implement duplicate handling and transactions.
# Make an older import preserve newer current listing information.
#
# DEMONSTRATION
# Import the example file.
# Import it again and show unchanged row counts.
# Change a price and timestamp, then show the added observation.