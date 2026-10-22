import json
import sys
import time

from treaty_checker.db import build_db, connect
from treaty_checker.embeddings import HybridRetriever
from treaty_checker.loader import load_clauses
from treaty_checker.pipeline import check, check_llm
from treaty_checker.ratifications import load_ratifications

K = 20


def evaluate(name, run, cases, skip_no_match=False) -> None:
    """`run(case)` returns clause IDs in ranked order."""
    print(f"\n== {name}")
    scored = top1 = top5 = found = returned = 0
    neg_total = neg_pass = 0
    for case in cases:
        if skip_no_match and case.get("no_match"):
            continue
        got = run(case)
        expected = case["expected"]

        if not expected:
            neg_total += 1
            ok = not got
            neg_pass += ok
            status = "PASS" if ok else "FAIL"
            print(f"{status:7} | expects nothing | {case['country']} | {case['text'][:40]}... -> {got[:5]}")
            continue

        scored += 1
        returned += len(got)
        rank = next((i + 1 for i, g in enumerate(got) if g in expected), None)
        top1 += rank == 1
        top5 += rank is not None and rank <= 5
        found += rank is not None
        label = f"rank {rank}" if rank else "MISS"
        print(f"{label:7} | expects {expected} | {case['text'][:40]}... -> {got[:5]}")
    print(f"top-1: {top1}/{scored}   top-5: {top5}/{scored}   found: {found}/{scored}"
          f"   avg returned: {returned / max(scored, 1):.1f}")
    if neg_total:
        print(f"no-match cases passed: {neg_pass}/{neg_total}")


def main() -> None:
    build_db()
    conn = connect()
    clauses = load_clauses("data/clauses.json")
    ratifications = load_ratifications()
    with open("tests/test_cases.json", encoding="utf-8") as f:
        cases = json.load(f)

    hybrid = HybridRetriever(clauses)  # holds the BM25 and embedding retrievers too

    def with_retriever(retriever):
        def run(case):
            found = check(case["text"], case["country"], retriever, conn, ratifications, k=K)
            return [f.clause.id for f in found]
        return run

    evaluate("bm25", with_retriever(hybrid.bm25), cases, skip_no_match=True)
    evaluate("embeddings", with_retriever(hybrid.emb), cases, skip_no_match=True)
    evaluate("hybrid", with_retriever(hybrid), cases, skip_no_match=True)

    if "--llm" in sys.argv:
        def run_llm(case):
            findings, note = check_llm(case["text"], case["country"], hybrid, conn, ratifications)
            if note:
                print(f"        note: {note}")
            time.sleep(2.5)  # stay under free-tier requests-per-minute limits
            return [f.clause.id for f in findings]
        evaluate("llm (chooses from bm25 top-10 + embeddings top-20)", run_llm, cases)
    conn.close()


if __name__ == "__main__":
    main()