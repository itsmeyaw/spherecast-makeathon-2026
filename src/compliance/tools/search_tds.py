from src.compliance.tools.search_documents import search_documents
from src.compliance.tools.web_search import web_search

LOCAL_SCORE_THRESHOLD = 0.3


def search_tds(
    ingredient_name: str,
    supplier_name: str | None = None,
) -> dict:
    """Search for Technical Data Sheets and fact sheets for an ingredient.

    Searches local document store first, then falls back to web search.
    If supplier_name is provided, searches for supplier-specific specs.
    If omitted, runs a single generic search without supplier scoping.
    """
    name_parts = [ingredient_name]
    if supplier_name:
        name_parts.append(supplier_name)

    local_query = " ".join(name_parts + ["technical data sheet specifications"])
    local_result = search_documents(query=local_query, n_results=5)

    if local_result["status"] == "error":
        return {"status": "error", "message": local_result["message"]}

    local_hits = local_result["data"]
    has_good_local = any(r["score"] >= LOCAL_SCORE_THRESHOLD for r in local_hits)

    web_hits = []
    if not has_good_local:
        web_query = " ".join(name_parts + ["TDS specifications purity"])
        web_result = web_search(query=web_query, count=5)
        if web_result["status"] == "ok":
            web_hits = web_result["data"]

    return {
        "status": "ok",
        "data": {
            "local_results": local_hits,
            "web_results": web_hits,
            "supplier_name": supplier_name,
        },
    }
