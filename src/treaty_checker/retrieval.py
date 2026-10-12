import re

import snowballstemmer
from rank_bm25 import BM25Okapi

from treaty_checker.models import Clause

_stemmer = snowballstemmer.stemmer("english")

STOPWORDS = {
    "a", "an", "the", "of", "to", "and", "or", "in", "on", "for", "be", "is",
    "are", "shall", "any", "may", "with", "by", "at", "as", "it", "his", "him",
    "he", "that", "this", "such",
    "has", "no", "their", "them", "there",
}


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return _stemmer.stemWords([w for w in words if w not in STOPWORDS])


class Retriever:
    def __init__(self, clauses: list[Clause]):
        # Index only the smallest units (clauses nobody else points to as a parent).
        # Their parents are for display context only.
        parents = {c.parent_id for c in clauses if c.parent_id}
        self.clauses = [c for c in clauses if c.id not in parents]
        self.bm25 = BM25Okapi([tokenize(c.text) for c in self.clauses])

    def search(self, query: str, treaties: set[str], k: int = 5) -> list[tuple[Clause, float]]:
        scores = self.bm25.get_scores(tokenize(query))
        ranked = sorted(zip(self.clauses, scores), key=lambda p: p[1], reverse=True)
        return [(c, s) for c, s in ranked if c.treaty in treaties and s > 0][:k]


if __name__ == "__main__":
    from treaty_checker.loader import load_clauses
    from treaty_checker.ratifications import bound_by, load_ratifications

    clauses = load_clauses("data/clauses.json")
    treaties = {r.treaty for r in bound_by("Sri Lanka", load_ratifications())}
    retriever = Retriever(clauses)

    queries = [
        "The government may arrest and detain any person without telling them the reason.",
        "A suspect has no right to a lawyer of their own choosing.",
    ]
    for q in queries:
        print(q)
        for clause, score in retriever.search(q, treaties):
            print(f"  {score:5.2f} | {clause.id} | {clause.citation}")