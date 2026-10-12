import sqlite3
from pathlib import Path

from treaty_checker.loader import load_clauses
from treaty_checker.models import Clause

DB_PATH = Path("data/treaty.db")

SCHEMA = """
CREATE TABLE clauses (
    id           TEXT PRIMARY KEY,
    treaty       TEXT NOT NULL,
    article      TEXT NOT NULL,
    paragraph    TEXT,
    subparagraph TEXT,
    parent_id    TEXT,
    text         TEXT NOT NULL,
    source_url   TEXT NOT NULL,
    verified     INTEGER NOT NULL DEFAULT 0
);
"""


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def build_db(seed_path: str = "data/clauses.json", db_path: Path = DB_PATH) -> None:
    clauses = load_clauses(seed_path)
    conn = connect(db_path)
    conn.executescript("DROP TABLE IF EXISTS clauses;" + SCHEMA)
    conn.executemany(
        "INSERT INTO clauses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (c.id, c.treaty, c.article, c.paragraph, c.subparagraph,
             c.parent_id, c.text, c.source_url, int(c.verified))
            for c in clauses
        ],
    )
    conn.commit()
    conn.close()


def get_clause(clause_id: str, conn: sqlite3.Connection) -> Clause | None:
    row = conn.execute("SELECT * FROM clauses WHERE id = ?", (clause_id,)).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["verified"] = bool(data["verified"])
    return Clause(**data)


if __name__ == "__main__":
    build_db()
    conn = connect()
    c = get_clause("ICCPR-14-3-b", conn)
    print(c.citation)
    print(c.text)
    print(get_clause("NOPE", conn))
    conn.close()