"""The ICRC table as copied from the browser: one tab after a name = has a signature date, two tabs = none."""
import pytest

from treaty_checker.import_icrc import build_entries, key, parse_states

SAMPLE = (
    "States\t\nSignature\n59 States\nRatification / Accession\n196 States\n(1)\nReservation / Declaration\n(2)\n"
    "Afghanistan\t\n08.12.1949\n26.09.1956\n"
    "Albania\t\n12.12.1949\n27.05.1957\n27.05.1957\n"
    "Algeria\t\t\n20.06.1960\n"
    "Islamic Republic of Iran\t\n08.12.1949\n20.02.1957\n04.09.1980\n12.09.2000\n"
    "(1)\nRatification: a treaty is generally open for signature ...\n"
)


def test_parse_states():
    s = {x["name"]: x for x in parse_states(SAMPLE)}
    assert len(s) == 4
    assert s["Afghanistan"] == {"name": "Afghanistan", "signature": "08.12.1949",
                                "ratification": "26.09.1956", "other_dates": []}
    assert s["Algeria"]["signature"] is None and s["Algeria"]["ratification"] == "20.06.1960"
    assert s["Albania"]["other_dates"] == ["27.05.1957"]
    assert s["Islamic Republic of Iran"]["other_dates"] == ["04.09.1980", "12.09.2000"]


def test_windows_line_endings_are_fine():
    assert len(parse_states(SAMPLE.replace("\n", "\r\n"))) == 4


def test_stripped_tabs_are_refused():
    with pytest.raises(SystemExit):
        parse_states(SAMPLE.replace("\t", ""))


def test_entries_use_the_names_already_in_the_data():
    known = {key("Iran (Islamic Republic of)"): "Iran (Islamic Republic of)"}
    e = {x["country"]: x for x in build_entries("GC-I", "URL", parse_states(SAMPLE), known, "2026-11-23")}
    iran = e["Iran (Islamic Republic of)"]
    assert (iran["status"], iran["date"], len(iran["reservations"])) == ("ratified", "1957-02-20", 2)
    assert "2000-09-12" in iran["reservations"][1]
    assert e["Algeria"]["status"] == "acceded" and e["Algeria"]["reservations"] == []


def test_saint_and_st_are_the_same_country():
    assert key("Saint Lucia") == key("St. Lucia")
    assert key("Saint Vincent and the Grenadines") == key("St. Vincent and the Grenadines")
    assert key("Saint Kitts and Nevis") == key("St. Kitts and Nevis")
    assert key("Sao Tome and Principe") != key("Saint Lucia")