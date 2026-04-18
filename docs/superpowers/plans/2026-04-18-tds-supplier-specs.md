# TDS / Supplier Specs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the research agent to search for Technical Data Sheets / fact sheets per supplier-product, extract specs as key-value pairs, persist them in a new EAV table, and show a comparison view in the UI.

**Architecture:** New `Supplier_Spec` EAV table stores per-(supplier, product) spec rows. A new `search_tds` tool does two-phase search (pgvector local → web fallback). The research agent's system prompt instructs it to call the tool per supplier and emit `spec:*` evidence rows. `run_research` extracts spec rows from the verdict and upserts them. The Product Research page pivots specs into a comparison table.

**Tech Stack:** Python, SQLite, Streamlit, pgvector (via existing `search_documents`), Brave Search API (via existing `web_search`)

**Spec:** `docs/superpowers/specs/2026-04-18-tds-supplier-specs-design.md`

---

### Task 1: Add `Supplier_Spec` Table and DB Helpers

**Files:**
- Modify: `src/common/db.py` (in `init_workspace_schema` around line 231, and add new functions at end of file)
- Test: `tests/test_supplier_specs.py` (create)

- [ ] **Step 1: Write the failing test for `upsert_supplier_spec`**

Create `tests/test_supplier_specs.py`:

```python
import sqlite3
from src.common.db import init_workspace_schema, upsert_supplier_spec, get_supplier_specs


def _setup_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE Supplier (Id INTEGER PRIMARY KEY, Name TEXT NOT NULL)")
    conn.execute("CREATE TABLE Product (Id INTEGER PRIMARY KEY, SKU TEXT NOT NULL, CompanyId INTEGER NOT NULL, Type TEXT NOT NULL)")
    conn.execute("INSERT INTO Supplier (Id, Name) VALUES (1, 'ADM'), (2, 'AIDP')")
    conn.execute("INSERT INTO Product (Id, SKU, CompanyId, Type) VALUES (100, 'RM-C1-vitamin-c-abcd1234', 1, 'raw-material')")
    conn.commit()
    conn.close()
    init_workspace_schema(db_path)
    return db_path


def test_upsert_supplier_spec_insert(tmp_path):
    db_path = _setup_db(tmp_path)
    upsert_supplier_spec(
        db_path=db_path,
        supplier_id=1,
        product_id=100,
        spec_key="purity",
        spec_value="99.5",
        spec_unit="%",
        source_uri="https://adm.com/tds/vitc.pdf",
        source_type="web-search",
    )
    specs = get_supplier_specs(db_path=db_path, product_id=100)
    assert len(specs) == 1
    assert specs[0]["SpecKey"] == "purity"
    assert specs[0]["SpecValue"] == "99.5"
    assert specs[0]["SpecUnit"] == "%"
    assert specs[0]["SupplierId"] == 1


def test_upsert_supplier_spec_updates_on_conflict(tmp_path):
    db_path = _setup_db(tmp_path)
    upsert_supplier_spec(db_path=db_path, supplier_id=1, product_id=100, spec_key="purity", spec_value="98.0", spec_unit="%")
    upsert_supplier_spec(db_path=db_path, supplier_id=1, product_id=100, spec_key="purity", spec_value="99.5", spec_unit="%")
    specs = get_supplier_specs(db_path=db_path, product_id=100)
    purity_rows = [s for s in specs if s["SpecKey"] == "purity"]
    assert len(purity_rows) == 1
    assert purity_rows[0]["SpecValue"] == "99.5"


def test_get_supplier_specs_multiple_suppliers(tmp_path):
    db_path = _setup_db(tmp_path)
    upsert_supplier_spec(db_path=db_path, supplier_id=1, product_id=100, spec_key="purity", spec_value="99.5", spec_unit="%")
    upsert_supplier_spec(db_path=db_path, supplier_id=2, product_id=100, spec_key="purity", spec_value="98.0", spec_unit="%")
    upsert_supplier_spec(db_path=db_path, supplier_id=1, product_id=100, spec_key="form_grade", spec_value="USP")
    specs = get_supplier_specs(db_path=db_path, product_id=100)
    assert len(specs) == 3
    supplier_ids = {s["SupplierId"] for s in specs}
    assert supplier_ids == {1, 2}


def test_different_products_same_supplier_different_specs(tmp_path):
    db_path = _setup_db(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO Product (Id, SKU, CompanyId, Type) VALUES (101, 'RM-C1-vitamin-c-efgh5678', 1, 'raw-material')")
    conn.commit()
    conn.close()
    upsert_supplier_spec(db_path=db_path, supplier_id=1, product_id=100, spec_key="purity", spec_value="99.5", spec_unit="%")
    upsert_supplier_spec(db_path=db_path, supplier_id=1, product_id=101, spec_key="purity", spec_value="98.0", spec_unit="%")
    specs_100 = get_supplier_specs(db_path=db_path, product_id=100)
    specs_101 = get_supplier_specs(db_path=db_path, product_id=101)
    assert len(specs_100) == 1
    assert specs_100[0]["SpecValue"] == "99.5"
    assert len(specs_101) == 1
    assert specs_101[0]["SpecValue"] == "98.0"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_supplier_specs.py -v`
Expected: FAIL with `ImportError` (functions don't exist yet)

- [ ] **Step 3: Add `Supplier_Spec` table to `init_workspace_schema`**

In `src/common/db.py`, inside `init_workspace_schema()`, add this SQL after the `Research_Job` table creation (before the `CREATE INDEX` statements, around line 243):

```python
        CREATE TABLE IF NOT EXISTS Supplier_Spec (
            Id INTEGER PRIMARY KEY,
            SupplierId INTEGER NOT NULL,
            ProductId INTEGER NOT NULL,
            SpecKey TEXT NOT NULL,
            SpecValue TEXT NOT NULL,
            SpecUnit TEXT,
            SourceUri TEXT,
            SourceType TEXT,
            ExtractedAt TEXT NOT NULL,
            FOREIGN KEY (SupplierId) REFERENCES Supplier (Id),
            FOREIGN KEY (ProductId) REFERENCES Product (Id)
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_supplier_spec_key
            ON Supplier_Spec (SupplierId, ProductId, SpecKey);
```

- [ ] **Step 4: Implement `upsert_supplier_spec` and `get_supplier_specs`**

Add to the end of `src/common/db.py` (before any `if __name__` block if present):

```python
def upsert_supplier_spec(db_path=None, supplier_id=None, product_id=None,
                         spec_key=None, spec_value=None, spec_unit=None,
                         source_uri=None, source_type=None):
    conn = get_connection(db_path)
    conn.execute(
        """
        INSERT INTO Supplier_Spec (SupplierId, ProductId, SpecKey, SpecValue, SpecUnit, SourceUri, SourceType, ExtractedAt)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (SupplierId, ProductId, SpecKey)
        DO UPDATE SET SpecValue = excluded.SpecValue,
                      SpecUnit = excluded.SpecUnit,
                      SourceUri = excluded.SourceUri,
                      SourceType = excluded.SourceType,
                      ExtractedAt = excluded.ExtractedAt
        """,
        (supplier_id, product_id, spec_key, spec_value, spec_unit, source_uri, source_type, now_iso()),
    )
    conn.commit()
    conn.close()


def get_supplier_specs(db_path=None, product_id=None):
    conn = get_connection(db_path)
    rows = conn.execute(
        """
        SELECT ss.*, s.Name AS SupplierName
        FROM Supplier_Spec ss
        JOIN Supplier s ON s.Id = ss.SupplierId
        WHERE ss.ProductId = ?
        ORDER BY s.Name, ss.SpecKey
        """,
        (product_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_supplier_id_by_name(db_path=None, supplier_name=None):
    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT Id FROM Supplier WHERE Name = ?",
        (supplier_name,),
    ).fetchone()
    conn.close()
    return row["Id"] if row else None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_supplier_specs.py -v`
Expected: all 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_supplier_specs.py src/common/db.py
git commit -m "feat: add Supplier_Spec EAV table and DB helpers"
```

---

### Task 2: Create `search_tds` Tool

**Files:**
- Create: `src/compliance/tools/search_tds.py`
- Test: `tests/test_search_tds.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_search_tds.py`:

```python
from unittest.mock import patch


def test_search_tds_local_results_only():
    mock_local = [
        {"text": "Purity: 99.5%, Heavy metals (Pb): <0.5ppm", "score": 0.85, "source": "s3://tds/adm-vitc.pdf", "section_title": "Specifications"},
    ]
    with patch("src.compliance.tools.search_tds.search_documents", return_value={"status": "ok", "data": mock_local}):
        from src.compliance.tools.search_tds import search_tds
        result = search_tds(ingredient_name="vitamin-c", supplier_name="ADM")

    assert result["status"] == "ok"
    assert len(result["data"]["local_results"]) == 1
    assert result["data"]["web_results"] == []
    assert result["data"]["supplier_name"] == "ADM"


def test_search_tds_falls_back_to_web_when_local_empty():
    mock_web = {
        "status": "ok",
        "data": [
            {"title": "ADM Vitamin C TDS", "url": "https://adm.com/tds", "description": "Purity 99.5%"},
        ],
    }
    with patch("src.compliance.tools.search_tds.search_documents", return_value={"status": "ok", "data": []}):
        with patch("src.compliance.tools.search_tds.web_search", return_value=mock_web):
            from src.compliance.tools.search_tds import search_tds
            result = search_tds(ingredient_name="vitamin-c", supplier_name="ADM")

    assert result["status"] == "ok"
    assert result["data"]["local_results"] == []
    assert len(result["data"]["web_results"]) == 1


def test_search_tds_falls_back_to_web_when_local_low_scores():
    mock_local = [
        {"text": "unrelated content", "score": 0.15, "source": "s3://docs/other.pdf", "section_title": "Intro"},
    ]
    mock_web = {
        "status": "ok",
        "data": [{"title": "TDS Result", "url": "https://example.com", "description": "specs"}],
    }
    with patch("src.compliance.tools.search_tds.search_documents", return_value={"status": "ok", "data": mock_local}):
        with patch("src.compliance.tools.search_tds.web_search", return_value=mock_web):
            from src.compliance.tools.search_tds import search_tds
            result = search_tds(ingredient_name="vitamin-c", supplier_name="ADM")

    assert result["status"] == "ok"
    assert len(result["data"]["local_results"]) == 1
    assert len(result["data"]["web_results"]) == 1


def test_search_tds_without_supplier_name():
    mock_local = [
        {"text": "Generic vitamin C specs", "score": 0.70, "source": "s3://docs/generic.pdf", "section_title": "Specs"},
    ]
    with patch("src.compliance.tools.search_tds.search_documents", return_value={"status": "ok", "data": mock_local}):
        from src.compliance.tools.search_tds import search_tds
        result = search_tds(ingredient_name="vitamin-c")

    assert result["status"] == "ok"
    assert result["data"]["supplier_name"] is None


def test_search_tds_handles_search_documents_error():
    with patch("src.compliance.tools.search_tds.search_documents", return_value={"status": "error", "message": "connection refused"}):
        from src.compliance.tools.search_tds import search_tds
        result = search_tds(ingredient_name="vitamin-c", supplier_name="ADM")

    assert result["status"] == "error"
    assert "connection refused" in result["message"]


def test_search_tds_skips_web_when_no_brave_key():
    with patch("src.compliance.tools.search_tds.search_documents", return_value={"status": "ok", "data": []}):
        with patch("src.compliance.tools.search_tds.web_search", return_value={"status": "error", "message": "BRAVE_API_KEY environment variable not set"}):
            from src.compliance.tools.search_tds import search_tds
            result = search_tds(ingredient_name="vitamin-c", supplier_name="ADM")

    assert result["status"] == "ok"
    assert result["data"]["local_results"] == []
    assert result["data"]["web_results"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_search_tds.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `search_tds`**

Create `src/compliance/tools/search_tds.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_search_tds.py -v`
Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/compliance/tools/search_tds.py tests/test_search_tds.py
git commit -m "feat: add search_tds tool with local-first, web-fallback strategy"
```

---

### Task 3: Wire `search_tds` into the Research Agent and Update System Prompt

**Files:**
- Modify: `src/compliance/research_agent.py` (lines 18-57 for prompt, line 80 for tools)
- Test: `tests/test_research_agent.py` (modify)

- [ ] **Step 1: Write the failing test for `search_tds` in tool list**

Add to `tests/test_research_agent.py`:

```python
def test_build_tools_includes_search_tds():
    with patch("src.compliance.research_agent.create_deep_agent"):
        with patch("src.compliance.research_agent.ChatBedrockConverse"):
            from src.compliance.research_agent import _build_tools
            tools = _build_tools()

    tool_names = [t.__name__ for t in tools]
    assert "search_tds" in tool_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_research_agent.py::test_build_tools_includes_search_tds -v`
Expected: FAIL with `AssertionError`

- [ ] **Step 3: Add `search_tds` import and tool registration**

In `src/compliance/research_agent.py`, add to imports (around line 14):

```python
from src.compliance.tools.search_tds import search_tds
```

In `_build_tools()` (line 80), add `search_tds` to the base tool list:

```python
def _build_tools():
    tools = [search_documents, query_database, pubchem_lookup, fda_lookup, search_tds]
    if os.environ.get("BRAVE_API_KEY"):
        tools.append(web_search)
    return tools
```

- [ ] **Step 4: Update `RESEARCH_SYSTEM_PROMPT`**

In `src/compliance/research_agent.py`, append the following to the end of the `RESEARCH_SYSTEM_PROMPT` string (before the closing `"""`):

```python
\n
When researching a substitution, also search for Technical Data Sheets (TDS), \
Certificates of Analysis (CoA), and fact sheets for both the original ingredient \
and the proposed substitute. The same substance from different suppliers can have \
different specifications (purity, heavy metals, particle size, etc.).

For each ingredient:
1. Look up which suppliers provide it (query_database with supplier_products).
2. For each supplier, search for TDS/spec data (search_tds with supplier_name).
3. Extract specification key-value pairs from the results.
4. Include spec differences across suppliers in your evidence and caveats.

Important: the same supplier can offer the same substance under different product \
SKUs with different specifications (e.g., different purity grades). Treat each \
supplier-product combination as a distinct spec source, not just each supplier.

When reporting evidence_rows for TDS/spec findings, use:
- source_type: "tds"
- fact_type: "spec:<key>" (e.g., "spec:purity", "spec:heavy_metals_lead")
- fact_value: the extracted value with unit (e.g., "99.5%", "< 0.5 ppm")
- source_label: include supplier name and product SKU (e.g., "ADM TDS for RM-vitamin-c-123")
```

- [ ] **Step 5: Run all research agent tests**

Run: `pytest tests/test_research_agent.py -v`
Expected: all tests PASS (including the new one)

- [ ] **Step 6: Commit**

```bash
git add src/compliance/research_agent.py tests/test_research_agent.py
git commit -m "feat: wire search_tds into research agent and extend system prompt"
```

---

### Task 4: Extract and Persist Spec Rows from Research Verdicts

**Files:**
- Modify: `src/research/run.py` (after verdict, around line 74-82)
- Create: `tests/test_spec_extraction.py`

- [ ] **Step 1: Write the failing tests for spec extraction and persistence**

Create `tests/test_spec_extraction.py`:

```python
import json
import sqlite3
from unittest.mock import patch

from src.common.db import get_supplier_specs, init_workspace_schema


def _setup_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE Company (Id INTEGER PRIMARY KEY, Name TEXT NOT NULL)")
    conn.execute("CREATE TABLE Supplier (Id INTEGER PRIMARY KEY, Name TEXT NOT NULL)")
    conn.execute("CREATE TABLE Product (Id INTEGER PRIMARY KEY, SKU TEXT NOT NULL, CompanyId INTEGER NOT NULL, Type TEXT NOT NULL)")
    conn.execute("CREATE TABLE BOM (Id INTEGER PRIMARY KEY, ProducedProductId INTEGER NOT NULL)")
    conn.execute("CREATE TABLE BOM_Component (Id INTEGER PRIMARY KEY, BOMId INTEGER NOT NULL, ConsumedProductId INTEGER NOT NULL)")
    conn.execute("CREATE TABLE Supplier_Product (SupplierId INTEGER NOT NULL, ProductId INTEGER NOT NULL, PRIMARY KEY (SupplierId, ProductId))")
    conn.execute("INSERT INTO Company (Id, Name) VALUES (1, 'TestCo')")
    conn.execute("INSERT INTO Supplier (Id, Name) VALUES (1, 'ADM'), (2, 'AIDP')")
    conn.execute("INSERT INTO Product (Id, SKU, CompanyId, Type) VALUES (10, 'FG-test-001', 1, 'finished-good')")
    conn.execute("INSERT INTO Product (Id, SKU, CompanyId, Type) VALUES (100, 'RM-C1-vitamin-c-abcd1234', 1, 'raw-material')")
    conn.execute("INSERT INTO Supplier_Product VALUES (1, 100), (2, 100)")
    conn.execute("INSERT INTO BOM (Id, ProducedProductId) VALUES (1, 10)")
    conn.execute("INSERT INTO BOM_Component (Id, BOMId, ConsumedProductId) VALUES (1, 1, 100)")
    conn.commit()
    conn.close()
    init_workspace_schema(db_path)
    return db_path


def test_run_research_persists_spec_rows(tmp_path):
    db_path = _setup_db(tmp_path)

    mock_verdict = {
        "facts": ["Vitamin C purity varies by supplier"],
        "rules": [],
        "inference": "Both suppliers meet minimum purity.",
        "caveats": [],
        "evidence_rows": [
            {
                "source_type": "tds",
                "source_label": "ADM TDS for RM-C1-vitamin-c-abcd1234",
                "source_uri": "https://adm.com/tds/vitc.pdf",
                "fact_type": "spec:purity",
                "fact_value": "99.5%",
                "quality_score": 0.9,
                "snippet": "Assay (purity): 99.5%",
            },
            {
                "source_type": "tds",
                "source_label": "AIDP TDS for RM-C1-vitamin-c-abcd1234",
                "source_uri": "https://aidp.com/tds/vitc.pdf",
                "fact_type": "spec:purity",
                "fact_value": "98.0%",
                "quality_score": 0.85,
                "snippet": "Assay (purity): 98.0%",
            },
            {
                "source_type": "pgvector",
                "source_label": "Document search",
                "source_uri": "s3://docs/product.json",
                "fact_type": "product_context",
                "fact_value": "Contains vitamin C",
                "quality_score": 0.9,
                "snippet": "Supplement Facts: Vitamin C 1000mg",
            },
        ],
    }

    mock_candidates_data = {
        "original_ingredient": "vitamin-c",
        "canonical_names": ["vitamin-c"],
        "exact_candidates": [{"current_match_name": "ascorbic-acid", "match_type": "exact"}],
        "alias_candidates": [],
    }

    with patch("src.research.run.research_substitution", return_value=mock_verdict):
        with patch("src.research.run.find_candidates_for_component", return_value=mock_candidates_data):
            from src.research.run import run_research
            run_research(
                db_path=db_path,
                product={"product_id": 10, "sku": "FG-test-001", "company_name": "TestCo"},
                component={"product_id": 100, "sku": "RM-C1-vitamin-c-abcd1234"},
            )

    specs = get_supplier_specs(db_path=db_path, product_id=100)
    assert len(specs) == 2
    spec_by_supplier = {s["SupplierName"]: s for s in specs}
    assert spec_by_supplier["ADM"]["SpecValue"] == "99.5%"
    assert spec_by_supplier["AIDP"]["SpecValue"] == "98.0%"


def test_run_research_skips_unresolvable_supplier(tmp_path):
    db_path = _setup_db(tmp_path)

    mock_verdict = {
        "facts": [],
        "rules": [],
        "inference": "ok",
        "caveats": [],
        "evidence_rows": [
            {
                "source_type": "tds",
                "source_label": "UnknownCorp TDS for RM-C1-vitamin-c-abcd1234",
                "source_uri": "https://unknown.com/tds.pdf",
                "fact_type": "spec:purity",
                "fact_value": "97.0%",
                "quality_score": 0.8,
                "snippet": "Purity: 97%",
            },
        ],
    }

    mock_candidates_data = {
        "original_ingredient": "vitamin-c",
        "canonical_names": ["vitamin-c"],
        "exact_candidates": [{"current_match_name": "ascorbic-acid", "match_type": "exact"}],
        "alias_candidates": [],
    }

    with patch("src.research.run.research_substitution", return_value=mock_verdict):
        with patch("src.research.run.find_candidates_for_component", return_value=mock_candidates_data):
            from src.research.run import run_research
            run_research(
                db_path=db_path,
                product={"product_id": 10, "sku": "FG-test-001", "company_name": "TestCo"},
                component={"product_id": 100, "sku": "RM-C1-vitamin-c-abcd1234"},
            )

    specs = get_supplier_specs(db_path=db_path, product_id=100)
    assert len(specs) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_spec_extraction.py -v`
Expected: FAIL (spec extraction logic doesn't exist yet)

- [ ] **Step 3: Implement spec extraction in `run_research`**

In `src/research/run.py`, add import at the top:

```python
import logging
import re

from src.common.db import (
    create_research_job,
    get_supplier_id_by_name,
    update_research_job,
    upsert_supplier_spec,
)
```

Then add a helper function after the imports:

```python
def _extract_and_persist_specs(db_path, evidence_rows, component_product_id):
    for row in evidence_rows:
        if not row.get("fact_type", "").startswith("spec:"):
            continue
        source_label = row.get("source_label", "")
        supplier_name_match = re.match(r"^(.+?)\s+TDS\s+for\s+", source_label)
        if not supplier_name_match:
            logger.warning("Cannot parse supplier name from source_label: %s", source_label)
            continue
        supplier_name = supplier_name_match.group(1)
        supplier_id = get_supplier_id_by_name(db_path=db_path, supplier_name=supplier_name)
        if supplier_id is None:
            logger.warning("Supplier not found: %s (from source_label: %s)", supplier_name, source_label)
            continue
        spec_key = row["fact_type"].removeprefix("spec:")
        value = row.get("fact_value", "")
        unit_match = re.search(r"(%|ppm|mg|mcg|CFU/g|mesh)$", value.strip())
        spec_unit = unit_match.group(0) if unit_match else None
        upsert_supplier_spec(
            db_path=db_path,
            supplier_id=supplier_id,
            product_id=component_product_id,
            spec_key=spec_key,
            spec_value=value,
            spec_unit=spec_unit,
            source_uri=row.get("source_uri"),
            source_type=row.get("source_type", "tds"),
        )
```

Then in `run_research()`, after each candidate verdict is collected (after line 82 where `candidates_researched.append(...)` is called), add:

```python
            _extract_and_persist_specs(
                db_path=db_path,
                evidence_rows=verdict["evidence_rows"],
                component_product_id=component["product_id"],
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_spec_extraction.py -v`
Expected: both tests PASS

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `pytest tests/ -v`
Expected: all existing tests still PASS

- [ ] **Step 6: Commit**

```bash
git add src/research/run.py tests/test_spec_extraction.py
git commit -m "feat: extract and persist supplier specs from research verdicts"
```

---

### Task 5: Add Supplier Spec Comparison UI

**Files:**
- Modify: `pages/6_Product_Research.py` (after the existing results expander, around line 186)

- [ ] **Step 1: Add import for `get_supplier_specs`**

In `pages/6_Product_Research.py`, add to the imports:

```python
from src.common.db import (
    get_bom_components,
    get_finished_goods,
    get_latest_research_job,
    get_research_jobs_for_product,
    get_suppliers_for_product,
    get_supplier_specs,
    parse_ingredient_name,
)
```

- [ ] **Step 2: Add spec comparison expander after existing results**

In `pages/6_Product_Research.py`, after the line `st.caption(f"Completed: {job.get('UpdatedAt', '-')}")` (line 187) and before the `st.divider()` (line 189), add:

```python
    if job_status == "completed":
        specs = get_supplier_specs(product_id=component["product_id"])
        if specs:
            with st.expander("Supplier Specs Comparison", expanded=False):
                pivot = {}
                all_suppliers = set()
                for s in specs:
                    all_suppliers.add(s["SupplierName"])
                    pivot.setdefault(s["SpecKey"], {})[s["SupplierName"]] = (
                        f"{s['SpecValue']}" + (f" {s['SpecUnit']}" if s.get("SpecUnit") else "")
                    )
                suppliers_sorted = sorted(all_suppliers)
                table_data = []
                for spec_key in sorted(pivot.keys()):
                    row_data = {"Specification": spec_key}
                    for supplier in suppliers_sorted:
                        row_data[supplier] = pivot[spec_key].get(supplier, "—")
                    table_data.append(row_data)
                st.dataframe(table_data, use_container_width=True, hide_index=True)
```

- [ ] **Step 3: Manually verify the UI**

Run: `streamlit run streamlit_app.py`

1. Navigate to the "Product Research" page.
2. Select a product that has completed research.
3. Verify the "Supplier Specs Comparison" expander appears when spec data exists.
4. If no spec data exists yet, confirm the expander does not appear (no empty table).

- [ ] **Step 4: Commit**

```bash
git add pages/6_Product_Research.py
git commit -m "feat: add supplier spec comparison table to Product Research page"
```

---

### Task 6: Integration Smoke Test

**Files:**
- None new (uses existing test infrastructure)

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -v`
Expected: all tests PASS

- [ ] **Step 2: Reinitialize workspace and verify schema**

Run: `python3 -c "from src.common.db import init_workspace_schema; init_workspace_schema(); print('Schema OK')"`
Expected: prints `Schema OK` with no errors

- [ ] **Step 3: Verify `Supplier_Spec` table exists**

Run: `python3 -c "import sqlite3; conn = sqlite3.connect('db.sqlite'); print([r[1] for r in conn.execute('PRAGMA table_info(Supplier_Spec)').fetchall()]); conn.close()"`
Expected: prints `['SupplierId', 'ProductId', 'SpecKey', 'SpecValue', 'SpecUnit', 'SourceUri', 'SourceType', 'ExtractedAt']`

- [ ] **Step 4: Commit any remaining changes (if any)**

```bash
git status
```

If clean, no commit needed.
