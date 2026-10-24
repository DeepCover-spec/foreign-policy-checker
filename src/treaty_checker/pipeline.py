from dataclasses import dataclass

from treaty_checker.db import build_db, connect, get_clause
from treaty_checker.llm import LLMError, analyze
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
    reasoning: str | None = None   # LLM note (only set by check_llm)
    confidence: str | None = None  # "high" / "medium" / "low" (only set by check_llm)


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


def check_llm(text, country, retriever, conn, ratifications, analyze_fn=analyze):
    """Retrieve a wide candidate list, let the LLM choose from it, validate in code.

    Returns (findings, note). `note` is None, or a message to show the user
    (the LLM step failed and retrieval results are shown instead, a fallback model
    answered, or some IDs were dropped).
    """
    bound = {r.treaty: r for r in bound_by(country, ratifications)}
    if not bound:
        return [], None
    candidates = retriever.candidates(text, set(bound))
    if not candidates:
        return [], None

    try:
        result = analyze_fn(text, candidates)
    except LLMError as e:
        return (check(text, country, retriever, conn, ratifications),
                f"The LLM step failed ({e}). Showing retrieval results only.")

    findings = []
    for m in result.matches:
        clause = get_clause(m.id, conn)  # the quote comes from the database, by ID
        if clause is None:
            raise ValueError(f"{m.id} not found in database")
        parent = get_clause(clause.parent_id, conn) if clause.parent_id else None
        findings.append(Finding(clause, 0.0, bound[clause.treaty], parent, m.reasoning, m.confidence))

    notes = []
    if result.used_fallback:
        notes.append(f"The primary model's daily limit was reached, so this answer came from {result.model}.")
    if result.rejected:
        notes.append(f"Ignored {len(result.rejected)} ID(s) from the model that were not in the candidate list.")
    return findings, " ".join(notes) or None


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