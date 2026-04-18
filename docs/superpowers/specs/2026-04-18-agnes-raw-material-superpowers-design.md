# Agnes Raw Material Superpowers — Design Spec

## Problem

CPG supplement companies buy the same functional ingredients independently, missing consolidation opportunities. The database has 61 supplement brands, 149 finished goods, 876 raw materials (357 distinct ingredient names), and 40 suppliers — but no quality specs, pricing, quantities, or compliance data. The challenge: determine which ingredients are functionally equivalent, verify substitutions are compliant, and produce explainable sourcing recommendations.

## Approach

Reasoning-first pipeline. Five sequential stages, each a standalone Python module. External enrichment via scraping product pages (iherb, thrive-market, amazon, etc.) and FDA regulatory documents, stored in AWS Bedrock Knowledge Base for RAG-grounded compliance reasoning.

## Domain

Nutraceuticals / dietary supplements. All 61 companies are supplement brands (GNC, Nature Made, Optimum Nutrition, etc.). Compliance framework: FDA dietary supplement regulations.

## Data Landscape

| Metric | Value |
|--------|-------|
| Companies | 61 |
| Finished goods | 149 (SKUs encode retail source: iherb, thrive-market, amazon, walmart, etc.) |
| Raw materials | 876 (each scoped to one company via CompanyId) |
| Distinct ingredient names | 357 |
| Suppliers | 40 |
| Avg BOM size | ~10 components (range: 2-48) |
| Suppliers per raw material | mostly 2, some 1 |

Key observations:
- Raw material SKU format: `RM-C{companyId}-{ingredient-name}-{8-char-hash}`
- Finished good SKU format: `FG-{source}-{product-id-or-slug}`
- Same ingredient appears as separate Product rows across companies (e.g., vitamin-d3-cholecalciferol exists for 17 companies)
- Name variants exist: vitamin-d3, vitamin-d3-cholecalciferol, cholecalciferol-vitamin-d3, vitamin-d
- Functional variants exist: 16 magnesium forms with different bioavailability and purposes

## Architecture

### AWS Services

| Service | Purpose |
|---------|---------|
| Bedrock (Claude) | All LLM calls: normalization, compliance evaluation, recommendation |
| Bedrock Knowledge Base | RAG over scraped product pages + FDA regulations |
| S3 | Document storage for Knowledge Base source files |

### Local Stack

| Component | Purpose |
|-----------|---------|
| SQLite | Existing schema + Ingredient_Group table |
| Streamlit | Frontend |
| Python | Pipeline stages |

### Project Structure

```
makeathon2026/
├── streamlit_app.py
├── db.sqlite
├── requirements.txt
├── src/
│   ├── scraper/
│   │   ├── iherb.py
│   │   ├── thrive_market.py
│   │   └── upload_to_s3.py
│   ├── normalize/
│   │   └── group_ingredients.py
│   ├── substitute/
│   │   └── find_candidates.py
│   ├── compliance/
│   │   └── evaluate.py
│   ├── recommend/
│   │   └── rank.py
│   └── common/
│       ├── db.py
│       ├── bedrock.py
│       └── knowledge_base.py
├── docs/
│   └── fda/
└── scripts/
    └── setup_kb.py
```

## Pipeline Stages

### Stage 1: Scrape & Ingest

Parse FG SKUs to construct product page URLs:
- `FG-iherb-10421` → iherb.com product page
- `FG-thrive-market-{slug}` → thrivemarket.com product page
- Similar patterns for amazon, walmart, costco, cvs, walgreens, target, gnc, vitacost, sams

Scrape from each page:
- Supplement facts panel (ingredients, amounts, % daily value)
- Certifications (NSF, Non-GMO Project, USDA Organic, etc.)
- Allergen warnings
- Product claims (gluten-free, vegan, etc.)
- Raw HTML for reprocessing

Save scraped documents to S3. Knowledge Base auto-indexes them.

Also ingest into Knowledge Base:
- FDA dietary supplement labeling regulations (21 CFR 101, 21 CFR 111)
- GRAS ingredient lists
- USP/NF monograph references

### Stage 2: Ingredient Normalization

Feed all 357 distinct ingredient names to Bedrock LLM in batches. LLM groups them into functional equivalence classes.

Output: `Ingredient_Group` table in SQLite:

```sql
CREATE TABLE Ingredient_Group (
    id INTEGER PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    function TEXT NOT NULL,
    members TEXT NOT NULL,  -- JSON array of ingredient name strings
    confidence TEXT CHECK (confidence IN ('high', 'medium', 'low')),
    reasoning TEXT
);
```

Grouping logic:
- **Same chemical entity, different names** → high confidence (vitamin-d3-cholecalciferol = cholecalciferol-vitamin-d3)
- **Same functional role, different forms** → medium confidence (magnesium-citrate and magnesium-glycinate both serve as Mg sources)
- **Same name but different functions** → excluded from grouping (magnesium-stearate is a flow agent, not a Mg source)

Human review step: team eyeballs groupings, fixes errors before proceeding.

### Stage 3: Substitution Candidate Generation

Given a user-selected finished good:
1. Pull its BOM components from SQLite
2. For each component, look up its Ingredient_Group
3. Find other members of the same group that are available from existing suppliers (via Supplier_Product)
4. Output: list of (original ingredient → candidate substitutes) with supplier availability

### Stage 4: Compliance Evaluation

For each substitution candidate, query Bedrock with Knowledge Base retrieval:

Input context:
- Target product's scraped supplement facts and claims (from KB)
- FDA regulations relevant to the ingredient category (from KB)
- Candidate ingredient's properties
- Original ingredient's role in the formulation

LLM evaluates:
- Does the substitute satisfy the same functional role?
- Are there FDA labeling implications? (e.g., name change on supplement facts panel)
- Does it conflict with any product claims? (e.g., substituting a non-organic ingredient into an organic-certified product)
- Are there allergen implications?
- Are there bioavailability differences that matter?

Output per substitution:

```json
{
    "original": "magnesium-oxide",
    "substitute": "magnesium-citrate",
    "verdict": "safe",
    "confidence": "medium",
    "facts": ["Product claims 400mg Magnesium per serving"],
    "rules": ["FDA requires supplement facts to list specific Mg form"],
    "inference": "Magnesium citrate provides bioavailable Mg but label must update form name. No certification conflicts.",
    "sources": ["iherb.com/pr/10421 (supplement facts)", "21 CFR 101.36"],
    "caveats": ["Dosage equivalence cannot be verified — no quantity data"]
}
```

### Stage 5: Recommendation & Display

Aggregate Stage 4 results into ranked recommendations per ingredient. Display in Streamlit.

## Streamlit UI

### Main Flow

1. **Product selector** — dropdown of 149 finished goods, showing company name + product SKU
2. **BOM view** — table of all ingredients with current supplier(s)
3. **Substitution panel** — per-ingredient expandable sections:
   - Functional equivalence group
   - Candidate substitutes with verdict badges (safe / risky / incompatible)
   - Evidence trail: collapsible block with LLM reasoning, cited sources, confidence
4. **Consolidation summary** — sidebar: "X companies also use this ingredient — consolidation opportunity with Supplier Y"

### UI Principles

- Evidence is first-class: every recommendation shows why
- Confidence is visible: color-coded (green/yellow/red)
- Decision-support only: presents options and evidence, user decides

### Nice-to-haves (if time permits)

- Side-by-side original vs. substitute comparison
- Export as PDF report
- Filter by safe substitutions only

## Trustworthiness & Hallucination Control

### Prevention

- Never recommend without evidence. If Knowledge Base returns nothing relevant, output "insufficient evidence" instead of guessing.
- Source attribution on every claim. Each verdict links to a scraped product page, FDA regulation section, or both.
- Separate fact from inference in structured output:
  - **Facts:** from scraped data
  - **Rules:** from FDA regulations in Knowledge Base
  - **Inference:** LLM reasoning connecting facts to rules

### Confidence Scoring

- **High:** Same chemical entity, different name. Name normalization only.
- **Medium:** Functional equivalent with supporting evidence from scraped data and regulations.
- **Low:** Functional equivalent but missing evidence. Flagged for human review.

### Known Limitations

- No quantity/dosage data in the database
- Scraped data may be incomplete or stale
- LLM compliance reasoning is advisory, not legal advice
- No supplier pricing data — consolidation value is structural, not dollar-quantified

## Team Split (5 people, 36 hours)

| Person | Responsibility |
|--------|---------------|
| 1 | Scraping + S3/Knowledge Base setup |
| 2 | Ingredient normalization + review |
| 3 | Substitution logic (Stages 3-4 pipeline) |
| 4 | Prompt engineering + evaluation (trustworthiness) |
| 5 | Streamlit frontend + presentation |

## Open Questions for Judges

- Are quantities intentionally omitted, or will they appear in the actual data? (Affects whether volume-based consolidation is possible)
- Should we discover new suppliers, or only optimize across the existing 40?

## Execution Flow

```
scraper → S3 → Knowledge Base (auto-index)
                     ↓
SQLite → normalize → Ingredient_Group table
                     ↓
User selects product in Streamlit
                     ↓
find_candidates (SQLite) → evaluate (Bedrock + KB) → rank → display
```
