import sqlite3
import json
import tempfile
import os
from src.common.db import (
    get_connection,
    get_finished_goods,
    get_bom_components,
    get_suppliers_for_product,
    get_all_ingredient_names,
    save_ingredient_groups,
    get_ingredient_group_for,
)


def _make_test_db(path):
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE Company (Id INTEGER PRIMARY KEY, Name TEXT NOT NULL);
        CREATE TABLE Product (
            Id INTEGER PRIMARY KEY, SKU TEXT NOT NULL,
            CompanyId INTEGER NOT NULL, Type TEXT NOT NULL,
            FOREIGN KEY (CompanyId) REFERENCES Company (Id)
        );
        CREATE TABLE BOM (
            Id INTEGER PRIMARY KEY, ProducedProductId INTEGER NOT NULL UNIQUE,
            FOREIGN KEY (ProducedProductId) REFERENCES Product (Id)
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

        INSERT INTO Company VALUES (1, 'TestCo'), (2, 'OtherCo');
        INSERT INTO Product VALUES
            (1, 'FG-iherb-123', 1, 'finished-good'),
            (2, 'RM-C1-vitamin-d3-abc12345', 1, 'raw-material'),
            (3, 'RM-C1-magnesium-oxide-def67890', 1, 'raw-material'),
            (4, 'RM-C2-vitamin-d3-cholecalciferol-aaa11111', 2, 'raw-material');
        INSERT INTO BOM VALUES (1, 1);
        INSERT INTO BOM_Component VALUES (1, 2), (1, 3);
        INSERT INTO Supplier VALUES (1, 'SupplierA'), (2, 'SupplierB');
        INSERT INTO Supplier_Product VALUES (1, 2), (2, 2), (1, 4);
    """)
    conn.commit()
    return conn


class TestGetFinishedGoods:
    def test_returns_all_finished_goods_with_company(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _make_test_db(db_path)
        results = get_finished_goods(db_path)
        assert len(results) == 1
        assert results[0]["sku"] == "FG-iherb-123"
        assert results[0]["company_name"] == "TestCo"
        assert results[0]["product_id"] == 1


class TestGetBomComponents:
    def test_returns_components_with_suppliers(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _make_test_db(db_path)
        results = get_bom_components(db_path, product_id=1)
        assert len(results) == 2
        skus = {r["sku"] for r in results}
        assert "RM-C1-vitamin-d3-abc12345" in skus
        assert "RM-C1-magnesium-oxide-def67890" in skus


class TestGetSuppliersForProduct:
    def test_returns_supplier_names(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _make_test_db(db_path)
        suppliers = get_suppliers_for_product(db_path, product_id=2)
        assert set(suppliers) == {"SupplierA", "SupplierB"}


class TestGetAllIngredientNames:
    def test_returns_distinct_parsed_names(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _make_test_db(db_path)
        names = get_all_ingredient_names(db_path)
        assert "vitamin-d3" in names
        assert "magnesium-oxide" in names
        assert "vitamin-d3-cholecalciferol" in names


class TestIngredientGroups:
    def test_save_and_retrieve(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _make_test_db(db_path)
        groups = [
            {
                "canonical_name": "Vitamin D3",
                "function": "vitamin D source",
                "members": ["vitamin-d3", "vitamin-d3-cholecalciferol"],
                "confidence": "high",
                "reasoning": "Same chemical entity",
            }
        ]
        save_ingredient_groups(db_path, groups)
        group = get_ingredient_group_for(db_path, "vitamin-d3")
        assert group["canonical_name"] == "Vitamin D3"
        assert "vitamin-d3-cholecalciferol" in group["members"]
