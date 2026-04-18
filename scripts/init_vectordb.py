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
