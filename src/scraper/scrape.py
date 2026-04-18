import json
import os
from pathlib import Path

from src.common.db import get_finished_goods
from src.scraper.adapters import build_product_lookup_hint, get_cached_product_snapshot

SCRAPED_DIR = "data/scraped"


def scrape_and_extract(sku, company_name):
    """
    Demo-safe retrieval path.

    The Phase 1 workspace prefers a checked-in cache over live scraping so the
    sourcing demo is reproducible. Live scraping remains a future extension.
    """
    snapshot = get_cached_product_snapshot(sku, company_name)
    result = {
        "sku": sku,
        "company": company_name,
        "source": "demo-cache",
        "lookup_hint": build_product_lookup_hint(sku, company_name),
        "product_name": sku,
        "supplement_facts": [],
        "certifications": snapshot["certifications"],
        "allergen_warnings": snapshot["allergens"],
        "claims": snapshot["claims"],
        "notes": snapshot["notes"],
        "live_scrape_enabled": False,
    }

    Path(SCRAPED_DIR).mkdir(parents=True, exist_ok=True)
    safe_sku = sku.replace("/", "_")
    with open(os.path.join(SCRAPED_DIR, f"{safe_sku}.json"), "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)

    return result


def scrape_all_products(db_path=None):
    products = get_finished_goods(db_path)
    return [scrape_and_extract(p["sku"], p["company_name"]) for p in products]
