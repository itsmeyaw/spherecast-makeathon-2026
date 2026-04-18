import httpx

OPENFDA_BASE = "https://api.fda.gov"

ENDPOINT_MAP = {
    "labeling": "/drug/label.json",
    "adverse_events": "/drug/event.json",
    "dsld": "/other/substance.json",
}


def fda_lookup(ingredient_name: str, endpoint: str = "labeling") -> dict:
    """Query the openFDA API for dietary supplement and drug information.

    Available endpoints:
    - "labeling": Drug/supplement labeling data
    - "adverse_events": Adverse event reports
    - "dsld": Dietary Supplement Label Database substance data
    """
    if endpoint not in ENDPOINT_MAP:
        return {
            "status": "error",
            "message": f"Unknown endpoint: {endpoint}. Choose from: {list(ENDPOINT_MAP.keys())}",
        }

    try:
        url = f"{OPENFDA_BASE}{ENDPOINT_MAP[endpoint]}"
        response = httpx.get(
            url,
            params={"search": ingredient_name, "limit": 5},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        return {"status": "ok", "data": data.get("results", [])}
    except Exception as e:
        return {"status": "error", "message": str(e)}
