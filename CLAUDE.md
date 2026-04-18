# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Agnes is a sourcing decision workspace for supplement/CPG raw-material consolidation. It finds opportunities to substitute or consolidate BOM ingredients across a portfolio of finished goods, using a deterministic blocker engine (not LLM inference) to gate decisions. The demo runs against a pre-seeded SQLite database (`db.sqlite`) containing the portfolio graph: Company -> Product -> BOM -> BOM_Component -> Supplier_Product.

## Commands

```bash
# Initialize workspace tables and seed ingredient aliases
python3 scripts/init_db.py

# Run Streamlit app (opens on http://localhost:8501)
streamlit run streamlit_app.py

# Run all tests
pytest -q

# Run a single test file
pytest tests/test_blockers.py -q

# Docker
docker compose up --build
```

## Architecture

### Data flow (opportunity pipeline)

`build_all_opportunities()` in `src/opportunity/build.py` is the main entry point. It runs on first load or "Rebuild Demo Workspace" button:

1. **Portfolio scan** — `src/common/db.py` queries the pre-existing `Product`, `BOM`, `BOM_Component`, `Supplier`, `Supplier_Product` tables
2. **Candidate discovery** — `src/substitute/find_candidates.py` finds exact-match and alias/hypothesis candidates per BOM component. Aliases come from `Ingredient_Alias` table (seeded by `init_db.py`)
3. **Requirement profiling** — `src/reasoning/requirements.py` builds per-component requirement profiles from the demo fact cache
4. **Blocker evaluation** — `src/reasoning/blockers.py` runs deterministic checks (allergen conflicts, vegan compatibility, certification gaps, evidence strength) returning `pass_known_blockers | needs_review | blocked`
5. **Evidence collection** — `src/evidence/normalize.py` converts cached facts into structured evidence rows; `src/evidence/store.py` persists them
6. **Scoring** — `src/recommend/rank.py` computes a priority score per opportunity
7. **Persistence** — `src/opportunity/store.py` upserts opportunities, candidates, evidence, and requirements into workspace tables

### Demo fact cache

`src/scraper/cache.py` contains hardcoded `DEMO_INGREDIENT_FACTS` and `DEMO_PRODUCT_FACTS` — no live web scraping runs by default. The blocker engine and evidence layer read from this cache.

### Streamlit UI

- `streamlit_app.py` — home page with metrics and workspace rebuild button
- `pages/1_Overview.py` — portfolio overview
- `pages/2_Opportunity_Queue.py` — filterable opportunity list
- `pages/3_Opportunity_Detail.py` — single opportunity deep-dive with candidates, evidence, requirements
- `pages/4_Review.py` — review decision recording
- `pages/5_Suppliers.py` — supplier view

### External service integrations

- **AWS Bedrock** (`src/common/bedrock.py`) — Claude model calls via `boto3`. Requires `AWS_DEFAULT_REGION` and standard AWS credentials. Used for LLM-based grouping/analysis, not for the core blocker engine.
- **PostgreSQL + pgvector** (`src/common/vector_db.py`, `src/common/vector_store.py`) — hybrid vector + keyword retrieval (RRF). Requires `DATABASE_URL` env var. Used by the document retrieval path, not the core opportunity pipeline.
- **S3** (`src/scraper/upload_to_s3.py`) — document upload. Requires `S3_BUCKET_NAME`.

### Key SQLite tables (workspace-extended)

Pre-existing (the portfolio graph): `Company`, `Product`, `BOM`, `BOM_Component`, `Supplier`, `Supplier_Product`

Workspace-added (created by `init_workspace_schema()`): `Ingredient_Alias`, `Opportunity`, `Opportunity_Candidate`, `Evidence`, `Requirement_Profile`, `Review_Decision`, `Ingredient_Group`

### Match type hierarchy

- **exact** — same `parsed_ingredient_name`, high confidence, can auto-pass blockers
- **alias** — curated same-chemical-entity alias (e.g. ascorbic-acid = vitamin-c), medium confidence, requires high-strength identity evidence to pass
- **hypothesis** — functional family member (e.g. magnesium-oxide ~ magnesium-citrate), low confidence, always routed to `needs-review`

## Testing

Tests use a temporary SQLite database (`conftest.py` patches `sys.path` to project root). The test suite covers: DB schema/queries, BOM SKU parsing, candidate finding, blocker evaluation, opportunity building, review flow, ranking, chunking, embeddings, and vector store.
