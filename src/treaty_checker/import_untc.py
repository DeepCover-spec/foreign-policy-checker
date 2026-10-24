"""Import ratification status and reservations from a UN Treaty Collection page that you saved yourself.

In your browser: open the treaty's page on treaties.un.org, scroll to the bottom once, press Ctrl+S and
save as "Webpage, HTML only". This script only reads that file; it makes no requests to the UN.

Usage (from the project root):
    python src\\treaty_checker\\import_untc.py CAT data/raw/untc/cat.html "<page URL>"
    python src\\treaty_checker\\import_untc.py CAT data/raw/untc/cat.html "<page URL>" data/ratifications.json

Entries for this treaty already in the ratifications file are compared with the import (so hand-entered
data can be checked) and then replaced. Entries for other treaties are kept.
"""
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# The UN's long names -> the shorter names already used in ratifications.json
NAME_MAP = {
    "United Kingdom of Great Britain and Northern Ireland": "United Kingdom",
    "United States of America": "United States",
}
SUFFIX_STATUS = {"": "ratified", "a": "acceded", "d": "succeeded", "A": "accepted", "AA": "approved"}
BINDING = {"ratified", "acceded", "succeeded"}  # what the app currently treats as bound


def clean_name(fragment: str) -> str:
    fragment = re.sub(r"(?is)<sup>.*?</sup>", "", fragment)
    fragment = re.sub(r"(?s)<[^>]+>", "", fragment)
    name = re.sub(r"\s+", " ", html.unescape(fragment).replace("\xa0", " ")).strip()
    return NAME_MAP.get(name, name)


def note_numbers(fragment: str) -> list[str]:
    numbers = [n for sup in re.findall(r"(?is)<sup>(.*?)</sup>", fragment) for n in re.findall(r"\d+", sup)]
    return list(dict.fromkeys(numbers))  # no duplicates, order kept


def lines_from_html(fragment: str) -> list[tuple[bool, str]]:
    """[(is_label, text)]: the text of a fragment, one entry per line.

    The UN's markup is malformed. A heading such as "Reservations:" always starts a paragraph with
    `<p align=left><i>`; italics anywhere else are inline emphasis and are kept as plain text.
    """
    fragment = re.sub(r"(?is)<p class='invisible'>.*?</p>", "", fragment)
    fragment = re.sub(r"(?is)<p[^>]*align=left[^>]*>\s*(?:<i>\s*)+", "\n@@L@@", fragment)
    fragment = re.sub(r"(?i)<br\s*/?>|</n>|</?p[^>]*>", "\n", fragment)
    fragment = re.sub(r"(?s)<[^>]+>", "", fragment)
    out = []
    for line in html.unescape(fragment).replace("\xa0", " ").split("\n"):
        label = line.startswith("@@L@@")
        line = re.sub(r"\s+", " ", line.replace("@@L@@", "")).strip()
        if line:
            out.append((label, line))
    return out


def reservation_entries(fragment: str) -> list[str]:
    """Each paragraph of reservation text, prefixed with its heading ("Reservations: ...")."""
    entries, labels = [], []
    last_was_label = False
    for is_label, text in lines_from_html(fragment):
        if is_label:
            if not last_was_label:
                labels = []
            labels.append(re.sub(r"\s*:\s*$", "", text).strip())
            last_was_label = True
        else:
            entries.append(f"{' / '.join(labels)}: {text}" if labels else text)
            last_was_label = False
    return entries


def parse_date(text: str) -> str:
    return datetime.strptime(re.sub(r"\s+", " ", text).strip(), "%d %b %Y").strftime("%Y-%m-%d")


def parse_page(page: str) -> dict:
    m = re.search(r"STATUS AS AT\s*:\s*(\d{2})-(\d{2})-(\d{4})", page)
    if not m:
        raise SystemExit("Could not find the 'STATUS AS AT' line: is this a saved UN Treaty Collection page?")
    status_date = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"

    # participants table
    start = page.find('id="participants"')
    table = page[start : page.find("</table>", start)]
    header = re.search(r"(?is)<tr class=\"thead-one\">(.*?)</tr>", table)
    header_notes = set(note_numbers(header.group(1))) if header else set()
    rows = []
    for tr in re.findall(r"(?is)<tr class=\"trB[^\"]*\">(.*?)</tr>", table):
        tds = re.findall(r"(?is)<td[^>]*>(.*?)</td>", tr)
        if len(tds) != 3:
            raise SystemExit(f"Unexpected row layout: {tr[:200]!r}")
        name = clean_name(tds[0])
        sig = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", tds[1])).replace("\xa0", " ")).strip()
        rat = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", tds[2])).replace("\xa0", " ")).strip()
        rows.append({"country": name, "signature": sig, "ratification": rat,
                     "notes": [n for n in note_numbers(tds[0]) if n not in header_notes]})  # more added below

    # declarations and reservations
    a = page.find('_dgDec"')
    block = page[a : page.find("</table>", a)]
    decls, decl_notes = {}, {}
    for name_html, text_html in re.findall(
            r'(?is)divParticipant" class="heading-two">(.*?)</div>\s*<div id="[^"]*divText" class="content-two">(.*?)</div>',
            block):
        decls[clean_name(name_html)] = reservation_entries(text_html)
        decl_notes[clean_name(name_html)] = [n for n in note_numbers(name_html) if n not in header_notes]

    # footnotes
    notes = {}
    for num, text_html in re.findall(
            r"(?is)divNotesAll\"[^>]*><a name='(\d+)'>\d+</a><index></index>(.*?)</div>", page):
        notes[num] = " ".join(t for _, t in lines_from_html(text_html))
    for row in rows:  # footnotes can be marked in the table, in the reservations list, or both
        row["notes"] = list(dict.fromkeys(row["notes"] + decl_notes.get(row["country"], [])))
    return {"status_date": status_date, "rows": rows, "decls": decls, "notes": notes}


def build_entries(treaty: str, url: str, parsed: dict) -> list[dict]:
    entries = []
    for row in parsed["rows"]:
        rat = row["ratification"]
        m = re.match(r"^(\d{1,2} \w{3} \d{4})\s*(\S*)$", rat)
        if m:
            suffix = m.group(2)
            if suffix not in SUFFIX_STATUS:
                raise SystemExit(f"{row['country']}: unknown status code {suffix!r} in {rat!r}")
            status, date = SUFFIX_STATUS[suffix], parse_date(m.group(1))
        elif rat:
            raise SystemExit(f"{row['country']}: cannot read {rat!r}")
        elif row["signature"]:
            status, date = "signed", parse_date(row["signature"])
        else:
            continue  # neither signed nor joined
        reservations = list(parsed["decls"].get(row["country"], []))
        reservations += [f"UN note {n}: {parsed['notes'][n]}" for n in row["notes"] if n in parsed["notes"]]
        entries.append({"country": row["country"], "treaty": treaty, "status": status, "date": date,
                        "reservations": reservations, "source_url": url, "retrieved_on": parsed["status_date"]})
    return sorted(entries, key=lambda e: e["country"])


def compare(old: list[dict], new: list[dict]) -> None:
    by_country = {e["country"]: e for e in new}
    for o in old:
        n = by_country.get(o["country"])
        if n is None:
            print(f"  CHECK  {o['country']}: in the old file, not in the import")
            continue
        problems = []
        if o["status"] != n["status"]:
            problems.append(f"status {o['status']} -> {n['status']}")
        if o.get("date") != n["date"]:
            problems.append(f"date {o.get('date')} -> {n['date']}")
        old_res = [re.sub(r"\W+", " ", r).strip().lower() for r in o["reservations"]]
        new_res = [re.sub(r"\W+", " ", r).strip().lower() for r in n["reservations"]]
        missing = [r for r in old_res if not any(r[-120:] in x for x in new_res)]
        if missing:
            problems.append(f"{len(missing)} of {len(old_res)} old reservation(s) not found in the import")
        print(f"  {'OK    ' if not problems else 'DIFFERS'} {o['country']}: " + ("; ".join(problems) or
              f"same status/date, {len(o['reservations'])} old vs {len(n['reservations'])} imported reservation entries"))


if __name__ == "__main__":
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    treaty, html_path, url = sys.argv[1], sys.argv[2], sys.argv[3]
    out_path = Path(sys.argv[4] if len(sys.argv) > 4 else "data/ratifications.json")

    parsed = parse_page(Path(html_path).read_text(encoding="utf-8", errors="replace"))
    entries = build_entries(treaty, url, parsed)
    counts: dict[str, int] = {}
    for e in entries:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    print(f"Status as at {parsed['status_date']}: {len(entries)} participants {counts}")
    print(f"{sum(1 for e in entries if e['reservations'])} with reservations/declarations/notes")
    odd = sorted(s for s in counts if s not in BINDING and s != "signed")
    if odd:
        print(f"WARNING: statuses {odd} are legally binding but the app does not count them as bound yet.")

    existing = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else []
    old = [e for e in existing if e["treaty"] == treaty]
    if old:
        print("Comparing the entries already in the file with the import:")
        compare(old, entries)
    kept = [e for e in existing if e["treaty"] != treaty]
    out_path.write_text(json.dumps(kept + entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}: {len(kept)} entries of other treaties + {len(entries)} {treaty} entries")