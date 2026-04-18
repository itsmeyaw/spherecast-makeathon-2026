import json
import sqlite3
from unittest.mock import patch

from src.common.db import (
    init_workspace_schema,
    get_connection,
    get_latest_research_job,
)


def _init_test_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE Company (Id INTEGER PRIMARY KEY, Name TEXT);
        INSERT INTO Company VALUES (1, 'TestCo');

        CREATE TABLE Product (Id INTEGER PRIMARY KEY, SKU TEXT, CompanyId INTEGER, Type TEXT);
        INSERT INTO Product VALUES (1, 'FG-test-001', 1, 'finished-good');
        INSERT INTO Product VALUES (10, 'RM-C1-vitamin-c-abcd1234', 1, 'raw-material');

        CREATE TABLE Supplier (Id INTEGER PRIMARY KEY, Name TEXT);
        CREATE TABLE Supplier_Product (Id INTEGER PRIMARY KEY, SupplierId INTEGER, ProductId INTEGER);

        CREATE TABLE BOM (Id INTEGER PRIMARY KEY, ProducedProductId INTEGER);
        INSERT INTO BOM VALUES (1, 1);

        CREATE TABLE BOM_Component (Id INTEGER PRIMARY KEY, BOMId INTEGER, ConsumedProductId INTEGER);
        INSERT INTO BOM_Component VALUES (1, 1, 10);
        """
    )
    conn.commit()
    conn.close()
    init_workspace_schema(db_path)
    return db_path


def test_run_research_completes_job(tmp_path):
    db_path = _init_test_db(tmp_path)

    mock_verdict = {
        "facts": ["Vitamin C is ascorbic acid"],
        "rules": ["FDA 21 CFR 101.36"],
        "inference": "Safe substitute.",
        "caveats": [],
        "evidence_rows": [],
        "kb_sources": [],
    }

    mock_candidates = {
        "bom_id": 1,
        "finished_product": {"product_id": 1, "sku": "FG-test-001", "company_id": 1, "company_name": "TestCo"},
        "original_ingredient": "vitamin-c",
        "original_product_id": 10,
        "original_sku": "RM-C1-vitamin-c-abcd1234",
        "original_company_name": "TestCo",
        "current_suppliers": [],
        "canonical_names": ["vitamin-c"],
        "exact_candidates": [
            {
                "product_id": 11,
                "sku": "RM-C2-vitamin-c-xyz789",
                "company_id": 1,
                "company_name": "TestCo",
                "parsed_ingredient_name": "vitamin-c",
                "current_match_name": "vitamin-c",
                "match_type": "exact",
                "canonical_name": "vitamin-c",
                "candidate_suppliers": [],
            }
        ],
        "alias_candidates": [],
    }

    product = {"product_id": 1, "sku": "FG-test-001", "company_id": 1, "company_name": "TestCo"}
    component = {"bom_id": 1, "product_id": 10, "sku": "RM-C1-vitamin-c-abcd1234", "company_id": 1, "component_company_name": "TestCo"}

    with patch("src.research.run.find_candidates_for_component", return_value=mock_candidates):
        with patch("src.research.run.research_substitution", return_value=mock_verdict):
            from src.research.run import run_research
            run_research(db_path=db_path, product=product, component=component)

    job = get_latest_research_job(db_path=db_path, product_id=1, component_product_id=10)
    assert job["Status"] == "completed"
    result = json.loads(job["ResultJson"])
    assert "candidates_researched" in result


def test_run_research_marks_failed_on_error(tmp_path):
    db_path = _init_test_db(tmp_path)

    product = {"product_id": 1, "sku": "FG-test-001", "company_id": 1, "company_name": "TestCo"}
    component = {"bom_id": 1, "product_id": 10, "sku": "RM-C1-vitamin-c-abcd1234", "company_id": 1, "component_company_name": "TestCo"}

    with patch("src.research.run.find_candidates_for_component", side_effect=Exception("agent crashed")):
        from src.research.run import run_research
        run_research(db_path=db_path, product=product, component=component)

    job = get_latest_research_job(db_path=db_path, product_id=1, component_product_id=10)
    assert job["Status"] == "failed"
    assert "agent crashed" in job["ErrorMessage"]
