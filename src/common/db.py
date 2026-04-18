import sqlite3
import json
import re

DB_PATH = "db.sqlite"


def get_connection(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_finished_goods(db_path=None):
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT p.Id as product_id, p.SKU as sku, c.Name as company_name
        FROM Product p
        JOIN Company c ON p.CompanyId = c.Id
        WHERE p.Type = 'finished-good'
        ORDER BY c.Name, p.SKU
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_bom_components(db_path=None, product_id=None):
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT p2.Id as product_id, p2.SKU as sku, p2.CompanyId as company_id
        FROM BOM b
        JOIN BOM_Component bc ON bc.BOMId = b.Id
        JOIN Product p2 ON p2.Id = bc.ConsumedProductId
        WHERE b.ProducedProductId = ?
        ORDER BY p2.SKU
    """, (product_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_suppliers_for_product(db_path=None, product_id=None):
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT s.Name
        FROM Supplier_Product sp
        JOIN Supplier s ON sp.SupplierId = s.Id
        WHERE sp.ProductId = ?
        ORDER BY s.Name
    """, (product_id,)).fetchall()
    conn.close()
    return [r["Name"] for r in rows]


def parse_ingredient_name(sku):
    match = re.match(r"RM-C\d+-(.+)-[a-f0-9]{8}$", sku)
    if match:
        return match.group(1)
    return sku


def get_all_ingredient_names(db_path=None):
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT DISTINCT SKU FROM Product WHERE Type = 'raw-material'
    """).fetchall()
    conn.close()
    names = set()
    for r in rows:
        names.add(parse_ingredient_name(r["SKU"]))
    return sorted(names)


def save_ingredient_groups(db_path=None, groups=None):
    conn = get_connection(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Ingredient_Group (
            id INTEGER PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            function TEXT NOT NULL,
            members TEXT NOT NULL,
            confidence TEXT CHECK (confidence IN ('high', 'medium', 'low')),
            reasoning TEXT
        )
    """)
    conn.execute("DELETE FROM Ingredient_Group")
    for g in groups:
        conn.execute(
            "INSERT INTO Ingredient_Group (canonical_name, function, members, confidence, reasoning) VALUES (?, ?, ?, ?, ?)",
            (g["canonical_name"], g["function"], json.dumps(g["members"]), g["confidence"], g["reasoning"]),
        )
    conn.commit()
    conn.close()


def get_ingredient_group_for(db_path=None, ingredient_name=None):
    conn = get_connection(db_path)
    rows = conn.execute("SELECT * FROM Ingredient_Group").fetchall()
    conn.close()
    for r in rows:
        members = json.loads(r["members"])
        if ingredient_name in members:
            return {
                "id": r["id"],
                "canonical_name": r["canonical_name"],
                "function": r["function"],
                "members": members,
                "confidence": r["confidence"],
                "reasoning": r["reasoning"],
            }
    return None
