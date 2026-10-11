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


if __name__ == "__main__":
    rows = load_ratifications()
    for country in sorted({r.country for r in rows}):
        for r in bound_by(country, rows):
            print(country, "|", r.treaty, "|", r.status, "|", r.date,
                  "|", len(r.reservations), "reservation(s)")