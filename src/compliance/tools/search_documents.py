from src.common.vector_store import retrieve


def search_documents(query: str, n_results: int = 5) -> dict:
    """Search the pgvector document store for relevant content.

    Queries product labels, FDA guidance, and other ingested documents.
    Returns ranked text chunks with source metadata.
    """
    try:
        results = retrieve(query, n_results=n_results)
        return {
            "status": "ok",
            "data": [
                {
                    "text": r["text"],
                    "score": r["score"],
                    "source": r["source"],
                    "section_title": r["section_title"],
                }
                for r in results
            ],
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
