# Product Research Page — Design Spec

**Date:** 2026-04-18
**Status:** Draft

## Problem

The current workspace shows sourcing opportunities based on deterministic exact-match and alias lookups against a cached fact pack. Users cannot trigger deeper research on a specific ingredient from a product-centric view. There is no way to ask an agent to investigate chemical identity, regulatory compliance, supplier landscape, and functional equivalence for a given BOM component — and no way to see the results of such research alongside the product's ingredient list.

## Solution

A new Streamlit page (`pages/6_Product_Research.py`) that:

1. Lets the user select a company and finished-good product
2. Shows a table of the product's BOM ingredients with existing match context
3. Provides per-ingredient action buttons to launch background agentic research
4. Persists research job state in SQLite so users can navigate away and return to see results
5. Displays completed research findings inline per ingredient

## Page Layout

### Selection Bar

Two dropdowns in a row:
- **Company** — populated from `Company` table (filtered to companies with finished goods)
- **Product** — populated from `Product` table, filtered by selected company, type `finished-good`

### Ingredients Table

For the selected product, one row per BOM component showing:

| Column | Source |
|--------|--------|
| Ingredient Name | `parse_ingredient_name(component["sku"])` |
| SKU | `component["sku"]` |
| Supplier(s) | `get_suppliers_for_product(product_id=component["product_id"])` |
| Exact Matches | Count of exact-match candidates from `find_candidates_for_component()` |
| Alias Matches | Count of alias/hypothesis candidates |
| Research Status | From `Research_Job` table: none / pending / running / completed / failed |
| Actions | Buttons (see below) |

### Per-Ingredient Actions

State-dependent buttons per ingredient row:

| Research Status | Buttons Shown |
|-----------------|---------------|
| No job exists | "Find substitution" |
| `pending` or `running` | "Research in progress..." (disabled) + "Refresh" |
| `completed` | "View results" + "Redo research" |
| `failed` | "Redo research" + error message |

### Results Display

When the user clicks "View results" (or when research just completed), an expander opens below the ingredient row showing:

- **Verdict summary** — inference text from the agent
- **Facts** — bulleted list of discovered facts
- **Rules** — applicable regulatory rules
- **Caveats** — limitations and uncertainties
- **Evidence table** — source type, source label, fact type, fact value, quality score, snippet
- **Timestamp** — when the research completed

## Data Model

### New Table: `Research_Job`

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

CREATE INDEX IF NOT EXISTS idx_research_job_lookup
    ON Research_Job (ProductId, BomComponentProductId, Status);
```

Only the **latest** job per (ProductId, BomComponentProductId) pair matters for display. "Redo research" inserts a new row rather than updating the old one, preserving history.

The `Research_Job` table is added to `init_workspace_schema()` in `src/common/db.py` alongside the existing workspace tables.

### New Functions in `src/common/db.py`

- `create_research_job(db_path, product_id, component_product_id)` — insert `pending` row, return job ID
- `update_research_job(db_path, job_id, status, result_json=None, error_message=None)` — update status and result
- `get_latest_research_job(db_path, product_id, component_product_id)` — return the most recent job for this pair
- `get_research_jobs_for_product(db_path, product_id)` — return latest job per component for the whole product

All functions follow the existing `db_path=None` convention used throughout `src/common/db.py`.

## Background Research Mechanism

### Thread-based execution

When "Find substitution" is clicked:

1. `create_research_job()` inserts a `pending` row
2. A `threading.Thread` is spawned targeting `run_research(job_id, product, component)`
3. The thread:
   - Updates job to `running`
   - Calls `find_candidates_for_component()` to get exact + alias candidates
   - Builds the `original_info` dict with ingredient name, canonical names, and group function
   - For each candidate, calls `research_substitution(original, substitute, product_sku, company_name)` from `src/compliance/research_agent.py`
   - On success: updates job to `completed` with `ResultJson` containing aggregated results
   - On failure: updates job to `failed` with `ErrorMessage`
4. The page shows "Research in progress..." for that ingredient
5. A "Refresh" button at the top of the page triggers `st.rerun()` to poll status

### Research Agent Integration

Uses `research_substitution()` from `src/compliance/research_agent.py` (already implemented). The function signature is:

```python
research_substitution(original, substitute, product_sku, company_name)
```

Where:
- `original` — dict with keys `original_ingredient`, `group` (dict with `canonical_name`, `function`), `requirements` (list)
- `substitute` — dict with keys `current_match_name`, `match_type`
- `product_sku` — string
- `company_name` — string

Returns a dict with keys: `facts`, `rules`, `inference`, `caveats`, `evidence_rows`, `kb_sources`.

The background runner builds these inputs from `find_candidates_for_component()` output, following the same pattern as `scripts/research.py` lines 124-148.

### Result Format

`ResultJson` stores a JSON object:

```json
{
  "candidates_researched": [
    {
      "name": "ascorbic-acid",
      "match_type": "alias",
      "facts": ["Ascorbic acid is the same chemical entity as vitamin C"],
      "rules": ["FDA 21 CFR 101.36"],
      "inference": "Chemically identical substitute.",
      "caveats": ["No dosage equivalence data available"],
      "evidence_rows": [
        {
          "source_type": "pubchem",
          "source_label": "PubChem compound lookup",
          "source_uri": "https://pubchem.ncbi.nlm.nih.gov/compound/54670067",
          "fact_type": "chemical_identity",
          "fact_value": "Ascorbic acid (CID 54670067) is the L-enantiomer of vitamin C",
          "quality_score": 0.95,
          "snippet": "IUPAC: (2R)-2-[(1S)-1,2-dihydroxyethyl]-..."
        }
      ]
    }
  ]
}
```

Each entry in `candidates_researched` corresponds to one `research_substitution()` call. If only exact/alias matches exist with no real candidates, the result stores an empty list with a note.

## Files to Create/Modify

| File | Action |
|------|--------|
| `pages/6_Product_Research.py` | Create — new Streamlit page |
| `src/common/db.py` | Modify — add `Research_Job` table to `init_workspace_schema()`, add 4 job CRUD functions |
| `src/research/__init__.py` | Create — new package marker |
| `src/research/run.py` | Create — `run_research()` background runner function |
| `tests/test_research_job.py` | Create — tests for job CRUD functions |
| `tests/test_research_run.py` | Create — tests for background runner |

## Out of Scope

- Real-time streaming of agent progress (future enhancement)
- Bulk "research all ingredients" button (can be added later)
- Evidence persistence to the `Evidence` table (the existing opportunity pipeline handles that separately; research results are self-contained in `ResultJson`)
