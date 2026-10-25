"""Split a treaty's text (extracted by extract.py) into Clause records and merge them into clauses.json.

Usage (from the project root):
    python src\\treaty_checker\\parse_treaty.py CAT data/raw/cat.txt 16 https://www.ohchr.org/sites/default/files/cat.pdf
    python src\\treaty_checker\\parse_treaty.py ICCPR data/raw/ccpr.txt 27 https://www.ohchr.org/sites/default/files/ccpr.pdf

Arguments: TREATY  RAW_TEXT_PATH  LAST_ARTICLE  SOURCE_URL  [OUTPUT_JSON, default data/clauses.json]
Option:    --whole=1,5   keep these articles as one clause each (not split into paragraphs and items)
Records of other treaties already in the output file are kept. Records of this treaty are replaced,
keeping any `verified` flag whose text is unchanged.
"""
import json
import re
import sys
from pathlib import Path


def collapse(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def drop_page_numbers(raw: str) -> str:
    """Remove lines holding only a number (page numbers left by the PDF extraction).
    A number line directly under a bare "Article" line is kept: it is a split heading."""
    out, prev = [], ""
    for line in raw.split("\n"):
        if re.fullmatch(r"[ \t]*\d{1,3}[ \t]*", line) and prev != "Article":
            continue
        out.append(line)
        if line.strip():
            prev = line.strip()
    return "\n".join(out)


def roman_to_int(s: str) -> int:
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    total = 0
    for i, ch in enumerate(s):
        v = values[ch]
        total += -v if i + 1 < len(s) and values[s[i + 1]] > v else v
    return total


def roman_headings_to_arabic(raw: str) -> str:
    """Turn lines such as "Article IV" into "Article 4" (headings only: cross-references in the text
    use a lowercase "article" or sit inside a sentence, so they are left alone)."""
    return re.sub(r"(?m)^[ \t]*Article[ \t]+([IVXLC]+)[ \t]*$",
                  lambda m: f"Article {roman_to_int(m.group(1))}", raw)


def split_articles(raw: str, last_article: int) -> dict[int, str]:
    raw = re.sub(r"(?m)^[ \t]*PART [IVX]+[ \t]*$", "", raw)
    # "Chapter II" followed by an all-capitals title line, between articles
    raw = re.sub(r"(?m)^[ \t]*Chapter [IVX]+[ \t]*\n[ \t]*[A-Z][A-Z ,\-]*\n", "", raw)
    # Find "Article N" for N = 1, 2, 3 ... in order. The heading may be split across
    # two lines in the PDF ("Article" / "12"), so allow any whitespace after "Article".
    # A title may follow on the same line ("Article 1 - Definition of the term ...").
    heads, pos = [], 0
    for n in range(1, last_article + 2):  # one extra, to mark where the last article ends
        m = re.compile(rf"Article\s+{n}(?:[ \t]*[-\u2013\u2014.][^\n]*)?[ \t]*\n").search(raw, pos)
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
    first = re.search(r"(?<!\S)1 ?\. (?=[A-Z(])", body)
    if not first:
        return []
    # before "1." allow a lead-in sentence ending in ":" ("The States Parties recognize that:")
    # or a short article title without a full stop ("Equality and non-discrimination")
    lead = body[: first.start()].strip()
    if lead and not (lead.endswith(":") or (len(lead) <= 100 and not lead.endswith("."))):
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
    for letter in "abcdefghijklmnopqrstuvwxyz":
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


def rec(treaty, source_url, id_, article, paragraph, sub, parent, text):
    return {
        "id": id_, "treaty": treaty, "article": str(article),
        "paragraph": paragraph, "subparagraph": sub, "parent_id": parent,
        "text": text, "source_url": source_url, "verified": False,
    }


def build(raw: str, treaty: str, source_url: str, last_article: int, whole: set[int] = frozenset()) -> list[dict]:
    """`whole`: articles kept as one clause, not split into paragraphs and items."""
    records = []
    for art, body in split_articles(raw, last_article).items():
        art_id = f"{treaty}-{art}"
        records.append(rec(treaty, source_url, art_id, art, None, None, None, body))
        if art in whole:
            continue
        paras = split_paragraphs(body)
        if not paras:  # no numbered paragraphs: lettered items may hang off the article
            for letter, t in split_subparagraphs(body):
                records.append(rec(treaty, source_url, f"{art_id}-{letter}", art, None, letter, art_id, t))
            continue
        for num, ptext in paras:
            p_id = f"{art_id}-{num}"
            records.append(rec(treaty, source_url, p_id, art, num, None, art_id, ptext))
            for letter, t in split_subparagraphs(ptext):
                records.append(rec(treaty, source_url, f"{p_id}-{letter}", art, num, letter, p_id, t))
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
    args = [a for a in sys.argv[1:] if not a.startswith("--whole=")]
    whole = {int(n) for a in sys.argv[1:] if a.startswith("--whole=") for n in a[8:].split(",") if n}
    if len(args) < 4:
        raise SystemExit("Usage: parse_treaty.py TREATY RAW_TEXT_PATH LAST_ARTICLE SOURCE_URL [OUTPUT_JSON] "
                         "[--whole=1,5]")
    treaty = args[0]
    raw_path = args[1]
    last_article = int(args[2])
    source_url = args[3]
    out_path = Path(args[4] if len(args) > 4 else "data/clauses.json")

    raw = roman_headings_to_arabic(drop_page_numbers(Path(raw_path).read_text(encoding="utf-8")))
    records = build(raw, treaty, source_url, last_article, whole)
    check(records, raw)

    print("article: paragraphs / lettered items")
    for art in range(1, last_article + 1):
        mine = [r for r in records if r["article"] == str(art)]
        paras = [r["paragraph"] for r in mine if r["paragraph"] and not r["subparagraph"]]
        subs = [(r["paragraph"] or "-") + r["subparagraph"] for r in mine if r["subparagraph"]]
        print(f"  {art:>2}: {len(paras)} para {' '.join(subs)}")
    print(len(records), "records")

    if treaty == "ICCPR":
        compare_with_seed(records, "data/seed_clauses.json")

    # merge: keep other treaties, keep earlier manual verification when the text is unchanged
    others, old = [], {}
    if out_path.exists():
        for r in json.loads(out_path.read_text(encoding="utf-8")):
            if r["treaty"] == treaty:
                old[r["id"]] = r
            else:
                others.append(r)
    for r in records:
        if r["id"] in old and old[r["id"]]["text"] == r["text"]:
            r["verified"] = old[r["id"]]["verified"]

    out_path.write_text(json.dumps(others + records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}: {len(others)} records of other treaties + {len(records)} {treaty} records")