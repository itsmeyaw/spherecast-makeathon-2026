import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.common.db import init_workspace_schema, seed_default_ingredient_aliases

DB_PATH = "db.sqlite"


def init_db(db_path=None):
    target = db_path or DB_PATH
    init_workspace_schema(target)
    seed_default_ingredient_aliases(target)
    print("Workspace tables ready and default ingredient aliases seeded.")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    init_db(path)
