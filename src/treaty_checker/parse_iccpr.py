"""Split the ICCPR text (extracted by extract.py) into Clause records.

Usage (from the project root):
    python src\\treaty_checker\\parse_iccpr.py
Reads  data/raw/ccpr.txt   Writes data/clauses.json
"""
import json
import re
import sys
from pathlib import Path

TREATY = "ICCPR"
SOURCE_URL = "https://www.ohchr.org/sites/default/files/ccpr.pdf"
LAST_ARTICLE = 27  # Parts I-III (substantive rights). Part IV onwards is Committee machinery.


def collapse(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def split_articles(raw: str) -> dict[int, str]:
    raw = re.sub(r"(?m)^[ \t]*PART [IVX]+[ \t]*$", "", raw)
    # Find "Article N" for N = 1, 2, 3 ... in order. The heading may be split across
    # two lines in the PDF ("Article" / "12"), so allow any whitespace after "Article".
    heads, pos = [], 0
    for n in range(1, LAST_ARTICLE + 2):  # one extra, to mark where the last article ends
        m = re.compile(rf"Article\s+{n}[ \t]*\n").search(raw, pos)
        if not m:
            raise SystemExit(f"Could not find the heading for Article {n}")
        heads.append((n, m))
        pos = m.end()
    articles = {}
    for (n, m), (_, nxt) in zip(heads, heads[1:]):
        articles[n] = collapse(raw[m.end() : nxt.start()])
    return articles


def split_paragraphs(body: str) -> list[tuple[str, str]]:
    """[(number, text)] if the article has numbered paragraphs 1., 2., ... else []."""
    if not re.match(r"1 ?\. (?=[A-Z(])", body):
        return []
    marks, pos, n = [], 0, 1
    while True:
        m = re.compile(rf"(?<!\S){n} ?\. (?=[A-Z(])").search(body, pos)
        if not m:
            break
        marks.append((str(n), m.start(), m.end()))
        pos, n = m.end(), n + 1
    out = []
    for i, (num, _start, end) in enumerate(marks):
        stop = marks[i + 1][1] if i + 1 < len(marks) else len(body)
        out.append((num, body[end:stop].strip()))
    return out


def split_subparagraphs(text: str) -> list[tuple[str, str]]:
    """[(letter, text)] for inline (a), (b), ... markers, else []."""
    marks, pos = [], 0
    for letter in "abcdefghij":
        m = re.compile(rf"(?<!\S)\({letter}\) (?=[A-Z])").search(text, pos)
        if not m:
            break
        marks.append((letter, m.start(), m.end()))
        pos = m.end()
    out = []
    for i, (letter, _start, end) in enumerate(marks):
        stop = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        out.append((letter, text[end:stop].strip()))
    return out


def rec(id_, article, paragraph, sub, parent, text):
    return {
        "id": id_, "treaty": TREATY, "article": str(article),
        "paragraph": paragraph, "subparagraph": sub, "parent_id": parent,
        "text": text, "source_url": SOURCE_URL, "verified": False,
    }


def build(raw: str) -> list[dict]:
    records = []
    for art, body in split_articles(raw).items():
        art_id = f"{TREATY}-{art}"
        records.append(rec(art_id, art, None, None, None, body))
        paras = split_paragraphs(body)
        if not paras:  # no numbered paragraphs: lettered items may hang off the article
            for letter, t in split_subparagraphs(body):
                records.append(rec(f"{art_id}-{letter}", art, None, letter, art_id, t))
            continue
        for num, ptext in paras:
            p_id = f"{art_id}-{num}"
            records.append(rec(p_id, art, num, None, art_id, ptext))
            for letter, t in split_subparagraphs(ptext):
                records.append(rec(f"{p_id}-{letter}", art, num, letter, p_id, t))
    return records


def check(records: list[dict], raw: str) -> None:
    src = collapse(raw)
    by_id = {r["id"]: r for r in records}
    assert len(by_id) == len(records), "duplicate ids"
    for r in records:
        assert r["text"] and r["text"] in src, f"{r['id']}: text not verbatim in source"
        assert "PART " not in r["text"], f"{r['id']}: contains a PART heading"
        if r["parent_id"]:
            parent = by_id[r["parent_id"]]  # KeyError if the parent is missing
            assert r["text"] in parent["text"], f"{r['id']}: not inside its parent"
    # siblings must appear in order inside the parent
    kids: dict[str, list[dict]] = {}
    for r in records:
        if r["parent_id"]:
            kids.setdefault(r["parent_id"], []).append(r)
    for pid, children in kids.items():
        at = 0
        for c in children:
            i = by_id[pid]["text"].find(c["text"], at)
            assert i >= 0, f"{c['id']}: out of order inside {pid}"
            at = i + len(c["text"])


def compare_with_seed(records: list[dict], seed_path: str) -> None:
    if not Path(seed_path).exists():
        return
    by_id = {r["id"]: r for r in records}
    seed = json.load(open(seed_path, encoding="utf-8"))
    bad = 0
    for s in seed:
        mine = by_id.get(s["id"])
        if mine is None or mine["text"] != s["text"]:
            bad += 1
            print(f"  DIFFERS from seed: {s['id']}")
    print(f"Seed comparison: {len(seed) - bad}/{len(seed)} seed clauses identical")


if __name__ == "__main__":
    raw_path = sys.argv[1] if len(sys.argv) > 1 else "data/raw/ccpr.txt"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "data/clauses.json"
    raw = Path(raw_path).read_text(encoding="utf-8")
    records = build(raw)
    check(records, raw)

    print("article: paragraphs / lettered items")
    for art in range(1, LAST_ARTICLE + 1):
        mine = [r for r in records if r["article"] == str(art)]
        paras = [r["paragraph"] for r in mine if r["paragraph"] and not r["subparagraph"]]
        subs = [(r["paragraph"] or "-") + r["subparagraph"] for r in mine if r["subparagraph"]]
        print(f"  {art:>2}: {len(paras)} para {' '.join(subs)}")
    print(len(records), "records")

    compare_with_seed(records, "data/seed_clauses.json")

    # keep earlier manual verification when the text is unchanged
    if Path(out_path).exists():
        old = {r["id"]: r for r in json.loads(Path(out_path).read_text(encoding="utf-8"))}
        for r in records:
            if r["id"] in old and old[r["id"]]["text"] == r["text"]:
                r["verified"] = old[r["id"]]["verified"]

    Path(out_path).write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Wrote", out_path)