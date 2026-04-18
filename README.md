# Agnes Sourcing Workspace

Agnes is now a lightweight sourcing decision workspace demo built on top of the provided SQLite portfolio graph.

What is real in this repo:
- the internal graph: `company -> product -> BOM -> BOM component -> supplier product`
- exact-match consolidation opportunities
- curated alias-match opportunities
- persisted opportunity, evidence, requirement, and review state in SQLite
- deterministic blocker states for a narrow demo slice
- a Streamlit workspace with Overview, Queue, Detail, and Review pages

What is intentionally not claimed:
- autonomous substitute approval
- full compliance validation
- pricing or savings optimization
- live scraping as a demo-critical dependency

## Demo posture

The app is opinionated about uncertainty:
- exact-match opportunities can pass known blockers
- curated aliases only pass when the local demo evidence pack marks them as high-strength identity matches
- broader alias and hypothesis candidates are routed to `needs-review`
- if supporting data is missing, the app records the gap instead of inventing certainty

## Workspace schema additions

The repo now extends `db.sqlite` with:
- `Ingredient_Alias`
- `Opportunity`
- `Opportunity_Candidate`
- `Evidence`
- `Requirement_Profile`
- `Review_Decision`

These tables are created by `scripts/init_db.py`.

## Local demo evidence pack

Phase 1 uses a reproducible local fact cache in [src/scraper/cache.py](/Users/janetbrinz/Documents/Codex/2026-04-18-git-clone-https-github-com-itsmeyaw/src/scraper/cache.py:1) instead of relying on live web retrieval.

That cache supplies:
- reviewed ingredient identity facts for a narrow ingredient slice
- limited product-level facts for demo blocker scenarios
- evidence-strength labels used by the blocker engine

## Run the app

1. Initialize the workspace tables and seed aliases:

```bash
python3 scripts/init_db.py
```

2. Launch Streamlit:

```bash
streamlit run streamlit_app.py
```

3. Open `http://localhost:8501`

The app will build the opportunity workspace from the current `db.sqlite` on first load. You can force a rebuild from the home page.

## Run tests

```bash
pytest -q
```

## Main modules

- [src/common/db.py](/Users/janetbrinz/Documents/Codex/2026-04-18-git-clone-https-github-com-itsmeyaw/src/common/db.py:1): schema helpers, portfolio queries, alias seeding
- [src/substitute/find_candidates.py](/Users/janetbrinz/Documents/Codex/2026-04-18-git-clone-https-github-com-itsmeyaw/src/substitute/find_candidates.py:1): exact and alias candidate discovery
- [src/opportunity/build.py](/Users/janetbrinz/Documents/Codex/2026-04-18-git-clone-https-github-com-itsmeyaw/src/opportunity/build.py:1): opportunity generation pipeline
- [src/opportunity/store.py](/Users/janetbrinz/Documents/Codex/2026-04-18-git-clone-https-github-com-itsmeyaw/src/opportunity/store.py:1): persistence, queue queries, review state
- [src/reasoning/blockers.py](/Users/janetbrinz/Documents/Codex/2026-04-18-git-clone-https-github-com-itsmeyaw/src/reasoning/blockers.py:1): deterministic blocker engine
- [src/reasoning/explain.py](/Users/janetbrinz/Documents/Codex/2026-04-18-git-clone-https-github-com-itsmeyaw/src/reasoning/explain.py:1): explanation synthesis from structured facts
- [pages/1_Overview.py](/Users/janetbrinz/Documents/Codex/2026-04-18-git-clone-https-github-com-itsmeyaw/pages/1_Overview.py:1), [pages/2_Opportunity_Queue.py](/Users/janetbrinz/Documents/Codex/2026-04-18-git-clone-https-github-com-itsmeyaw/pages/2_Opportunity_Queue.py:1), [pages/3_Opportunity_Detail.py](/Users/janetbrinz/Documents/Codex/2026-04-18-git-clone-https-github-com-itsmeyaw/pages/3_Opportunity_Detail.py:1), [pages/4_Review.py](/Users/janetbrinz/Documents/Codex/2026-04-18-git-clone-https-github-com-itsmeyaw/pages/4_Review.py:1): sourcing workspace UI

## Deferred on purpose

- live supplier scraping
- OCR and multimodal extraction
- pricing, savings, and lead-time logic
- universal compliance engine
- broader CPG generalization beyond the narrow supplement demo slice
