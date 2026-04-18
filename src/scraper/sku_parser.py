import re

KNOWN_SOURCES = [
    "thrive-market",
    "the-vitamin-shoppe",
    "sams-club",
    "iherb",
    "amazon",
    "walmart",
    "target",
    "cvs",
    "walgreens",
    "costco",
    "vitacost",
    "gnc",
]

# Sort by length descending so "thrive-market" matches before "thrive"
KNOWN_SOURCES.sort(key=len, reverse=True)


def parse_fg_sku(sku):
    if not sku.startswith("FG-"):
        return {"source": "unknown", "product_id": sku}

    remainder = sku[3:]  # strip "FG-"

    for source in KNOWN_SOURCES:
        if remainder.startswith(source + "-"):
            product_id = remainder[len(source) + 1:]
            return {"source": source, "product_id": product_id}

    parts = remainder.split("-", 1)
    return {"source": parts[0], "product_id": parts[1] if len(parts) > 1 else ""}


def build_search_query(sku, company_name):
    parsed = parse_fg_sku(sku)
    return f"{company_name} supplement {parsed['source']} {parsed['product_id']}"
