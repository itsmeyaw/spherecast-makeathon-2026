# pgvector RAG Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace AWS Bedrock Knowledge Base with pgvector on RDS PostgreSQL for hybrid RAG retrieval (vector + keyword search with RRF).

**Architecture:** Documents in S3 are downloaded, converted to text via markitdown, structurally extracted into sections by Claude Sonnet 4.6, chunked, embedded with Titan V2, and stored in RDS PostgreSQL with pgvector. Retrieval uses cosine similarity + tsvector full-text search merged via Reciprocal Rank Fusion.

**Tech Stack:** Python 3.12, psycopg2-binary, markitdown, boto3 (Bedrock for Titan V2 + Claude Sonnet 4.6), PostgreSQL 16 + pgvector on AWS RDS.

**Spec:** `docs/superpowers/specs/2026-04-18-pgvector-rag-migration-design.md`

---

### Task 1: Update dependencies and configuration

**Files:**
- Modify: `requirements.txt`
- Modify: `.env.example`

- [ ] **Step 1: Add new Python dependencies to requirements.txt**

```
streamlit
boto3
httpx
beautifulsoup4
lxml
psycopg2-binary
markitdown
```

- [ ] **Step 2: Update .env.example with pgvector config, remove KNOWLEDGE_BASE_ID**

```
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET_NAME=agnes-hackathon-kb
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250514
PGVECTOR_HOST=your-rds-endpoint.us-east-1.rds.amazonaws.com
PGVECTOR_PORT=5432
PGVECTOR_DB=agnes
PGVECTOR_USER=agnes_app
PGVECTOR_PASSWORD=your-password
S3_DOCUMENTS_PREFIX=documents/
EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
EXTRACTION_MODEL_ID=us.anthropic.claude-sonnet-4-6-v1
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt .env.example
git commit -m "chore: add pgvector dependencies and config vars"
```

---

### Task 2: Database connection helper

**Files:**
- Create: `src/common/vector_db.py`
- Create: `tests/test_vector_db.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vector_db.py
import os
import pytest
from unittest.mock import patch, MagicMock


class TestGetConnection:
    @patch("psycopg2.connect")
    def test_connects_with_env_vars(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        env = {
            "PGVECTOR_HOST": "test-host",
            "PGVECTOR_PORT": "5432",
            "PGVECTOR_DB": "testdb",
            "PGVECTOR_USER": "testuser",
            "PGVECTOR_PASSWORD": "testpass",
        }
        with patch.dict(os.environ, env):
            from src.common.vector_db import get_connection
            conn = get_connection()

        mock_connect.assert_called_once_with(
            host="test-host",
            port=5432,
            dbname="testdb",
            user="testuser",
            password="testpass",
        )
        assert conn is mock_conn

    @patch("psycopg2.connect")
    def test_uses_default_port(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        env = {
            "PGVECTOR_HOST": "test-host",
            "PGVECTOR_DB": "testdb",
            "PGVECTOR_USER": "testuser",
            "PGVECTOR_PASSWORD": "testpass",
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("PGVECTOR_PORT", None)
            from importlib import reload
            import src.common.vector_db as vdb
            reload(vdb)
            conn = vdb.get_connection()

        mock_connect.assert_called_once_with(
            host="test-host",
            port=5432,
            dbname="testdb",
            user="testuser",
            password="testpass",
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_vector_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.common.vector_db'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/common/vector_db.py
import os
import psycopg2


def get_connection():
    return psycopg2.connect(
        host=os.environ["PGVECTOR_HOST"],
        port=int(os.environ.get("PGVECTOR_PORT", "5432")),
        dbname=os.environ["PGVECTOR_DB"],
        user=os.environ["PGVECTOR_USER"],
        password=os.environ["PGVECTOR_PASSWORD"],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_vector_db.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/common/vector_db.py tests/test_vector_db.py
git commit -m "feat: add pgvector database connection helper"
```

---

### Task 3: Database initialization script

**Files:**
- Create: `scripts/init_vectordb.py`

- [ ] **Step 1: Write the init script**

```python
# scripts/init_vectordb.py
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common.vector_db import get_connection


def init_vectordb():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY,
            s3_key TEXT UNIQUE NOT NULL,
            s3_etag TEXT NOT NULL,
            filename TEXT NOT NULL,
            doc_type TEXT,
            extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id SERIAL PRIMARY KEY,
            document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            section_title TEXT,
            content TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            embedding vector(1024) NOT NULL,
            tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
            metadata JSONB DEFAULT '{}'
        );
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
            ON document_chunks USING hnsw (embedding vector_cosine_ops);
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS document_chunks_tsv_idx
            ON document_chunks USING gin (tsv);
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("Vector database initialized successfully.")


if __name__ == "__main__":
    init_vectordb()
```

- [ ] **Step 2: Commit**

```bash
git add scripts/init_vectordb.py
git commit -m "feat: add vectordb schema initialization script"
```

---

### Task 4: Titan V2 embedding wrapper

**Files:**
- Create: `src/common/embeddings.py`
- Create: `tests/test_embeddings.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_embeddings.py
import json
import os
import pytest
from unittest.mock import patch, MagicMock


class TestEmbedText:
    @patch("src.common.embeddings.get_bedrock_client")
    def test_returns_embedding_vector(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        fake_embedding = [0.1] * 1024
        response_body = json.dumps({"embedding": fake_embedding}).encode()
        mock_response = MagicMock()
        mock_response.read.return_value = response_body
        mock_client.invoke_model.return_value = {"body": mock_response}

        from src.common.embeddings import embed_text
        result = embed_text("test query")

        assert result == fake_embedding
        assert len(result) == 1024
        mock_client.invoke_model.assert_called_once()
        call_kwargs = mock_client.invoke_model.call_args[1]
        assert call_kwargs["modelId"] == "amazon.titan-embed-text-v2:0"
        body = json.loads(call_kwargs["body"])
        assert body["inputText"] == "test query"

    @patch("src.common.embeddings.get_bedrock_client")
    def test_uses_custom_model_id(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        fake_embedding = [0.2] * 1024
        response_body = json.dumps({"embedding": fake_embedding}).encode()
        mock_response = MagicMock()
        mock_response.read.return_value = response_body
        mock_client.invoke_model.return_value = {"body": mock_response}

        with patch.dict(os.environ, {"EMBEDDING_MODEL_ID": "custom-model"}):
            from importlib import reload
            import src.common.embeddings as emb
            reload(emb)
            result = emb.embed_text("test")

        call_kwargs = mock_client.invoke_model.call_args[1]
        assert call_kwargs["modelId"] == "custom-model"


class TestEmbedTexts:
    @patch("src.common.embeddings.embed_text")
    def test_embeds_multiple_texts(self, mock_embed):
        mock_embed.side_effect = [[0.1] * 1024, [0.2] * 1024]

        from src.common.embeddings import embed_texts
        results = embed_texts(["text1", "text2"])

        assert len(results) == 2
        assert mock_embed.call_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_embeddings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.common.embeddings'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/common/embeddings.py
import json
import os
from src.common.bedrock import get_bedrock_client


def embed_text(text, model_id=None):
    client = get_bedrock_client()
    model = model_id or os.environ.get("EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")

    response = client.invoke_model(
        modelId=model,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": text}),
    )
    result = json.loads(response["body"].read())
    return result["embedding"]


def embed_texts(texts, model_id=None):
    return [embed_text(text, model_id=model_id) for text in texts]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_embeddings.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/common/embeddings.py tests/test_embeddings.py
git commit -m "feat: add Titan V2 embedding wrapper"
```

---

### Task 5: Text chunking utility

**Files:**
- Create: `src/common/chunker.py`
- Create: `tests/test_chunker.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_chunker.py
from src.common.chunker import chunk_sections


class TestChunkSections:
    def test_short_section_stays_intact(self):
        sections = [{"section_title": "Intro", "content": "Short text."}]
        chunks = chunk_sections(sections, max_tokens=500, overlap_tokens=100)
        assert len(chunks) == 1
        assert chunks[0]["section_title"] == "Intro"
        assert chunks[0]["content"] == "Short text."
        assert chunks[0]["chunk_index"] == 0

    def test_long_section_is_split(self):
        long_text = "This is a sentence. " * 200
        sections = [{"section_title": "Long", "content": long_text}]
        chunks = chunk_sections(sections, max_tokens=100, overlap_tokens=20)
        assert len(chunks) > 1
        assert all(c["section_title"] == "Long" for c in chunks)
        for i, c in enumerate(chunks):
            assert c["chunk_index"] == i

    def test_multiple_sections(self):
        sections = [
            {"section_title": "A", "content": "First section."},
            {"section_title": "B", "content": "Second section."},
        ]
        chunks = chunk_sections(sections, max_tokens=500, overlap_tokens=100)
        assert len(chunks) == 2
        assert chunks[0]["section_title"] == "A"
        assert chunks[0]["chunk_index"] == 0
        assert chunks[1]["section_title"] == "B"
        assert chunks[1]["chunk_index"] == 0

    def test_chunk_overlap_contains_shared_text(self):
        sentences = [f"Sentence number {i} is here." for i in range(50)]
        long_text = " ".join(sentences)
        sections = [{"section_title": "Overlap", "content": long_text}]
        chunks = chunk_sections(sections, max_tokens=50, overlap_tokens=15)
        if len(chunks) >= 2:
            first_end_words = set(chunks[0]["content"].split()[-10:])
            second_start_words = set(chunks[1]["content"].split()[:10])
            assert len(first_end_words & second_start_words) > 0

    def test_empty_sections_skipped(self):
        sections = [
            {"section_title": "Empty", "content": ""},
            {"section_title": "Full", "content": "Has content."},
        ]
        chunks = chunk_sections(sections, max_tokens=500, overlap_tokens=100)
        assert len(chunks) == 1
        assert chunks[0]["section_title"] == "Full"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_chunker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.common.chunker'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/common/chunker.py

def _estimate_tokens(text):
    return len(text.split())


def _split_into_sentences(text):
    sentences = []
    current = []
    for char in text:
        current.append(char)
        if char in ".!?" and len(current) > 1:
            sentences.append("".join(current).strip())
            current = []
    remainder = "".join(current).strip()
    if remainder:
        sentences.append(remainder)
    return sentences


def chunk_sections(sections, max_tokens=500, overlap_tokens=100):
    chunks = []
    for section in sections:
        content = section["content"].strip()
        if not content:
            continue

        title = section["section_title"]

        if _estimate_tokens(content) <= max_tokens:
            chunks.append({
                "section_title": title,
                "content": content,
                "chunk_index": 0,
            })
            continue

        sentences = _split_into_sentences(content)
        current_chunk = []
        current_tokens = 0
        chunk_index = 0

        for sentence in sentences:
            sentence_tokens = _estimate_tokens(sentence)
            if current_tokens + sentence_tokens > max_tokens and current_chunk:
                chunks.append({
                    "section_title": title,
                    "content": " ".join(current_chunk),
                    "chunk_index": chunk_index,
                })
                chunk_index += 1

                overlap_chunk = []
                overlap_count = 0
                for s in reversed(current_chunk):
                    s_tokens = _estimate_tokens(s)
                    if overlap_count + s_tokens > overlap_tokens:
                        break
                    overlap_chunk.insert(0, s)
                    overlap_count += s_tokens

                current_chunk = overlap_chunk
                current_tokens = overlap_count

            current_chunk.append(sentence)
            current_tokens += sentence_tokens

        if current_chunk:
            chunks.append({
                "section_title": title,
                "content": " ".join(current_chunk),
                "chunk_index": chunk_index,
            })

    return chunks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_chunker.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/common/chunker.py tests/test_chunker.py
git commit -m "feat: add text chunking utility with sentence-boundary splitting"
```

---

### Task 6: Hybrid retrieval (vector_store.py)

**Files:**
- Create: `src/common/vector_store.py`
- Create: `tests/test_vector_store.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_vector_store.py
import pytest
from unittest.mock import patch, MagicMock


class TestRetrieve:
    @patch("src.common.vector_store.get_connection")
    @patch("src.common.vector_store.embed_text")
    def test_returns_merged_results(self, mock_embed, mock_get_conn):
        mock_embed.return_value = [0.1] * 1024

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_get_conn.return_value = mock_conn

        # Vector search returns 2 results
        mock_cur.fetchall.side_effect = [
            [
                (1, "chunk A content", "s3-key-a", "Section A", "{}"),
                (2, "chunk B content", "s3-key-b", "Section B", "{}"),
            ],
            # Keyword search returns 2 results (one overlapping)
            [
                (2, "chunk B content", "s3-key-b", "Section B", "{}"),
                (3, "chunk C content", "s3-key-c", "Section C", "{}"),
            ],
        ]

        from src.common.vector_store import retrieve
        results = retrieve("test query", n_results=3)

        assert len(results) <= 3
        assert all("text" in r for r in results)
        assert all("score" in r for r in results)
        assert all("source" in r for r in results)
        assert all("section_title" in r for r in results)
        mock_conn.close.assert_called_once()

    @patch("src.common.vector_store.get_connection")
    @patch("src.common.vector_store.embed_text")
    def test_empty_results(self, mock_embed, mock_get_conn):
        mock_embed.return_value = [0.1] * 1024

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_get_conn.return_value = mock_conn
        mock_cur.fetchall.side_effect = [[], []]

        from src.common.vector_store import retrieve
        results = retrieve("query with no results")

        assert results == []
        mock_conn.close.assert_called_once()

    @patch("src.common.vector_store.get_connection")
    @patch("src.common.vector_store.embed_text")
    def test_rrf_ranks_items_in_both_searches_higher(self, mock_embed, mock_get_conn):
        mock_embed.return_value = [0.1] * 1024

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_get_conn.return_value = mock_conn

        # Chunk 2 appears in both searches — should rank highest
        mock_cur.fetchall.side_effect = [
            [
                (1, "only in vector", "key-a", "Sec A", "{}"),
                (2, "in both searches", "key-b", "Sec B", "{}"),
            ],
            [
                (2, "in both searches", "key-b", "Sec B", "{}"),
                (3, "only in keyword", "key-c", "Sec C", "{}"),
            ],
        ]

        from src.common.vector_store import retrieve
        results = retrieve("test", n_results=3)

        assert results[0]["text"] == "in both searches"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_vector_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.common.vector_store'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/common/vector_store.py
from src.common.vector_db import get_connection
from src.common.embeddings import embed_text

RRF_K = 60


def retrieve(query, n_results=5, keyword_weight=0.4):
    embedding = embed_text(query)
    conn = get_connection()
    cur = conn.cursor()

    try:
        embedding_literal = "[" + ",".join(str(x) for x in embedding) + "]"

        cur.execute(
            """
            SELECT dc.id, dc.content, d.s3_key, dc.section_title, dc.metadata::text
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            ORDER BY dc.embedding <=> %s::vector
            LIMIT 20
            """,
            (embedding_literal,),
        )
        vector_results = cur.fetchall()

        cur.execute(
            """
            SELECT dc.id, dc.content, d.s3_key, dc.section_title, dc.metadata::text
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.tsv @@ websearch_to_tsquery('english', %s)
            ORDER BY ts_rank(dc.tsv, websearch_to_tsquery('english', %s)) DESC
            LIMIT 20
            """,
            (query, query),
        )
        keyword_results = cur.fetchall()

    finally:
        conn.close()

    vector_ranks = {row[0]: rank for rank, row in enumerate(vector_results)}
    keyword_ranks = {row[0]: rank for rank, row in enumerate(keyword_results)}

    all_ids = set(vector_ranks.keys()) | set(keyword_ranks.keys())
    rows_by_id = {}
    for row in vector_results + keyword_results:
        rows_by_id[row[0]] = row

    scored = []
    for chunk_id in all_ids:
        v_rank = vector_ranks.get(chunk_id, 1000)
        k_rank = keyword_ranks.get(chunk_id, 1000)
        score = (1 - keyword_weight) / (RRF_K + v_rank) + keyword_weight / (RRF_K + k_rank)
        row = rows_by_id[chunk_id]
        scored.append({
            "text": row[1],
            "score": round(score, 6),
            "source": row[2],
            "section_title": row[3],
            "metadata": row[4],
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:n_results]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_vector_store.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/common/vector_store.py tests/test_vector_store.py
git commit -m "feat: add hybrid retrieval with vector + keyword RRF search"
```

---

### Task 7: Document sync script

**Files:**
- Create: `scripts/sync_documents.py`
- Create: `tests/test_sync_documents.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sync_documents.py
import json
import pytest
from unittest.mock import patch, MagicMock, call


class TestListNewS3Objects:
    @patch("scripts.sync_documents.get_connection")
    def test_filters_out_already_ingested(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = [("documents/a.pdf", "etag-a")]
        mock_get_conn.return_value = mock_conn

        s3_objects = [
            {"Key": "documents/a.pdf", "ETag": '"etag-a"'},
            {"Key": "documents/b.pdf", "ETag": '"etag-b"'},
        ]

        from scripts.sync_documents import list_new_s3_objects
        new_objects = list_new_s3_objects(s3_objects, mock_conn)

        assert len(new_objects) == 1
        assert new_objects[0]["Key"] == "documents/b.pdf"

    @patch("scripts.sync_documents.get_connection")
    def test_detects_changed_etag(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = [("documents/a.pdf", "old-etag")]
        mock_get_conn.return_value = mock_conn

        s3_objects = [
            {"Key": "documents/a.pdf", "ETag": '"new-etag"'},
        ]

        from scripts.sync_documents import list_new_s3_objects
        new_objects = list_new_s3_objects(s3_objects, mock_conn)

        assert len(new_objects) == 1


class TestExtractSections:
    @patch("scripts.sync_documents.invoke_model_json")
    def test_returns_sections_from_claude(self, mock_invoke):
        mock_invoke.return_value = [
            {"section_title": "Overview", "content": "This is the overview."},
            {"section_title": "Details", "content": "These are the details."},
        ]

        from scripts.sync_documents import extract_sections
        sections = extract_sections("Some raw document text")

        assert len(sections) == 2
        assert sections[0]["section_title"] == "Overview"
        mock_invoke.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sync_documents.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.sync_documents'`

- [ ] **Step 3: Create scripts/__init__.py so tests can import from scripts**

```python
# scripts/__init__.py
```

(empty file)

- [ ] **Step 4: Write the sync script**

```python
# scripts/sync_documents.py
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import boto3
from markitdown import MarkItDown

from src.common.vector_db import get_connection
from src.common.bedrock import invoke_model_json
from src.common.embeddings import embed_texts
from src.common.chunker import chunk_sections


def get_s3_client():
    return boto3.client(
        "s3",
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )


def list_s3_objects(bucket, prefix):
    s3 = get_s3_client()
    objects = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if not obj["Key"].endswith("/"):
                objects.append(obj)
    return objects


def list_new_s3_objects(s3_objects, conn):
    cur = conn.cursor()
    cur.execute("SELECT s3_key, s3_etag FROM documents")
    existing = {row[0]: row[1] for row in cur.fetchall()}

    new_objects = []
    for obj in s3_objects:
        key = obj["Key"]
        etag = obj["ETag"].strip('"')
        if key not in existing or existing[key] != etag:
            new_objects.append(obj)
    return new_objects


def download_from_s3(bucket, key):
    s3 = get_s3_client()
    suffix = os.path.splitext(key)[1] or ".bin"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    s3.download_file(bucket, key, tmp.name)
    return tmp.name


def convert_to_text(file_path):
    md = MarkItDown()
    result = md.convert(file_path)
    return result.text_content


def extract_sections(raw_text):
    prompt = f"""Break the following document into logical sections. Return a JSON array where each element has:
- "section_title": a descriptive title for the section
- "content": the full text content of that section

Preserve all information from the original document. Do not summarize or omit content.

DOCUMENT:
{raw_text}

Return a JSON array only."""

    system = "You are a document structuring assistant. Return valid JSON only."

    model_id = os.environ.get("EXTRACTION_MODEL_ID", "us.anthropic.claude-sonnet-4-6-v1")
    return invoke_model_json(prompt, system=system, model_id=model_id)


def ingest_document(bucket, s3_obj, conn):
    key = s3_obj["Key"]
    etag = s3_obj["ETag"].strip('"')
    filename = os.path.basename(key)
    doc_type = os.path.splitext(filename)[1].lstrip(".") or None

    print(f"  Downloading {key}...")
    tmp_path = download_from_s3(bucket, key)

    try:
        print(f"  Converting to text...")
        raw_text = convert_to_text(tmp_path)

        print(f"  Extracting sections with Claude...")
        sections = extract_sections(raw_text)

        if not isinstance(sections, list):
            sections = [{"section_title": "Full Document", "content": raw_text}]

        print(f"  Chunking {len(sections)} sections...")
        chunks = chunk_sections(sections)

        print(f"  Embedding {len(chunks)} chunks...")
        texts = [c["content"] for c in chunks]
        embeddings = embed_texts(texts)

        cur = conn.cursor()

        cur.execute("DELETE FROM documents WHERE s3_key = %s", (key,))

        cur.execute(
            """
            INSERT INTO documents (s3_key, s3_etag, filename, doc_type)
            VALUES (%s, %s, %s, %s) RETURNING id
            """,
            (key, etag, filename, doc_type),
        )
        doc_id = cur.fetchone()[0]

        for chunk, embedding in zip(chunks, embeddings):
            embedding_literal = "[" + ",".join(str(x) for x in embedding) + "]"
            cur.execute(
                """
                INSERT INTO document_chunks (document_id, section_title, content, chunk_index, embedding, metadata)
                VALUES (%s, %s, %s, %s, %s::vector, %s::jsonb)
                """,
                (
                    doc_id,
                    chunk["section_title"],
                    chunk["content"],
                    chunk["chunk_index"],
                    embedding_literal,
                    json.dumps({}),
                ),
            )

        conn.commit()
        print(f"  Ingested {len(chunks)} chunks for {filename}")

    finally:
        os.unlink(tmp_path)


def sync():
    bucket = os.environ["S3_BUCKET_NAME"]
    prefix = os.environ.get("S3_DOCUMENTS_PREFIX", "documents/")

    print(f"Listing objects in s3://{bucket}/{prefix}...")
    s3_objects = list_s3_objects(bucket, prefix)
    print(f"Found {len(s3_objects)} objects in S3.")

    conn = get_connection()
    try:
        new_objects = list_new_s3_objects(s3_objects, conn)
        print(f"{len(new_objects)} new/changed documents to ingest.")

        for s3_obj in new_objects:
            print(f"\nProcessing {s3_obj['Key']}...")
            ingest_document(bucket, s3_obj, conn)

        print(f"\nSync complete. Ingested {len(new_objects)} documents.")
    finally:
        conn.close()


if __name__ == "__main__":
    sync()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_sync_documents.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add scripts/__init__.py scripts/sync_documents.py tests/test_sync_documents.py
git commit -m "feat: add S3 document sync script with structured extraction"
```

---

### Task 8: Wire up evaluate.py to new vector_store

**Files:**
- Modify: `src/compliance/evaluate.py`

- [ ] **Step 1: Update the import**

Change line 3 of `src/compliance/evaluate.py` from:

```python
from src.common.knowledge_base import retrieve
```

to:

```python
from src.common.vector_store import retrieve
```

- [ ] **Step 2: Verify no other code changes needed**

The `retrieve` function in `vector_store.py` returns dicts with `text`, `score`, and `source` keys — the same keys that `evaluate.py` reads on lines 10-15 and line 59. The `section_title` and `metadata` keys are extra but unused, which is fine.

Run: `python -c "from src.compliance.evaluate import evaluate_substitution; print('import OK')"`
Expected: `import OK` (no import errors)

- [ ] **Step 3: Commit**

```bash
git add src/compliance/evaluate.py
git commit -m "feat: switch compliance evaluation from Knowledge Base to pgvector"
```

---

### Task 9: Remove old Knowledge Base code

**Files:**
- Delete: `src/common/knowledge_base.py`
- Delete: `scripts/setup_kb.py`

- [ ] **Step 1: Verify no remaining imports of knowledge_base**

Run: `grep -r "knowledge_base" src/ scripts/ tests/ streamlit_app.py`
Expected: No matches (the only import was in `evaluate.py`, updated in Task 8)

- [ ] **Step 2: Delete the files**

```bash
rm src/common/knowledge_base.py scripts/setup_kb.py
```

- [ ] **Step 3: Commit**

```bash
git add -u src/common/knowledge_base.py scripts/setup_kb.py
git commit -m "chore: remove old Knowledge Base code"
```

---

### Task 10: Run full test suite

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests pass, including existing tests (`test_db.py`, `test_sku_parser.py`, `test_find_candidates.py`, `test_rank.py`) and new tests (`test_vector_db.py`, `test_embeddings.py`, `test_chunker.py`, `test_vector_store.py`, `test_sync_documents.py`).

- [ ] **Step 2: Fix any failures, re-run, commit if fixes needed**

---

### Task 11: End-to-end manual verification

- [ ] **Step 1: Ensure RDS instance is running with pgvector enabled**

Connect to your RDS instance and verify:
```sql
SELECT extversion FROM pg_extension WHERE extname = 'vector';
```
Expected: Returns a version like `0.8.0`

- [ ] **Step 2: Initialize the vector database**

```bash
python scripts/init_vectordb.py
```
Expected: `Vector database initialized successfully.`

- [ ] **Step 3: Upload test documents to S3**

Place at least one PDF/DOCX in your S3 bucket under the `documents/` prefix.

- [ ] **Step 4: Run the sync script**

```bash
python scripts/sync_documents.py
```
Expected: Documents downloaded, extracted, chunked, embedded, and stored. Output shows chunk counts per document.

- [ ] **Step 5: Test retrieval via Python REPL**

```python
from src.common.vector_store import retrieve
results = retrieve("FDA dietary supplement labeling requirements")
for r in results:
    print(f"[{r['score']:.4f}] {r['section_title']}: {r['text'][:100]}...")
```
Expected: Relevant results with scores, section titles, and source S3 keys.

- [ ] **Step 6: Start Streamlit and test compliance evaluation**

```bash
streamlit run streamlit_app.py
```

Select a product, trigger analysis, verify that compliance evaluations return results using the new pgvector retrieval (check that `kb_sources` in results contain S3 keys from the `documents/` prefix).
