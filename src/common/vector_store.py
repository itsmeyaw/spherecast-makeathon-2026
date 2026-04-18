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
        cur.close()
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
