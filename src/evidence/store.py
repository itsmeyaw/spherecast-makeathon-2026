from src.common.db import get_connection, now_iso


def replace_opportunity_evidence(db_path=None, opportunity_id=None, evidence_rows=None):
    conn = get_connection(db_path)
    conn.execute("DELETE FROM Evidence WHERE OpportunityId = ?", (opportunity_id,))
    for row in evidence_rows or []:
        conn.execute(
            """
            INSERT INTO Evidence (
                OpportunityId,
                OpportunityCandidateId,
                SourceType,
                SourceLabel,
                SourceUri,
                FactType,
                FactValue,
                QualityScore,
                Snippet,
                PayloadRef,
                CreatedAt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                opportunity_id,
                row.get("opportunity_candidate_id"),
                row["source_type"],
                row["source_label"],
                row.get("source_uri"),
                row["fact_type"],
                row["fact_value"],
                row.get("quality_score"),
                row.get("snippet"),
                row.get("payload_ref"),
                now_iso(),
            ),
        )
    conn.commit()
    conn.close()


def list_evidence_for_opportunity(db_path=None, opportunity_id=None):
    conn = get_connection(db_path)
    rows = conn.execute(
        """
        SELECT *
        FROM Evidence
        WHERE OpportunityId = ?
        ORDER BY OpportunityCandidateId, FactType, Id
        """,
        (opportunity_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
