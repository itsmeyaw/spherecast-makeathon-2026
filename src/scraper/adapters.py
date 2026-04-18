from src.scraper.cache import get_cached_product_facts


def get_cached_product_snapshot(sku, company_name):
    facts = get_cached_product_facts(sku)
    return {
        "sku": sku,
        "company": company_name,
        "source_type": "demo-cache",
        "claims": facts.get("claims", []),
        "certifications": facts.get("certifications", []),
        "allergens": facts.get("allergens", []),
        "notes": facts.get("notes", "No cached product facts available."),
    }


def build_product_lookup_hint(sku, company_name):
    return f"{company_name} {sku} demo-cache"
