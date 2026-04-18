from src.common.db import (
    get_alias_rows,
    get_bom_components,
    get_portfolio_usage_for_names,
    get_suppliers_for_product,
)
from src.scraper.cache import get_cached_ingredient_facts


def query_database(
    query_type: str,
    product_id: int | None = None,
    ingredient_name: str | None = None,
    ingredient_names: list[str] | None = None,
) -> dict:
    """Query the SQLite database using predefined read-only query types.

    Available query_type values:
    - "product_bom": BOM components for a product. Requires product_id.
    - "supplier_products": Suppliers for a raw material. Requires product_id.
    - "ingredient_aliases": Alias/canonical mappings. Requires ingredient_name.
    - "portfolio_usage": Which finished products use given ingredients. Requires ingredient_names (list).
    - "ingredient_facts": Cached facts for an ingredient. Requires ingredient_name.
    """
    try:
        if query_type == "product_bom":
            data = get_bom_components(product_id=product_id)
            return {"status": "ok", "data": data}

        if query_type == "supplier_products":
            data = get_suppliers_for_product(product_id=product_id, detailed=True)
            return {"status": "ok", "data": data}

        if query_type == "ingredient_aliases":
            data = get_alias_rows(alias_name=ingredient_name, include_unapproved=True)
            return {"status": "ok", "data": data}

        if query_type == "portfolio_usage":
            names = ingredient_names or ([ingredient_name] if ingredient_name else [])
            data = get_portfolio_usage_for_names(ingredient_names=names)
            return {"status": "ok", "data": data}

        if query_type == "ingredient_facts":
            data = get_cached_ingredient_facts(ingredient_name)
            return {"status": "ok", "data": data or {}}

        return {"status": "error", "message": f"Unknown query_type: {query_type}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
