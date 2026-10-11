"""Step 6: retrieve stored information for the eventual comparison tool.

Use dictionary cursors, parameterized queries, and close cursors after use.
These functions receive an open connection and must not commit or close it.
"""


def get_listing(connection, listing_id: int) -> dict | None:
    """Return a listing's descriptive details and retailer name."""
    # TODO: JOIN listings to retailers; return None if ID does not exist.
    # Decode attributes JSON into a Python dictionary.
    raise NotImplementedError("Mentee TODO: retrieve listing")


def get_latest_observation(connection, listing_id: int) -> dict | None:
    """Return the newest observed offer, even when its price is unknown."""
    # TODO: WHERE listing_id = %s ORDER BY scraped_at DESC LIMIT 1.
    # Do not pick highest ID or silently fall back to an older known price.
    raise NotImplementedError("Mentee TODO: retrieve latest observation")


def get_price_history(connection, listing_id: int) -> list[dict]:
    """Show how the listing's offer changed over time."""
    # TODO: Retrieve observations ordered by scraped_at ASC.
    # Preserve null amounts and condition changes; include timestamps.
    raise NotImplementedError("Mentee TODO: retrieve price history")


def find_listings(connection, brand: str, model_number: str) -> list[dict]:
    """Find possible offers by explicit brand/model for a first demonstration."""
    # TODO: Join each matching listing to its newest observation and retailer.
    # Include attributes, condition, seller, currency, shipping and timestamp.
    # These are candidates: model alone does not establish equal capacity/color.
    # Do not call an unknown price 'cheapest' or compare different currencies.
    raise NotImplementedError("Mentee TODO: retrieve candidate offers")
