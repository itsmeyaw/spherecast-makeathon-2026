import sqlite3
import sys

DB_PATH = "db.sqlite"


def init_db(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH)
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
    conn.commit()
    print("Ingredient_Group table ready.")
    conn.close()


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    init_db(path)
