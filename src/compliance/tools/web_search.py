import os

import httpx

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


def web_search(query: str, count: int = 5) -> dict:
    """Search the web using the Brave Search API.

    Use for regulatory guidance, ingredient safety data, or labeling
    precedent not found in the local document store.
    """
    api_key = os.environ.get("BRAVE_API_KEY")
    if not api_key:
        return {"status": "error", "message": "BRAVE_API_KEY environment variable not set"}

    try:
        response = httpx.get(
            BRAVE_SEARCH_URL,
            params={"q": query, "count": count},
            headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
            timeout=15,
        )
        response.raise_for_status()
        results = response.json().get("web", {}).get("results", [])
        return {
            "status": "ok",
            "data": [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "description": r.get("description", ""),
                }
                for r in results
            ],
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
