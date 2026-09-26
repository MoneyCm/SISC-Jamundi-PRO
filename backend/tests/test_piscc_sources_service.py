from datetime import date

from services.piscc_sources_service import load_mindefensa


def test_mindefensa_preserves_independent_cutoffs():
    sources, notices = load_mindefensa(date(2026, 8, 31))
    assert sources["secuestro"]["countBase"] == 4
    assert sources["secuestro"]["fechaCorte"] == "2026-02-24"
    assert sources["extorsion"]["countBase"] == 16
    assert sources["vif"]["countBase"] == 152
    assert not notices


def test_mindefensa_does_not_use_future_values():
    sources, notices = load_mindefensa(date(2026, 1, 31))
    assert sources == {}
    assert len(notices) == 3
