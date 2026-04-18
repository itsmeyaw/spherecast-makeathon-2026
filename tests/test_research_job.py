import sqlite3
from src.common.db import init_workspace_schema, get_connection


def test_research_job_table_exists_after_init(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE Product (Id INTEGER PRIMARY KEY, SKU TEXT, CompanyId INTEGER, Type TEXT)")
    conn.commit()
    conn.close()

    init_workspace_schema(db_path)

    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='Research_Job'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["name"] == "Research_Job"
