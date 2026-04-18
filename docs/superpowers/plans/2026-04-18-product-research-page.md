# Product Research Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Streamlit page where users select a product, see its BOM ingredients, and trigger background agentic research per ingredient — with persistent job state and inline results display.

**Architecture:** New `Research_Job` SQLite table + CRUD functions in `db.py` for job state. A `src/research/run.py` module runs the research agent in a background thread. A new `pages/6_Product_Research.py` Streamlit page ties it together with company/product selection, ingredient table, action buttons, and results display.

**Tech Stack:** Streamlit, SQLite, threading, existing `research_substitution()` from `src/compliance/research_agent.py`

**Spec:** `docs/superpowers/specs/2026-04-18-product-research-page-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/common/db.py` | Add `Research_Job` table to `init_workspace_schema()`, add 4 CRUD functions |
| `src/research/__init__.py` | Package marker |
| `src/research/run.py` | `run_research()` — background thread target that calls `research_substitution()` per candidate |
| `pages/6_Product_Research.py` | Streamlit page: company/product selection, ingredient table, action buttons, results display |
| `tests/test_research_job.py` | Tests for Research_Job CRUD functions |
| `tests/test_research_run.py` | Tests for background runner |

---

### Task 1: Research_Job Table Schema

**Files:**
- Modify: `src/common/db.py:132-246`

- [ ] **Step 1: Write the failing test**

Create `tests/test_research_job.py`:

```python
import sqlite3
from src.common.db import init_workspace_schema, get_connection


def test_research_job_table_exists_after_init(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE Product (Id INTEGER PRIMARY KEY, SKU TEXT, CompanyId INTEGER, Type TEXT)")
    conn.commit()
    conn.close()

    init_workspace_schema(db_path)

    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='Research_Job'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["name"] == "Research_Job"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_research_job.py::test_research_job_table_exists_after_init -v`

Expected: FAIL — `Research_Job` table not found

- [ ] **Step 3: Add Research_Job table to init_workspace_schema()**

In `src/common/db.py`, inside the `init_workspace_schema()` function, add the following SQL block **after** the `Review_Decision` table definition (after line 229, before the `CREATE INDEX` statements):

```sql
        CREATE TABLE IF NOT EXISTS Research_Job (
            Id INTEGER PRIMARY KEY,
            ProductId INTEGER NOT NULL,
            BomComponentProductId INTEGER NOT NULL,
            Status TEXT NOT NULL CHECK (Status IN ('pending', 'running', 'completed', 'failed')),
            ResultJson TEXT,
            ErrorMessage TEXT,
            CreatedAt TEXT NOT NULL,
            UpdatedAt TEXT NOT NULL,
            FOREIGN KEY (ProductId) REFERENCES Product (Id),
            FOREIGN KEY (BomComponentProductId) REFERENCES Product (Id)
        );
```

And add this index after the existing index definitions (after line 242):

```sql
        CREATE INDEX IF NOT EXISTS idx_research_job_lookup
            ON Research_Job (ProductId, BomComponentProductId, Status);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_research_job.py::test_research_job_table_exists_after_init -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/common/db.py tests/test_research_job.py
git commit -m "feat: add Research_Job table to workspace schema"
```

---

### Task 2: Research Job CRUD Functions

**Files:**
- Modify: `src/common/db.py` (append new functions at end of file)
- Test: `tests/test_research_job.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_research_job.py`:

```python
import json
from src.common.db import (
    init_workspace_schema,
    get_connection,
    create_research_job,
    update_research_job,
    get_latest_research_job,
    get_research_jobs_for_product,
)


def _init_test_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE Product (Id INTEGER PRIMARY KEY, SKU TEXT, CompanyId INTEGER, Type TEXT)")
    conn.execute("INSERT INTO Product VALUES (1, 'FG-test-001', 1, 'finished-good')")
    conn.execute("INSERT INTO Product VALUES (10, 'RM-C1-vitamin-c-abcd1234', 1, 'raw-material')")
    conn.execute("INSERT INTO Product VALUES (11, 'RM-C1-vitamin-d3-abcd1234', 1, 'raw-material')")
    conn.commit()
    conn.close()
    init_workspace_schema(db_path)
    return db_path


def test_create_research_job(tmp_path):
    db_path = _init_test_db(tmp_path)
    job_id = create_research_job(db_path=db_path, product_id=1, component_product_id=10)
    assert isinstance(job_id, int)
    assert job_id > 0

    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM Research_Job WHERE Id = ?", (job_id,)).fetchone()
    conn.close()
    assert row["Status"] == "pending"
    assert row["ProductId"] == 1
    assert row["BomComponentProductId"] == 10


def test_update_research_job_to_completed(tmp_path):
    db_path = _init_test_db(tmp_path)
    job_id = create_research_job(db_path=db_path, product_id=1, component_product_id=10)

    result = {"candidates_researched": [{"name": "ascorbic-acid", "facts": ["same compound"]}]}
    update_research_job(db_path=db_path, job_id=job_id, status="completed", result_json=json.dumps(result))

    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM Research_Job WHERE Id = ?", (job_id,)).fetchone()
    conn.close()
    assert row["Status"] == "completed"
    assert json.loads(row["ResultJson"])["candidates_researched"][0]["name"] == "ascorbic-acid"


def test_update_research_job_to_failed(tmp_path):
    db_path = _init_test_db(tmp_path)
    job_id = create_research_job(db_path=db_path, product_id=1, component_product_id=10)
    update_research_job(db_path=db_path, job_id=job_id, status="failed", error_message="agent timeout")

    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM Research_Job WHERE Id = ?", (job_id,)).fetchone()
    conn.close()
    assert row["Status"] == "failed"
    assert row["ErrorMessage"] == "agent timeout"


def test_get_latest_research_job(tmp_path):
    db_path = _init_test_db(tmp_path)
    job1 = create_research_job(db_path=db_path, product_id=1, component_product_id=10)
    update_research_job(db_path=db_path, job_id=job1, status="completed", result_json='{"old": true}')
    job2 = create_research_job(db_path=db_path, product_id=1, component_product_id=10)

    latest = get_latest_research_job(db_path=db_path, product_id=1, component_product_id=10)
    assert latest["Id"] == job2
    assert latest["Status"] == "pending"


def test_get_latest_research_job_returns_none_when_empty(tmp_path):
    db_path = _init_test_db(tmp_path)
    result = get_latest_research_job(db_path=db_path, product_id=1, component_product_id=10)
    assert result is None


def test_get_research_jobs_for_product(tmp_path):
    db_path = _init_test_db(tmp_path)
    create_research_job(db_path=db_path, product_id=1, component_product_id=10)
    create_research_job(db_path=db_path, product_id=1, component_product_id=10)
    create_research_job(db_path=db_path, product_id=1, component_product_id=11)

    jobs = get_research_jobs_for_product(db_path=db_path, product_id=1)
    assert len(jobs) == 2
    component_ids = {j["BomComponentProductId"] for j in jobs}
    assert component_ids == {10, 11}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_research_job.py -v -k "not table_exists"`

Expected: FAIL — `ImportError: cannot import name 'create_research_job'`

- [ ] **Step 3: Implement the four CRUD functions**

Append to `src/common/db.py` (after the `table_count` function at the end of the file):

```python
def create_research_job(db_path=None, product_id=None, component_product_id=None):
    conn = get_connection(db_path)
    now = now_iso()
    conn.execute(
        """
        INSERT INTO Research_Job (ProductId, BomComponentProductId, Status, CreatedAt, UpdatedAt)
        VALUES (?, ?, 'pending', ?, ?)
        """,
        (product_id, component_product_id, now, now),
    )
    job_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    conn.commit()
    conn.close()
    return job_id


def update_research_job(db_path=None, job_id=None, status=None, result_json=None, error_message=None):
    conn = get_connection(db_path)
    conn.execute(
        """
        UPDATE Research_Job
        SET Status = ?, ResultJson = ?, ErrorMessage = ?, UpdatedAt = ?
        WHERE Id = ?
        """,
        (status, result_json, error_message, now_iso(), job_id),
    )
    conn.commit()
    conn.close()


def get_latest_research_job(db_path=None, product_id=None, component_product_id=None):
    conn = get_connection(db_path)
    row = conn.execute(
        """
        SELECT *
        FROM Research_Job
        WHERE ProductId = ? AND BomComponentProductId = ?
        ORDER BY Id DESC
        LIMIT 1
        """,
        (product_id, component_product_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_research_jobs_for_product(db_path=None, product_id=None):
    conn = get_connection(db_path)
    rows = conn.execute(
        """
        SELECT rj.*
        FROM Research_Job rj
        INNER JOIN (
            SELECT BomComponentProductId, MAX(Id) AS MaxId
            FROM Research_Job
            WHERE ProductId = ?
            GROUP BY BomComponentProductId
        ) latest ON rj.Id = latest.MaxId
        ORDER BY rj.Id DESC
        """,
        (product_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_research_job.py -v`

Expected: All 7 tests pass

- [ ] **Step 5: Run existing tests for regressions**

Run: `python -m pytest tests/test_db.py -v`

Expected: All existing db tests pass

- [ ] **Step 6: Commit**

```bash
git add src/common/db.py tests/test_research_job.py
git commit -m "feat: add Research_Job CRUD functions"
```

---

### Task 3: Background Research Runner

**Files:**
- Create: `src/research/__init__.py`
- Create: `src/research/run.py`
- Create: `tests/test_research_run.py`

- [ ] **Step 1: Create package marker**

Create `src/research/__init__.py` as an empty file.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_research_run.py`:

```python
import json
import sqlite3
from unittest.mock import patch, MagicMock

from src.common.db import (
    init_workspace_schema,
    get_connection,
    get_latest_research_job,
)


def _init_test_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE Company (Id INTEGER PRIMARY KEY, Name TEXT);
        INSERT INTO Company VALUES (1, 'TestCo');

        CREATE TABLE Product (Id INTEGER PRIMARY KEY, SKU TEXT, CompanyId INTEGER, Type TEXT);
        INSERT INTO Product VALUES (1, 'FG-test-001', 1, 'finished-good');
        INSERT INTO Product VALUES (10, 'RM-C1-vitamin-c-abcd1234', 1, 'raw-material');

        CREATE TABLE Supplier (Id INTEGER PRIMARY KEY, Name TEXT);
        CREATE TABLE Supplier_Product (Id INTEGER PRIMARY KEY, SupplierId INTEGER, ProductId INTEGER);

        CREATE TABLE BOM (Id INTEGER PRIMARY KEY, ProducedProductId INTEGER);
        INSERT INTO BOM VALUES (1, 1);

        CREATE TABLE BOM_Component (Id INTEGER PRIMARY KEY, BOMId INTEGER, ConsumedProductId INTEGER);
        INSERT INTO BOM_Component VALUES (1, 1, 10);
        """
    )
    conn.commit()
    conn.close()
    init_workspace_schema(db_path)
    return db_path


def test_run_research_completes_job(tmp_path):
    db_path = _init_test_db(tmp_path)

    mock_verdict = {
        "facts": ["Vitamin C is ascorbic acid"],
        "rules": ["FDA 21 CFR 101.36"],
        "inference": "Safe substitute.",
        "caveats": [],
        "evidence_rows": [],
        "kb_sources": [],
    }

    product = {"product_id": 1, "sku": "FG-test-001", "company_id": 1, "company_name": "TestCo"}
    component = {"bom_id": 1, "product_id": 10, "sku": "RM-C1-vitamin-c-abcd1234", "company_id": 1, "component_company_name": "TestCo"}

    with patch("src.research.run.research_substitution", return_value=mock_verdict):
        from src.research.run import run_research
        run_research(db_path=db_path, product=product, component=component)

    job = get_latest_research_job(db_path=db_path, product_id=1, component_product_id=10)
    assert job["Status"] == "completed"
    result = json.loads(job["ResultJson"])
    assert "candidates_researched" in result


def test_run_research_marks_failed_on_error(tmp_path):
    db_path = _init_test_db(tmp_path)

    product = {"product_id": 1, "sku": "FG-test-001", "company_id": 1, "company_name": "TestCo"}
    component = {"bom_id": 1, "product_id": 10, "sku": "RM-C1-vitamin-c-abcd1234", "company_id": 1, "component_company_name": "TestCo"}

    with patch("src.research.run.research_substitution", side_effect=Exception("agent crashed")):
        from src.research.run import run_research
        run_research(db_path=db_path, product=product, component=component)

    job = get_latest_research_job(db_path=db_path, product_id=1, component_product_id=10)
    assert job["Status"] == "failed"
    assert "agent crashed" in job["ErrorMessage"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_research_run.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'src.research'`

- [ ] **Step 4: Implement run_research()**

Create `src/research/run.py`:

```python
import json
import logging

from src.common.db import (
    create_research_job,
    get_alias_rows,
    update_research_job,
    parse_ingredient_name,
)
from src.compliance.research_agent import research_substitution
from src.substitute.find_candidates import find_candidates_for_component

logger = logging.getLogger(__name__)


def run_research(db_path=None, product=None, component=None):
    job_id = create_research_job(
        db_path=db_path,
        product_id=product["product_id"],
        component_product_id=component["product_id"],
    )
    update_research_job(db_path=db_path, job_id=job_id, status="running")

    try:
        candidates_data = find_candidates_for_component(
            db_path=db_path,
            component=component,
            finished_product=product,
        )

        all_candidates = candidates_data["exact_candidates"] + candidates_data["alias_candidates"]

        original_info = {
            "original_ingredient": candidates_data["original_ingredient"],
            "group": {
                "canonical_name": ", ".join(candidates_data["canonical_names"]),
                "function": "reviewed-alias-layer" if candidates_data["alias_candidates"] else "exact-match",
            },
            "requirements": [],
        }

        candidates_researched = []
        for candidate in all_candidates:
            sub_info = {
                "current_match_name": candidate["current_match_name"],
                "match_type": candidate["match_type"],
            }
            verdict = research_substitution(
                original=original_info,
                substitute=sub_info,
                product_sku=product["sku"],
                company_name=product["company_name"],
            )
            candidates_researched.append({
                "name": candidate["current_match_name"],
                "match_type": candidate["match_type"],
                "facts": verdict["facts"],
                "rules": verdict["rules"],
                "inference": verdict["inference"],
                "caveats": verdict["caveats"],
                "evidence_rows": verdict["evidence_rows"],
            })

        result_json = json.dumps({"candidates_researched": candidates_researched})
        update_research_job(db_path=db_path, job_id=job_id, status="completed", result_json=result_json)

    except Exception as e:
        logger.exception("Research failed for job %s", job_id)
        update_research_job(db_path=db_path, job_id=job_id, status="failed", error_message=str(e))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_research_run.py -v`

Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add src/research/__init__.py src/research/run.py tests/test_research_run.py
git commit -m "feat: add background research runner"
```

---

### Task 4: Streamlit Product Research Page

**Files:**
- Create: `pages/6_Product_Research.py`

- [ ] **Step 1: Create the page**

Create `pages/6_Product_Research.py`:

```python
import json
import threading

import streamlit as st

from src.common.db import (
    get_bom_components,
    get_finished_goods,
    get_latest_research_job,
    get_research_jobs_for_product,
    get_suppliers_for_product,
    parse_ingredient_name,
)
from src.research.run import run_research
from src.substitute.find_candidates import find_candidates_for_component

st.set_page_config(page_title="Product Research", layout="wide")
st.title("Product Research")
st.caption("Select a product to view its ingredients and trigger agentic substitution research.")

finished_goods = get_finished_goods()
if not finished_goods:
    st.info("No finished goods found. Run the workspace initialization first.")
    st.stop()

companies = sorted({p["company_name"] for p in finished_goods})
company_col, product_col, refresh_col = st.columns([2, 3, 1])

with company_col:
    selected_company = st.selectbox("Company", options=companies)

company_products = [p for p in finished_goods if p["company_name"] == selected_company]
with product_col:
    selected_product = st.selectbox(
        "Product",
        options=company_products,
        format_func=lambda p: p["sku"],
    )

with refresh_col:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Refresh"):
        st.rerun()

if not selected_product:
    st.stop()

components = get_bom_components(product_id=selected_product["product_id"])
if not components:
    st.info("No BOM components found for this product.")
    st.stop()

jobs = get_research_jobs_for_product(product_id=selected_product["product_id"])
jobs_by_component = {j["BomComponentProductId"]: j for j in jobs}

st.subheader("Ingredients")

for component in components:
    ingredient_name = parse_ingredient_name(component["sku"])
    suppliers = get_suppliers_for_product(product_id=component["product_id"])
    candidates_data = find_candidates_for_component(
        component=component,
        finished_product=selected_product,
    )
    exact_count = len(candidates_data["exact_candidates"])
    alias_count = len(candidates_data["alias_candidates"])

    job = jobs_by_component.get(component["product_id"])
    job_status = job["Status"] if job else None

    col_name, col_suppliers, col_exact, col_alias, col_status, col_actions = st.columns(
        [2, 2, 1, 1, 1, 2]
    )

    with col_name:
        st.markdown(f"**{ingredient_name}**")
        st.caption(component["sku"])
    with col_suppliers:
        st.write(", ".join(suppliers) if suppliers else "-")
    with col_exact:
        st.metric("Exact", exact_count)
    with col_alias:
        st.metric("Alias", alias_count)
    with col_status:
        if job_status == "completed":
            st.success("Done")
        elif job_status == "running":
            st.warning("Running")
        elif job_status == "pending":
            st.warning("Pending")
        elif job_status == "failed":
            st.error("Failed")
        else:
            st.caption("—")

    with col_actions:
        if job_status in ("pending", "running"):
            st.info("Research in progress...")
        elif job_status == "completed":
            view_key = f"view_{component['product_id']}"
            redo_key = f"redo_{component['product_id']}"
            view_col, redo_col = st.columns(2)
            with view_col:
                if st.button("View results", key=view_key):
                    st.session_state[f"show_results_{component['product_id']}"] = True
            with redo_col:
                if st.button("Redo research", key=redo_key):
                    thread = threading.Thread(
                        target=run_research,
                        kwargs={
                            "product": selected_product,
                            "component": component,
                        },
                        daemon=True,
                    )
                    thread.start()
                    st.rerun()
        elif job_status == "failed":
            st.error(job.get("ErrorMessage", "Unknown error")[:80])
            if st.button("Redo research", key=f"redo_failed_{component['product_id']}"):
                thread = threading.Thread(
                    target=run_research,
                    kwargs={
                        "product": selected_product,
                        "component": component,
                    },
                    daemon=True,
                )
                thread.start()
                st.rerun()
        else:
            if st.button("Find substitution", key=f"find_{component['product_id']}"):
                thread = threading.Thread(
                    target=run_research,
                    kwargs={
                        "product": selected_product,
                        "component": component,
                    },
                    daemon=True,
                )
                thread.start()
                st.rerun()

    show_key = f"show_results_{component['product_id']}"
    if st.session_state.get(show_key) and job_status == "completed" and job.get("ResultJson"):
        result = json.loads(job["ResultJson"])
        candidates = result.get("candidates_researched", [])
        if not candidates:
            st.info("No candidates were researched for this ingredient.")
        for candidate in candidates:
            with st.expander(f"{candidate['name']} ({candidate['match_type']})", expanded=True):
                st.markdown(f"**Inference:** {candidate.get('inference', '-')}")

                if candidate.get("facts"):
                    st.markdown("**Facts:**")
                    for fact in candidate["facts"]:
                        st.markdown(f"- {fact}")

                if candidate.get("rules"):
                    st.markdown("**Rules:**")
                    for rule in candidate["rules"]:
                        st.markdown(f"- {rule}")

                if candidate.get("caveats"):
                    st.markdown("**Caveats:**")
                    for caveat in candidate["caveats"]:
                        st.markdown(f"- {caveat}")

                evidence = candidate.get("evidence_rows", [])
                if evidence:
                    st.markdown("**Evidence:**")
                    st.dataframe(
                        [
                            {
                                "Source Type": e.get("source_type", ""),
                                "Source": e.get("source_label", ""),
                                "Fact Type": e.get("fact_type", ""),
                                "Fact Value": e.get("fact_value", ""),
                                "Quality": e.get("quality_score", ""),
                            }
                            for e in evidence
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )

        st.caption(f"Completed: {job.get('UpdatedAt', '-')}")

    st.divider()
```

- [ ] **Step 2: Add page link to home page**

In `streamlit_app.py`, add after the existing `st.page_link` lines (after line 35):

```python
st.page_link("pages/6_Product_Research.py", label="Open Product Research", icon="🔬")
```

- [ ] **Step 3: Manually verify the page loads**

Run: `streamlit run streamlit_app.py`

Open `http://localhost:8501` and navigate to the "Product Research" page. Verify:
1. Company dropdown populates
2. Product dropdown filters by company
3. Ingredients table shows BOM components with supplier, match counts, and status
4. "Find substitution" buttons appear for ingredients without research jobs

- [ ] **Step 4: Commit**

```bash
git add pages/6_Product_Research.py streamlit_app.py
git commit -m "feat: add Product Research page with ingredient table and action buttons"
```

---

### Task 5: Integration Verification

**Files:**
- All files from previous tasks

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ -v`

Expected: All tests pass (existing + new)

- [ ] **Step 2: Verify Research_Job schema is created on app startup**

Run: `streamlit run streamlit_app.py`

Open the app, navigate to Product Research. Open a SQLite browser or run:

```bash
python -c "import sqlite3; conn = sqlite3.connect('db.sqlite'); print(conn.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='Research_Job'\").fetchone()); conn.close()"
```

Expected: `('Research_Job',)`

- [ ] **Step 3: Test the full research flow in browser**

1. Select a company and product
2. Click "Find substitution" on an ingredient
3. Click "Refresh" after a few seconds
4. Verify status changes from pending/running to completed or failed
5. Click "View results" to see the research findings
6. Click "Redo research" to trigger a new research job

- [ ] **Step 4: Commit any final adjustments**

```bash
git add -A
git commit -m "chore: integration verification for product research page"
```
