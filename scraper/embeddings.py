"""Compatibility entry point using Shoppie's cached, normalized MiniLM model."""

from db.embeddings import build_text, generate_embedding, load_model


def generate_product_embedding(product, model=None):
    # accepts scraper records and normalized backend listings without a second model
    listing = dict(product)
    listing['model_number'] = listing.get('model_number') or listing.get('model')
    text = build_text(listing)
    if not text:
        raise ValueError('Product identity text is missing')
    return generate_embedding(model or load_model(), text)
