from src.common.db import (
    get_alias_rows,
    get_aliases_for_canonical,
    get_bom_components,
    get_ingredient_group_for,
    get_product,
    get_raw_material_products,
    get_suppliers_for_product,
    parse_ingredient_name,
)

_RAW_MATERIAL_CACHE = {}


def _raw_material_products(db_path):
    cache_key = db_path or "__default__"
    if cache_key not in _RAW_MATERIAL_CACHE:
        _RAW_MATERIAL_CACHE[cache_key] = get_raw_material_products(db_path)
    return _RAW_MATERIAL_CACHE[cache_key]


def _build_exact_candidates(db_path, ingredient_name, original_product_id):
    candidates = []
    for product in _raw_material_products(db_path):
        if product["parsed_ingredient_name"] != ingredient_name:
            continue
        if product["product_id"] == original_product_id:
            continue
        candidates.append(
            {
                **product,
                "match_type": "exact",
                "canonical_name": ingredient_name,
                "current_match_name": ingredient_name,
                "candidate_suppliers": product["suppliers"],
            }
        )
    return candidates


def _build_alias_candidates(db_path, ingredient_name, original_product_id):
    alias_rows = get_alias_rows(db_path, alias_name=ingredient_name, include_unapproved=True)
    products = _raw_material_products(db_path)
    candidates = []

    if not alias_rows:
        group = get_ingredient_group_for(db_path, ingredient_name)
        if not group:
            return []
        group_members = [member for member in group["members"] if member != ingredient_name]
        for product in products:
            if product["product_id"] == original_product_id:
                continue
            if product["parsed_ingredient_name"] not in group_members:
                continue
            candidates.append(
                {
                    **product,
                    "match_type": "alias" if group.get("confidence") != "low" else "hypothesis",
                    "canonical_name": group["canonical_name"],
                    "current_match_name": product["parsed_ingredient_name"],
                    "approved": True,
                    "alias_notes": group.get("reasoning"),
                    "candidate_suppliers": product["suppliers"],
                }
            )
        return candidates

    for alias_row in alias_rows:
        for alias in get_aliases_for_canonical(
            db_path, canonical_name=alias_row["CanonicalName"], include_unapproved=True
        ):
            alias_name = alias["AliasName"]
            if alias_name == ingredient_name:
                continue
            for product in products:
                if product["product_id"] == original_product_id:
                    continue
                if product["parsed_ingredient_name"] != alias_name:
                    continue
                candidates.append(
                    {
                        **product,
                        "match_type": alias["MatchType"],
                        "canonical_name": alias["CanonicalName"],
                        "current_match_name": alias_name,
                        "approved": bool(alias["Approved"]),
                        "alias_notes": alias["Notes"],
                        "candidate_suppliers": product["suppliers"],
                    }
                )
    # Keep deterministic ordering for tests and UI.
    candidates.sort(
        key=lambda row: (
            {"alias": 0, "hypothesis": 1}.get(row["match_type"], 2),
            row["current_match_name"],
            row["company_name"],
            row["product_id"],
        )
    )
    return candidates


def find_candidates_for_component(db_path=None, component=None, finished_product=None):
    ingredient_name = parse_ingredient_name(component["sku"])
    exact_candidates = _build_exact_candidates(db_path, ingredient_name, component["product_id"])
    alias_candidates = _build_alias_candidates(db_path, ingredient_name, component["product_id"])

    alias_rows = get_alias_rows(db_path, alias_name=ingredient_name, include_unapproved=True)
    canonical_names = sorted({row["CanonicalName"] for row in alias_rows}) or [ingredient_name]

    return {
        "bom_id": component.get("bom_id"),
        "finished_product": finished_product,
        "original_ingredient": ingredient_name,
        "original_product_id": component["product_id"],
        "original_sku": component["sku"],
        "original_company_name": component.get("component_company_name"),
        "current_suppliers": get_suppliers_for_product(
            db_path, product_id=component["product_id"], detailed=True
        ),
        "canonical_names": canonical_names,
        "exact_candidates": exact_candidates,
        "alias_candidates": alias_candidates,
    }


def find_candidates_for_product(db_path=None, product_id=None):
    product = get_product(db_path, product_id=product_id)
    components = get_bom_components(db_path, product_id=product_id)
    results = []
    for component in components:
        result = find_candidates_for_component(db_path, component, finished_product=product)
        results.append(
            {
                "original_ingredient": result["original_ingredient"],
                "original_product_id": result["original_product_id"],
                "original_sku": result["original_sku"],
                "current_suppliers": [s["supplier_name"] for s in result["current_suppliers"]],
                "group": {
                    "canonical_name": ", ".join(result["canonical_names"]),
                    "function": "reviewed-alias-layer" if result["alias_candidates"] else "exact-match",
                    "confidence": "high" if result["exact_candidates"] else "medium" if result["alias_candidates"] else "low",
                },
                "candidates": [
                    {
                        "ingredient_name": candidate["current_match_name"],
                        "product_id": candidate["product_id"],
                        "sku": candidate["sku"],
                        "company": candidate["company_name"],
                        "suppliers": [s["supplier_name"] for s in candidate["candidate_suppliers"]],
                        "match_type": candidate["match_type"],
                    }
                    for candidate in result["exact_candidates"] + result["alias_candidates"]
                ],
            }
        )
    return results
