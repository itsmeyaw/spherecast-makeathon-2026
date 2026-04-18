# Agnes Raw Material Superpowers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an AI decision-support system that identifies functionally equivalent supplement ingredients across 61 companies, verifies substitution compliance via FDA regulations, and produces explainable sourcing recommendations.

**Architecture:** Five-stage reasoning pipeline — scrape product pages for enrichment, normalize 357 ingredient names into functional equivalence groups via LLM, generate substitution candidates from SQLite, evaluate compliance via Bedrock + Knowledge Base RAG, display results in Streamlit. Dockerized for consistent team environment.

**Tech Stack:** Python 3.12, Streamlit, SQLite, AWS Bedrock (Claude), AWS Bedrock Knowledge Base, S3, BeautifulSoup/httpx, Docker Compose

---

## File Map

| File | Responsibility |
|------|---------------|
| `Dockerfile` | Python 3.12 image, install deps, run Streamlit |
| `docker-compose.yml` | Service definition, volume mounts, env vars |
| `.env.example` | Template for AWS credentials |
| `.dockerignore` | Exclude .venv, .git, docs |
| `requirements.txt` | All Python dependencies |
| `src/__init__.py` | Package marker |
| `src/common/__init__.py` | Package marker |
| `src/common/db.py` | SQLite connection + query helpers |
| `src/common/bedrock.py` | Bedrock client wrapper (invoke model, parse response) |
| `src/common/knowledge_base.py` | Knowledge Base retrieve-and-generate helper |
| `src/scraper/__init__.py` | Package marker |
| `src/scraper/sku_parser.py` | Parse FG SKUs into retail source URLs |
| `src/scraper/scrape.py` | Scrape product pages, extract supplement facts |
| `src/scraper/upload_to_s3.py` | Upload scraped docs to S3 for KB ingestion |
| `src/normalize/__init__.py` | Package marker |
| `src/normalize/group_ingredients.py` | LLM-based ingredient grouping into equivalence classes |
| `src/substitute/__init__.py` | Package marker |
| `src/substitute/find_candidates.py` | SQL-driven candidate generation from equivalence groups |
| `src/compliance/__init__.py` | Package marker |
| `src/compliance/evaluate.py` | Bedrock + KB compliance evaluation per substitution |
| `src/recommend/__init__.py` | Package marker |
| `src/recommend/rank.py` | Aggregate compliance results into ranked recommendations |
| `streamlit_app.py` | Main UI — product selector, BOM view, substitution panel |
| `scripts/setup_kb.py` | Create S3 bucket, Knowledge Base, and data source |
| `tests/test_db.py` | Tests for db helpers |
| `tests/test_sku_parser.py` | Tests for SKU parsing |
| `tests/test_find_candidates.py` | Tests for substitution candidate generation |
| `tests/test_rank.py` | Tests for recommendation ranking |

---

### Task 1: Docker & Project Scaffold

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `.dockerignore`
- Modify: `.gitignore`
- Modify: `requirements.txt`
- Create: `src/__init__.py`, `src/common/__init__.py`, `src/scraper/__init__.py`, `src/normalize/__init__.py`, `src/substitute/__init__.py`, `src/compliance/__init__.py`, `src/recommend/__init__.py`

- [ ] **Step 1: Update .gitignore**

Add entries for Docker and env files. Append to `.gitignore`:

```
.venv
.env
__pycache__
*.pyc
data/
```

- [ ] **Step 2: Create .env.example**

```
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET_NAME=agnes-hackathon-kb
KNOWLEDGE_BASE_ID=your-kb-id
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250514
```

- [ ] **Step 3: Update requirements.txt**

```
streamlit
boto3
httpx
beautifulsoup4
lxml
```

- [ ] **Step 4: Create Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.address", "0.0.0.0"]
```

- [ ] **Step 5: Create docker-compose.yml**

```yaml
services:
  app:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./db.sqlite:/app/db.sqlite
      - ./src:/app/src
    env_file:
      - .env
```

- [ ] **Step 6: Create .dockerignore**

```
.venv
.git
docs
*.md
__pycache__
```

- [ ] **Step 7: Create all __init__.py package markers**

Create empty files at:
- `src/__init__.py`
- `src/common/__init__.py`
- `src/scraper/__init__.py`
- `src/normalize/__init__.py`
- `src/substitute/__init__.py`
- `src/compliance/__init__.py`
- `src/recommend/__init__.py`

- [ ] **Step 8: Verify Docker build works**

Run: `docker compose build`
Expected: Image builds successfully with all deps installed.

- [ ] **Step 9: Verify Docker run works**

Run: `docker compose up -d && sleep 3 && curl -s http://localhost:8501 | head -5 && docker compose down`
Expected: Streamlit returns HTML. The existing hello-world app renders.

- [ ] **Step 10: Commit**

```bash
git add Dockerfile docker-compose.yml .env.example .dockerignore .gitignore requirements.txt src/
git commit -m "feat: add Docker scaffold and project structure"
```

---

### Task 2: SQLite Database Helpers

**Files:**
- Create: `src/common/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write failing tests for db helpers**

Create `tests/test_db.py`:

```python
import sqlite3
import json
import tempfile
import os
from src.common.db import (
    get_connection,
    get_finished_goods,
    get_bom_components,
    get_suppliers_for_product,
    get_all_ingredient_names,
    save_ingredient_groups,
    get_ingredient_group_for,
)


def _make_test_db(path):
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE Company (Id INTEGER PRIMARY KEY, Name TEXT NOT NULL);
        CREATE TABLE Product (
            Id INTEGER PRIMARY KEY, SKU TEXT NOT NULL,
            CompanyId INTEGER NOT NULL, Type TEXT NOT NULL,
            FOREIGN KEY (CompanyId) REFERENCES Company (Id)
        );
        CREATE TABLE BOM (
            Id INTEGER PRIMARY KEY, ProducedProductId INTEGER NOT NULL UNIQUE,
            FOREIGN KEY (ProducedProductId) REFERENCES Product (Id)
        );
        CREATE TABLE BOM_Component (
            BOMId INTEGER NOT NULL, ConsumedProductId INTEGER NOT NULL,
            PRIMARY KEY (BOMId, ConsumedProductId)
        );
        CREATE TABLE Supplier (Id INTEGER PRIMARY KEY, Name TEXT NOT NULL);
        CREATE TABLE Supplier_Product (
            SupplierId INTEGER NOT NULL, ProductId INTEGER NOT NULL,
            PRIMARY KEY (SupplierId, ProductId)
        );

        INSERT INTO Company VALUES (1, 'TestCo'), (2, 'OtherCo');
        INSERT INTO Product VALUES
            (1, 'FG-iherb-123', 1, 'finished-good'),
            (2, 'RM-C1-vitamin-d3-abc12345', 1, 'raw-material'),
            (3, 'RM-C1-magnesium-oxide-def67890', 1, 'raw-material'),
            (4, 'RM-C2-vitamin-d3-cholecalciferol-aaa11111', 2, 'raw-material');
        INSERT INTO BOM VALUES (1, 1);
        INSERT INTO BOM_Component VALUES (1, 2), (1, 3);
        INSERT INTO Supplier VALUES (1, 'SupplierA'), (2, 'SupplierB');
        INSERT INTO Supplier_Product VALUES (1, 2), (2, 2), (1, 4);
    """)
    conn.commit()
    return conn


class TestGetFinishedGoods:
    def test_returns_all_finished_goods_with_company(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _make_test_db(db_path)
        results = get_finished_goods(db_path)
        assert len(results) == 1
        assert results[0]["sku"] == "FG-iherb-123"
        assert results[0]["company_name"] == "TestCo"
        assert results[0]["product_id"] == 1


class TestGetBomComponents:
    def test_returns_components_with_suppliers(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _make_test_db(db_path)
        results = get_bom_components(db_path, product_id=1)
        assert len(results) == 2
        skus = {r["sku"] for r in results}
        assert "RM-C1-vitamin-d3-abc12345" in skus
        assert "RM-C1-magnesium-oxide-def67890" in skus


class TestGetSuppliersForProduct:
    def test_returns_supplier_names(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _make_test_db(db_path)
        suppliers = get_suppliers_for_product(db_path, product_id=2)
        assert set(suppliers) == {"SupplierA", "SupplierB"}


class TestGetAllIngredientNames:
    def test_returns_distinct_parsed_names(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _make_test_db(db_path)
        names = get_all_ingredient_names(db_path)
        assert "vitamin-d3" in names
        assert "magnesium-oxide" in names
        assert "vitamin-d3-cholecalciferol" in names


class TestIngredientGroups:
    def test_save_and_retrieve(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _make_test_db(db_path)
        groups = [
            {
                "canonical_name": "Vitamin D3",
                "function": "vitamin D source",
                "members": ["vitamin-d3", "vitamin-d3-cholecalciferol"],
                "confidence": "high",
                "reasoning": "Same chemical entity",
            }
        ]
        save_ingredient_groups(db_path, groups)
        group = get_ingredient_group_for(db_path, "vitamin-d3")
        assert group["canonical_name"] == "Vitamin D3"
        assert "vitamin-d3-cholecalciferol" in group["members"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.common.db'`

- [ ] **Step 3: Implement src/common/db.py**

```python
import sqlite3
import json
import re

DB_PATH = "db.sqlite"


def get_connection(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_finished_goods(db_path=None):
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT p.Id as product_id, p.SKU as sku, c.Name as company_name
        FROM Product p
        JOIN Company c ON p.CompanyId = c.Id
        WHERE p.Type = 'finished-good'
        ORDER BY c.Name, p.SKU
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_bom_components(db_path=None, product_id=None):
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT p2.Id as product_id, p2.SKU as sku, p2.CompanyId as company_id
        FROM BOM b
        JOIN BOM_Component bc ON bc.BOMId = b.Id
        JOIN Product p2 ON p2.Id = bc.ConsumedProductId
        WHERE b.ProducedProductId = ?
        ORDER BY p2.SKU
    """, (product_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_suppliers_for_product(db_path=None, product_id=None):
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT s.Name
        FROM Supplier_Product sp
        JOIN Supplier s ON sp.SupplierId = s.Id
        WHERE sp.ProductId = ?
        ORDER BY s.Name
    """, (product_id,)).fetchall()
    conn.close()
    return [r["Name"] for r in rows]


def parse_ingredient_name(sku):
    match = re.match(r"RM-C\d+-(.+)-[a-f0-9]{8}$", sku)
    if match:
        return match.group(1)
    return sku


def get_all_ingredient_names(db_path=None):
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT DISTINCT SKU FROM Product WHERE Type = 'raw-material'
    """).fetchall()
    conn.close()
    names = set()
    for r in rows:
        names.add(parse_ingredient_name(r["SKU"]))
    return sorted(names)


def save_ingredient_groups(db_path=None, groups=None):
    conn = get_connection(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Ingredient_Group (
            id INTEGER PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            function TEXT NOT NULL,
            members TEXT NOT NULL,
            confidence TEXT CHECK (confidence IN ('high', 'medium', 'low')),
            reasoning TEXT
        )
    """)
    conn.execute("DELETE FROM Ingredient_Group")
    for g in groups:
        conn.execute(
            "INSERT INTO Ingredient_Group (canonical_name, function, members, confidence, reasoning) VALUES (?, ?, ?, ?, ?)",
            (g["canonical_name"], g["function"], json.dumps(g["members"]), g["confidence"], g["reasoning"]),
        )
    conn.commit()
    conn.close()


def get_ingredient_group_for(db_path=None, ingredient_name=None):
    conn = get_connection(db_path)
    rows = conn.execute("SELECT * FROM Ingredient_Group").fetchall()
    conn.close()
    for r in rows:
        members = json.loads(r["members"])
        if ingredient_name in members:
            return {
                "id": r["id"],
                "canonical_name": r["canonical_name"],
                "function": r["function"],
                "members": members,
                "confidence": r["confidence"],
                "reasoning": r["reasoning"],
            }
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_db.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/common/db.py tests/test_db.py
git commit -m "feat: add SQLite database helpers with tests"
```

---

### Task 3: Bedrock Client Wrapper

**Files:**
- Create: `src/common/bedrock.py`

- [ ] **Step 1: Implement Bedrock wrapper**

Create `src/common/bedrock.py`:

```python
import json
import os
import boto3


def get_bedrock_client():
    return boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )


def invoke_model(prompt, system=None, model_id=None):
    client = get_bedrock_client()
    model = model_id or os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-20250514")

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": messages,
    }
    if system:
        body["system"] = [{"type": "text", "text": system}]

    response = client.invoke_model(
        modelId=model,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def invoke_model_json(prompt, system=None, model_id=None):
    raw = invoke_model(prompt, system=system, model_id=model_id)
    start = raw.find("[") if raw.find("[") < raw.find("{") or raw.find("{") == -1 else raw.find("{")
    end = raw.rfind("]") + 1 if start == raw.find("[") else raw.rfind("}") + 1
    if start == -1:
        return raw
    return json.loads(raw[start:end])
```

- [ ] **Step 2: Manual smoke test**

Run: `python -c "from src.common.bedrock import invoke_model; print(invoke_model('Say hello in one word'))"`
Expected: Prints a one-word greeting (requires `.env` with valid AWS credentials).

- [ ] **Step 3: Commit**

```bash
git add src/common/bedrock.py
git commit -m "feat: add Bedrock client wrapper"
```

---

### Task 4: Knowledge Base Helper

**Files:**
- Create: `src/common/knowledge_base.py`
- Create: `scripts/setup_kb.py`

- [ ] **Step 1: Implement Knowledge Base query helper**

Create `src/common/knowledge_base.py`:

```python
import os
import boto3


def get_kb_client():
    return boto3.client(
        "bedrock-agent-runtime",
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )


def retrieve(query, n_results=5):
    client = get_kb_client()
    kb_id = os.environ["KNOWLEDGE_BASE_ID"]

    response = client.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {"numberOfResults": n_results}
        },
    )
    results = []
    for item in response.get("retrievalResults", []):
        results.append({
            "text": item["content"]["text"],
            "score": item.get("score", 0),
            "source": item.get("location", {}).get("s3Location", {}).get("uri", "unknown"),
        })
    return results


def retrieve_and_generate(query, model_id=None):
    client = get_kb_client()
    kb_id = os.environ["KNOWLEDGE_BASE_ID"]
    model = model_id or os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-20250514")
    model_arn = f"arn:aws:bedrock:{os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')}::foundation-model/{model}"

    response = client.retrieve_and_generate(
        input={"text": query},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": kb_id,
                "modelArn": model_arn,
            },
        },
    )
    output = response["output"]["text"]
    citations = []
    for citation in response.get("citations", []):
        for ref in citation.get("retrievedReferences", []):
            citations.append({
                "text": ref["content"]["text"],
                "source": ref.get("location", {}).get("s3Location", {}).get("uri", "unknown"),
            })
    return {"answer": output, "citations": citations}
```

- [ ] **Step 2: Create KB setup script**

Create `scripts/setup_kb.py`:

```python
import os
import sys
import time
import boto3


def create_s3_bucket(bucket_name, region):
    s3 = boto3.client("s3", region_name=region)
    try:
        if region == "us-east-1":
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": region},
            )
        print(f"Created S3 bucket: {bucket_name}")
    except s3.exceptions.BucketAlreadyOwnedByYou:
        print(f"Bucket already exists: {bucket_name}")


def upload_directory(local_dir, bucket_name, prefix, region):
    s3 = boto3.client("s3", region_name=region)
    count = 0
    for root, dirs, files in os.walk(local_dir):
        for filename in files:
            local_path = os.path.join(root, filename)
            rel_path = os.path.relpath(local_path, local_dir)
            s3_key = f"{prefix}/{rel_path}"
            s3.upload_file(local_path, bucket_name, s3_key)
            count += 1
    print(f"Uploaded {count} files to s3://{bucket_name}/{prefix}/")


if __name__ == "__main__":
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    bucket = os.environ.get("S3_BUCKET_NAME", "agnes-hackathon-kb")

    create_s3_bucket(bucket, region)

    scraped_dir = "data/scraped"
    if os.path.isdir(scraped_dir):
        upload_directory(scraped_dir, bucket, "scraped-products", region)

    fda_dir = "docs/fda"
    if os.path.isdir(fda_dir):
        upload_directory(fda_dir, bucket, "fda-regulations", region)

    print("\nNext steps:")
    print("1. Go to AWS Console → Bedrock → Knowledge bases")
    print(f"2. Create a Knowledge Base pointing to s3://{bucket}/")
    print("3. Copy the Knowledge Base ID into your .env file as KNOWLEDGE_BASE_ID")
```

- [ ] **Step 3: Commit**

```bash
git add src/common/knowledge_base.py scripts/setup_kb.py
git commit -m "feat: add Knowledge Base helper and setup script"
```

---

### Task 5: SKU Parser

**Files:**
- Create: `src/scraper/sku_parser.py`
- Create: `tests/test_sku_parser.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_sku_parser.py`:

```python
from src.scraper.sku_parser import parse_fg_sku, build_search_query


class TestParseFgSku:
    def test_iherb(self):
        result = parse_fg_sku("FG-iherb-10421")
        assert result["source"] == "iherb"
        assert result["product_id"] == "10421"

    def test_thrive_market(self):
        result = parse_fg_sku("FG-thrive-market-thorne-vitamin-d-5-000")
        assert result["source"] == "thrive-market"
        assert result["product_id"] == "thorne-vitamin-d-5-000"

    def test_amazon(self):
        result = parse_fg_sku("FG-amazon-b0002wrqy4")
        assert result["source"] == "amazon"
        assert result["product_id"] == "b0002wrqy4"

    def test_walmart(self):
        result = parse_fg_sku("FG-walmart-8053802024")
        assert result["source"] == "walmart"
        assert result["product_id"] == "8053802024"

    def test_target(self):
        result = parse_fg_sku("FG-target-a-10996455")
        assert result["source"] == "target"
        assert result["product_id"] == "a-10996455"

    def test_cvs(self):
        result = parse_fg_sku("FG-cvs-704167")
        assert result["source"] == "cvs"
        assert result["product_id"] == "704167"

    def test_walgreens(self):
        result = parse_fg_sku("FG-walgreens-prod6083374")
        assert result["source"] == "walgreens"
        assert result["product_id"] == "prod6083374"

    def test_costco(self):
        result = parse_fg_sku("FG-costco-11467951")
        assert result["source"] == "costco"
        assert result["product_id"] == "11467951"

    def test_vitacost(self):
        result = parse_fg_sku("FG-vitacost-vitacost-magnesium")
        assert result["source"] == "vitacost"
        assert result["product_id"] == "vitacost-magnesium"

    def test_sams_club(self):
        result = parse_fg_sku("FG-sams-club-prod15990273")
        assert result["source"] == "sams-club"
        assert result["product_id"] == "prod15990273"

    def test_gnc(self):
        result = parse_fg_sku("FG-gnc-145223")
        assert result["source"] == "gnc"
        assert result["product_id"] == "145223"

    def test_the_vitamin_shoppe(self):
        result = parse_fg_sku("FG-the-vitamin-shoppe-vs-2750")
        assert result["source"] == "the-vitamin-shoppe"
        assert result["product_id"] == "vs-2750"


class TestBuildSearchQuery:
    def test_builds_query_from_sku_and_company(self):
        query = build_search_query("FG-iherb-10421", "NOW Foods")
        assert "NOW Foods" in query
        assert "iherb" in query
        assert "10421" in query
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sku_parser.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement SKU parser**

Create `src/scraper/sku_parser.py`:

```python
import re

KNOWN_SOURCES = [
    "thrive-market",
    "the-vitamin-shoppe",
    "sams-club",
    "iherb",
    "amazon",
    "walmart",
    "target",
    "cvs",
    "walgreens",
    "costco",
    "vitacost",
    "gnc",
]

# Sort by length descending so "thrive-market" matches before "thrive"
KNOWN_SOURCES.sort(key=len, reverse=True)


def parse_fg_sku(sku):
    if not sku.startswith("FG-"):
        return {"source": "unknown", "product_id": sku}

    remainder = sku[3:]  # strip "FG-"

    for source in KNOWN_SOURCES:
        if remainder.startswith(source + "-"):
            product_id = remainder[len(source) + 1:]
            return {"source": source, "product_id": product_id}

    parts = remainder.split("-", 1)
    return {"source": parts[0], "product_id": parts[1] if len(parts) > 1 else ""}


def build_search_query(sku, company_name):
    parsed = parse_fg_sku(sku)
    return f"{company_name} supplement {parsed['source']} {parsed['product_id']}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sku_parser.py -v`
Expected: All 13 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/scraper/sku_parser.py tests/test_sku_parser.py
git commit -m "feat: add SKU parser for retail source URL construction"
```

---

### Task 6: Product Page Scraper

**Files:**
- Create: `src/scraper/scrape.py`
- Create: `src/scraper/upload_to_s3.py`

- [ ] **Step 1: Implement scraper**

Create `src/scraper/scrape.py`:

```python
import os
import json
import time
import httpx
from bs4 import BeautifulSoup
from src.scraper.sku_parser import parse_fg_sku
from src.common.bedrock import invoke_model, invoke_model_json

SCRAPED_DIR = "data/scraped"


def scrape_product_page(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    response = httpx.get(url, headers=headers, follow_redirects=True, timeout=15)
    response.raise_for_status()
    return response.text


def extract_with_llm(html, sku, company_name):
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)[:8000]

    prompt = f"""Extract supplement product information from this webpage text.
Product: {company_name} (SKU: {sku})

Webpage text:
{text}

Return a JSON object with these fields:
- "product_name": string
- "supplement_facts": list of {{"ingredient": string, "amount": string, "daily_value_pct": string or null}}
- "certifications": list of strings (e.g., "NSF Certified", "Non-GMO Project Verified", "USDA Organic")
- "allergen_warnings": list of strings
- "claims": list of strings (e.g., "gluten-free", "vegan", "no artificial colors")

If a field cannot be determined, use an empty list or "unknown"."""

    return invoke_model_json(prompt)


def scrape_and_extract(sku, company_name):
    parsed = parse_fg_sku(sku)
    source = parsed["source"]
    product_id = parsed["product_id"]

    search_query = f"{company_name} {source} {product_id} supplement facts"

    prompt = f"""I need to find the product page for this supplement:
Company: {company_name}
Retail source: {source}
Product identifier: {product_id}

This is a dietary supplement sold on {source}. Based on the identifier, what would the likely product page URL be?
Return ONLY the URL, nothing else."""

    url = invoke_model(prompt).strip()

    try:
        html = scrape_product_page(url)
        extracted = extract_with_llm(html, sku, company_name)
    except Exception:
        extracted = {
            "product_name": "unknown",
            "supplement_facts": [],
            "certifications": [],
            "allergen_warnings": [],
            "claims": [],
            "error": f"Could not scrape {url}",
        }

    result = {"sku": sku, "company": company_name, "source": source, "url": url, **extracted}

    os.makedirs(SCRAPED_DIR, exist_ok=True)
    safe_sku = sku.replace("/", "_")
    with open(f"{SCRAPED_DIR}/{safe_sku}.json", "w") as f:
        json.dump(result, f, indent=2)

    return result


def scrape_all_products(db_path=None):
    from src.common.db import get_finished_goods
    products = get_finished_goods(db_path)
    results = []
    for p in products:
        print(f"Scraping {p['sku']} ({p['company_name']})...")
        result = scrape_and_extract(p["sku"], p["company_name"])
        results.append(result)
        time.sleep(1)
    return results
```

- [ ] **Step 2: Implement S3 uploader**

Create `src/scraper/upload_to_s3.py`:

```python
import os
import boto3

SCRAPED_DIR = "data/scraped"


def upload_scraped_to_s3(bucket_name=None, prefix="scraped-products"):
    bucket = bucket_name or os.environ.get("S3_BUCKET_NAME", "agnes-hackathon-kb")
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))

    count = 0
    for filename in os.listdir(SCRAPED_DIR):
        if not filename.endswith(".json"):
            continue
        local_path = os.path.join(SCRAPED_DIR, filename)
        s3_key = f"{prefix}/{filename}"
        s3.upload_file(local_path, bucket, s3_key)
        count += 1

    print(f"Uploaded {count} files to s3://{bucket}/{prefix}/")
    return count


if __name__ == "__main__":
    upload_scraped_to_s3()
```

- [ ] **Step 3: Commit**

```bash
git add src/scraper/scrape.py src/scraper/upload_to_s3.py
git commit -m "feat: add product page scraper and S3 uploader"
```

---

### Task 7: Ingredient Normalization (Stage 2)

**Files:**
- Create: `src/normalize/group_ingredients.py`

- [ ] **Step 1: Implement ingredient grouping**

Create `src/normalize/group_ingredients.py`:

```python
import json
from src.common.db import get_all_ingredient_names, save_ingredient_groups
from src.common.bedrock import invoke_model_json

BATCH_SIZE = 50


def build_grouping_prompt(ingredient_names):
    names_str = "\n".join(f"- {name}" for name in ingredient_names)

    return f"""You are an expert in dietary supplement formulation and nutraceutical chemistry.

Given this list of raw material ingredient names from supplement bill-of-materials data, group them into functional equivalence classes.

RULES:
1. Group ingredients that serve the SAME FUNCTIONAL ROLE in a supplement formulation.
2. "Same chemical entity, different name" = high confidence (e.g., "vitamin-d3-cholecalciferol" and "cholecalciferol-vitamin-d3")
3. "Same functional role, different chemical form" = medium confidence (e.g., "magnesium-citrate" and "magnesium-glycinate" both serve as bioavailable magnesium sources)
4. Do NOT group ingredients that share a word but serve different functions (e.g., "magnesium-stearate" is a flow agent/lubricant, NOT a magnesium source — do not group it with magnesium-citrate)
5. Ingredients with no functional equivalents in this list should be in their own single-member group.

INGREDIENT LIST:
{names_str}

Return a JSON array of objects, each with:
- "canonical_name": human-readable group name (e.g., "Vitamin D3")
- "function": what this group does in a supplement (e.g., "vitamin D source", "flow agent", "protein source")
- "members": array of ingredient name strings from the list above that belong to this group
- "confidence": "high" if all members are the same chemical entity, "medium" if functionally equivalent but different forms, "low" if grouping is uncertain
- "reasoning": one sentence explaining why these are grouped

Every ingredient from the list must appear in exactly one group."""


def group_all_ingredients(db_path=None):
    all_names = get_all_ingredient_names(db_path)
    all_groups = []

    for i in range(0, len(all_names), BATCH_SIZE):
        batch = all_names[i : i + BATCH_SIZE]
        prompt = build_grouping_prompt(batch)
        system = "You are a nutraceutical chemistry expert. Return valid JSON only."
        groups = invoke_model_json(prompt, system=system)
        all_groups.extend(groups)

    save_ingredient_groups(db_path, all_groups)
    print(f"Saved {len(all_groups)} ingredient groups from {len(all_names)} ingredients")
    return all_groups


if __name__ == "__main__":
    group_all_ingredients()
```

- [ ] **Step 2: Commit**

```bash
git add src/normalize/group_ingredients.py
git commit -m "feat: add LLM-based ingredient normalization"
```

---

### Task 8: Substitution Candidate Generation (Stage 3)

**Files:**
- Create: `src/substitute/find_candidates.py`
- Create: `tests/test_find_candidates.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_find_candidates.py`:

```python
import json
import sqlite3
from src.substitute.find_candidates import find_candidates_for_product


def _make_test_db(path):
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE Company (Id INTEGER PRIMARY KEY, Name TEXT NOT NULL);
        CREATE TABLE Product (
            Id INTEGER PRIMARY KEY, SKU TEXT NOT NULL,
            CompanyId INTEGER NOT NULL, Type TEXT NOT NULL
        );
        CREATE TABLE BOM (
            Id INTEGER PRIMARY KEY, ProducedProductId INTEGER NOT NULL UNIQUE
        );
        CREATE TABLE BOM_Component (
            BOMId INTEGER NOT NULL, ConsumedProductId INTEGER NOT NULL,
            PRIMARY KEY (BOMId, ConsumedProductId)
        );
        CREATE TABLE Supplier (Id INTEGER PRIMARY KEY, Name TEXT NOT NULL);
        CREATE TABLE Supplier_Product (
            SupplierId INTEGER NOT NULL, ProductId INTEGER NOT NULL,
            PRIMARY KEY (SupplierId, ProductId)
        );
        CREATE TABLE Ingredient_Group (
            id INTEGER PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            function TEXT NOT NULL,
            members TEXT NOT NULL,
            confidence TEXT,
            reasoning TEXT
        );

        INSERT INTO Company VALUES (1, 'CompA'), (2, 'CompB');
        INSERT INTO Product VALUES
            (1, 'FG-iherb-001', 1, 'finished-good'),
            (2, 'RM-C1-magnesium-citrate-aaa11111', 1, 'raw-material'),
            (3, 'RM-C2-magnesium-glycinate-bbb22222', 2, 'raw-material'),
            (4, 'RM-C1-vitamin-c-ccc33333', 1, 'raw-material');
        INSERT INTO BOM VALUES (1, 1);
        INSERT INTO BOM_Component VALUES (1, 2), (1, 4);
        INSERT INTO Supplier VALUES (1, 'SupA'), (2, 'SupB');
        INSERT INTO Supplier_Product VALUES (1, 2), (2, 3), (1, 4);

        INSERT INTO Ingredient_Group VALUES
            (1, 'Magnesium Source', 'bioavailable magnesium',
             '["magnesium-citrate", "magnesium-glycinate"]', 'medium', 'Both Mg sources'),
            (2, 'Vitamin C', 'vitamin C source',
             '["vitamin-c"]', 'high', 'Single member');
    """)
    conn.commit()
    return conn


class TestFindCandidates:
    def test_finds_substitutes_in_same_group(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _make_test_db(db_path)
        results = find_candidates_for_product(db_path, product_id=1)
        mg_result = [r for r in results if r["original_ingredient"] == "magnesium-citrate"][0]
        candidate_names = [c["ingredient_name"] for c in mg_result["candidates"]]
        assert "magnesium-glycinate" in candidate_names

    def test_no_candidates_for_single_member_group(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _make_test_db(db_path)
        results = find_candidates_for_product(db_path, product_id=1)
        vc_result = [r for r in results if r["original_ingredient"] == "vitamin-c"][0]
        assert len(vc_result["candidates"]) == 0

    def test_includes_supplier_info(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _make_test_db(db_path)
        results = find_candidates_for_product(db_path, product_id=1)
        mg_result = [r for r in results if r["original_ingredient"] == "magnesium-citrate"][0]
        mg_glyc = [c for c in mg_result["candidates"] if c["ingredient_name"] == "magnesium-glycinate"][0]
        assert "SupB" in mg_glyc["suppliers"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_find_candidates.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement candidate finder**

Create `src/substitute/find_candidates.py`:

```python
import json
from src.common.db import (
    get_connection,
    get_bom_components,
    get_suppliers_for_product,
    parse_ingredient_name,
    get_ingredient_group_for,
)


def find_candidates_for_product(db_path=None, product_id=None):
    components = get_bom_components(db_path, product_id=product_id)
    results = []

    for comp in components:
        ingredient_name = parse_ingredient_name(comp["sku"])
        group = get_ingredient_group_for(db_path, ingredient_name)

        candidates = []
        if group and len(group["members"]) > 1:
            other_members = [m for m in group["members"] if m != ingredient_name]
            candidate_products = _find_products_for_ingredients(db_path, other_members)

            for cp in candidate_products:
                suppliers = get_suppliers_for_product(db_path, product_id=cp["product_id"])
                candidates.append({
                    "ingredient_name": cp["ingredient_name"],
                    "product_id": cp["product_id"],
                    "sku": cp["sku"],
                    "company": cp["company_name"],
                    "suppliers": suppliers,
                })

        current_suppliers = get_suppliers_for_product(db_path, product_id=comp["product_id"])

        results.append({
            "original_ingredient": ingredient_name,
            "original_product_id": comp["product_id"],
            "original_sku": comp["sku"],
            "current_suppliers": current_suppliers,
            "group": {
                "canonical_name": group["canonical_name"] if group else ingredient_name,
                "function": group["function"] if group else "unknown",
                "confidence": group["confidence"] if group else "low",
            },
            "candidates": candidates,
        })

    return results


def _find_products_for_ingredients(db_path, ingredient_names):
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT p.Id as product_id, p.SKU as sku, p.CompanyId, c.Name as company_name
        FROM Product p
        JOIN Company c ON p.CompanyId = c.Id
        WHERE p.Type = 'raw-material'
    """).fetchall()
    conn.close()

    results = []
    seen = set()
    for r in rows:
        name = parse_ingredient_name(r["sku"])
        if name in ingredient_names and name not in seen:
            seen.add(name)
            results.append({
                "product_id": r["product_id"],
                "sku": r["sku"],
                "ingredient_name": name,
                "company_name": r["company_name"],
            })
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_find_candidates.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/substitute/find_candidates.py tests/test_find_candidates.py
git commit -m "feat: add substitution candidate generation with tests"
```

---

### Task 9: Compliance Evaluation (Stage 4)

**Files:**
- Create: `src/compliance/evaluate.py`

- [ ] **Step 1: Implement compliance evaluator**

Create `src/compliance/evaluate.py`:

```python
import json
from src.common.bedrock import invoke_model_json
from src.common.knowledge_base import retrieve


def evaluate_substitution(original, substitute, product_sku, company_name):
    kb_product_context = retrieve(f"{company_name} {product_sku} supplement facts certifications claims")
    kb_fda_context = retrieve(f"FDA dietary supplement labeling requirements {original['group']['canonical_name']}")

    product_evidence = "\n".join(
        f"[Source: {r['source']}]\n{r['text']}" for r in kb_product_context
    )
    fda_evidence = "\n".join(
        f"[Source: {r['source']}]\n{r['text']}" for r in kb_fda_context
    )

    prompt = f"""You are an FDA dietary supplement compliance expert evaluating whether an ingredient substitution is safe and compliant.

PRODUCT: {company_name} — {product_sku}
ORIGINAL INGREDIENT: {original['original_ingredient']} (function: {original['group']['function']})
PROPOSED SUBSTITUTE: {substitute['ingredient_name']}

PRODUCT INFORMATION FROM KNOWLEDGE BASE:
{product_evidence if product_evidence.strip() else "No product information available in knowledge base."}

FDA REGULATORY CONTEXT FROM KNOWLEDGE BASE:
{fda_evidence if fda_evidence.strip() else "No specific FDA guidance found in knowledge base."}

EVALUATE THIS SUBSTITUTION:
1. Does the substitute serve the same functional role?
2. Are there FDA labeling implications (name change on supplement facts panel)?
3. Does it conflict with any product claims (organic, non-GMO, allergen-free, etc.)?
4. Are there allergen implications?
5. Are there bioavailability or efficacy differences?

IMPORTANT:
- Only state facts you can support with the evidence above.
- If evidence is missing, say "insufficient evidence" for that aspect.
- Never guess about compliance — flag uncertainty explicitly.

Return a JSON object:
{{
    "original": "{original['original_ingredient']}",
    "substitute": "{substitute['ingredient_name']}",
    "verdict": "safe" | "risky" | "incompatible" | "insufficient-evidence",
    "confidence": "high" | "medium" | "low",
    "facts": ["list of facts from scraped product data"],
    "rules": ["list of applicable FDA rules"],
    "inference": "your reasoning connecting facts to rules",
    "sources": ["list of source URLs/references used"],
    "caveats": ["list of limitations or uncertainties"]
}}"""

    system = "You are an FDA compliance expert. Return valid JSON only. Never fabricate evidence."

    result = invoke_model_json(prompt, system=system)

    if isinstance(result, dict):
        source_list = [r["source"] for r in kb_product_context + kb_fda_context]
        result["kb_sources"] = source_list
    return result


def evaluate_all_candidates(candidates, product_sku, company_name):
    evaluations = []
    for component in candidates:
        component_evals = []
        for substitute in component["candidates"]:
            evaluation = evaluate_substitution(
                original=component,
                substitute=substitute,
                product_sku=product_sku,
                company_name=company_name,
            )
            component_evals.append(evaluation)
        evaluations.append({
            "original_ingredient": component["original_ingredient"],
            "group": component["group"],
            "current_suppliers": component["current_suppliers"],
            "evaluations": component_evals,
        })
    return evaluations
```

- [ ] **Step 2: Commit**

```bash
git add src/compliance/evaluate.py
git commit -m "feat: add compliance evaluation with KB-grounded reasoning"
```

---

### Task 10: Recommendation Ranking (Stage 5)

**Files:**
- Create: `src/recommend/rank.py`
- Create: `tests/test_rank.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_rank.py`:

```python
from src.recommend.rank import rank_evaluations

SAMPLE_EVALUATIONS = [
    {
        "original_ingredient": "magnesium-oxide",
        "group": {"canonical_name": "Magnesium Source", "function": "Mg source", "confidence": "medium"},
        "current_suppliers": ["SupA"],
        "evaluations": [
            {
                "original": "magnesium-oxide",
                "substitute": "magnesium-citrate",
                "verdict": "safe",
                "confidence": "medium",
                "facts": ["Product claims 400mg Mg"],
                "rules": ["FDA labeling rule"],
                "inference": "Compatible",
                "sources": ["source1"],
                "caveats": [],
            },
            {
                "original": "magnesium-oxide",
                "substitute": "magnesium-stearate",
                "verdict": "incompatible",
                "confidence": "high",
                "facts": ["Different function"],
                "rules": [],
                "inference": "Not a Mg source",
                "sources": [],
                "caveats": [],
            },
        ],
    },
    {
        "original_ingredient": "vitamin-c",
        "group": {"canonical_name": "Vitamin C", "function": "vitamin C", "confidence": "high"},
        "current_suppliers": ["SupB"],
        "evaluations": [],
    },
]


class TestRankEvaluations:
    def test_safe_ranked_first(self):
        ranked = rank_evaluations(SAMPLE_EVALUATIONS)
        mg = [r for r in ranked if r["original_ingredient"] == "magnesium-oxide"][0]
        assert mg["ranked_substitutes"][0]["verdict"] == "safe"

    def test_incompatible_ranked_last(self):
        ranked = rank_evaluations(SAMPLE_EVALUATIONS)
        mg = [r for r in ranked if r["original_ingredient"] == "magnesium-oxide"][0]
        assert mg["ranked_substitutes"][-1]["verdict"] == "incompatible"

    def test_no_candidates_still_included(self):
        ranked = rank_evaluations(SAMPLE_EVALUATIONS)
        vc = [r for r in ranked if r["original_ingredient"] == "vitamin-c"][0]
        assert len(vc["ranked_substitutes"]) == 0
        assert vc["has_alternatives"] is False

    def test_has_alternatives_flag(self):
        ranked = rank_evaluations(SAMPLE_EVALUATIONS)
        mg = [r for r in ranked if r["original_ingredient"] == "magnesium-oxide"][0]
        assert mg["has_alternatives"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_rank.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement ranking**

Create `src/recommend/rank.py`:

```python
VERDICT_ORDER = {"safe": 0, "risky": 1, "insufficient-evidence": 2, "incompatible": 3}
CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}


def rank_evaluations(evaluations):
    ranked = []
    for component in evaluations:
        sorted_evals = sorted(
            component["evaluations"],
            key=lambda e: (
                VERDICT_ORDER.get(e.get("verdict", "incompatible"), 3),
                CONFIDENCE_ORDER.get(e.get("confidence", "low"), 2),
            ),
        )

        safe_count = sum(1 for e in sorted_evals if e.get("verdict") == "safe")
        risky_count = sum(1 for e in sorted_evals if e.get("verdict") == "risky")

        ranked.append({
            "original_ingredient": component["original_ingredient"],
            "group": component["group"],
            "current_suppliers": component["current_suppliers"],
            "ranked_substitutes": sorted_evals,
            "has_alternatives": len(sorted_evals) > 0,
            "safe_count": safe_count,
            "risky_count": risky_count,
            "total_candidates": len(sorted_evals),
        })

    ranked.sort(key=lambda r: (-r["safe_count"], -r["total_candidates"]))
    return ranked
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_rank.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/recommend/rank.py tests/test_rank.py
git commit -m "feat: add recommendation ranking with tests"
```

---

### Task 11: Streamlit UI — Product Selector & BOM View

**Files:**
- Modify: `streamlit_app.py`

- [ ] **Step 1: Implement product selector and BOM view**

Replace the contents of `streamlit_app.py`:

```python
import streamlit as st
from src.common.db import (
    get_finished_goods,
    get_bom_components,
    get_suppliers_for_product,
    parse_ingredient_name,
)

st.set_page_config(page_title="Agnes — Raw Material Superpowers", layout="wide")
st.title("Agnes — Raw Material Superpowers")
st.caption("AI-powered ingredient substitution & compliance analysis for supplements")

products = get_finished_goods()

product_options = {
    f"{p['company_name']} — {p['sku']}": p for p in products
}

selected_label = st.selectbox(
    "Select a finished good product",
    options=list(product_options.keys()),
)

if selected_label:
    product = product_options[selected_label]
    st.subheader(f"Bill of Materials — {product['company_name']}")

    components = get_bom_components(product_id=product["product_id"])

    bom_data = []
    for comp in components:
        ingredient = parse_ingredient_name(comp["sku"])
        suppliers = get_suppliers_for_product(product_id=comp["product_id"])
        bom_data.append({
            "Ingredient": ingredient,
            "SKU": comp["sku"],
            "Suppliers": ", ".join(suppliers) if suppliers else "None",
        })

    st.dataframe(bom_data, use_container_width=True)
```

- [ ] **Step 2: Verify it runs**

Run: `docker compose up --build -d && sleep 5`
Open: `http://localhost:8501`
Expected: Page shows product dropdown. Selecting a product shows its BOM ingredients and suppliers in a table.

Run: `docker compose down`

- [ ] **Step 3: Commit**

```bash
git add streamlit_app.py
git commit -m "feat: add product selector and BOM view to Streamlit UI"
```

---

### Task 12: Streamlit UI — Substitution Analysis Panel

**Files:**
- Modify: `streamlit_app.py`

- [ ] **Step 1: Add analysis trigger and substitution display**

Add the following code to the end of `streamlit_app.py` (after the BOM dataframe):

```python
    from src.substitute.find_candidates import find_candidates_for_product
    from src.compliance.evaluate import evaluate_all_candidates
    from src.recommend.rank import rank_evaluations

    st.divider()

    if st.button("Analyze Substitution Opportunities", type="primary"):
        with st.spinner("Finding substitution candidates..."):
            candidates = find_candidates_for_product(product_id=product["product_id"])

        if not any(c["candidates"] for c in candidates):
            st.info("No substitution candidates found for this product's ingredients.")
        else:
            with st.spinner("Evaluating compliance for each candidate..."):
                evaluations = evaluate_all_candidates(
                    candidates, product["sku"], product["company_name"]
                )

            ranked = rank_evaluations(evaluations)
            st.session_state["ranked_results"] = ranked

    if "ranked_results" in st.session_state:
        ranked = st.session_state["ranked_results"]

        st.subheader("Substitution Analysis")

        col_safe, col_risky, col_total = st.columns(3)
        total_safe = sum(r["safe_count"] for r in ranked)
        total_risky = sum(r["risky_count"] for r in ranked)
        total_candidates = sum(r["total_candidates"] for r in ranked)
        col_safe.metric("Safe Substitutions", total_safe)
        col_risky.metric("Risky Substitutions", total_risky)
        col_total.metric("Total Candidates Evaluated", total_candidates)

        for component in ranked:
            with st.expander(
                f"**{component['original_ingredient']}** "
                f"({component['group']['canonical_name']}) — "
                f"{component['safe_count']} safe, "
                f"{component['total_candidates']} total",
                expanded=component["safe_count"] > 0,
            ):
                st.caption(f"Function: {component['group']['function']}")
                st.caption(f"Current suppliers: {', '.join(component['current_suppliers'])}")

                if not component["ranked_substitutes"]:
                    st.info("No functional equivalents found.")
                    continue

                for sub in component["ranked_substitutes"]:
                    verdict = sub.get("verdict", "unknown")
                    color = {
                        "safe": "green",
                        "risky": "orange",
                        "incompatible": "red",
                        "insufficient-evidence": "gray",
                    }.get(verdict, "gray")

                    st.markdown(
                        f"**:{color}[{verdict.upper()}]** — "
                        f"**{sub.get('substitute', 'unknown')}** "
                        f"(confidence: {sub.get('confidence', 'unknown')})"
                    )

                    if sub.get("facts"):
                        st.markdown("**Facts:**")
                        for fact in sub["facts"]:
                            st.markdown(f"- {fact}")

                    if sub.get("rules"):
                        st.markdown("**FDA Rules:**")
                        for rule in sub["rules"]:
                            st.markdown(f"- {rule}")

                    if sub.get("inference"):
                        st.markdown(f"**Reasoning:** {sub['inference']}")

                    if sub.get("sources"):
                        st.markdown("**Sources:**")
                        for source in sub["sources"]:
                            st.markdown(f"- {source}")

                    if sub.get("caveats"):
                        st.warning("**Caveats:** " + "; ".join(sub["caveats"]))

                    st.divider()
```

- [ ] **Step 2: Verify the full UI renders**

Run: `docker compose up --build -d && sleep 5`
Open: `http://localhost:8501`
Expected: Product selector → BOM table → "Analyze" button → substitution results with evidence trails, verdicts, and confidence badges.

Note: The "Analyze" button requires valid AWS credentials and a populated Knowledge Base. Without those, it will show an error — that's expected at this stage.

Run: `docker compose down`

- [ ] **Step 3: Commit**

```bash
git add streamlit_app.py
git commit -m "feat: add substitution analysis panel with evidence trails"
```

---

### Task 13: Consolidation Summary Sidebar

**Files:**
- Modify: `streamlit_app.py`

- [ ] **Step 1: Add consolidation sidebar**

Add this code near the top of `streamlit_app.py`, right after the `st.caption(...)` line and before the product selector:

```python
from src.common.db import get_connection, parse_ingredient_name


def get_consolidation_opportunities():
    conn = get_connection()
    rows = conn.execute("""
        SELECT p.SKU, p.CompanyId, c.Name as company_name
        FROM Product p
        JOIN Company c ON p.CompanyId = c.Id
        WHERE p.Type = 'raw-material'
    """).fetchall()
    conn.close()

    ingredient_companies = {}
    for r in rows:
        name = parse_ingredient_name(r["SKU"])
        if name not in ingredient_companies:
            ingredient_companies[name] = set()
        ingredient_companies[name].add(r["company_name"])

    shared = {
        name: companies
        for name, companies in ingredient_companies.items()
        if len(companies) > 1
    }
    return dict(sorted(shared.items(), key=lambda x: -len(x[1])))


with st.sidebar:
    st.header("Consolidation Opportunities")
    st.caption("Ingredients used by multiple companies")
    opportunities = get_consolidation_opportunities()
    for ingredient, companies in list(opportunities.items())[:15]:
        st.markdown(f"**{ingredient}** — {len(companies)} companies")
        st.caption(", ".join(sorted(companies)[:5]) + ("..." if len(companies) > 5 else ""))
```

- [ ] **Step 2: Verify sidebar renders**

Run: `docker compose up --build -d && sleep 5`
Open: `http://localhost:8501`
Expected: Left sidebar shows top shared ingredients with company counts.

Run: `docker compose down`

- [ ] **Step 3: Commit**

```bash
git add streamlit_app.py
git commit -m "feat: add consolidation opportunities sidebar"
```

---

### Task 14: End-to-End Integration Test

**Files:**
- None new — this is a manual integration verification

- [ ] **Step 1: Create .env file with real credentials**

Copy `.env.example` to `.env` and fill in real AWS credentials, S3 bucket name, and Knowledge Base ID.

- [ ] **Step 2: Run the scraper on a small batch**

Run: `docker compose run app python -c "
from src.scraper.scrape import scrape_and_extract
result = scrape_and_extract('FG-iherb-10421', 'NOW Foods')
print(result)
"`
Expected: Prints extracted supplement facts for a NOW Foods product.

- [ ] **Step 3: Upload scraped data and sync KB**

Run: `docker compose run app python scripts/setup_kb.py`
Expected: Files uploaded to S3. Console prints next steps for KB creation if not yet created.

- [ ] **Step 4: Run ingredient normalization**

Run: `docker compose run app python -m src.normalize.group_ingredients`
Expected: Prints "Saved N ingredient groups from 357 ingredients".

- [ ] **Step 5: Run full pipeline through the UI**

Run: `docker compose up --build -d`
Open: `http://localhost:8501`
Steps:
1. Select a product from the dropdown
2. Verify BOM table shows ingredients and suppliers
3. Click "Analyze Substitution Opportunities"
4. Verify substitution results appear with verdicts, evidence, and sources
5. Check sidebar shows consolidation opportunities

- [ ] **Step 6: Commit any fixes**

```bash
git add -u
git commit -m "fix: integration fixes from end-to-end testing"
```
