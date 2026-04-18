import json
import sqlite3
from unittest.mock import patch

from src.common.db import get_supplier_specs, init_workspace_schema


def _setup_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE Company (Id INTEGER PRIMARY KEY, Name TEXT NOT NULL)")
    conn.execute("CREATE TABLE Supplier (Id INTEGER PRIMARY KEY, Name TEXT NOT NULL)")
    conn.execute("CREATE TABLE Product (Id INTEGER PRIMARY KEY, SKU TEXT NOT NULL, CompanyId INTEGER NOT NULL, Type TEXT NOT NULL)")
    conn.execute("CREATE TABLE BOM (Id INTEGER PRIMARY KEY, ProducedProductId INTEGER NOT NULL)")
    conn.execute("CREATE TABLE BOM_Component (Id INTEGER PRIMARY KEY, BOMId INTEGER NOT NULL, ConsumedProductId INTEGER NOT NULL)")
    conn.execute("CREATE TABLE Supplier_Product (SupplierId INTEGER NOT NULL, ProductId INTEGER NOT NULL, PRIMARY KEY (SupplierId, ProductId))")
    conn.execute("INSERT INTO Company (Id, Name) VALUES (1, 'TestCo')")
    conn.execute("INSERT INTO Supplier (Id, Name) VALUES (1, 'ADM'), (2, 'AIDP')")
    conn.execute("INSERT INTO Product (Id, SKU, CompanyId, Type) VALUES (10, 'FG-test-001', 1, 'finished-good')")
    conn.execute("INSERT INTO Product (Id, SKU, CompanyId, Type) VALUES (100, 'RM-C1-vitamin-c-abcd1234', 1, 'raw-material')")
    conn.execute("INSERT INTO Supplier_Product VALUES (1, 100), (2, 100)")
    conn.execute("INSERT INTO BOM (Id, ProducedProductId) VALUES (1, 10)")
    conn.execute("INSERT INTO BOM_Component (Id, BOMId, ConsumedProductId) VALUES (1, 1, 100)")
    conn.commit()
    conn.close()
    init_workspace_schema(db_path)
    return db_path


def test_run_research_persists_spec_rows(tmp_path):
    db_path = _setup_db(tmp_path)

    mock_verdict = {
        "facts": ["Vitamin C purity varies by supplier"],
        "rules": [],
        "inference": "Both suppliers meet minimum purity.",
        "caveats": [],
        "evidence_rows": [
            {
                "source_type": "tds",
                "source_label": "ADM TDS for RM-C1-vitamin-c-abcd1234",
                "source_uri": "https://adm.com/tds/vitc.pdf",
                "fact_type": "spec:purity",
                "fact_value": "99.5%",
                "quality_score": 0.9,
                "snippet": "Assay (purity): 99.5%",
            },
            {
                "source_type": "tds",
                "source_label": "AIDP TDS for RM-C1-vitamin-c-abcd1234",
                "source_uri": "https://aidp.com/tds/vitc.pdf",
                "fact_type": "spec:purity",
                "fact_value": "98.0%",
                "quality_score": 0.85,
                "snippet": "Assay (purity): 98.0%",
            },
            {
                "source_type": "pgvector",
                "source_label": "Document search",
                "source_uri": "s3://docs/product.json",
                "fact_type": "product_context",
                "fact_value": "Contains vitamin C",
                "quality_score": 0.9,
                "snippet": "Supplement Facts: Vitamin C 1000mg",
            },
        ],
    }

    mock_candidates_data = {
        "original_ingredient": "vitamin-c",
        "canonical_names": ["vitamin-c"],
        "exact_candidates": [{"current_match_name": "ascorbic-acid", "match_type": "exact"}],
        "alias_candidates": [],
    }

    with patch("src.research.run.research_substitution", return_value=mock_verdict):
        with patch("src.research.run.find_candidates_for_component", return_value=mock_candidates_data):
            from src.research.run import run_research
            run_research(
                db_path=db_path,
                product={"product_id": 10, "sku": "FG-test-001", "company_name": "TestCo"},
                component={"product_id": 100, "sku": "RM-C1-vitamin-c-abcd1234"},
            )

    specs = get_supplier_specs(db_path=db_path, product_id=100)
    assert len(specs) == 2
    spec_by_supplier = {s["SupplierName"]: s for s in specs}
    assert spec_by_supplier["ADM"]["SpecValue"] == "99.5%"
    assert spec_by_supplier["AIDP"]["SpecValue"] == "98.0%"


def test_run_research_skips_unresolvable_supplier(tmp_path):
    db_path = _setup_db(tmp_path)

    mock_verdict = {
        "facts": [],
        "rules": [],
        "inference": "ok",
        "caveats": [],
        "evidence_rows": [
            {
                "source_type": "tds",
                "source_label": "UnknownCorp TDS for RM-C1-vitamin-c-abcd1234",
                "source_uri": "https://unknown.com/tds.pdf",
                "fact_type": "spec:purity",
                "fact_value": "97.0%",
                "quality_score": 0.8,
                "snippet": "Purity: 97%",
            },
        ],
    }

    mock_candidates_data = {
        "original_ingredient": "vitamin-c",
        "canonical_names": ["vitamin-c"],
        "exact_candidates": [{"current_match_name": "ascorbic-acid", "match_type": "exact"}],
        "alias_candidates": [],
    }

    with patch("src.research.run.research_substitution", return_value=mock_verdict):
        with patch("src.research.run.find_candidates_for_component", return_value=mock_candidates_data):
            from src.research.run import run_research
            run_research(
                db_path=db_path,
                product={"product_id": 10, "sku": "FG-test-001", "company_name": "TestCo"},
                component={"product_id": 100, "sku": "RM-C1-vitamin-c-abcd1234"},
            )

    specs = get_supplier_specs(db_path=db_path, product_id=100)
    assert len(specs) == 0
