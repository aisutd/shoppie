# PURPOSE
# Build consistent product text, generate embeddings, and store them.
#
# INPUT
# Normalized listings from MySQL.
#
# OUTPUT
# One numerical vector for each listing with usable product text.
#
# FIRST MODEL
# Start with a standard single-vector SentenceTransformer.
# Suggested baseline: sentence-transformers/all-MiniLM-L6-v2.
# This model produces 384 values per embedding.
#
# TEXT TEMPLATE
# Brand | Product title | Model | Key attributes
#
# EXAMPLE
# Acme | QuietSound Q100 Headphones | model: Q100 |
# color: black | connectivity: wireless | condition: new
#
# INCLUDE
# Brand, product name, manufacturer model, and identifying specifications.
#
# EXCLUDE
# Price, retailer name, retailer SKU, URL, and scrape timestamp.
# These describe the offer or source rather than product identity.
#
# MISSING DATA
# Omit unavailable fields from the text.
# Do not invent specifications.
# Skip records with no usable product description.
#
# CONSISTENCY
# Sort attributes so the same information produces the same text.
# Record the model name, exact revision, and template version.
# Only compare vectors produced by compatible configurations.
#
# UPDATES
# Hash the input text.
# Reuse the embedding if the input and configuration are unchanged.
# Recompute when product text changes.
# A price-only change should not require a new embedding.
#
# TODO
# Implement build_text(listing).
# Load the model once per run.
# Encode and normalize vectors.
# Store vectors and their metadata in MySQL.
#
# QUESTIONS
# What is an embedding?
# Why record the exact input text?
# Why exclude price?
# Why must outdated embeddings be refreshed or excluded?