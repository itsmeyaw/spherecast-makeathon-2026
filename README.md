# Agnes — Raw Material Superpowers

AI-powered decision-support system for supplement ingredient substitution and compliance verification. Built for the Spherecast hackathon challenge: consolidating fragmented raw material sourcing across CPG supplement companies.

## Problem

61 supplement brands (GNC, Nature Made, Optimum Nutrition, etc.) independently purchase the same functional ingredients from 40 suppliers. No one has full visibility into combined demand. Agnes analyzes 876 raw materials across 149 finished products, identifies which ingredients are functionally equivalent, verifies FDA compliance for substitutions, and produces explainable sourcing recommendations.

## How It Works

Agnes runs a five-stage reasoning pipeline:

```
Scrape product pages → S3 → Knowledge Base (auto-index)
                                    ↓
SQLite → LLM normalizes 357 ingredients → Ingredient Groups
                                    ↓
          User selects product in Streamlit
                                    ↓
    Find candidates → Evaluate compliance (Bedrock + KB RAG) → Rank → Display
```

### Stage 1: Scrape & Ingest
Parses finished-good SKUs (encoding retail source: iherb, amazon, walmart, etc.) to scrape supplement facts panels, certifications, allergen warnings, and product claims. Documents are stored in S3 and auto-indexed by Bedrock Knowledge Base.

### Stage 2: Ingredient Normalization
Feeds all 357 distinct ingredient names to Claude via Bedrock in batches. The LLM groups them into functional equivalence classes — distinguishing between name variants (vitamin-d3 = cholecalciferol-vitamin-d3), functional equivalents (magnesium-citrate ~ magnesium-glycinate as Mg sources), and false friends (magnesium-stearate is a flow agent, not a magnesium source).

### Stage 3: Substitution Candidate Generation
For a selected product, pulls its BOM components, looks up each ingredient's equivalence group, and finds alternatives available from existing suppliers.

### Stage 4: Compliance Evaluation
For each substitution candidate, queries the Knowledge Base for the target product's scraped label data and relevant FDA regulations. Claude evaluates functional equivalence, labeling implications, certification conflicts, allergen risks, and bioavailability differences. Every verdict includes cited sources and explicit uncertainty flags.

### Stage 5: Recommendation & Display
Aggregates results into a ranked recommendation per ingredient. Displayed in Streamlit with color-coded verdicts (safe/risky/incompatible), evidence trails, and a consolidation opportunities sidebar.

## Architecture

| Component | Technology |
|-----------|-----------|
| Frontend | Streamlit |
| Database | SQLite (provided schema + Ingredient_Group table) |
| LLM | AWS Bedrock (Claude) |
| RAG | AWS Bedrock Knowledge Base |
| Document Storage | AWS S3 |
| Scraping | httpx + BeautifulSoup + LLM extraction |
| Containerization | Docker Compose |

## Project Structure

```
makeathon2026/
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── db.sqlite                    # Provided dataset
├── streamlit_app.py             # Main UI
├── src/
│   ├── common/
│   │   ├── bedrock.py           # Bedrock client wrapper
│   │   ├── db.py                # SQLite query helpers
│   │   └── knowledge_base.py    # KB retrieve + RAG helper
│   ├── scraper/
│   │   ├── sku_parser.py        # Parse FG SKUs into retail source + product ID
│   │   ├── scrape.py            # Scrape product pages, extract with LLM
│   │   └── upload_to_s3.py      # Upload scraped docs to S3
│   ├── normalize/
│   │   └── group_ingredients.py # LLM-based ingredient grouping
│   ├── substitute/
│   │   └── find_candidates.py   # SQL-driven candidate generation
│   ├── compliance/
│   │   └── evaluate.py          # Bedrock + KB compliance evaluation
│   └── recommend/
│       └── rank.py              # Aggregate and rank recommendations
├── scripts/
│   └── setup_kb.py              # Create S3 bucket and upload docs
└── tests/
    ├── test_db.py
    ├── test_sku_parser.py
    ├── test_find_candidates.py
    └── test_rank.py
```

## Dataset

The provided SQLite database contains:

| Table | Records | Description |
|-------|---------|-------------|
| Company | 61 | Supplement brands (GNC, Nature Made, etc.) |
| Product | 1,025 | 149 finished goods + 876 raw materials |
| BOM | 149 | Bill of materials (one per finished good) |
| BOM_Component | 1,528 | Ingredient assignments (avg 10 per BOM) |
| Supplier | 40 | Raw material suppliers |
| Supplier_Product | 1,633 | Supplier-to-ingredient mappings |

**SKU conventions:**
- Finished goods: `FG-{source}-{product-id}` (e.g., `FG-iherb-10421`, `FG-amazon-b0002wrqy4`)
- Raw materials: `RM-C{companyId}-{ingredient-name}-{8-char-hash}` (e.g., `RM-C28-vitamin-d3-cholecalciferol-8956b79c`)

**Retail sources:** iherb, amazon, walmart, target, cvs, walgreens, costco, thrive-market, vitacost, sams-club, gnc, the-vitamin-shoppe

## Setup

### Prerequisites

- Docker and Docker Compose
- AWS account with Bedrock access (Claude model enabled)
- AWS credentials with permissions for S3, Bedrock, and Bedrock Agent Runtime

### 1. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your AWS credentials:

```
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET_NAME=agnes-hackathon-kb
KNOWLEDGE_BASE_ID=your-kb-id
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250514
```

### 2. Create S3 Bucket

```bash
docker compose run app python scripts/setup_kb.py
```

### 3. Create Knowledge Base

1. Go to **AWS Console > Bedrock > Knowledge bases**
2. Create a new Knowledge Base pointing to `s3://agnes-hackathon-kb/`
3. Copy the Knowledge Base ID into your `.env` file as `KNOWLEDGE_BASE_ID`

### 4. Scrape Product Pages

```bash
# Scrape all 149 finished goods (takes ~10 min with rate limiting)
docker compose run app python -c "from src.scraper.scrape import scrape_all_products; scrape_all_products()"

# Upload scraped data to S3 for Knowledge Base indexing
docker compose run app python src/scraper/upload_to_s3.py
```

After uploading, sync/re-index the Knowledge Base in the AWS Console.

### 5. Run Ingredient Normalization

```bash
docker compose run app python -m src.normalize.group_ingredients
```

This groups 357 ingredient names into functional equivalence classes and saves them to the `Ingredient_Group` table in SQLite.

### 6. Launch the App

```bash
docker compose up
```

Open [http://localhost:8501](http://localhost:8501).

## Usage

1. **Select a product** from the dropdown (e.g., "NOW Foods — FG-iherb-10421")
2. **Review the BOM** — see all ingredients, SKUs, and current suppliers
3. **Click "Analyze Substitution Opportunities"** — triggers the full pipeline
4. **Review results** — each ingredient shows:
   - Functional equivalence group and confidence level
   - Candidate substitutes with color-coded verdicts (green=safe, orange=risky, red=incompatible, gray=insufficient evidence)
   - Evidence trail: facts from scraped data, applicable FDA rules, LLM reasoning, source citations, and caveats
5. **Check the sidebar** for consolidation opportunities — ingredients shared across multiple companies

## Trustworthiness & Hallucination Control

- **Never recommends without evidence.** If the Knowledge Base returns nothing relevant, the system outputs "insufficient evidence" instead of guessing.
- **Source attribution on every claim.** Each verdict links back to scraped product pages and/or FDA regulation sections.
- **Structured fact/rule/inference separation.** Facts come from scraped data, rules from the Knowledge Base, inference is the LLM's reasoning connecting them.
- **Confidence scoring.** High = same chemical entity (name normalization). Medium = functional equivalent with evidence. Low = missing evidence, flagged for human review.

### Known Limitations

- No quantity/dosage data in the database — dosage equivalence cannot be verified
- Scraped product page data may be incomplete or stale
- LLM compliance reasoning is advisory, not legal advice
- No supplier pricing data — consolidation value is structural, not dollar-quantified

## Running Tests

```bash
# With Docker
docker compose run app python -m pytest tests/ -v

# Without Docker (requires Python 3.11+ and dependencies installed)
pip install -r requirements.txt
pip install pytest
python -m pytest tests/ -v
```

25 tests covering database helpers, SKU parsing, substitution candidate generation, and recommendation ranking.

## Team

Built during a 36-hour hackathon by a team of 5.
