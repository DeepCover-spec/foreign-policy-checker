import json

from treaty_checker.models import Ratification

BINDING = {"ratified", "acceded", "succeeded"}
ALLOWED = BINDING | {"signed"}


def load_ratifications(path: str = "data/ratifications.json") -> list[Ratification]:
    with open(path, encoding="utf-8") as f:
        rows = [Ratification(**r) for r in json.load(f)]
    for r in rows:
        if r.status not in ALLOWED:
            raise ValueError(f"{r.country}/{r.treaty}: unknown status {r.status!r}")
    return rows


def bound_by(country: str, rows: list[Ratification]) -> list[Ratification]:
    return [r for r in rows if r.country == country and r.status in BINDING]


def coverage(country: str, rows: list[Ratification]) -> tuple[list[str], list[str]]:
    """Treaties in the dataset: (those the country is bound by, those it is not)."""
    treaties = sorted({r.treaty for r in rows})
    bound = {r.treaty for r in rows if r.country == country and r.status in BINDING}
    return [t for t in treaties if t in bound], [t for t in treaties if t not in bound]