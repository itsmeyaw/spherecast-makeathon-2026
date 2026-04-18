import httpx

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"


def _extract_prop(props, label, name=None):
    for prop in props:
        urn = prop.get("urn", {})
        if urn.get("label") == label and (name is None or urn.get("name") == name):
            val = prop.get("value", {})
            return val.get("sval") or val.get("fval") or val.get("ival")
    return None


def pubchem_lookup(compound: str) -> dict:
    """Look up a compound on PubChem by name or CID.

    Returns chemical identity, synonyms, molecular formula, and safety data.
    Use to verify chemical equivalence between original and substitute ingredients.
    """
    try:
        if compound.isdigit():
            url = f"{PUBCHEM_BASE}/compound/cid/{compound}/JSON"
        else:
            url = f"{PUBCHEM_BASE}/compound/name/{compound}/JSON"

        response = httpx.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()

        compounds = data.get("PC_Compounds", [])
        if not compounds:
            return {"status": "ok", "data": None}

        comp = compounds[0]
        cid = comp.get("id", {}).get("id", {}).get("cid")
        props = comp.get("props", [])

        return {
            "status": "ok",
            "data": {
                "cid": cid,
                "iupac_name": _extract_prop(props, "IUPAC Name", "Preferred"),
                "molecular_formula": _extract_prop(props, "Molecular Formula"),
                "molecular_weight": _extract_prop(props, "Molecular Weight"),
            },
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
