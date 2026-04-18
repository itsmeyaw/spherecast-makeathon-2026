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
| Ingredient Name | `parse_ingredient_name(component.sku)` |
| SKU | `component.sku` |
| Supplier(s) | `get_suppliers_for_product(component.product_id)` |
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

- `create_research_job(product_id, component_product_id)` — insert `pending` row, return job ID
- `update_research_job(job_id, status, result_json=None, error_message=None)` — update status and result
- `get_latest_research_job(product_id, component_product_id)` — return the most recent job for this pair
- `get_research_jobs_for_product(product_id)` — return latest job per component for the whole product

## Background Research Mechanism

### Thread-based execution

When "Find substitution" is clicked:

1. `create_research_job()` inserts a `pending` row
2. A `threading.Thread` is spawned targeting `_run_research(job_id, product, component)`
3. The thread:
   - Updates job to `running`
   - Calls `find_candidates_for_component()` to get exact + alias candidates
   - Builds the context (requirements, canonical names, existing matches)
   - Calls `research_substitution()` from the existing research agent spec
   - On success: updates job to `completed` with `ResultJson` containing the full verdict
   - On failure: updates job to `failed` with `ErrorMessage`
4. The page shows "Research in progress..." for that ingredient
5. A "Refresh" button at the top of the page triggers `st.rerun()` to poll status

### Research Agent Integration

Uses `research_substitution()` from `src/compliance/research_agent.py` (the DeepAgents-based agent from the existing spec). The agent receives:

- Original ingredient info (name, canonical name, requirements from `build_requirement_profile()`)
- All candidates (exact + alias + hypothesis) as context — these inform the agent but are not standalone findings
- Product SKU and company name for product-level context

The system prompt instructs the agent that exact/alias matches are **hints for understanding ingredient identity**, not conclusions. The agent must independently verify equivalence through its tools (PubChem, FDA, web search, document store).

### Result Format

`ResultJson` stores a JSON object:

```json
{
  "facts": ["..."],
  "rules": ["..."],
  "inference": "...",
  "caveats": ["..."],
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
  ],
  "candidates_researched": [
    {
      "name": "ascorbic-acid",
      "match_type": "alias",
      "verdict": "safe"
    }
  ]
}
```

## Dependencies

This design depends on the research agent from `docs/superpowers/specs/2026-04-18-agentic-research-design.md` being implemented (Tasks 1-7 of the existing plan: dependencies, 5 tools, agent core). If the agent is not yet available, the page still works — "Find substitution" will show an error and the user can retry later.

## Files to Create/Modify

| File | Action |
|------|--------|
| `pages/6_Product_Research.py` | Create — new Streamlit page |
| `src/common/db.py` | Modify — add `Research_Job` table to schema, add job CRUD functions |
| `src/research/__init__.py` | Create — new package marker |
| `src/research/run.py` | Create — background research runner function |
| `tests/test_research_page.py` | Create — tests for job CRUD and research runner |

## Out of Scope

- Real-time streaming of agent progress (future enhancement)
- Bulk "research all ingredients" button (can be added later)
- Evidence persistence to the `Evidence` table (the existing opportunity pipeline handles that separately; research results are self-contained in `ResultJson`)
