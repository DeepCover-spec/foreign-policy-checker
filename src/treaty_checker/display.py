"""Display-only formatting. Never used for storage or matching: it only adds line breaks."""
import re


def paragraphs_for_display(text: str) -> str:
    """Put numbered paragraphs ("1. ... 2. ...") and lettered items ("(a) ...") on their own lines.

    Only whitespace changes: removing the added line breaks gives back the stored text exactly.
    """
    if not re.match(r"1 ?\. (?=[A-Z(])", text):
        return _break_letters(text)
    starts, pos, n = [0], 0, 1
    m = re.compile(r"1 ?\. ").match(text)
    pos = m.end()
    while True:
        n += 1
        m = re.compile(rf"(?<!\S){n} ?\. (?=[A-Z(])").search(text, pos)
        if not m:
            break
        starts.append(m.start())
        pos = m.end()
    chunks = [text[a:b].rstrip() for a, b in zip(starts, starts[1:] + [len(text)])]
    return "\n\n".join(_break_letters(c) for c in chunks)


def _break_letters(text: str) -> str:
    out, pos = [], 0
    for letter in "abcdefghij":
        m = re.compile(rf"(?<!\S)\({letter}\) (?=[A-Z])").search(text, pos)
        if not m:
            break
        out.append((m.start(), m.end()))
        pos = m.end()
    if not out:
        return text
    pieces, last = [], 0
    for start, _end in out:
        pieces.append(text[last:start].rstrip())
        last = start
    pieces.append(text[last:])
    return "\n   ".join(pieces)