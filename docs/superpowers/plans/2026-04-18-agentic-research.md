# Agentic Research Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-shot `_rag_evaluation()` in `src/compliance/evaluate.py` with a multi-round research agent that autonomously queries pgvector, SQLite, web search, PubChem, and FDA APIs to build a thorough compliance verdict.

**Architecture:** A DeepAgents-based agent (`create_deep_agent`) backed by `ChatBedrockConverse` (Anthropic Claude on Bedrock). Five tools defined as plain Python functions. The agent returns a `SubstitutionVerdict` Pydantic model. Integration point: `evaluate_substitution()` calls `research_substitution()` instead of `_rag_evaluation()`, with fallback to the old path on failure.

**Tech Stack:** deepagents, langchain-aws (ChatBedrockConverse), httpx (PubChem/FDA/Brave APIs), pydantic, pytest

**Spec:** `docs/superpowers/specs/2026-04-18-agentic-research-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/compliance/research_agent.py` | Agent creation, system prompt, `research_substitution()` entry point |
| `src/compliance/tools/__init__.py` | Package marker |
| `src/compliance/tools/search_documents.py` | pgvector search tool |
| `src/compliance/tools/query_database.py` | SQLite predefined-query tool |
| `src/compliance/tools/web_search.py` | Brave Search API tool |
| `src/compliance/tools/pubchem_lookup.py` | PubChem REST API tool |
| `src/compliance/tools/fda_lookup.py` | openFDA API tool |
| `src/compliance/evaluate.py` | Modified — wire in `research_substitution()` |
| `scripts/research.py` | CLI entry point |
| `requirements.txt` | Add `deepagents`, `langchain-aws` |
| `tests/test_research_tools.py` | Unit tests for all five tools |
| `tests/test_research_agent.py` | Integration test for the agent loop |
| `tests/test_research_cli.py` | Test for the CLI script |

---

### Task 1: Add Dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add new packages to requirements.txt**

Open `requirements.txt` and append:

```
deepagents
langchain-aws
```

The final file should be:

```
streamlit
boto3
httpx
beautifulsoup4
lxml
pytest
psycopg2-binary
markitdown
deepagents
langchain-aws
```

- [ ] **Step 2: Install dependencies**

Run: `pip install deepagents langchain-aws`

Expected: Both packages install successfully. `deepagents` pulls in `langgraph` and `langchain-core` as transitive deps.

- [ ] **Step 3: Verify imports work**

Run: `python -c "from deepagents import create_deep_agent; from langchain_aws import ChatBedrockConverse; print('OK')"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add deepagents and langchain-aws dependencies"
```

---

### Task 2: search_documents Tool

**Files:**
- Create: `src/compliance/tools/__init__.py`
- Create: `src/compliance/tools/search_documents.py`
- Test: `tests/test_research_tools.py`

- [ ] **Step 1: Create package marker**

Create `src/compliance/tools/__init__.py` as an empty file.

- [ ] **Step 2: Write the failing test**

Create `tests/test_research_tools.py`:

```python
from unittest.mock import patch


def test_search_documents_returns_ok_with_results():
    mock_results = [
        {"text": "Vitamin D3 supplement facts", "score": 0.95, "source": "s3://docs/product.json", "section_title": "Supplement Facts", "metadata": "{}"},
        {"text": "FDA labeling requirement", "score": 0.88, "source": "s3://docs/fda.pdf", "section_title": "Labeling", "metadata": "{}"},
    ]
    with patch("src.compliance.tools.search_documents.retrieve", return_value=mock_results):
        from src.compliance.tools.search_documents import search_documents
        result = search_documents(query="vitamin D3 supplement facts", n_results=5)

    assert result["status"] == "ok"
    assert len(result["data"]) == 2
    assert result["data"][0]["text"] == "Vitamin D3 supplement facts"
    assert result["data"][0]["source"] == "s3://docs/product.json"


def test_search_documents_returns_ok_empty_when_no_results():
    with patch("src.compliance.tools.search_documents.retrieve", return_value=[]):
        from src.compliance.tools.search_documents import search_documents
        result = search_documents(query="nonexistent ingredient xyz", n_results=5)

    assert result["status"] == "ok"
    assert result["data"] == []


def test_search_documents_returns_error_on_exception():
    with patch("src.compliance.tools.search_documents.retrieve", side_effect=Exception("connection refused")):
        from src.compliance.tools.search_documents import search_documents
        result = search_documents(query="vitamin D3", n_results=5)

    assert result["status"] == "error"
    assert "connection refused" in result["message"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_research_tools.py::test_search_documents_returns_ok_with_results tests/test_research_tools.py::test_search_documents_returns_ok_empty_when_no_results tests/test_research_tools.py::test_search_documents_returns_error_on_exception -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'src.compliance.tools'`

- [ ] **Step 4: Implement search_documents tool**

Create `src/compliance/tools/search_documents.py`:

```python
from src.common.vector_store import retrieve


def search_documents(query: str, n_results: int = 5) -> dict:
    """Search the pgvector document store for relevant content.

    Queries product labels, FDA guidance, and other ingested documents.
    Returns ranked text chunks with source metadata.
    """
    try:
        results = retrieve(query, n_results=n_results)
        return {
            "status": "ok",
            "data": [
                {
                    "text": r["text"],
                    "score": r["score"],
                    "source": r["source"],
                    "section_title": r["section_title"],
                }
                for r in results
            ],
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_research_tools.py::test_search_documents_returns_ok_with_results tests/test_research_tools.py::test_search_documents_returns_ok_empty_when_no_results tests/test_research_tools.py::test_search_documents_returns_error_on_exception -v`

Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add src/compliance/tools/__init__.py src/compliance/tools/search_documents.py tests/test_research_tools.py
git commit -m "feat: add search_documents tool for research agent"
```

---

### Task 3: query_database Tool

**Files:**
- Create: `src/compliance/tools/query_database.py`
- Modify: `tests/test_research_tools.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_research_tools.py`:

```python
from unittest.mock import patch, MagicMock


def test_query_database_product_bom():
    mock_components = [
        {"bom_id": 1, "product_id": 100, "sku": "RM-C1-vitamin-c-abcd1234", "company_id": 1, "component_company_name": "TestCo"},
    ]
    with patch("src.compliance.tools.query_database.get_bom_components", return_value=mock_components):
        from src.compliance.tools.query_database import query_database
        result = query_database(query_type="product_bom", product_id=10)

    assert result["status"] == "ok"
    assert len(result["data"]) == 1
    assert result["data"][0]["sku"] == "RM-C1-vitamin-c-abcd1234"


def test_query_database_ingredient_aliases():
    mock_aliases = [
        {"Id": 1, "CanonicalName": "vitamin-c", "AliasName": "ascorbic-acid", "MatchType": "alias", "Notes": "same entity", "Approved": 1},
    ]
    with patch("src.compliance.tools.query_database.get_alias_rows", return_value=mock_aliases):
        from src.compliance.tools.query_database import query_database
        result = query_database(query_type="ingredient_aliases", ingredient_name="ascorbic-acid")

    assert result["status"] == "ok"
    assert result["data"][0]["CanonicalName"] == "vitamin-c"


def test_query_database_ingredient_facts():
    with patch(
        "src.compliance.tools.query_database.get_cached_ingredient_facts",
        return_value={"canonical_name": "vitamin-c", "vegan_compatible": True, "allergens": [], "certifications": ["demo-identity-reviewed"], "evidence_strength": "high", "notes": "demo"},
    ):
        from src.compliance.tools.query_database import query_database
        result = query_database(query_type="ingredient_facts", ingredient_name="vitamin-c")

    assert result["status"] == "ok"
    assert result["data"]["canonical_name"] == "vitamin-c"


def test_query_database_unknown_query_type():
    from src.compliance.tools.query_database import query_database
    result = query_database(query_type="nonexistent_query", product_id=1)
    assert result["status"] == "error"
    assert "Unknown query_type" in result["message"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_research_tools.py::test_query_database_product_bom tests/test_research_tools.py::test_query_database_ingredient_aliases tests/test_research_tools.py::test_query_database_ingredient_facts tests/test_research_tools.py::test_query_database_unknown_query_type -v`

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement query_database tool**

Create `src/compliance/tools/query_database.py`:

```python
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
            return {"status": "ok", "data": [dict(r) for r in data]}

        if query_type == "ingredient_facts":
            data = get_cached_ingredient_facts(ingredient_name)
            return {"status": "ok", "data": data or {}}

        return {"status": "error", "message": f"Unknown query_type: {query_type}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_research_tools.py::test_query_database_product_bom tests/test_research_tools.py::test_query_database_ingredient_aliases tests/test_research_tools.py::test_query_database_ingredient_facts tests/test_research_tools.py::test_query_database_unknown_query_type -v`

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/compliance/tools/query_database.py tests/test_research_tools.py
git commit -m "feat: add query_database tool for research agent"
```

---

### Task 4: web_search Tool

**Files:**
- Create: `src/compliance/tools/web_search.py`
- Modify: `tests/test_research_tools.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_research_tools.py`:

```python
def test_web_search_returns_results():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "web": {
            "results": [
                {"title": "FDA Vitamin D3 Guidance", "url": "https://fda.gov/d3", "description": "Labeling requirements for vitamin D3"},
                {"title": "D3 Safety Review", "url": "https://example.com/d3", "description": "Safety review of D3 supplements"},
            ]
        }
    }
    with patch("src.compliance.tools.web_search.httpx.get", return_value=mock_response):
        with patch.dict("os.environ", {"BRAVE_API_KEY": "test-key"}):
            from src.compliance.tools.web_search import web_search
            result = web_search(query="FDA vitamin D3 labeling requirements")

    assert result["status"] == "ok"
    assert len(result["data"]) == 2
    assert result["data"][0]["title"] == "FDA Vitamin D3 Guidance"


def test_web_search_returns_error_without_api_key():
    with patch.dict("os.environ", {}, clear=True):
        import importlib
        import src.compliance.tools.web_search as ws_mod
        importlib.reload(ws_mod)
        result = ws_mod.web_search(query="test query")

    assert result["status"] == "error"
    assert "BRAVE_API_KEY" in result["message"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_research_tools.py::test_web_search_returns_results tests/test_research_tools.py::test_web_search_returns_error_without_api_key -v`

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement web_search tool**

Create `src/compliance/tools/web_search.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_research_tools.py::test_web_search_returns_results tests/test_research_tools.py::test_web_search_returns_error_without_api_key -v`

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/compliance/tools/web_search.py tests/test_research_tools.py
git commit -m "feat: add web_search tool for research agent"
```

---

### Task 5: pubchem_lookup Tool

**Files:**
- Create: `src/compliance/tools/pubchem_lookup.py`
- Modify: `tests/test_research_tools.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_research_tools.py`:

```python
def test_pubchem_lookup_by_name():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "PC_Compounds": [
            {
                "id": {"id": {"cid": 5280795}},
                "props": [
                    {"urn": {"label": "IUPAC Name", "name": "Preferred"}, "value": {"sval": "cholecalciferol"}},
                    {"urn": {"label": "Molecular Formula"}, "value": {"sval": "C27H44O"}},
                    {"urn": {"label": "Molecular Weight"}, "value": {"fval": 384.64}},
                ],
            }
        ]
    }
    with patch("src.compliance.tools.pubchem_lookup.httpx.get", return_value=mock_response):
        from src.compliance.tools.pubchem_lookup import pubchem_lookup
        result = pubchem_lookup(compound="cholecalciferol")

    assert result["status"] == "ok"
    assert result["data"]["cid"] == 5280795


def test_pubchem_lookup_not_found():
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Not Found", request=MagicMock(), response=mock_response
    )
    with patch("src.compliance.tools.pubchem_lookup.httpx.get", return_value=mock_response) as mock_get:
        mock_get.return_value.raise_for_status = mock_response.raise_for_status
        from src.compliance.tools.pubchem_lookup import pubchem_lookup
        result = pubchem_lookup(compound="xyznonexistent12345")

    assert result["status"] == "error"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_research_tools.py::test_pubchem_lookup_by_name tests/test_research_tools.py::test_pubchem_lookup_not_found -v`

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement pubchem_lookup tool**

Create `src/compliance/tools/pubchem_lookup.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_research_tools.py::test_pubchem_lookup_by_name tests/test_research_tools.py::test_pubchem_lookup_not_found -v`

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/compliance/tools/pubchem_lookup.py tests/test_research_tools.py
git commit -m "feat: add pubchem_lookup tool for research agent"
```

---

### Task 6: fda_lookup Tool

**Files:**
- Create: `src/compliance/tools/fda_lookup.py`
- Modify: `tests/test_research_tools.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_research_tools.py`:

```python
def test_fda_lookup_labeling():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {"openfda": {"brand_name": ["Test Supplement"]}, "indications_and_usage": ["dietary supplement"]},
        ]
    }
    with patch("src.compliance.tools.fda_lookup.httpx.get", return_value=mock_response):
        from src.compliance.tools.fda_lookup import fda_lookup
        result = fda_lookup(ingredient_name="vitamin D3", endpoint="labeling")

    assert result["status"] == "ok"
    assert len(result["data"]) == 1


def test_fda_lookup_adverse_events():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {"reactions": ["nausea"], "serious": 1},
        ]
    }
    with patch("src.compliance.tools.fda_lookup.httpx.get", return_value=mock_response):
        from src.compliance.tools.fda_lookup import fda_lookup
        result = fda_lookup(ingredient_name="vitamin D3", endpoint="adverse_events")

    assert result["status"] == "ok"
    assert len(result["data"]) == 1


def test_fda_lookup_invalid_endpoint():
    from src.compliance.tools.fda_lookup import fda_lookup
    result = fda_lookup(ingredient_name="vitamin D3", endpoint="invalid")
    assert result["status"] == "error"
    assert "Unknown endpoint" in result["message"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_research_tools.py::test_fda_lookup_labeling tests/test_research_tools.py::test_fda_lookup_adverse_events tests/test_research_tools.py::test_fda_lookup_invalid_endpoint -v`

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement fda_lookup tool**

Create `src/compliance/tools/fda_lookup.py`:

```python
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
        return {"status": "error", "message": f"Unknown endpoint: {endpoint}. Choose from: {list(ENDPOINT_MAP.keys())}"}

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_research_tools.py::test_fda_lookup_labeling tests/test_research_tools.py::test_fda_lookup_adverse_events tests/test_research_tools.py::test_fda_lookup_invalid_endpoint -v`

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/compliance/tools/fda_lookup.py tests/test_research_tools.py
git commit -m "feat: add fda_lookup tool for research agent"
```

---

### Task 7: Research Agent Core

**Files:**
- Create: `src/compliance/research_agent.py`
- Create: `tests/test_research_agent.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_research_agent.py`:

```python
from unittest.mock import patch, MagicMock


def test_research_substitution_returns_verdict_shape():
    mock_agent = MagicMock()
    mock_agent.invoke.return_value = {
        "structured_response": MagicMock(
            facts=["Ascorbic acid is the same chemical entity as vitamin C"],
            rules=["FDA allows chemical name variants on supplement facts panels"],
            inference="The substitute is chemically identical to the original.",
            caveats=["No dosage equivalence data available"],
            evidence_rows=[
                {
                    "source_type": "pgvector",
                    "source_label": "Document search",
                    "source_uri": "s3://docs/product.json",
                    "fact_type": "product_context",
                    "fact_value": "Product contains vitamin C as ascorbic acid",
                    "quality_score": 0.9,
                    "snippet": "Supplement Facts: Vitamin C (as Ascorbic Acid) 1000mg",
                }
            ],
        )
    }

    with patch("src.compliance.research_agent.create_deep_agent", return_value=mock_agent):
        with patch("src.compliance.research_agent.ChatBedrockConverse"):
            from src.compliance.research_agent import research_substitution

            result = research_substitution(
                original={
                    "original_ingredient": "vitamin-c",
                    "group": {"canonical_name": "vitamin-c", "function": "antioxidant"},
                    "requirements": [],
                },
                substitute={"current_match_name": "ascorbic-acid", "match_type": "alias"},
                product_sku="FG-iherb-10421",
                company_name="NOW Foods",
            )

    assert "facts" in result
    assert "rules" in result
    assert "inference" in result
    assert "caveats" in result
    assert "evidence_rows" in result
    assert isinstance(result["facts"], list)
    assert isinstance(result["evidence_rows"], list)


def test_research_substitution_excluded_tools_when_no_brave_key():
    mock_agent = MagicMock()
    mock_agent.invoke.return_value = {
        "structured_response": MagicMock(
            facts=[], rules=[], inference="No evidence found.", caveats=["Limited tools available"], evidence_rows=[],
        )
    }

    with patch("src.compliance.research_agent.create_deep_agent", return_value=mock_agent) as mock_create:
        with patch("src.compliance.research_agent.ChatBedrockConverse"):
            with patch.dict("os.environ", {}, clear=False):
                import os
                os.environ.pop("BRAVE_API_KEY", None)
                from src.compliance.research_agent import _build_tools
                tools = _build_tools()

    tool_names = [t.__name__ for t in tools]
    assert "search_documents" in tool_names
    assert "query_database" in tool_names
    assert "web_search" not in tool_names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_research_agent.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'src.compliance.research_agent'`

- [ ] **Step 3: Implement research_agent.py**

Create `src/compliance/research_agent.py`:

```python
import logging
import os

from deepagents import create_deep_agent
from langchain_aws import ChatBedrockConverse
from pydantic import BaseModel

from src.compliance.tools.fda_lookup import fda_lookup
from src.compliance.tools.pubchem_lookup import pubchem_lookup
from src.compliance.tools.query_database import query_database
from src.compliance.tools.search_documents import search_documents
from src.compliance.tools.web_search import web_search

logger = logging.getLogger(__name__)

RESEARCH_SYSTEM_PROMPT = """\
You are an FDA dietary supplement compliance research agent. Your job is to \
thoroughly research whether a proposed ingredient substitution is safe and \
compliant before issuing a verdict.

You have tools to search a local document store (scraped product labels, FDA \
docs), query a structured database (BOMs, suppliers, ingredient aliases), \
search the web, look up compounds on PubChem, and query the openFDA API.

Research strategy:
1. Start by searching the local document store for the product and ingredient.
2. Check the database for ingredient aliases, supplier data, and portfolio usage.
3. If local evidence is insufficient, search the web, PubChem, or FDA for \
   external data on the ingredient pair.
4. Stop when you have enough evidence to make a confident verdict.

For your final answer, provide:
- facts: concrete facts you found from any source
- rules: applicable FDA rules or regulatory requirements
- inference: your reasoning connecting facts to rules
- caveats: limitations, uncertainties, or missing evidence
- evidence_rows: structured evidence for each significant finding, each with \
  source_type (pgvector, sqlite, web-search, pubchem, fda-api), source_label, \
  source_uri, fact_type, fact_value, quality_score (0.0-1.0), and snippet.

IMPORTANT:
- Only state facts you can support with evidence from your tools.
- If evidence is missing, say "insufficient evidence" for that aspect.
- Never guess about compliance — flag uncertainty explicitly.
"""


class SubstitutionVerdict(BaseModel):
    facts: list[str]
    rules: list[str]
    inference: str
    caveats: list[str]
    evidence_rows: list[dict]


def _build_tools():
    tools = [search_documents, query_database, pubchem_lookup, fda_lookup]
    if os.environ.get("BRAVE_API_KEY"):
        tools.append(web_search)
    return tools


def _build_agent():
    model_id = os.environ.get("RESEARCH_MODEL_ID", "us.anthropic.claude-sonnet-4-6-v1:0")
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

    llm = ChatBedrockConverse(
        model=model_id,
        provider="anthropic",
        region_name=region,
    )

    max_rounds = int(os.environ.get("RESEARCH_MAX_ROUNDS", "20"))

    return create_deep_agent(
        model=llm,
        tools=_build_tools(),
        system_prompt=RESEARCH_SYSTEM_PROMPT,
        response_format=SubstitutionVerdict,
    ), max_rounds


def research_substitution(original, substitute, product_sku, company_name):
    agent, max_rounds = _build_agent()

    user_message = (
        f"Research this ingredient substitution for compliance:\n\n"
        f"PRODUCT: {company_name} — {product_sku}\n"
        f"ORIGINAL INGREDIENT: {original['original_ingredient']} "
        f"(canonical: {original['group']['canonical_name']}, "
        f"function: {original['group']['function']})\n"
        f"PROPOSED SUBSTITUTE: {substitute.get('current_match_name', 'unknown')} "
        f"(match type: {substitute.get('match_type', 'unknown')})\n\n"
        f"Investigate whether this substitution is safe, compliant with FDA "
        f"regulations, and functionally equivalent. Check for allergen conflicts, "
        f"labeling implications, certification issues, and bioavailability differences."
    )

    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
        config={"recursion_limit": max_rounds * 2},
    )

    verdict = result["structured_response"]
    return {
        "facts": verdict.facts,
        "rules": verdict.rules,
        "inference": verdict.inference,
        "caveats": verdict.caveats,
        "evidence_rows": verdict.evidence_rows,
        "kb_sources": [],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_research_agent.py -v`

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/compliance/research_agent.py tests/test_research_agent.py
git commit -m "feat: add research agent core with DeepAgents and Bedrock"
```

---

### Task 8: Wire Research Agent into evaluate.py

**Files:**
- Modify: `src/compliance/evaluate.py:88-136`

- [ ] **Step 1: Write the failing test**

Create `tests/test_evaluate_research.py`:

```python
from unittest.mock import patch, MagicMock


def test_evaluate_substitution_uses_research_agent():
    mock_blocker = {
        "verdict": "pass_known_blockers",
        "confidence": "high",
        "rules": ["No known blockers"],
        "inference": "Passed blocker checks.",
        "blocker_state": "pass_known_blockers",
        "evidence_completeness": "high",
    }
    mock_research = {
        "facts": ["Ascorbic acid is vitamin C"],
        "rules": ["FDA 21 CFR 101.36"],
        "inference": "Chemically identical.",
        "caveats": [],
        "evidence_rows": [
            {
                "source_type": "pgvector",
                "source_label": "Document search",
                "source_uri": "s3://test",
                "fact_type": "identity",
                "fact_value": "same compound",
                "quality_score": 0.95,
                "snippet": "test",
            }
        ],
        "kb_sources": ["s3://test"],
    }

    with patch("src.compliance.evaluate._blocker_evaluation", return_value=mock_blocker):
        with patch("src.compliance.evaluate.research_substitution", return_value=mock_research):
            from src.compliance.evaluate import evaluate_substitution

            result = evaluate_substitution(
                original={
                    "original_ingredient": "vitamin-c",
                    "group": {"canonical_name": "vitamin-c", "function": "antioxidant"},
                    "requirements": [],
                },
                substitute={"current_match_name": "ascorbic-acid", "match_type": "alias", "ingredient_name": "ascorbic-acid"},
                product_sku="FG-iherb-10421",
                company_name="NOW Foods",
            )

    assert result["verdict"] == "pass_known_blockers"
    assert "Ascorbic acid is vitamin C" in result["facts"]
    assert "FDA 21 CFR 101.36" in result["rules"]


def test_evaluate_substitution_falls_back_on_research_failure():
    mock_blocker = {
        "verdict": "pass_known_blockers",
        "confidence": "high",
        "rules": ["No known blockers"],
        "inference": "Passed blocker checks.",
        "blocker_state": "pass_known_blockers",
        "evidence_completeness": "high",
    }
    mock_rag = {
        "facts": ["fallback fact"],
        "rules": [],
        "inference": "fallback",
        "caveats": ["RAG only"],
        "kb_sources": ["s3://fallback"],
    }

    with patch("src.compliance.evaluate._blocker_evaluation", return_value=mock_blocker):
        with patch("src.compliance.evaluate.research_substitution", side_effect=Exception("agent failed")):
            with patch("src.compliance.evaluate._rag_evaluation", return_value=mock_rag):
                from src.compliance.evaluate import evaluate_substitution

                result = evaluate_substitution(
                    original={
                        "original_ingredient": "vitamin-c",
                        "group": {"canonical_name": "vitamin-c", "function": "antioxidant"},
                        "requirements": [],
                    },
                    substitute={"current_match_name": "ascorbic-acid", "match_type": "alias", "ingredient_name": "ascorbic-acid"},
                    product_sku="FG-iherb-10421",
                    company_name="NOW Foods",
                )

    assert "fallback fact" in result["facts"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_evaluate_research.py -v`

Expected: FAIL — `research_substitution` is not yet imported in `evaluate.py`

- [ ] **Step 3: Modify evaluate.py to use the research agent**

In `src/compliance/evaluate.py`, add the import at the top (after existing imports):

```python
from src.compliance.research_agent import research_substitution
```

Replace the body of `evaluate_substitution()` (lines 88-136) with:

```python
def evaluate_substitution(original, substitute, product_sku, company_name):
    blocker_result = _blocker_evaluation(original, substitute, product_sku)

    research_enabled = os.environ.get("RESEARCH_ENABLED", "true").lower() == "true"

    rag_result = {}
    if research_enabled:
        try:
            rag_result = research_substitution(
                original=original,
                substitute=substitute,
                product_sku=product_sku,
                company_name=company_name,
            )
        except Exception:
            logger.warning(
                "Research agent failed for %s → %s, falling back to RAG",
                original["original_ingredient"],
                substitute.get("current_match_name") or substitute.get("ingredient_name"),
                exc_info=True,
            )

    if not rag_result:
        try:
            rag_result = _rag_evaluation(original, substitute, product_sku, company_name)
        except Exception:
            logger.warning(
                "RAG evaluation also unavailable for %s → %s, using blocker engine only",
                original["original_ingredient"],
                substitute.get("current_match_name") or substitute.get("ingredient_name"),
                exc_info=True,
            )

    rag_facts = rag_result.get("facts", [])
    rag_rules = rag_result.get("rules", [])
    rag_inference = rag_result.get("inference", "")
    rag_caveats = rag_result.get("caveats", [])

    combined_rules = blocker_result["rules"] + [
        r for r in rag_rules if r not in blocker_result["rules"]
    ]
    combined_inference = blocker_result["inference"]
    if rag_inference:
        combined_inference += "\n\n[Research-grounded analysis]\n" + rag_inference

    caveats = rag_caveats if rag_caveats else [
        "Research agent and RAG evaluation unavailable. Deterministic blocker engine only."
    ]

    sub_name = substitute.get("current_match_name") or substitute["ingredient_name"]

    return {
        "original": original["original_ingredient"],
        "substitute": sub_name,
        "verdict": blocker_result["verdict"],
        "confidence": blocker_result["confidence"],
        "facts": rag_facts,
        "rules": combined_rules,
        "inference": combined_inference,
        "sources": [
            f"demo://product/{product_sku}",
            f"demo://ingredient/{sub_name}",
        ] + rag_result.get("kb_sources", []),
        "caveats": caveats,
        "blocker_state": blocker_result["blocker_state"],
        "evidence_completeness": blocker_result["evidence_completeness"],
        "match_type": substitute["match_type"],
    }
```

Also add `import os` at the top of the file if not already present.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_evaluate_research.py -v`

Expected: 2 passed

- [ ] **Step 5: Run existing evaluate-related tests to check for regressions**

Run: `python -m pytest tests/ -v`

Expected: All existing tests pass. The new code path only activates when `RESEARCH_ENABLED=true` (default), but existing tests mock `_blocker_evaluation` and `_rag_evaluation` directly, so they're unaffected.

- [ ] **Step 6: Commit**

```bash
git add src/compliance/evaluate.py tests/test_evaluate_research.py
git commit -m "feat: wire research agent into evaluate pipeline with fallback"
```

---

### Task 9: CLI Research Script

**Files:**
- Create: `scripts/research.py`
- Create: `tests/test_research_cli.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_research_cli.py`:

```python
import subprocess
import sys


def test_research_cli_missing_args():
    result = subprocess.run(
        [sys.executable, "scripts/research.py"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "required" in result.stderr.lower() or "error" in result.stderr.lower()


def test_research_cli_help():
    result = subprocess.run(
        [sys.executable, "scripts/research.py", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--product-sku" in result.stdout
    assert "--original" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_research_cli.py -v`

Expected: FAIL — `No such file or directory: 'scripts/research.py'`

- [ ] **Step 3: Implement the CLI script**

Create `scripts/research.py`:

```python
import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common.db import (
    get_bom_components,
    get_finished_goods,
    get_product,
    parse_ingredient_name,
)
from src.compliance.research_agent import research_substitution
from src.opportunity.store import ensure_workspace_ready
from src.substitute.find_candidates import find_candidates_for_component

GREEN = "\033[92m"
ORANGE = "\033[93m"
RED = "\033[91m"
GRAY = "\033[90m"
RESET = "\033[0m"
BOLD = "\033[1m"

VERDICT_COLORS = {
    "safe": GREEN,
    "pass_known_blockers": GREEN,
    "risky": ORANGE,
    "needs_review": ORANGE,
    "incompatible": RED,
    "blocked": RED,
    "insufficient-evidence": GRAY,
}


def find_product_by_sku(sku):
    for product in get_finished_goods():
        if product["sku"] == sku:
            return product
    return None


def find_component_by_ingredient(product, ingredient_name):
    components = get_bom_components(product_id=product["product_id"])
    for component in components:
        if parse_ingredient_name(component["sku"]) == ingredient_name:
            return component
    return None


def print_verdict(candidate_name, result):
    verdict = result.get("verdict", result.get("blocker_state", "unknown"))
    color = VERDICT_COLORS.get(verdict, GRAY)
    print(f"\n{BOLD}Candidate: {candidate_name}{RESET}")
    print(f"  Verdict: {color}{verdict.upper()}{RESET}")
    print(f"  Confidence: {result.get('confidence', 'unknown')}")

    if result.get("facts"):
        print(f"  {BOLD}Facts:{RESET}")
        for fact in result["facts"]:
            print(f"    - {fact}")

    if result.get("rules"):
        print(f"  {BOLD}Rules:{RESET}")
        for rule in result["rules"]:
            print(f"    - {rule}")

    if result.get("inference"):
        print(f"  {BOLD}Reasoning:{RESET} {result['inference']}")

    if result.get("caveats"):
        print(f"  {BOLD}Caveats:{RESET}")
        for caveat in result["caveats"]:
            print(f"    - {caveat}")

    if result.get("sources"):
        print(f"  {BOLD}Sources:{RESET}")
        for source in result["sources"]:
            print(f"    - {source}")


def main():
    parser = argparse.ArgumentParser(
        description="Run the agentic research agent for a product ingredient"
    )
    parser.add_argument("--product-sku", required=True, help="Finished product SKU (e.g. FG-iherb-10421)")
    parser.add_argument("--original", required=True, help="Original ingredient name (e.g. vitamin-d3)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    ensure_workspace_ready()

    product = find_product_by_sku(args.product_sku)
    if not product:
        print(f"{RED}Error: Product '{args.product_sku}' not found.{RESET}", file=sys.stderr)
        sys.exit(1)

    component = find_component_by_ingredient(product, args.original)
    if not component:
        print(
            f"{RED}Error: Ingredient '{args.original}' not found in BOM for {args.product_sku}.{RESET}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"{BOLD}Product:{RESET} {product['company_name']} — {product['sku']}")
    print(f"{BOLD}Original ingredient:{RESET} {args.original}")

    candidates_data = find_candidates_for_component(component=component, finished_product=product)
    all_candidates = candidates_data["exact_candidates"] + candidates_data["alias_candidates"]

    if not all_candidates:
        print(f"\n{GRAY}No substitution candidates found for {args.original}.{RESET}")
        sys.exit(0)

    print(f"\nFound {len(all_candidates)} candidate(s). Researching...\n")
    print("=" * 60)

    original_info = {
        "original_ingredient": candidates_data["original_ingredient"],
        "group": {
            "canonical_name": ", ".join(candidates_data["canonical_names"]),
            "function": "reviewed-alias-layer" if candidates_data["alias_candidates"] else "exact-match",
        },
        "requirements": [],
    }

    for candidate in all_candidates:
        sub_info = {
            "current_match_name": candidate["current_match_name"],
            "match_type": candidate["match_type"],
            "ingredient_name": candidate["current_match_name"],
        }

        try:
            result = research_substitution(
                original=original_info,
                substitute=sub_info,
                product_sku=product["sku"],
                company_name=product["company_name"],
            )
            print_verdict(candidate["current_match_name"], result)
        except Exception as e:
            print(f"\n{RED}Error researching {candidate['current_match_name']}: {e}{RESET}")

    print("\n" + "=" * 60)
    print(f"{BOLD}Research complete.{RESET}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_research_cli.py -v`

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/research.py tests/test_research_cli.py
git commit -m "feat: add CLI research script for terminal-based research"
```

---

### Task 10: Final Integration Test & Cleanup

**Files:**
- All files from previous tasks

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ -v`

Expected: All tests pass — both new and existing.

- [ ] **Step 2: Verify the CLI script shows help correctly**

Run: `python scripts/research.py --help`

Expected output should show `--product-sku` and `--original` as required arguments.

- [ ] **Step 3: Verify imports are clean**

Run: `python -c "from src.compliance.research_agent import research_substitution; print('OK')"`

Expected: `OK`

- [ ] **Step 4: Verify tool list excludes web_search when BRAVE_API_KEY is unset**

Run: `BRAVE_API_KEY= python -c "from src.compliance.research_agent import _build_tools; tools = _build_tools(); print([t.__name__ for t in tools])"`

Expected: List without `web_search`: `['search_documents', 'query_database', 'pubchem_lookup', 'fda_lookup']`

- [ ] **Step 5: Commit any final adjustments**

```bash
git add -A
git commit -m "chore: final integration verification for research agent"
```
