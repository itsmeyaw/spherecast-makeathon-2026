# TDS / Fact Sheet Search with Per-Supplier Specifications

**Date:** 2026-04-18
**Status:** Approved

## Problem

The research agent investigates ingredient substitution compliance but does not search for Technical Data Sheets (TDS), Certificates of Analysis (CoA), or fact sheets. It also treats ingredients as uniform across suppliers, ignoring that the same substance from different companies can have different specifications (purity, heavy metals limits, particle size, etc.). These differences can affect substitution safety and compliance decisions.

## Solution

Extend the research agent to search for TDS/fact sheet data per supplier, extract specification key-value pairs, and persist them in a new EAV (Entity-Attribute-Value) `Supplier_Spec` table. Spec data also flows into the existing `Evidence` table for audit trail. A comparison view on the Product Research page shows spec differences across suppliers.

## Architecture

### New Table: `Supplier_Spec` (EAV)

```sql
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

- **SupplierId + ProductId + SpecKey** is unique — upserts overwrite stale data.
- **ProductId** references a raw-material `Product` row (the BOM component's product).
- **SpecKey** uses a standardized vocabulary (below) but accepts arbitrary keys for novel TDS fields.
- **SpecValue** is always text; numeric comparisons happen in Python.
- **SpecUnit** is nullable (e.g., NULL for text values like "USP").
- **SourceUri** and **SourceType** trace provenance back to the document or search result.

Standardized SpecKey vocabulary:

| Category | Keys |
|----------|------|
| Purity | `purity` |
| Particle size | `particle_size` |
| Heavy metals | `heavy_metals_lead`, `heavy_metals_arsenic`, `heavy_metals_cadmium`, `heavy_metals_mercury` |
| Microbial | `microbial_tpc`, `microbial_yeast_mold`, `microbial_coliforms` |
| Physical | `moisture_content`, `solubility` |
| Origin | `country_of_origin` |
| Certifications | `cert_kosher`, `cert_halal`, `cert_non_gmo`, `cert_organic` |
| Allergens | `allergen_declaration` |
| Grade | `form_grade` |

### New Agent Tool: `search_tds`

A new tool in `src/compliance/tools/search_tds.py` added to the research agent's toolset.

```python
def search_tds(
    ingredient_name: str,
    supplier_name: str | None = None,
) -> dict:
    """Search for Technical Data Sheets and fact sheets for an ingredient.

    Searches local document store first, then falls back to web search.
    If supplier_name is provided, searches for supplier-specific specs.
    If omitted, searches across all known suppliers for this ingredient.
    """
```

Two-phase search strategy:

1. **Phase 1 — Local pgvector store:** Query `search_documents` with `"{ingredient_name} {supplier_name} technical data sheet specifications"`. Catches previously ingested TDS/CoA PDFs.
2. **Phase 2 — Web fallback:** If local results are insufficient (no hits or low relevance scores below 0.3), use `web_search` with `"{ingredient_name} {supplier_name} TDS specifications purity"`. Return snippets for the agent to parse.

Return shape:
```python
{
    "status": "ok",
    "data": {
        "local_results": [
            {"text": "...", "score": 0.85, "source": "...", "section_title": "..."}
        ],
        "web_results": [
            {"title": "...", "url": "...", "description": "..."}
        ],
        "supplier_name": "ADM",
    }
}
```

When `supplier_name` is `None`, the tool does NOT auto-expand to all suppliers (that would be expensive and opaque). Instead, it runs a single generic search without supplier scoping. The agent is instructed (via the system prompt) to first look up suppliers via `query_database("supplier_products", ...)` and then call `search_tds` once per supplier. This keeps the agent in control of the iteration and makes tool calls visible in the streaming UI.

### Updated Research Agent System Prompt

The existing `RESEARCH_SYSTEM_PROMPT` in `src/compliance/research_agent.py` is extended with:

```
When researching a substitution, also search for Technical Data Sheets (TDS),
Certificates of Analysis (CoA), and fact sheets for both the original ingredient
and the proposed substitute. The same substance from different suppliers can have
different specifications (purity, heavy metals, particle size, etc.).

For each ingredient:
1. Look up which suppliers provide it (query_database with supplier_products).
2. For each supplier, search for TDS/spec data (search_tds with supplier_name).
3. Extract specification key-value pairs from the results.
4. Include spec differences across suppliers in your evidence and caveats.

When reporting evidence_rows for TDS/spec findings, use:
- source_type: "tds"
- fact_type: "spec:<key>" (e.g., "spec:purity", "spec:heavy_metals_lead")
- fact_value: the extracted value with unit (e.g., "99.5%", "< 0.5 ppm")
- source_label: include supplier name (e.g., "ADM TDS for Vitamin C")
```

### Spec Persistence Flow

After the research agent returns its verdict, `run_research` in `src/research/run.py` is extended:

1. Parse evidence rows from the verdict where `fact_type` starts with `"spec:"`.
2. For each spec evidence row, resolve the supplier ID from `source_label` (lookup by name).
3. Call `upsert_supplier_spec()` to persist into `Supplier_Spec`.
4. Evidence rows are persisted as-is into the `Evidence` table via the existing flow.

New DB helper in `src/common/db.py`:

```python
def upsert_supplier_spec(db_path=None, supplier_id=None, product_id=None,
                         spec_key=None, spec_value=None, spec_unit=None,
                         source_uri=None, source_type=None):
    """Insert or update a supplier spec row (upsert on unique index)."""
```

Also:

```python
def get_supplier_specs(db_path=None, product_id=None):
    """Return all Supplier_Spec rows for a product, grouped by supplier."""
```

### UI: Spec Comparison on Product Research Page

On `pages/6_Product_Research.py`, when viewing an ingredient's research results, add a **"Supplier Specs"** expander below the existing results. It reads from `Supplier_Spec` and pivots in Python:

| Spec | ADM | AIDP | Ashland |
|------|-----|------|---------|
| Purity | 99.5% | 98.0% | 99.8% |
| Heavy metals (Pb) | < 0.5 ppm | < 1.0 ppm | < 0.3 ppm |
| Form/Grade | USP | FCC | USP |
| Country of Origin | China | India | USA |
| Moisture | < 0.5% | — | < 0.3% |

Empty cells ("—") where a supplier has no data for a given key. The pivot is built with a simple Python dict-of-dicts passed to `st.dataframe`.

### Integration Points

- **`_build_tools()` in `research_agent.py`** — adds `search_tds` to the tool list (always available, since it uses existing `search_documents` and conditionally `web_search`).
- **`run_research()` in `run.py`** — after verdict, extracts spec rows and calls `upsert_supplier_spec()`.
- **`init_workspace_schema()` in `db.py`** — adds `CREATE TABLE Supplier_Spec` and index.
- **`pages/6_Product_Research.py`** — adds spec comparison expander per ingredient.

### Error Handling

- **TDS not found for a supplier:** The tool returns empty results. The agent notes "No TDS found for {supplier}" in its caveats. No spec rows are persisted.
- **Ambiguous spec extraction:** The agent includes raw text in `snippet` field of evidence rows. Spec rows are only persisted when the agent emits structured `"spec:*"` fact_type entries.
- **Supplier name resolution failure:** If the supplier name from `source_label` doesn't match a `Supplier.Name` row, the spec row is skipped (evidence row is still persisted). A warning is logged.

## Files to Create/Modify

| File | Action |
|------|--------|
| `src/compliance/tools/search_tds.py` | Create — new TDS search tool |
| `src/compliance/research_agent.py` | Modify — add `search_tds` to tools, extend system prompt |
| `src/common/db.py` | Modify — add `Supplier_Spec` table, `upsert_supplier_spec()`, `get_supplier_specs()` |
| `src/research/run.py` | Modify — extract spec rows from verdict, persist to `Supplier_Spec` |
| `pages/6_Product_Research.py` | Modify — add supplier spec comparison expander |
| `tests/test_search_tds.py` | Create — tests for the new tool |
| `tests/test_supplier_specs.py` | Create — tests for DB helpers and spec extraction |
