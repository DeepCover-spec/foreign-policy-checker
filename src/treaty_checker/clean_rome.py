"""Clean the ICC's consolidated Rome Statute text (made by extract_mupdf.py) so parse_treaty.py can read it.

Usage (from the project root):
    python src\\treaty_checker\\clean_rome.py data\\raw\\rome.txt data\\raw\\rome_clean.txt
"""
import re
import sys
from pathlib import Path

HEADER = "Rome Statute of the International Criminal Court"
EXTRA = {8: ["8 bis"], 15: ["15 bis", "15 ter"]}  # articles inserted after these base articles


def labels(last=128):
    """Heading labels in order: "1", "2", ..., "8", "8 bis", "9", ..."""
    out = []
    for n in range(1, last + 1):
        out.append(str(n))
        out += EXTRA.get(n, [])
    return out


def clean(raw: str) -> str:
    # drop the cover, the table of contents and the preamble: the text starts after this line
    raw = raw.split("Have agreed as follows:", 1)[1]
    # footnotes: a line holding only "N" + a tab, up to the page-number line that precedes the running header
    foot = rf"(?ms)^\d{{1,3}}\t\n.*?(?=^\d{{1,3}}\n{HEADER}\n|\Z)"
    raw = re.sub(foot, "", raw)
    # the page number and running header at the top of each page
    raw = re.sub(rf"(?m)^\d{{1,3}}\n{HEADER}\n", "", raw)
    # "PART 2." and its capitals title (which may wrap over two lines)
    raw = re.sub(r"(?m)^PART \d+\.[ \t]*\n(?:[A-Z][A-Z ,\-]*\n)+", "", raw)
    # footnote numbers stuck to headings: "Article 51" -> "Article 5", "Article 8 bis4" -> "Article 8 bis".
    # Headings come in a known order, so only the next expected heading is accepted.
    expected, out = labels(), []
    for line in raw.split("\n"):
        if expected and re.fullmatch(rf"Article[ \t]+{re.escape(expected[0])}[\d ,]*[ \t]*", line):
            line = f"Article {expected.pop(0)}"
        out.append(line)
    raw = "\n".join(out)
    # cut the closing formula and add an end marker, which the parser needs after the last article
    return raw.split("In Witness Whereof", 1)[0] + "\nArticle 129\n"


if __name__ == "__main__":
    Path(sys.argv[2]).write_text(clean(Path(sys.argv[1]).read_text(encoding="utf-8")), encoding="utf-8")