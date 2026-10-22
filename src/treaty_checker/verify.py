"""Show clauses so you can compare them with the PDF, then mark the ones that match as verified.

Usage (from the project root):
    python src\\treaty_checker\\verify.py ICCPR-9-2 ICCPR-14-3-b ICCPR-19-2 ICCPR-4-2 ICCPR-25-b
"""
import json
import sys
from pathlib import Path

PATH = Path("data/clauses.json")


def main(ids: list[str]) -> None:
    records = json.loads(PATH.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in records}
    changed = 0
    for clause_id in ids:
        r = by_id.get(clause_id)
        if r is None:
            print(f"\n{clause_id}: not found, skipped")
            continue
        print(f"\n=== {clause_id} (verified: {r['verified']}) ===")
        print(r["text"])
        answer = input("Identical to the PDF, word for word? [y/N] ").strip().lower()
        if answer == "y":
            r["verified"] = True
            changed += 1
    PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total = sum(r["verified"] for r in records)
    print(f"\nMarked {changed} as verified. Total verified: {total}/{len(records)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Give one or more clause IDs")
    main(sys.argv[1:])