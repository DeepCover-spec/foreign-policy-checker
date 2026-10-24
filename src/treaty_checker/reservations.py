"""Find which reservations/declarations mention a given article.

A reservation that names the matched article may limit the country's obligation, so the app
shows those first. This is plain text matching: it flags reservations for a human to read,
it does not decide whether a reservation actually applies.
"""
import re

_ITEM = r"\d+(?:\s*\([^)]*\))*"  # "14" or "14(3)" or "30 (2)"
_SEP = r"(?:\s*,\s*(?:and\s+)?|\s+and\s+|\s*[-\u2013]\s*|\s+(?:to|through)\s+)"
_RANGE_SEP = re.compile(r"^\s*(?:[-\u2013]|to|through)\s*$")
_SPAN = re.compile(rf"\b[Aa]rticles?\s+({_ITEM}(?:{_SEP}{_ITEM})*)")


def articles_mentioned(text: str) -> set[int]:
    """Article numbers named in `text`, e.g. 'articles 10-14 and 16' -> {10, 11, 12, 13, 14, 16}."""
    found: set[int] = set()
    for m in _SPAN.finditer(text):
        parts = re.split(f"({_SEP})", m.group(1))  # items and separators, alternating
        numbers = [int(re.match(r"\d+", p).group()) for p in parts[0::2]]
        found.add(numbers[0])
        for sep, prev, nxt in zip(parts[1::2], numbers, numbers[1:]):
            if _RANGE_SEP.match(sep) and prev < nxt:
                found.update(range(prev, nxt + 1))
            else:
                found.add(nxt)
    return found


def split_reservations(reservations: list[str], article: int) -> tuple[list[str], list[str]]:
    """(mentions this article, everything else)."""
    relevant = [r for r in reservations if article in articles_mentioned(r)]
    others = [r for r in reservations if r not in relevant]
    return relevant, others