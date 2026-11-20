"""A state bound only by the 1967 Protocol counts as bound by the 1951 Refugee Convention (Arts 2-34)."""
from treaty_checker.models import Ratification
from treaty_checker.ratifications import bound_by, coverage, with_protocol_effect


def row(country, treaty, status, reservations=()):
    return Ratification(country=country, treaty=treaty, status=status, date="1968-11-01",
                        reservations=list(reservations), source_url="x", retrieved_on="2026-11-20")


ROWS = [
    row("United States", "REFUGEE-PROTOCOL", "acceded", ["Reservation on Article 24"]),
    row("France", "REFUGEE", "ratified"), row("France", "REFUGEE-PROTOCOL", "acceded"),
    row("Chad", "REFUGEE", "signed"),
    row("Chad", "REFUGEE-PROTOCOL", "signed"),
]


def test_protocol_only_state_is_bound_by_the_convention():
    us = {r.treaty: r for r in bound_by("United States", ROWS)}
    assert set(us) == {"REFUGEE", "REFUGEE-PROTOCOL"}
    assert "1967 Protocol" in us["REFUGEE"].reservations[0]
    assert us["REFUGEE"].reservations[1:] == ["Reservation on Article 24"]
    assert us["REFUGEE"].status == "acceded"


def test_party_to_both_gets_no_extra_row():
    assert len([r for r in bound_by("France", ROWS) if r.treaty == "REFUGEE"]) == 1
    assert len(with_protocol_effect(ROWS)) == len(ROWS) + 1


def test_signature_only_is_not_bound():
    assert bound_by("Chad", ROWS) == []


def test_coverage_and_originals_untouched():
    bound, not_bound = coverage("United States", ROWS)
    assert "REFUGEE" in bound and "REFUGEE" not in not_bound
    assert len(ROWS) == 5 and ROWS[0].reservations == ["Reservation on Article 24"]