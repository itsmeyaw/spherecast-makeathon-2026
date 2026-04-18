"""
Extract CID, name, CAS, and molecular weight from a PubChem compound JSON file
and upsert the record into a SQLite database table.

Usage:
    python pubchem_to_sqlite.py <json_file> [--db <database.db>]

Defaults:
    --db compounds.db
"""

import json
import sqlite3
import argparse
from pathlib import Path


def find_section(sections: list, heading: str) -> dict | None:
    """Recursively search a Section list for a TOCHeading match."""
    for sec in sections:
        if sec.get("TOCHeading") == heading:
            return sec
        nested = sec.get("Section", [])
        if nested:
            result = find_section(nested, heading)
            if result:
                return result
    return None


def extract_fields(data: dict) -> dict:
    record = data["Record"]
    sections = record.get("Section", [])

    cid = record["RecordNumber"]
    name = record["RecordTitle"]

    # --- CAS: first entry under the 'CAS' TOCHeading ---
    cas = None
    cas_section = find_section(sections, "CAS")
    if cas_section:
        info = cas_section.get("Information", [])
        if info:
            cas = info[0]["Value"]["StringWithMarkup"][0]["String"]

    # --- Molecular Weight ---
    mw = None
    mw_unit = None
    mw_section = find_section(sections, "Molecular Weight")
    if mw_section:
        info = mw_section.get("Information", [])
        if info:
            val = info[0]["Value"]
            mw = float(val["StringWithMarkup"][0]["String"])
            mw_unit = val.get("Unit", "g/mol")

    return {"cid": cid, "name": name, "cas": cas, "molecular_weight": mw, "mw_unit": mw_unit}


def upsert(db_path: str, fields: dict) -> None:
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS compounds (
            cid              INTEGER PRIMARY KEY,
            name             TEXT,
            cas              TEXT,
            molecular_weight REAL,
            mw_unit          TEXT
        )
    """)

    cur.execute("""
        INSERT INTO compounds (cid, name, cas, molecular_weight, mw_unit)
        VALUES (:cid, :name, :cas, :molecular_weight, :mw_unit)
        ON CONFLICT(cid) DO UPDATE SET
            name             = excluded.name,
            cas              = excluded.cas,
            molecular_weight = excluded.molecular_weight,
            mw_unit          = excluded.mw_unit
    """, fields)

    con.commit()
    con.close()
    print(f"Upserted CID {fields['cid']} ({fields['name']}) into '{db_path}'")


def main():
    parser = argparse.ArgumentParser(description="Load PubChem JSON into SQLite")
    parser.add_argument("json_file", help="Path to PubChem compound JSON file")
    parser.add_argument("--db", default="compounds.db", help="SQLite database path")
    args = parser.parse_args()

    json_path = Path(args.json_file)
    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with open(json_path) as f:
        data = json.load(f)

    fields = extract_fields(data)
    print(f"Extracted: {fields}")
    upsert(args.db, fields)


if __name__ == "__main__":
    main()
