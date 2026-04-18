import sqlite3

from src.common.db import init_workspace_schema, now_iso, seed_default_ingredient_aliases
from src.opportunity.store import (
    get_opportunity_detail,
    record_review_decision,
    upsert_opportunity,
)


def _make_test_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE Company (Id INTEGER PRIMARY KEY, Name TEXT NOT NULL);
        CREATE TABLE Product (
            Id INTEGER PRIMARY KEY,
            SKU TEXT NOT NULL,
            CompanyId INTEGER NOT NULL,
            Type TEXT NOT NULL
        );
        INSERT INTO Company VALUES (1, 'CompA');
        INSERT INTO Product VALUES
            (1, 'FG-iherb-001', 1, 'finished-good'),
            (2, 'RM-C1-vitamin-c-aaa11111', 1, 'raw-material');
        """
    )
    conn.commit()
    conn.close()


def test_review_decision_updates_opportunity_status(tmp_path):
    db_path = str(tmp_path / "review.db")
    _make_test_db(db_path)
    init_workspace_schema(db_path)
    seed_default_ingredient_aliases(db_path)
    opportunity_id = upsert_opportunity(
        db_path=db_path,
        payload={
            "company_id": 1,
            "product_id": 1,
            "bom_id": 1,
            "component_product_id": 2,
            "parsed_ingredient_name": "vitamin-c",
            "canonical_ingredient_name": "vitamin-c",
            "opportunity_type": "exact-match-consolidation",
            "match_type": "exact",
            "confidence_label": "high",
            "products_affected_count": 1,
            "suppliers_affected_count": 1,
            "candidate_count": 1,
            "evidence_completeness": "high",
            "blocker_state": "pass_known_blockers",
            "summary": "Test opportunity",
            "priority_score": 100,
        },
    )

    record_review_decision(
        db_path=db_path,
        opportunity_id=opportunity_id,
        status="approved",
        reviewer="QA",
        notes="Approved for the demo workflow.",
    )
    detail = get_opportunity_detail(db_path=db_path, opportunity_id=opportunity_id)
    assert detail["opportunity"]["Status"] == "approved"
    assert detail["review_history"][0]["Reviewer"] == "QA"
