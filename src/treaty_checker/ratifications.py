import json

from treaty_checker.models import Ratification

# Ratification, accession, succession, acceptance, approval and formal confirmation
# (used by organizations such as the EU) all make a state or organization a party.
BINDING = {"ratified", "acceded", "succeeded", "accepted", "approved", "confirmed"}
ALLOWED = BINDING | {"signed"}

# Shown first in the reservations list of a state that is bound only through the 1967 Protocol.
PROTOCOL_NOTE = ("Bound through the 1967 Protocol, not by ratifying the 1951 Convention itself: "
                 "Article I(1) of the Protocol applies Articles 2 to 34 of the Convention to its parties. "
                 "Articles 35 to 46 of the Convention (administrative and final provisions) do not apply to it.")


def load_ratifications(path: str = "data/ratifications.json") -> list[Ratification]:
    with open(path, encoding="utf-8") as f:
        rows = [Ratification(**r) for r in json.load(f)]
    for r in rows:
        if r.status not in ALLOWED:
            raise ValueError(f"{r.country}/{r.treaty}: unknown status {r.status!r}")
    return rows


def with_protocol_effect(rows: list[Ratification]) -> list[Ratification]:
    """Add a REFUGEE row for every country bound by the 1967 Protocol but not by the 1951 Convention.
    The new row copies the Protocol's status, date and reservations and starts with an explanatory note."""
    # countries that are parties to the Convention itself
    convention = {r.country for r in rows if r.treaty == "REFUGEE" and r.status in BINDING}
    extra = []
    for p in rows:
        if p.treaty == "REFUGEE-PROTOCOL" and p.status in BINDING and p.country not in convention:
            # copy the Protocol row, change its treaty to REFUGEE and put the note first
            extra.append(Ratification(**{**vars(p), "treaty": "REFUGEE",
                                         "reservations": [PROTOCOL_NOTE] + list(p.reservations)}))
    return rows + extra  # a new list: the loaded rows are not changed


def bound_by(country: str, rows: list[Ratification]) -> list[Ratification]:
    return [r for r in with_protocol_effect(rows) if r.country == country and r.status in BINDING]


def coverage(country: str, rows: list[Ratification]) -> tuple[list[str], list[str]]:
    """Treaties in the dataset: (those the country is bound by, those it is not)."""
    rows = with_protocol_effect(rows)
    treaties = sorted({r.treaty for r in rows})
    bound = {r.treaty for r in rows if r.country == country and r.status in BINDING}
    return [t for t in treaties if t in bound], [t for t in treaties if t not in bound]