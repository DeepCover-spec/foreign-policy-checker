import json

from treaty_checker.db import build_db, connect
from treaty_checker.loader import load_clauses
from treaty_checker.pipeline import check
from treaty_checker.ratifications import load_ratifications
from treaty_checker.retrieval import Retriever

K = 5


def main() -> None:
    build_db()
    conn = connect()
    retriever = Retriever(load_clauses("data/seed_clauses.json"))
    ratifications = load_ratifications()
    with open("tests/test_cases.json", encoding="utf-8") as f:
        cases = json.load(f)

    scored = top1 = topk = 0
    for case in cases:
        found = check(case["text"], case["country"], retriever, conn, ratifications, k=K)
        got = [f.clause.id for f in found]
        expected = case["expected"]

        if not expected:
            status = "PASS" if not got else "FAIL"
            print(f"{status:7} | expects nothing | {case['country']} | {case['text'][:40]}... -> {got}")
            continue

        scored += 1
        rank = next((i + 1 for i, g in enumerate(got) if g in expected), None)
        top1 += rank == 1
        topk += rank is not None
        label = f"rank {rank}" if rank else "MISS"
        print(f"{label:7} | expects {expected} | {case['text'][:40]}... -> {got}")

    print(f"\ntop-1: {top1}/{scored}   top-{K}: {topk}/{scored}")
    conn.close()


if __name__ == "__main__":
    main()