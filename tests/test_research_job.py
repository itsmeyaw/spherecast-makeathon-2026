import json
import sqlite3
from src.common.db import (
    init_workspace_schema,
    get_connection,
    create_research_job,
    update_research_job,
    get_latest_research_job,
    get_research_jobs_for_product,
)


def _init_test_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE Product (Id INTEGER PRIMARY KEY, SKU TEXT, CompanyId INTEGER, Type TEXT)")
    conn.execute("INSERT INTO Product VALUES (1, 'FG-test-001', 1, 'finished-good')")
    conn.execute("INSERT INTO Product VALUES (10, 'RM-C1-vitamin-c-abcd1234', 1, 'raw-material')")
    conn.execute("INSERT INTO Product VALUES (11, 'RM-C1-vitamin-d3-abcd1234', 1, 'raw-material')")
    conn.commit()
    conn.close()
    init_workspace_schema(db_path)
    return db_path


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


def test_create_research_job(tmp_path):
    db_path = _init_test_db(tmp_path)
    job_id = create_research_job(db_path=db_path, product_id=1, component_product_id=10)
    assert isinstance(job_id, int)
    assert job_id > 0

    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM Research_Job WHERE Id = ?", (job_id,)).fetchone()
    conn.close()
    assert row["Status"] == "pending"
    assert row["ProductId"] == 1
    assert row["BomComponentProductId"] == 10


def test_update_research_job_to_completed(tmp_path):
    db_path = _init_test_db(tmp_path)
    job_id = create_research_job(db_path=db_path, product_id=1, component_product_id=10)

    result = {"candidates_researched": [{"name": "ascorbic-acid", "facts": ["same compound"]}]}
    update_research_job(db_path=db_path, job_id=job_id, status="completed", result_json=json.dumps(result))

    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM Research_Job WHERE Id = ?", (job_id,)).fetchone()
    conn.close()
    assert row["Status"] == "completed"
    assert json.loads(row["ResultJson"])["candidates_researched"][0]["name"] == "ascorbic-acid"


def test_update_research_job_to_failed(tmp_path):
    db_path = _init_test_db(tmp_path)
    job_id = create_research_job(db_path=db_path, product_id=1, component_product_id=10)
    update_research_job(db_path=db_path, job_id=job_id, status="failed", error_message="agent timeout")

    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM Research_Job WHERE Id = ?", (job_id,)).fetchone()
    conn.close()
    assert row["Status"] == "failed"
    assert row["ErrorMessage"] == "agent timeout"


def test_get_latest_research_job(tmp_path):
    db_path = _init_test_db(tmp_path)
    job1 = create_research_job(db_path=db_path, product_id=1, component_product_id=10)
    update_research_job(db_path=db_path, job_id=job1, status="completed", result_json='{"old": true}')
    job2 = create_research_job(db_path=db_path, product_id=1, component_product_id=10)

    latest = get_latest_research_job(db_path=db_path, product_id=1, component_product_id=10)
    assert latest["Id"] == job2
    assert latest["Status"] == "pending"


def test_get_latest_research_job_returns_none_when_empty(tmp_path):
    db_path = _init_test_db(tmp_path)
    result = get_latest_research_job(db_path=db_path, product_id=1, component_product_id=10)
    assert result is None


def test_get_research_jobs_for_product(tmp_path):
    db_path = _init_test_db(tmp_path)
    create_research_job(db_path=db_path, product_id=1, component_product_id=10)
    create_research_job(db_path=db_path, product_id=1, component_product_id=10)
    create_research_job(db_path=db_path, product_id=1, component_product_id=11)

    jobs = get_research_jobs_for_product(db_path=db_path, product_id=1)
    assert len(jobs) == 2
    component_ids = {j["BomComponentProductId"] for j in jobs}
    assert component_ids == {10, 11}
