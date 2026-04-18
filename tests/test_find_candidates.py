import json
import sqlite3
from src.substitute.find_candidates import find_candidates_for_product


def _make_test_db(path):
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE Company (Id INTEGER PRIMARY KEY, Name TEXT NOT NULL);
        CREATE TABLE Product (
            Id INTEGER PRIMARY KEY, SKU TEXT NOT NULL,
            CompanyId INTEGER NOT NULL, Type TEXT NOT NULL
        );
        CREATE TABLE BOM (
            Id INTEGER PRIMARY KEY, ProducedProductId INTEGER NOT NULL UNIQUE
        );
        CREATE TABLE BOM_Component (
            BOMId INTEGER NOT NULL, ConsumedProductId INTEGER NOT NULL,
            PRIMARY KEY (BOMId, ConsumedProductId)
        );
        CREATE TABLE Supplier (Id INTEGER PRIMARY KEY, Name TEXT NOT NULL);
        CREATE TABLE Supplier_Product (
            SupplierId INTEGER NOT NULL, ProductId INTEGER NOT NULL,
            PRIMARY KEY (SupplierId, ProductId)
        );
        CREATE TABLE Ingredient_Group (
            id INTEGER PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            function TEXT NOT NULL,
            members TEXT NOT NULL,
            confidence TEXT,
            reasoning TEXT
        );

        INSERT INTO Company VALUES (1, 'CompA'), (2, 'CompB');
        INSERT INTO Product VALUES
            (1, 'FG-iherb-001', 1, 'finished-good'),
            (2, 'RM-C1-magnesium-citrate-aaa11111', 1, 'raw-material'),
            (3, 'RM-C2-magnesium-glycinate-bbb22222', 2, 'raw-material'),
            (4, 'RM-C1-vitamin-c-ccc33333', 1, 'raw-material');
        INSERT INTO BOM VALUES (1, 1);
        INSERT INTO BOM_Component VALUES (1, 2), (1, 4);
        INSERT INTO Supplier VALUES (1, 'SupA'), (2, 'SupB');
        INSERT INTO Supplier_Product VALUES (1, 2), (2, 3), (1, 4);

        INSERT INTO Ingredient_Group VALUES
            (1, 'Magnesium Source', 'bioavailable magnesium',
             '["magnesium-citrate", "magnesium-glycinate"]', 'medium', 'Both Mg sources'),
            (2, 'Vitamin C', 'vitamin C source',
             '["vitamin-c"]', 'high', 'Single member');
    """)
    conn.commit()
    return conn


class TestFindCandidates:
    def test_finds_substitutes_in_same_group(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _make_test_db(db_path)
        results = find_candidates_for_product(db_path, product_id=1)
        mg_result = [r for r in results if r["original_ingredient"] == "magnesium-citrate"][0]
        candidate_names = [c["ingredient_name"] for c in mg_result["candidates"]]
        assert "magnesium-glycinate" in candidate_names

    def test_no_candidates_for_single_member_group(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _make_test_db(db_path)
        results = find_candidates_for_product(db_path, product_id=1)
        vc_result = [r for r in results if r["original_ingredient"] == "vitamin-c"][0]
        assert len(vc_result["candidates"]) == 0

    def test_includes_supplier_info(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _make_test_db(db_path)
        results = find_candidates_for_product(db_path, product_id=1)
        mg_result = [r for r in results if r["original_ingredient"] == "magnesium-citrate"][0]
        mg_glyc = [c for c in mg_result["candidates"] if c["ingredient_name"] == "magnesium-glycinate"][0]
        assert "SupB" in mg_glyc["suppliers"]
