from collections import Counter

from src.common.db import (
    get_connection,
    init_workspace_schema,
    now_iso,
    seed_default_ingredient_aliases,
)


def _derived_status(blocker_state):
    return {
        "blocked": "blocked",
        "needs_review": "needs-review",
        "pass_known_blockers": "new",
    }[blocker_state]


def ensure_workspace_ready(db_path=None, force_rebuild=False):
    init_workspace_schema(db_path)
    seed_default_ingredient_aliases(db_path)

    conn = get_connection(db_path)
    count = conn.execute("SELECT COUNT(*) AS cnt FROM Opportunity").fetchone()["cnt"]
    conn.close()

    if force_rebuild or count == 0:
        from src.opportunity.build import build_all_opportunities

        build_all_opportunities(db_path=db_path)


def reset_workspace_analysis(db_path=None):
    conn = get_connection(db_path)
    conn.executescript(
        """
        DELETE FROM Evidence;
        DELETE FROM Opportunity_Candidate;
        DELETE FROM Review_Decision;
        DELETE FROM Requirement_Profile;
        DELETE FROM Opportunity;
        """
    )
    conn.commit()
    conn.close()


def upsert_requirement_profiles(db_path=None, product_id=None, component_product_id=None, requirements=None):
    conn = get_connection(db_path)
    conn.execute(
        "DELETE FROM Requirement_Profile WHERE ProductId = ? AND BomComponentProductId = ?",
        (product_id, component_product_id),
    )
    for requirement in requirements or []:
        conn.execute(
            """
            INSERT OR IGNORE INTO Requirement_Profile (
                ProductId,
                BomComponentProductId,
                RequirementType,
                RequirementValue,
                Source,
                Confidence
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                product_id,
                component_product_id,
                requirement["requirement_type"],
                requirement["requirement_value"],
                requirement["source"],
                requirement["confidence"],
            ),
        )
    conn.commit()
    conn.close()


def upsert_opportunity(db_path=None, payload=None):
    conn = get_connection(db_path)
    existing = conn.execute(
        """
        SELECT Id, Status
        FROM Opportunity
        WHERE ProductId = ? AND BomComponentProductId = ? AND OpportunityType = ? AND MatchType = ?
        """,
        (
            payload["product_id"],
            payload["component_product_id"],
            payload["opportunity_type"],
            payload["match_type"],
        ),
    ).fetchone()

    now = now_iso()
    status = _derived_status(payload["blocker_state"])
    if existing and existing["Status"] in {"approved", "rejected", "triaged"}:
        status = existing["Status"]

    if existing:
        conn.execute(
            """
            UPDATE Opportunity
            SET CompanyId = ?,
                BomId = ?,
                ParsedIngredientName = ?,
                CanonicalIngredientName = ?,
                Status = ?,
                ConfidenceLabel = ?,
                ProductsAffectedCount = ?,
                SuppliersAffectedCount = ?,
                CandidateCount = ?,
                EvidenceCompleteness = ?,
                BlockerState = ?,
                Summary = ?,
                PriorityScore = ?,
                UpdatedAt = ?
            WHERE Id = ?
            """,
            (
                payload["company_id"],
                payload.get("bom_id"),
                payload["parsed_ingredient_name"],
                payload["canonical_ingredient_name"],
                status,
                payload["confidence_label"],
                payload["products_affected_count"],
                payload["suppliers_affected_count"],
                payload["candidate_count"],
                payload["evidence_completeness"],
                payload["blocker_state"],
                payload["summary"],
                payload["priority_score"],
                now,
                existing["Id"],
            ),
        )
        opportunity_id = existing["Id"]
    else:
        conn.execute(
            """
            INSERT INTO Opportunity (
                CompanyId,
                ProductId,
                BomId,
                BomComponentProductId,
                ParsedIngredientName,
                CanonicalIngredientName,
                OpportunityType,
                MatchType,
                Status,
                ConfidenceLabel,
                ProductsAffectedCount,
                SuppliersAffectedCount,
                CandidateCount,
                EvidenceCompleteness,
                BlockerState,
                Summary,
                PriorityScore,
                CreatedAt,
                UpdatedAt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["company_id"],
                payload["product_id"],
                payload.get("bom_id"),
                payload["component_product_id"],
                payload["parsed_ingredient_name"],
                payload["canonical_ingredient_name"],
                payload["opportunity_type"],
                payload["match_type"],
                status,
                payload["confidence_label"],
                payload["products_affected_count"],
                payload["suppliers_affected_count"],
                payload["candidate_count"],
                payload["evidence_completeness"],
                payload["blocker_state"],
                payload["summary"],
                payload["priority_score"],
                now,
                now,
            ),
        )
        opportunity_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

    conn.commit()
    conn.close()
    return opportunity_id


def replace_opportunity_candidates(db_path=None, opportunity_id=None, candidates=None):
    conn = get_connection(db_path)
    conn.execute("DELETE FROM Opportunity_Candidate WHERE OpportunityId = ?", (opportunity_id,))
    inserted = {}
    for candidate in candidates or []:
        conn.execute(
            """
            INSERT INTO Opportunity_Candidate (
                OpportunityId,
                CandidateProductId,
                CandidateSupplierId,
                MatchType,
                CandidateSummary,
                BlockerState,
                EvidenceCompleteness,
                Explanation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                opportunity_id,
                candidate["candidate_product_id"],
                candidate.get("candidate_supplier_id"),
                candidate["match_type"],
                candidate["candidate_summary"],
                candidate["blocker_state"],
                candidate["evidence_completeness"],
                candidate.get("explanation"),
            ),
        )
        row_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        inserted[(candidate["candidate_product_id"], candidate.get("candidate_supplier_id"))] = row_id
    conn.commit()
    conn.close()
    return inserted


def record_review_decision(db_path=None, opportunity_id=None, status=None, reviewer="Analyst", notes=""):
    conn = get_connection(db_path)
    conn.execute(
        """
        INSERT INTO Review_Decision (OpportunityId, Status, Reviewer, Notes, CreatedAt)
        VALUES (?, ?, ?, ?, ?)
        """,
        (opportunity_id, status, reviewer, notes, now_iso()),
    )
    conn.execute(
        "UPDATE Opportunity SET Status = ?, UpdatedAt = ? WHERE Id = ?",
        (status, now_iso(), opportunity_id),
    )
    conn.commit()
    conn.close()


def get_review_history(db_path=None, opportunity_id=None):
    conn = get_connection(db_path)
    rows = conn.execute(
        """
        SELECT *
        FROM Review_Decision
        WHERE OpportunityId = ?
        ORDER BY CreatedAt DESC, Id DESC
        """,
        (opportunity_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def list_opportunities(
    db_path=None,
    status=None,
    company_id=None,
    match_type=None,
    blocker_state=None,
    confidence_label=None,
):
    conn = get_connection(db_path)
    query = """
        SELECT o.*,
               c.Name AS company_name,
               p.SKU AS finished_sku
        FROM Opportunity o
        JOIN Company c ON c.Id = o.CompanyId
        JOIN Product p ON p.Id = o.ProductId
        WHERE 1 = 1
    """
    params = []
    if status and status != "all":
        query += " AND o.Status = ?"
        params.append(status)
    if company_id and company_id != "all":
        query += " AND o.CompanyId = ?"
        params.append(company_id)
    if match_type and match_type != "all":
        query += " AND o.MatchType = ?"
        params.append(match_type)
    if blocker_state and blocker_state != "all":
        query += " AND o.BlockerState = ?"
        params.append(blocker_state)
    if confidence_label and confidence_label != "all":
        query += " AND o.ConfidenceLabel = ?"
        params.append(confidence_label)
    query += " ORDER BY o.PriorityScore DESC, o.UpdatedAt DESC, o.Id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_opportunity_detail(db_path=None, opportunity_id=None):
    conn = get_connection(db_path)
    opportunity = conn.execute(
        """
        SELECT o.*,
               c.Name AS company_name,
               p.SKU AS finished_sku,
               component.SKU AS component_sku
        FROM Opportunity o
        JOIN Company c ON c.Id = o.CompanyId
        JOIN Product p ON p.Id = o.ProductId
        JOIN Product component ON component.Id = o.BomComponentProductId
        WHERE o.Id = ?
        """,
        (opportunity_id,),
    ).fetchone()
    if not opportunity:
        conn.close()
        return None

    try:
        candidates = conn.execute(
            """
            SELECT oc.*,
                   p.SKU AS candidate_sku,
                   pc.Name AS candidate_company_name,
                   s.Name AS candidate_supplier_name
            FROM Opportunity_Candidate oc
            JOIN Product p ON p.Id = oc.CandidateProductId
            JOIN Company pc ON pc.Id = p.CompanyId
            LEFT JOIN Supplier s ON s.Id = oc.CandidateSupplierId
            WHERE oc.OpportunityId = ?
            ORDER BY oc.BlockerState, oc.MatchType, pc.Name, p.SKU, s.Name
            """,
            (opportunity_id,),
        ).fetchall()
    except Exception:
        candidates = conn.execute(
            """
            SELECT oc.*,
                   p.SKU AS candidate_sku,
                   pc.Name AS candidate_company_name,
                   NULL AS candidate_supplier_name
            FROM Opportunity_Candidate oc
            JOIN Product p ON p.Id = oc.CandidateProductId
            JOIN Company pc ON pc.Id = p.CompanyId
            WHERE oc.OpportunityId = ?
            ORDER BY oc.BlockerState, oc.MatchType, pc.Name, p.SKU
            """,
            (opportunity_id,),
        ).fetchall()

    evidence = conn.execute(
        """
        SELECT *
        FROM Evidence
        WHERE OpportunityId = ?
        ORDER BY OpportunityCandidateId, FactType, Id
        """,
        (opportunity_id,),
    ).fetchall()
    requirements = conn.execute(
        """
        SELECT *
        FROM Requirement_Profile
        WHERE ProductId = ? AND BomComponentProductId = ?
        ORDER BY RequirementType, RequirementValue
        """,
        (opportunity["ProductId"], opportunity["BomComponentProductId"]),
    ).fetchall()
    conn.close()
    return {
        "opportunity": dict(opportunity),
        "candidates": [dict(row) for row in candidates],
        "evidence": [dict(row) for row in evidence],
        "requirements": [dict(row) for row in requirements],
        "review_history": get_review_history(db_path, opportunity_id),
    }


def get_workspace_metrics(db_path=None):
    opportunities = list_opportunities(db_path=db_path)
    if not opportunities:
        return {
            "total": 0,
            "by_status": {},
            "by_blocker_state": {},
            "by_match_type": {},
            "products_affected": 0,
            "suppliers_affected": 0,
            "high_confidence_exact": 0,
            "needs_review_alias": 0,
        }

    return {
        "total": len(opportunities),
        "by_status": Counter(item["Status"] for item in opportunities),
        "by_blocker_state": Counter(item["BlockerState"] for item in opportunities),
        "by_match_type": Counter(item["MatchType"] for item in opportunities),
        "products_affected": len({item["ProductId"] for item in opportunities}),
        "suppliers_affected": sum(item["SuppliersAffectedCount"] for item in opportunities),
        "high_confidence_exact": sum(
            1
            for item in opportunities
            if item["MatchType"] == "exact" and item["ConfidenceLabel"] == "high"
        ),
        "needs_review_alias": sum(
            1
            for item in opportunities
            if item["MatchType"] == "alias" and item["BlockerState"] == "needs_review"
        ),
    }
