import sqlite3
from src.common.db import init_workspace_schema, upsert_supplier_spec, get_supplier_specs


def _setup_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE Supplier (Id INTEGER PRIMARY KEY, Name TEXT NOT NULL)")
    conn.execute("CREATE TABLE Product (Id INTEGER PRIMARY KEY, SKU TEXT NOT NULL, CompanyId INTEGER NOT NULL, Type TEXT NOT NULL)")
    conn.execute("INSERT INTO Supplier (Id, Name) VALUES (1, 'ADM'), (2, 'AIDP')")
    conn.execute("INSERT INTO Product (Id, SKU, CompanyId, Type) VALUES (100, 'RM-C1-vitamin-c-abcd1234', 1, 'raw-material')")
    conn.commit()
    conn.close()
    init_workspace_schema(db_path)
    return db_path


def test_upsert_supplier_spec_insert(tmp_path):
    db_path = _setup_db(tmp_path)
    upsert_supplier_spec(
        db_path=db_path,
        supplier_id=1,
        product_id=100,
        spec_key="purity",
        spec_value="99.5",
        spec_unit="%",
        source_uri="https://adm.com/tds/vitc.pdf",
        source_type="web-search",
    )
    specs = get_supplier_specs(db_path=db_path, product_id=100)
    assert len(specs) == 1
    assert specs[0]["SpecKey"] == "purity"
    assert specs[0]["SpecValue"] == "99.5"
    assert specs[0]["SpecUnit"] == "%"
    assert specs[0]["SupplierId"] == 1


def test_upsert_supplier_spec_updates_on_conflict(tmp_path):
    db_path = _setup_db(tmp_path)
    upsert_supplier_spec(db_path=db_path, supplier_id=1, product_id=100, spec_key="purity", spec_value="98.0", spec_unit="%")
    upsert_supplier_spec(db_path=db_path, supplier_id=1, product_id=100, spec_key="purity", spec_value="99.5", spec_unit="%")
    specs = get_supplier_specs(db_path=db_path, product_id=100)
    purity_rows = [s for s in specs if s["SpecKey"] == "purity"]
    assert len(purity_rows) == 1
    assert purity_rows[0]["SpecValue"] == "99.5"


def test_get_supplier_specs_multiple_suppliers(tmp_path):
    db_path = _setup_db(tmp_path)
    upsert_supplier_spec(db_path=db_path, supplier_id=1, product_id=100, spec_key="purity", spec_value="99.5", spec_unit="%")
    upsert_supplier_spec(db_path=db_path, supplier_id=2, product_id=100, spec_key="purity", spec_value="98.0", spec_unit="%")
    upsert_supplier_spec(db_path=db_path, supplier_id=1, product_id=100, spec_key="form_grade", spec_value="USP")
    specs = get_supplier_specs(db_path=db_path, product_id=100)
    assert len(specs) == 3
    supplier_ids = {s["SupplierId"] for s in specs}
    assert supplier_ids == {1, 2}


def test_different_products_same_supplier_different_specs(tmp_path):
    db_path = _setup_db(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO Product (Id, SKU, CompanyId, Type) VALUES (101, 'RM-C1-vitamin-c-efgh5678', 1, 'raw-material')")
    conn.commit()
    conn.close()
    upsert_supplier_spec(db_path=db_path, supplier_id=1, product_id=100, spec_key="purity", spec_value="99.5", spec_unit="%")
    upsert_supplier_spec(db_path=db_path, supplier_id=1, product_id=101, spec_key="purity", spec_value="98.0", spec_unit="%")
    specs_100 = get_supplier_specs(db_path=db_path, product_id=100)
    specs_101 = get_supplier_specs(db_path=db_path, product_id=101)
    assert len(specs_100) == 1
    assert specs_100[0]["SpecValue"] == "99.5"
    assert len(specs_101) == 1
    assert specs_101[0]["SpecValue"] == "98.0"
