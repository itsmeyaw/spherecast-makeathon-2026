from src.evidence.normalize import ingredient_fact_rows, product_fact_rows
from src.scraper.cache import get_cached_ingredient_facts, get_cached_product_facts


def build_requirement_profile(finished_product, component):
    ingredient_name = component["original_ingredient"]
    ingredient_facts = get_cached_ingredient_facts(ingredient_name) or {}
    product_facts = get_cached_product_facts(finished_product["sku"])

    requirements = [
        {
            "requirement_type": "ingredient_identity",
            "requirement_value": ingredient_facts.get("canonical_name", ingredient_name),
            "source": "internal-bom",
            "confidence": "high",
        }
    ]

    if ingredient_facts.get("vegan_compatible") is True:
        requirements.append(
            {
                "requirement_type": "vegan_compatible",
                "requirement_value": "true",
                "source": "demo-ingredient-pack",
                "confidence": "medium",
            }
        )

    for allergen in ingredient_facts.get("allergens", []):
        requirements.append(
            {
                "requirement_type": "known_allergen",
                "requirement_value": allergen,
                "source": "demo-ingredient-pack",
                "confidence": "medium",
            }
        )

    for claim in product_facts.get("claims", []):
        if claim == "vegan":
            requirements.append(
                {
                    "requirement_type": "vegan_compatible",
                    "requirement_value": "true",
                    "source": "demo-product-pack",
                    "confidence": "medium",
                }
            )

    for certification in product_facts.get("certifications", []):
        requirements.append(
            {
                "requirement_type": "required_certification",
                "requirement_value": certification,
                "source": "demo-product-pack",
                "confidence": "medium",
            }
        )

    if not ingredient_fact_rows(ingredient_name):
        requirements.append(
            {
                "requirement_type": "critical_evidence",
                "requirement_value": "missing_ingredient_fact_pack",
                "source": "workspace-gap",
                "confidence": "low",
            }
        )

    return requirements


def collect_requirement_evidence(finished_product, component):
    return ingredient_fact_rows(component["original_ingredient"]) + product_fact_rows(finished_product["sku"])

