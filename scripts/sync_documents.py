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
