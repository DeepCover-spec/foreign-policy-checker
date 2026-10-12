from dataclasses import dataclass

from treaty_checker.db import build_db, connect, get_clause
from treaty_checker.loader import load_clauses
from treaty_checker.models import Clause, Ratification
from treaty_checker.ratifications import bound_by, load_ratifications
from treaty_checker.retrieval import Retriever


@dataclass(frozen=True)
class Finding:
    clause: Clause            # loaded from the database, never written by a model
    score: float
    ratification: Ratification
    parent: Clause | None     # the whole article or paragraph, for context


def check(text, country, retriever, conn, ratifications, k=5) -> list[Finding]:
    bound = {r.treaty: r for r in bound_by(country, ratifications)}
    findings = []
    for hit, score in retriever.search(text, set(bound), k):
        clause = get_clause(hit.id, conn)  # the quote comes from the database, by ID
        if clause is None:
            raise ValueError(f"{hit.id} not found in database")
        parent = get_clause(clause.parent_id, conn) if clause.parent_id else None
        findings.append(Finding(clause, score, bound[clause.treaty], parent))
    return findings


if __name__ == "__main__":
    build_db()
    conn = connect()
    retriever = Retriever(load_clauses("data/clauses.json"))
    ratifications = load_ratifications()

    text = "The government may arrest and detain any person without telling them the reason."
    for country in ["Sri Lanka", "United States", "Cuba"]:
        print("==", country)
        for f in check(text, country, retriever, conn, ratifications):
            r = f.ratification
            print(f"{f.score:5.2f} | {f.clause.citation} | {r.status} {r.date}"
                  f" | {len(r.reservations)} reservation(s)")
            print("      ", f.clause.text[:80])
    conn.close()