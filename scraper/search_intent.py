"""Hard shopping requirements shared by live, catalog and AI-assisted search.

Fuzzy words rank candidates; they cannot establish a numeric specification or
turn a compatible accessory/device into the product the shopper requested.
"""
import re
from decimal import Decimal


PRODUCT_TYPES = (
    ("monitor_accessories", r"\bmonitor\s+(?:stands?|arms?|mounts?)\b"),
    ("laptop_accessories", r"\b(?:laptop|macbook)\s+(?:stands?|cases?|sleeves?|chargers?)\b"),
    ("laptops", r"\b(?:laptops?|notebooks?|macbooks?|chromebooks?|thinkpads?|zenbooks?|vivobooks?|ideapads?)\b"),
    ("monitors", r"\b(?:monitors?|computer\s+displays?)\b"),
    ("headphones", r"\b(?:headphones?|headsets?|earbuds?|airpods?)\b"),
    ("phones", r"\b(?:phones?|smartphones?|iphones?|galaxy\s+s\d+|pixel\s+\d+)\b"),
    ("tablets", r"\b(?:tablets?|ipads?)\b"),
    ("televisions", r"\b(?:televisions?|tvs?|smart\s+tv)\b"),
    ("keyboards", r"\bkeyboards?\b"),
    ("mice", r"\b(?:mouse|mice)\b"),
    ("graphics_cards", r"\b(?:graphics\s+cards?|gpus?)\b"),
    ("storage", r"\b(?:ssds?|hard\s+drives?|flash\s+drives?)\b"),
    ("desktops", r"\b(?:desktops?|mini\s+pcs?|gaming\s+pcs?)\b"),
    ("cameras", r"\bcameras?\b"),
    ("speakers", r"\b(?:speakers?|soundbars?)\b"),
)
SIZE = r'(?P<value>\d+(?:\.\d+)?)\s*(?:-\s*)?(?:inches?\b|inch\b|["″])'
HZ = r"(?P<value>\d+(?:\.\d+)?)\s*hz\b"
QUALIFIER = r"(?P<qualifier>at\s+least|minimum(?:\s+of)?|at\s+most|up\s+to|under|below|over|above|exactly)?\s*"


def product_type(text):
    matches = []
    for category, pattern in PRODUCT_TYPES:
        match = re.search(pattern, str(text or ""), re.I)
        if match:
            matches.append((match.start(), len(matches), category))
    # The subject precedes compatibility context: 'monitor for my laptop'.
    return min(matches)[2] if matches else None


def listing_type(product):
    # Descriptions mentioning compatible monitors must not reclassify a laptop.
    return product_type(product.get("title")) or product_type(
        str(product.get("category") or "").replace("_", " ").replace("-", " ")
    )


def parse_requirements(query):
    specs = []
    for name, pattern in (("screen_inches", SIZE), ("refresh_hz", HZ)):
        for match in re.finditer(QUALIFIER + pattern, query, re.I):
            specs.append((name, Decimal(match["value"]), " ".join((match["qualifier"] or "exactly").lower().split())))
    return {"product_type": product_type(query), "specs": specs}


def spec_values(product, name):
    pattern = SIZE if name == "screen_inches" else HZ
    values = {Decimal(m["value"]) for m in re.finditer(pattern, str(product.get("title") or ""), re.I)}
    if values:
        return values
    # Only labeled description specs count, not compatibility/variant prose.
    label = r"(?:screen\s+size|display\s+size|screen\s+diagonal)" if name == "screen_inches" else r"(?:refresh\s+rate)"
    return {Decimal(m["value"]) for m in re.finditer(
        label + r"\s*(?:[:=-]|is)?\s*" + pattern,
        str(product.get("description") or ""), re.I,
    )}


def value_matches(actual, requested, qualifier):
    if qualifier.startswith(("at least", "minimum")):
        return actual >= requested
    if qualifier in ("at most", "up to"):
        return actual <= requested
    if qualifier in ("under", "below"):
        return actual < requested
    if qualifier in ("over", "above"):
        return actual > requested
    return actual == requested


def apply_requirements(query, products):
    requirements = parse_requirements(query)
    results = []
    for product in products:
        if requirements["product_type"] and listing_type(product) != requirements["product_type"]:
            continue
        valid = True
        for name, requested, qualifier in requirements["specs"]:
            values = spec_values(product, name)
            if len(values) != 1 or not value_matches(next(iter(values)), requested, qualifier):
                valid = False
                break
        if valid:
            results.append(product)
    return results
