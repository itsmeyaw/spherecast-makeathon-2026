from src.scraper.cache import get_cached_ingredient_facts, get_cached_product_facts


def ingredient_fact_rows(ingredient_name):
    facts = get_cached_ingredient_facts(ingredient_name)
    if not facts:
        return []

    rows = [
        {
            "source_type": "demo-cache",
            "source_label": "Demo ingredient fact pack",
            "source_uri": f"demo://ingredient/{ingredient_name}",
            "fact_type": "canonical_name",
            "fact_value": facts.get("canonical_name", ingredient_name),
            "quality_score": quality_to_score(facts.get("evidence_strength", "low")),
            "snippet": facts.get("notes", ""),
        },
        {
            "source_type": "demo-cache",
            "source_label": "Demo ingredient fact pack",
            "source_uri": f"demo://ingredient/{ingredient_name}",
            "fact_type": "vegan_compatible",
            "fact_value": str(facts.get("vegan_compatible", "")).lower(),
            "quality_score": quality_to_score(facts.get("evidence_strength", "low")),
            "snippet": facts.get("notes", ""),
        },
    ]
    for allergen in facts.get("allergens", []):
        rows.append(
            {
                "source_type": "demo-cache",
                "source_label": "Demo ingredient fact pack",
                "source_uri": f"demo://ingredient/{ingredient_name}",
                "fact_type": "allergen",
                "fact_value": allergen,
                "quality_score": quality_to_score(facts.get("evidence_strength", "low")),
                "snippet": facts.get("notes", ""),
            }
        )
    for certification in facts.get("certifications", []):
        rows.append(
            {
                "source_type": "demo-cache",
                "source_label": "Demo ingredient fact pack",
                "source_uri": f"demo://ingredient/{ingredient_name}",
                "fact_type": "certification",
                "fact_value": certification,
                "quality_score": quality_to_score(facts.get("evidence_strength", "low")),
                "snippet": facts.get("notes", ""),
            }
        )
    return rows


def product_fact_rows(product_sku):
    facts = get_cached_product_facts(product_sku)
    rows = []
    for claim in facts.get("claims", []):
        rows.append(
            {
                "source_type": "demo-cache",
                "source_label": "Demo product fact pack",
                "source_uri": f"demo://product/{product_sku}",
                "fact_type": "product_claim",
                "fact_value": claim,
                "quality_score": 0.7,
                "snippet": facts.get("notes", ""),
            }
        )
    for allergen in facts.get("allergens", []):
        rows.append(
            {
                "source_type": "demo-cache",
                "source_label": "Demo product fact pack",
                "source_uri": f"demo://product/{product_sku}",
                "fact_type": "product_allergen",
                "fact_value": allergen,
                "quality_score": 0.7,
                "snippet": facts.get("notes", ""),
            }
        )
    for certification in facts.get("certifications", []):
        rows.append(
            {
                "source_type": "demo-cache",
                "source_label": "Demo product fact pack",
                "source_uri": f"demo://product/{product_sku}",
                "fact_type": "product_certification",
                "fact_value": certification,
                "quality_score": 0.7,
                "snippet": facts.get("notes", ""),
            }
        )
    if not rows:
        rows.append(
            {
                "source_type": "demo-cache",
                "source_label": "Demo product fact pack",
                "source_uri": f"demo://product/{product_sku}",
                "fact_type": "product_context_gap",
                "fact_value": "no_cached_product_facts",
                "quality_score": 0.2,
                "snippet": facts.get("notes", "No cached product facts available."),
            }
        )
    return rows


def quality_to_score(label):
    return {"high": 0.95, "medium": 0.7, "low": 0.45}.get(label, 0.3)

