"""Import states parties of a Geneva Convention or Additional Protocol from the ICRC IHL Databases.

The ICRC page draws its table with JavaScript, so a saved "HTML only" page is empty. Instead, open the
treaty's page with the "States" table showing, scroll to the bottom, press Ctrl+A and Ctrl+C, paste into a
new text file (keep it as it is: the tabs after each name matter) and save it, for example as
data\\raw\\gc1_states.txt. This script only reads that file; it makes no requests to the ICRC.

Usage (from the project root):
    python src\\treaty_checker\\import_icrc.py GC-I data/raw/gc1_states.txt "<address of the ICRC page>"
    python src\\treaty_checker\\import_icrc.py GC-I data/raw/gc1_states.txt "<address>" data/ratifications.json

Entries for this treaty already in the ratifications file are replaced; entries for other treaties are kept.
"""
import json
import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path

NAME_MAP = {  # the same short names that import_untc.py uses
    "United Kingdom of Great Britain and Northern Ireland": "United Kingdom",
    "United States of America": "United States",
}
DATE = re.compile(r"\d{2}\.\d{2}\.\d{4}")


def iso(d: str) -> str:
    return datetime.strptime(d, "%d.%m.%Y").strftime("%Y-%m-%d")


def parse_states(text: str) -> list[dict]:
    """[{name, signature, ratification, other_dates}]. In the copied table a name followed by ONE tab has a
    signature date; a name followed by two tabs has none. The next date is the signature (if any), then the
    ratification or accession, and any dates after that are dates of reservations or declarations."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    try:
        start = next(i for i, l in enumerate(lines) if l.strip() == "Reservation / Declaration") + 2
    except StopIteration:
        raise SystemExit("Could not find the table header 'Reservation / Declaration': is this the copied ICRC table?")
    rows = []
    for line in lines[start:]:
        if line.startswith("(1)") or not line.strip():
            if line.startswith("(1)"):
                break  # the footnotes under the table
            continue
        if DATE.fullmatch(line.strip()):
            if not rows:
                raise SystemExit(f"A date before any state name: {line!r}")
            rows[-1]["dates"].append(line.strip())
        else:
            tabs = len(line) - len(line.rstrip("\t"))
            rows.append({"name": line.strip(), "tabs": tabs, "dates": []})
    out = []
    for r in rows:
        if r["tabs"] not in (1, 2):
            raise SystemExit(f"{r['name']}: expected one or two tabs after the name, found {r['tabs']}. "
                             "Was the file saved with its tabs kept (no 'trim trailing whitespace')?")
        has_sig = r["tabs"] == 1
        need = 2 if has_sig else 1
        if len(r["dates"]) < need:
            raise SystemExit(f"{r['name']}: too few dates {r['dates']}")
        d = r["dates"]
        out.append({"name": r["name"], "signature": d[0] if has_sig else None,
                    "ratification": d[need - 1], "other_dates": d[need:]})
    return out


def key(name: str) -> str:
    """A loose form of a country name, to match the ICRC's names with the UN's ('Iran (Islamic Republic of)')."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower().replace("'", "")
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"\bsaint\b", "st", s)  # "Saint Lucia" and "St. Lucia" are the same country
    for w in ("islamic republic of", "plurinational state of", "bolivarian republic of", "kingdom of the", "state of"):
        s = s.replace(w, "")
    s = {"czechia": "czech republic", "turkey": "turkiye"}.get(s.strip(), s)
    return re.sub(r"[^a-z]+", "", s)


def build_entries(treaty: str, url: str, states: list[dict], known: dict[str, str], today: str) -> list[dict]:
    entries = []
    for s in states:
        name = NAME_MAP.get(s["name"], s["name"])
        name = known.get(key(name), name)  # use the name already in the file, so one country has one name
        reservations = [f"Reservation or declaration dated {iso(d)}. The ICRC page lists only the date, "
                        f"not the text: see {url}" for d in s["other_dates"]]
        entries.append({"country": name, "treaty": treaty,
                        "status": "ratified" if s["signature"] else "acceded",
                        "date": iso(s["ratification"]), "reservations": reservations,
                        "source_url": url, "retrieved_on": today})
    return sorted(entries, key=lambda e: e["country"])


if __name__ == "__main__":
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    treaty, txt_path, url = sys.argv[1], sys.argv[2], sys.argv[3]
    out_path = Path(sys.argv[4] if len(sys.argv) > 4 else "data/ratifications.json")

    states = parse_states(Path(txt_path).read_text(encoding="utf-8", errors="replace"))
    existing = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else []
    known = {key(e["country"]): e["country"] for e in existing}
    entries = build_entries(treaty, url, states, known, date.today().isoformat())

    signed = sum(1 for s in states if s["signature"])
    print(f"{len(entries)} participants ({signed} with a signature date, {len(entries) - signed} without)")
    print(f"{sum(1 for e in entries if e['reservations'])} with reservations/declarations")
    new_names = sorted(e["country"] for e in entries if key(e["country"]) not in known)
    if new_names:
        print(f"Names not found in the other treaties (check the spelling): {'; '.join(new_names)}")
    kept = [e for e in existing if e["treaty"] != treaty]
    out_path.write_text(json.dumps(kept + entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}: {len(kept)} entries of other treaties + {len(entries)} {treaty} entries")