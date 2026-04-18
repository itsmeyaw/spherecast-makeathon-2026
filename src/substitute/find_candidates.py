import json
from src.common.db import (
    get_connection,
    get_bom_components,
    get_suppliers_for_product,
    parse_ingredient_name,
    get_ingredient_group_for,
)


def find_candidates_for_product(db_path=None, product_id=None):
    components = get_bom_components(db_path, product_id=product_id)
    results = []

    for comp in components:
        ingredient_name = parse_ingredient_name(comp["sku"])
        group = get_ingredient_group_for(db_path, ingredient_name)

        candidates = []
        if group and len(group["members"]) > 1:
            other_members = [m for m in group["members"] if m != ingredient_name]
            candidate_products = _find_products_for_ingredients(db_path, other_members)

            for cp in candidate_products:
                suppliers = get_suppliers_for_product(db_path, product_id=cp["product_id"])
                candidates.append({
                    "ingredient_name": cp["ingredient_name"],
                    "product_id": cp["product_id"],
                    "sku": cp["sku"],
                    "company": cp["company_name"],
                    "suppliers": suppliers,
                })

        current_suppliers = get_suppliers_for_product(db_path, product_id=comp["product_id"])

        results.append({
            "original_ingredient": ingredient_name,
            "original_product_id": comp["product_id"],
            "original_sku": comp["sku"],
            "current_suppliers": current_suppliers,
            "group": {
                "canonical_name": group["canonical_name"] if group else ingredient_name,
                "function": group["function"] if group else "unknown",
                "confidence": group["confidence"] if group else "low",
            },
            "candidates": candidates,
        })

    return results


def _find_products_for_ingredients(db_path, ingredient_names):
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT p.Id as product_id, p.SKU as sku, p.CompanyId, c.Name as company_name
        FROM Product p
        JOIN Company c ON p.CompanyId = c.Id
        WHERE p.Type = 'raw-material'
    """).fetchall()
    conn.close()

    results = []
    seen = set()
    for r in rows:
        name = parse_ingredient_name(r["sku"])
        if name in ingredient_names and name not in seen:
            seen.add(name)
            results.append({
                "product_id": r["product_id"],
                "sku": r["sku"],
                "ingredient_name": name,
                "company_name": r["company_name"],
            })
    return results
