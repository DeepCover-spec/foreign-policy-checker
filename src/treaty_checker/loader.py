import json
from pathlib import Path

from treaty_checker.models import Clause


def load_clauses(path: str | Path) -> list[Clause]:
    with open(path, encoding="utf-8") as f:
        records = json.load(f)
    clauses = [Clause(**record) for record in records]
    check_clauses(clauses)
    return clauses


def check_clauses(clauses: list[Clause]) -> None:
    ids = [c.id for c in clauses]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate clause IDs in seed file")
    known = set(ids)
    for c in clauses:
        if c.parent_id is not None and c.parent_id not in known:
            raise ValueError(f"{c.id}: parent {c.parent_id} not found")


if __name__ == "__main__":
    for c in load_clauses("data/seed_clauses.json"):
        print(c.id, "|", c.citation, "|", c.text[:50])