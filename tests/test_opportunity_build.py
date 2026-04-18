import sqlite3

from src.common.db import init_workspace_schema, seed_default_ingredient_aliases
from src.opportunity.build import build_all_opportunities
from src.opportunity.store import get_opportunity_detail, list_opportunities


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
        CREATE TABLE BOM (
            Id INTEGER PRIMARY KEY,
            ProducedProductId INTEGER NOT NULL UNIQUE
        );
        CREATE TABLE BOM_Component (
            BOMId INTEGER NOT NULL,
            ConsumedProductId INTEGER NOT NULL,
            PRIMARY KEY (BOMId, ConsumedProductId)
        );
        CREATE TABLE Supplier (Id INTEGER PRIMARY KEY, Name TEXT NOT NULL);
        CREATE TABLE Supplier_Product (
            SupplierId INTEGER NOT NULL,
            ProductId INTEGER NOT NULL,
            PRIMARY KEY (SupplierId, ProductId)
        );

        INSERT INTO Company VALUES (1, 'CompA'), (2, 'CompB');
        INSERT INTO Product VALUES
            (1, 'FG-iherb-001', 1, 'finished-good'),
            (2, 'RM-C1-vitamin-c-aaa11111', 1, 'raw-material'),
            (3, 'RM-C2-vitamin-c-bbb22222', 2, 'raw-material'),
            (4, 'RM-C2-ascorbic-acid-ccc33333', 2, 'raw-material');
        INSERT INTO BOM VALUES (1, 1);
        INSERT INTO BOM_Component VALUES (1, 2);
        INSERT INTO Supplier VALUES (1, 'SupA'), (2, 'SupB');
        INSERT INTO Supplier_Product VALUES (1, 2), (2, 3), (2, 4);
        """
    )
    conn.commit()
    conn.close()


def test_builds_exact_and_alias_opportunities(tmp_path):
    db_path = str(tmp_path / "workspace.db")
    _make_test_db(db_path)
    init_workspace_schema(db_path)
    seed_default_ingredient_aliases(db_path)

    build_all_opportunities(db_path)
    opportunities = list_opportunities(db_path=db_path)

    match_types = {item["MatchType"] for item in opportunities}
    assert "exact" in match_types
    assert "alias" in match_types

    exact = [item for item in opportunities if item["MatchType"] == "exact"][0]
    alias = [item for item in opportunities if item["MatchType"] == "alias"][0]
    assert exact["BlockerState"] == "pass_known_blockers"
    assert alias["BlockerState"] in {"pass_known_blockers", "needs_review"}
    assert exact["CandidateCount"] == 1

    detail = get_opportunity_detail(db_path=db_path, opportunity_id=exact["Id"])
    assert detail["candidates"]
    assert detail["evidence"]
    assert detail["requirements"]
