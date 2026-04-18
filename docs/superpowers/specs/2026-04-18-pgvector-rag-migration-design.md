# Replace AWS Knowledge Base with pgvector RAG

**Date:** 2026-04-18
**Status:** Approved

## Problem

AWS Bedrock Knowledge Base (OpenSearch Serverless) is hard to set up and manage. We need a simpler vector store for RAG that still supports hybrid search over regulatory and product documents.

## Decision

Replace the Knowledge Base with PostgreSQL + pgvector on AWS RDS, using built-in `tsvector` for hybrid search via Reciprocal Rank Fusion (RRF). Documents are extracted from S3 using Claude Sonnet 4.6 for structured section extraction and Amazon Titan V2 for embeddings.

## Architecture Overview

```
S3 (documents/)
    ↓ [manual sync script]
Download → markitdown (text conversion) → Claude Sonnet 4.6 (structured extraction)
    ↓
Section chunking (~500 tokens, ~100 overlap)
    ↓
Titan V2 embedding (1024 dimensions)
    ↓
RDS PostgreSQL + pgvector
    ↓ [hybrid retrieval]
Vector similarity (cosine) + Full-text search (tsvector)
    ↓ [RRF merge]
Compliance evaluation (evaluate.py)
```

## Database Schema

RDS PostgreSQL instance: `db.t4g.micro` (2 vCPU, 1 GB RAM), region `us-east-1`.

### `documents` table

Tracks ingested files from S3.

```sql
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    s3_key TEXT UNIQUE NOT NULL,
    s3_etag TEXT NOT NULL,
    filename TEXT NOT NULL,
    doc_type TEXT,
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `document_chunks` table

Extracted sections, chunked, with vector and full-text search indexes.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    section_title TEXT,
    content TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    embedding vector(1024) NOT NULL,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX ON document_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON document_chunks USING gin (tsv);
```

### Design rationale

- `s3_etag` detects changed files without downloading them.
- `ON DELETE CASCADE` ensures re-ingesting a document cleans up old chunks automatically.
- HNSW index for fast approximate nearest neighbor vector search.
- GIN index for fast full-text keyword search.
- `tsvector` is a generated column — no manual maintenance needed.

## Ingestion Pipeline

Manual sync script at `scripts/sync_documents.py`.

### Flow

1. **List S3 objects** under the configured prefix (`S3_DOCUMENTS_PREFIX`).
2. **Compare** against `documents` table by `s3_key` + `s3_etag`. Skip already-ingested, unchanged files.
3. **For each new/changed file:**
   - Download from S3 to a temp file.
   - Convert to text using **markitdown** (handles PDF, DOCX, HTML, PPTX, etc.).
   - Send raw text to **Claude Sonnet 4.6** with a structured extraction prompt.
   - Claude returns: `[{"section_title": "...", "content": "..."}, ...]`
   - Chunk large sections (~500 tokens, ~100 token overlap). Short sections stay as-is.
   - Embed each chunk via **Titan V2** (`amazon.titan-embed-text-v2:0`, 1024 dimensions).
   - If re-ingesting: delete old `documents` row (cascades to chunks).
   - Insert new `documents` row + all `document_chunks`.

### Idempotency

Re-running the script is safe: unchanged files are skipped, changed files are fully re-ingested.

### Text extraction prompt (Claude Sonnet 4.6)

The prompt instructs Claude to break the document into titled sections with content, preserving the document's logical structure. Each section gets a descriptive title and the full text of that section.

### Chunking strategy

- Target: ~500 tokens per chunk.
- Overlap: ~100 tokens between consecutive chunks within the same section.
- Sections under ~500 tokens are stored as a single chunk.
- Chunk boundaries respect sentence boundaries where possible.

## Hybrid Retrieval API

New module `src/common/vector_store.py` replaces `src/common/knowledge_base.py`.

### Function signature

```python
def retrieve(query: str, n_results: int = 5, keyword_weight: float = 0.4) -> list[dict]:
```

### Returns

```python
[
    {
        "text": "chunk content",
        "score": 0.85,
        "source": "documents/fda-guidance.pdf",
        "section_title": "Labeling Requirements",
        "metadata": {}
    },
    ...
]
```

### Hybrid search strategy

Two parallel searches, merged with Reciprocal Rank Fusion (RRF):

1. **Vector search:** Embed query with Titan V2, cosine similarity against `embedding` column, top 20 candidates.
2. **Keyword search:** `websearch_to_tsquery('english', query)` against `tsv` column, `ts_rank` scoring, top 20 candidates.
3. **RRF merge:** `score = (1 - keyword_weight) / (k + vector_rank) + keyword_weight / (k + keyword_rank)`, where `k = 60`.
4. **Return** top `n_results` by fused score.

### Rationale

- `keyword_weight=0.4` — vector similarity is the primary signal; keywords boost exact regulatory term matches.
- RRF is rank-based, not score-based — handles the different scales of cosine similarity vs. ts_rank naturally.
- Two queries + Python merge is simpler and more debuggable than a single complex SQL query.

## Configuration

### New environment variables

```
PGVECTOR_HOST=your-rds-endpoint.us-east-1.rds.amazonaws.com
PGVECTOR_PORT=5432
PGVECTOR_DB=agnes
PGVECTOR_USER=agnes_app
PGVECTOR_PASSWORD=your-password
S3_DOCUMENTS_PREFIX=documents/
EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
EXTRACTION_MODEL_ID=us.anthropic.claude-sonnet-4-6-v1
```

### Removed environment variables

```
KNOWLEDGE_BASE_ID  (no longer needed)
```

## File Changes

### New files

| File | Purpose |
|------|---------|
| `src/common/vector_db.py` | Postgres connection helper (`get_connection()`) |
| `src/common/vector_store.py` | Hybrid retrieval API (`retrieve()`) |
| `src/common/embeddings.py` | Titan V2 embedding wrapper |
| `scripts/sync_documents.py` | S3 → extract → embed → store pipeline |
| `scripts/init_vectordb.py` | Creates tables and indexes in RDS |

### Modified files

| File | Change |
|------|--------|
| `src/compliance/evaluate.py` | Import `retrieve` from `vector_store` instead of `knowledge_base` |
| `.env.example` | Add pgvector vars, remove `KNOWLEDGE_BASE_ID` |
| `requirements.txt` | Add `psycopg2-binary`, `markitdown` |

### Removed files

| File | Reason |
|------|--------|
| `src/common/knowledge_base.py` | Replaced by `vector_store.py` |
| `scripts/setup_kb.py` | No longer needed |

## Dependencies

### New Python packages

- `psycopg2-binary` — PostgreSQL adapter
- `markitdown` — multi-format document-to-text conversion (PDF, DOCX, HTML, PPTX)

### AWS services

- **RDS PostgreSQL** (`db.t4g.micro`) with pgvector extension — vector store
- **Bedrock** `amazon.titan-embed-text-v2:0` — embeddings (1024 dimensions)
- **Bedrock** `us.anthropic.claude-sonnet-4-6-v1` — structured text extraction
- **S3** — document source (existing bucket, new prefix `documents/`)
