from sentence_transformers import SentenceTransformer

from treaty_checker.models import Clause
from treaty_checker.retrieval import Retriever

MODEL_NAME = "all-MiniLM-L6-v2"


class EmbeddingRetriever:
    """Ranks clauses by meaning (cosine similarity), not by shared words."""

    def __init__(self, clauses: list[Clause]):
        parents = {c.parent_id for c in clauses if c.parent_id}
        self.clauses = [c for c in clauses if c.id not in parents]  # smallest units only
        self.model = SentenceTransformer(MODEL_NAME)
        self.vectors = self.model.encode(
            [c.text for c in self.clauses], normalize_embeddings=True
        )

    def search(self, query: str, treaties: set[str], k: int = 5) -> list[tuple[Clause, float]]:
        q = self.model.encode([query], normalize_embeddings=True)[0]
        scores = self.vectors @ q  # vectors are unit length, so this is cosine similarity
        ranked = sorted(zip(self.clauses, scores), key=lambda p: p[1], reverse=True)
        return [(c, float(s)) for c, s in ranked if c.treaty in treaties][:k]


class HybridRetriever:
    """Combines BM25 and embedding rankings with reciprocal rank fusion."""

    def __init__(self, clauses: list[Clause], rrf_k: int = 60):
        self.bm25 = Retriever(clauses)
        self.emb = EmbeddingRetriever(clauses)
        self.rrf_k = rrf_k

    def search(self, query: str, treaties: set[str], k: int = 5, pool: int = 20):
        fused: dict[str, float] = {}
        by_id: dict[str, Clause] = {}
        for retriever in (self.bm25, self.emb):
            for rank, (c, _score) in enumerate(retriever.search(query, treaties, pool), start=1):
                fused[c.id] = fused.get(c.id, 0.0) + 1.0 / (self.rrf_k + rank)
                by_id[c.id] = c
        ranked = sorted(fused.items(), key=lambda p: p[1], reverse=True)[:k]
        return [(by_id[i], score) for i, score in ranked]

    def candidates(self, query: str, treaties: set[str],
                   bm25_n: int = 10, emb_n: int = 20) -> list[Clause]:
        """A wide candidate list for the LLM: the top results of each method, combined.

        Not a fused top-k: a clause that only one method ranks well must still get through,
        because the two methods miss different things.
        """
        seen: dict[str, Clause] = {}
        for retriever, n in ((self.bm25, bm25_n), (self.emb, emb_n)):
            for c, _score in retriever.search(query, treaties, n):
                seen.setdefault(c.id, c)
        return list(seen.values())