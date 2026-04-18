import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone

DB_PATH = "db.sqlite"

STATUS_VALUES = ("new", "triaged", "needs-review", "approved", "rejected", "blocked")
BLOCKER_VALUES = ("pass_known_blockers", "needs_review", "blocked")
CONFIDENCE_VALUES = ("high", "medium", "low")
MATCH_TYPE_VALUES = ("exact", "alias", "hypothesis")

DEFAULT_INGREDIENT_ALIASES = [
    {
        "canonical_name": "vitamin-c",
        "alias_name": "vitamin-c",
        "match_type": "exact",
        "notes": "Exact ingredient name shared across products and companies.",
        "approved": 1,
    },
    {
        "canonical_name": "vitamin-c",
        "alias_name": "ascorbic-acid",
        "match_type": "alias",
        "notes": "Reviewed same-chemical-entity alias for the demo workspace.",
        "approved": 1,
    },
    {
        "canonical_name": "vitamin-d3",
        "alias_name": "vitamin-d3-cholecalciferol",
        "match_type": "alias",
        "notes": "Reviewed same-chemical-entity alias for the demo workspace.",
        "approved": 1,
    },
    {
        "canonical_name": "vitamin-d3",
        "alias_name": "cholecalciferol-vitamin-d3",
        "match_type": "alias",
        "notes": "Reviewed same-chemical-entity alias for the demo workspace.",
        "approved": 1,
    },
    {
        "canonical_name": "vitamin-d3",
        "alias_name": "vitamin-d3",
        "match_type": "alias",
        "notes": "Reviewed same-chemical-entity alias for the demo workspace.",
        "approved": 1,
    },
    {
        "canonical_name": "cellulose-excipient",
        "alias_name": "cellulose",
        "match_type": "alias",
        "notes": "Reviewed excipient alias. Treat as needs-review when product context is thin.",
        "approved": 1,
    },
    {
        "canonical_name": "cellulose-excipient",
        "alias_name": "microcrystalline-cellulose",
        "match_type": "alias",
        "notes": "Reviewed excipient alias. Treat as needs-review when product context is thin.",
        "approved": 1,
    },
    {
        "canonical_name": "gelatin-capsule",
        "alias_name": "gelatin",
        "match_type": "alias",
        "notes": "Reviewed capsule material alias.",
        "approved": 1,
    },
    {
        "canonical_name": "gelatin-capsule",
        "alias_name": "bovine-gelatin",
        "match_type": "alias",
        "notes": "Reviewed capsule material alias.",
        "approved": 1,
    },
    {
        "canonical_name": "whey-protein-family",
        "alias_name": "whey-protein-isolate",
        "match_type": "hypothesis",
        "notes": "Related functional family. Keep as hypothesis until a human reviews formulation fit.",
        "approved": 0,
    },
    {
        "canonical_name": "whey-protein-family",
        "alias_name": "whey-protein-concentrate",
        "match_type": "hypothesis",
        "notes": "Related functional family. Keep as hypothesis until a human reviews formulation fit.",
        "approved": 0,
    },
    {
        "canonical_name": "magnesium-source",
        "alias_name": "magnesium-oxide",
        "match_type": "hypothesis",
        "notes": "Related magnesium source, not auto-approvable.",
        "approved": 0,
    },
    {
        "canonical_name": "magnesium-source",
        "alias_name": "magnesium-citrate",
        "match_type": "hypothesis",
        "notes": "Related magnesium source, not auto-approvable.",
        "approved": 0,
    },
    {
        "canonical_name": "magnesium-source",
        "alias_name": "magnesium-glycinate",
        "match_type": "hypothesis",
        "notes": "Related magnesium source, not auto-approvable.",
        "approved": 0,
    },
]


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_connection(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def parse_ingredient_name(sku):
    match = re.match(r"RM-C\d+-(.+)-[a-f0-9]{8}$", sku)
    if match:
        return match.group(1)
    return sku


def init_workspace_schema(db_path=None):
    conn = get_connection(db_path)
    conn.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS Ingredient_Group (
            id INTEGER PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            function TEXT NOT NULL,
            members TEXT NOT NULL,
            confidence TEXT CHECK (confidence IN {CONFIDENCE_VALUES}),
            reasoning TEXT
        );

        CREATE TABLE IF NOT EXISTS Ingredient_Alias (
            Id INTEGER PRIMARY KEY,
            CanonicalName TEXT NOT NULL,
            AliasName TEXT NOT NULL,
            MatchType TEXT NOT NULL CHECK (MatchType IN {MATCH_TYPE_VALUES}),
            Notes TEXT,
            Approved INTEGER NOT NULL DEFAULT 0,
            UNIQUE (CanonicalName, AliasName)
        );

        CREATE TABLE IF NOT EXISTS Opportunity (
            Id INTEGER PRIMARY KEY,
            CompanyId INTEGER NOT NULL,
            ProductId INTEGER NOT NULL,
            BomId INTEGER,
            BomComponentProductId INTEGER NOT NULL,
            ParsedIngredientName TEXT NOT NULL,
            CanonicalIngredientName TEXT NOT NULL,
            OpportunityType TEXT NOT NULL,
            MatchType TEXT NOT NULL CHECK (MatchType IN {MATCH_TYPE_VALUES}),
            Status TEXT NOT NULL CHECK (Status IN {STATUS_VALUES}),
            ConfidenceLabel TEXT NOT NULL CHECK (ConfidenceLabel IN {CONFIDENCE_VALUES}),
            ProductsAffectedCount INTEGER NOT NULL DEFAULT 0,
            SuppliersAffectedCount INTEGER NOT NULL DEFAULT 0,
            CandidateCount INTEGER NOT NULL DEFAULT 0,
            EvidenceCompleteness TEXT NOT NULL,
            BlockerState TEXT NOT NULL CHECK (BlockerState IN {BLOCKER_VALUES}),
            Summary TEXT,
            PriorityScore REAL NOT NULL DEFAULT 0,
            CreatedAt TEXT NOT NULL,
            UpdatedAt TEXT NOT NULL,
            UNIQUE (ProductId, BomComponentProductId, OpportunityType, MatchType)
        );

        CREATE TABLE IF NOT EXISTS Opportunity_Candidate (
            Id INTEGER PRIMARY KEY,
            OpportunityId INTEGER NOT NULL,
            CandidateProductId INTEGER NOT NULL,
            CandidateSupplierId INTEGER,
            MatchType TEXT NOT NULL CHECK (MatchType IN {MATCH_TYPE_VALUES}),
            CandidateSummary TEXT,
            BlockerState TEXT NOT NULL CHECK (BlockerState IN {BLOCKER_VALUES}),
            EvidenceCompleteness TEXT NOT NULL,
            Explanation TEXT,
            FOREIGN KEY (OpportunityId) REFERENCES Opportunity (Id),
            UNIQUE (OpportunityId, CandidateProductId, CandidateSupplierId)
        );

        CREATE TABLE IF NOT EXISTS Evidence (
            Id INTEGER PRIMARY KEY,
            OpportunityId INTEGER NOT NULL,
            OpportunityCandidateId INTEGER,
            SourceType TEXT NOT NULL,
            SourceLabel TEXT NOT NULL,
            SourceUri TEXT,
            FactType TEXT NOT NULL,
            FactValue TEXT NOT NULL,
            QualityScore REAL,
            Snippet TEXT,
            PayloadRef TEXT,
            CreatedAt TEXT NOT NULL,
            FOREIGN KEY (OpportunityId) REFERENCES Opportunity (Id),
            FOREIGN KEY (OpportunityCandidateId) REFERENCES Opportunity_Candidate (Id)
        );

        CREATE TABLE IF NOT EXISTS Requirement_Profile (
            Id INTEGER PRIMARY KEY,
            ProductId INTEGER NOT NULL,
            BomComponentProductId INTEGER NOT NULL,
            RequirementType TEXT NOT NULL,
            RequirementValue TEXT NOT NULL,
            Source TEXT NOT NULL,
            Confidence TEXT NOT NULL CHECK (Confidence IN {CONFIDENCE_VALUES}),
            UNIQUE (ProductId, BomComponentProductId, RequirementType, RequirementValue, Source)
        );

        CREATE TABLE IF NOT EXISTS Review_Decision (
            Id INTEGER PRIMARY KEY,
            OpportunityId INTEGER NOT NULL,
            Status TEXT NOT NULL CHECK (Status IN {STATUS_VALUES}),
            Reviewer TEXT NOT NULL,
            Notes TEXT,
            CreatedAt TEXT NOT NULL,
            FOREIGN KEY (OpportunityId) REFERENCES Opportunity (Id)
        );

        CREATE TABLE IF NOT EXISTS Research_Job (
            Id INTEGER PRIMARY KEY,
            ProductId INTEGER NOT NULL,
            BomComponentProductId INTEGER NOT NULL,
            Status TEXT NOT NULL CHECK (Status IN ('pending', 'running', 'completed', 'failed')),
            ResultJson TEXT,
            ErrorMessage TEXT,
            CreatedAt TEXT NOT NULL,
            UpdatedAt TEXT NOT NULL,
            FOREIGN KEY (ProductId) REFERENCES Product (Id),
            FOREIGN KEY (BomComponentProductId) REFERENCES Product (Id)
        );

        CREATE TABLE IF NOT EXISTS Supplier_Spec (
            Id INTEGER PRIMARY KEY,
            SupplierId INTEGER NOT NULL,
            ProductId INTEGER NOT NULL,
            SpecKey TEXT NOT NULL,
            SpecValue TEXT NOT NULL,
            SpecUnit TEXT,
            SourceUri TEXT,
            SourceType TEXT,
            ExtractedAt TEXT NOT NULL,
            FOREIGN KEY (SupplierId) REFERENCES Supplier (Id),
            FOREIGN KEY (ProductId) REFERENCES Product (Id)
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_supplier_spec_key
            ON Supplier_Spec (SupplierId, ProductId, SpecKey);

        CREATE INDEX IF NOT EXISTS idx_ingredient_alias_alias_name
            ON Ingredient_Alias (AliasName, Approved);
        CREATE INDEX IF NOT EXISTS idx_opportunity_status
            ON Opportunity (Status, MatchType, BlockerState, PriorityScore);
        CREATE INDEX IF NOT EXISTS idx_opportunity_candidate_opportunity
            ON Opportunity_Candidate (OpportunityId);
        CREATE INDEX IF NOT EXISTS idx_evidence_opportunity
            ON Evidence (OpportunityId, OpportunityCandidateId);
        CREATE INDEX IF NOT EXISTS idx_requirement_profile_component
            ON Requirement_Profile (ProductId, BomComponentProductId);
        CREATE INDEX IF NOT EXISTS idx_review_decision_opportunity
            ON Review_Decision (OpportunityId, CreatedAt);
        CREATE INDEX IF NOT EXISTS idx_research_job_lookup
            ON Research_Job (ProductId, BomComponentProductId, Status);
        """
    )
    conn.commit()
    conn.close()


def seed_default_ingredient_aliases(db_path=None):
    conn = get_connection(db_path)
    for row in DEFAULT_INGREDIENT_ALIASES:
        conn.execute(
            """
            INSERT INTO Ingredient_Alias (CanonicalName, AliasName, MatchType, Notes, Approved)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (CanonicalName, AliasName) DO UPDATE SET
                MatchType = excluded.MatchType,
                Notes = excluded.Notes,
                Approved = excluded.Approved
            """,
            (
                row["canonical_name"],
                row["alias_name"],
                row["match_type"],
                row["notes"],
                row["approved"],
            ),
        )
    conn.commit()
    conn.close()


def get_finished_goods(db_path=None):
    conn = get_connection(db_path)
    rows = conn.execute(
        """
        SELECT p.Id AS product_id, p.SKU AS sku, p.CompanyId AS company_id, c.Name AS company_name
        FROM Product p
        JOIN Company c ON p.CompanyId = c.Id
        WHERE p.Type = 'finished-good'
        ORDER BY c.Name, p.SKU
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_product(db_path=None, product_id=None):
    conn = get_connection(db_path)
    row = conn.execute(
        """
        SELECT p.Id AS product_id, p.SKU AS sku, p.Type AS product_type, p.CompanyId AS company_id, c.Name AS company_name
        FROM Product p
        JOIN Company c ON p.CompanyId = c.Id
        WHERE p.Id = ?
        """,
        (product_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_bom_components(db_path=None, product_id=None):
    conn = get_connection(db_path)
    rows = conn.execute(
        """
        SELECT b.Id AS bom_id,
               p2.Id AS product_id,
               p2.SKU AS sku,
               p2.CompanyId AS company_id,
               c.Name AS component_company_name
        FROM BOM b
        JOIN BOM_Component bc ON bc.BOMId = b.Id
        JOIN Product p2 ON p2.Id = bc.ConsumedProductId
        JOIN Company c ON c.Id = p2.CompanyId
        WHERE b.ProducedProductId = ?
        ORDER BY p2.SKU
        """,
        (product_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_suppliers_for_product(db_path=None, product_id=None, detailed=False):
    conn = get_connection(db_path)
    rows = conn.execute(
        """
        SELECT s.Id AS supplier_id, s.Name AS supplier_name
        FROM Supplier_Product sp
        JOIN Supplier s ON sp.SupplierId = s.Id
        WHERE sp.ProductId = ?
        ORDER BY s.Name
        """,
        (product_id,),
    ).fetchall()
    conn.close()
    if detailed:
        return [dict(r) for r in rows]
    return [r["supplier_name"] for r in rows]


def get_all_ingredient_names(db_path=None):
    conn = get_connection(db_path)
    rows = conn.execute("SELECT DISTINCT SKU FROM Product WHERE Type = 'raw-material'").fetchall()
    conn.close()
    return sorted({parse_ingredient_name(r["SKU"]) for r in rows})


def save_ingredient_groups(db_path=None, groups=None):
    init_workspace_schema(db_path)
    conn = get_connection(db_path)
    conn.execute("DELETE FROM Ingredient_Group")
    for g in groups or []:
        conn.execute(
            """
            INSERT INTO Ingredient_Group (canonical_name, function, members, confidence, reasoning)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                g["canonical_name"],
                g["function"],
                json.dumps(g["members"]),
                g["confidence"],
                g["reasoning"],
            ),
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


def get_alias_rows(db_path=None, alias_name=None, include_unapproved=False):
    conn = get_connection(db_path)
    where = "AliasName = ?"
    params = [alias_name]
    if not include_unapproved:
        where += " AND Approved = 1"
    try:
        rows = conn.execute(
            f"""
            SELECT Id, CanonicalName, AliasName, MatchType, Notes, Approved
            FROM Ingredient_Alias
            WHERE {where}
            ORDER BY Approved DESC, MatchType, AliasName
            """,
            params,
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    return [dict(r) for r in rows]


def get_aliases_for_canonical(db_path=None, canonical_name=None, include_unapproved=True):
    conn = get_connection(db_path)
    query = """
        SELECT Id, CanonicalName, AliasName, MatchType, Notes, Approved
        FROM Ingredient_Alias
        WHERE CanonicalName = ?
    """
    params = [canonical_name]
    if not include_unapproved:
        query += " AND Approved = 1"
    query += " ORDER BY Approved DESC, MatchType, AliasName"
    try:
        rows = conn.execute(query, params).fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    return [dict(r) for r in rows]


def get_canonical_alias_mapping(db_path=None, include_unapproved=True):
    conn = get_connection(db_path)
    query = """
        SELECT CanonicalName, AliasName, MatchType, Notes, Approved
        FROM Ingredient_Alias
    """
    if not include_unapproved:
        query += " WHERE Approved = 1"
    try:
        rows = conn.execute(query).fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    mapping = {}
    for row in rows:
        mapping.setdefault(row["AliasName"], []).append(dict(row))
    return mapping


def get_raw_material_products(db_path=None):
    conn = get_connection(db_path)
    product_rows = conn.execute(
        """
        SELECT p.Id AS product_id, p.SKU AS sku, p.CompanyId AS company_id, c.Name AS company_name
        FROM Product p
        JOIN Company c ON p.CompanyId = c.Id
        WHERE p.Type = 'raw-material'
        ORDER BY p.Id
        """
    ).fetchall()
    supplier_rows = conn.execute(
        """
        SELECT sp.ProductId AS product_id, s.Id AS supplier_id, s.Name AS supplier_name
        FROM Supplier_Product sp
        JOIN Supplier s ON s.Id = sp.SupplierId
        """
    ).fetchall()
    conn.close()

    suppliers_by_product = {}
    for row in supplier_rows:
        suppliers_by_product.setdefault(row["product_id"], []).append(
            {"supplier_id": row["supplier_id"], "supplier_name": row["supplier_name"]}
        )

    products = []
    for row in product_rows:
        item = dict(row)
        item["parsed_ingredient_name"] = parse_ingredient_name(item["sku"])
        item["suppliers"] = suppliers_by_product.get(item["product_id"], [])
        products.append(item)
    return products


def get_portfolio_usage_for_names(db_path=None, ingredient_names=None):
    ingredient_names = set(ingredient_names or [])
    if not ingredient_names:
        return []
    conn = get_connection(db_path)
    rows = conn.execute(
        """
        SELECT fg.Id AS finished_product_id,
               fg.SKU AS finished_sku,
               fg.CompanyId AS company_id,
               c.Name AS company_name,
               rm.Id AS raw_material_product_id,
               rm.SKU AS raw_material_sku
        FROM BOM b
        JOIN Product fg ON fg.Id = b.ProducedProductId
        JOIN Company c ON c.Id = fg.CompanyId
        JOIN BOM_Component bc ON bc.BOMId = b.Id
        JOIN Product rm ON rm.Id = bc.ConsumedProductId
        WHERE fg.Type = 'finished-good' AND rm.Type = 'raw-material'
        """
    ).fetchall()
    conn.close()

    usage = []
    for row in rows:
        parsed_name = parse_ingredient_name(row["raw_material_sku"])
        if parsed_name in ingredient_names:
            record = dict(row)
            record["parsed_ingredient_name"] = parsed_name
            usage.append(record)
    return usage


def get_suppliers_with_materials(db_path=None):
    conn = get_connection(db_path)
    rows = conn.execute(
        """
        SELECT s.Id   AS supplier_id,
               s.Name AS supplier_name,
               p.Id   AS product_id,
               p.SKU  AS sku
        FROM Supplier s
        JOIN Supplier_Product sp ON sp.SupplierId = s.Id
        JOIN Product p ON p.Id = sp.ProductId
        WHERE p.Type = 'raw-material'
        ORDER BY s.Name, p.SKU
        """
    ).fetchall()
    conn.close()

    suppliers = {}
    for row in rows:
        sid = row["supplier_id"]
        if sid not in suppliers:
            suppliers[sid] = {
                "supplier_id": sid,
                "supplier_name": row["supplier_name"],
                "materials": [],
            }
        suppliers[sid]["materials"].append(
            {
                "product_id": row["product_id"],
                "sku": row["sku"],
                "ingredient_name": parse_ingredient_name(row["sku"]),
            }
        )
    return list(suppliers.values())


def table_count(db_path=None, table_name=None):
    conn = get_connection(db_path)
    row = conn.execute(f"SELECT COUNT(*) AS cnt FROM {table_name}").fetchone()
    conn.close()
    return row["cnt"]


def create_research_job(db_path=None, product_id=None, component_product_id=None):
    conn = get_connection(db_path)
    now = now_iso()
    conn.execute(
        """
        INSERT INTO Research_Job (ProductId, BomComponentProductId, Status, CreatedAt, UpdatedAt)
        VALUES (?, ?, 'pending', ?, ?)
        """,
        (product_id, component_product_id, now, now),
    )
    job_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    conn.commit()
    conn.close()
    return job_id


def update_research_job(db_path=None, job_id=None, status=None, result_json=None, error_message=None):
    conn = get_connection(db_path)
    conn.execute(
        """
        UPDATE Research_Job
        SET Status = ?, ResultJson = ?, ErrorMessage = ?, UpdatedAt = ?
        WHERE Id = ?
        """,
        (status, result_json, error_message, now_iso(), job_id),
    )
    conn.commit()
    conn.close()


def expire_stale_running_jobs(db_path=None, stale_minutes=30):
    conn = get_connection(db_path)
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=stale_minutes)).isoformat()
    conn.execute(
        """
        UPDATE Research_Job
        SET Status = 'failed', ErrorMessage = 'Job timed out (stuck in running state)', UpdatedAt = ?
        WHERE Status IN ('pending', 'running') AND UpdatedAt < ?
        """,
        (now_iso(), cutoff),
    )
    conn.commit()
    conn.close()


def get_latest_research_job(db_path=None, product_id=None, component_product_id=None):
    conn = get_connection(db_path)
    row = conn.execute(
        """
        SELECT *
        FROM Research_Job
        WHERE ProductId = ? AND BomComponentProductId = ?
        ORDER BY Id DESC
        LIMIT 1
        """,
        (product_id, component_product_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_research_jobs_for_product(db_path=None, product_id=None):
    conn = get_connection(db_path)
    rows = conn.execute(
        """
        SELECT rj.*
        FROM Research_Job rj
        INNER JOIN (
            SELECT BomComponentProductId, MAX(Id) AS MaxId
            FROM Research_Job
            WHERE ProductId = ?
            GROUP BY BomComponentProductId
        ) latest ON rj.Id = latest.MaxId
        ORDER BY rj.Id DESC
        """,
        (product_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def upsert_supplier_spec(db_path=None, supplier_id=None, product_id=None,
                         spec_key=None, spec_value=None, spec_unit=None,
                         source_uri=None, source_type=None):
    conn = get_connection(db_path)
    conn.execute(
        """
        INSERT INTO Supplier_Spec (SupplierId, ProductId, SpecKey, SpecValue, SpecUnit, SourceUri, SourceType, ExtractedAt)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (SupplierId, ProductId, SpecKey)
        DO UPDATE SET SpecValue = excluded.SpecValue,
                      SpecUnit = excluded.SpecUnit,
                      SourceUri = excluded.SourceUri,
                      SourceType = excluded.SourceType,
                      ExtractedAt = excluded.ExtractedAt
        """,
        (supplier_id, product_id, spec_key, spec_value, spec_unit, source_uri, source_type, now_iso()),
    )
    conn.commit()
    conn.close()


def get_supplier_specs(db_path=None, product_id=None):
    conn = get_connection(db_path)
    rows = conn.execute(
        """
        SELECT ss.*, s.Name AS SupplierName
        FROM Supplier_Spec ss
        JOIN Supplier s ON s.Id = ss.SupplierId
        WHERE ss.ProductId = ?
        ORDER BY s.Name, ss.SpecKey
        """,
        (product_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_supplier_id_by_name(db_path=None, supplier_name=None):
    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT Id FROM Supplier WHERE Name = ?",
        (supplier_name,),
    ).fetchone()
    conn.close()
    return row["Id"] if row else None
