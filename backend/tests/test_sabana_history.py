from datetime import date
from decimal import Decimal

from services.sabana_history import build_coverage, claim_snapshot_record, normalize_source_id, snapshot_hecho_key, stable_record_key


def test_normalize_source_id_keeps_stable_numeric_identity():
    assert normalize_source_id(123.0) == "123"
    assert normalize_source_id(Decimal("456.000")) == "456"
    assert normalize_source_id("  ABC-9 ") == "ABC-9"


def test_normalize_source_id_rejects_empty_spreadsheet_values():
    assert normalize_source_id(None) == ""
    assert normalize_source_id(float("nan")) == ""
    assert normalize_source_id("NaN") == ""


def test_snapshot_hecho_key_prefers_official_id():
    assert snapshot_hecho_key("H-42", "fingerprint") == "ID:H-42"
    assert snapshot_hecho_key("", "fingerprint") == "FP:fingerprint"


def test_build_coverage_tracks_each_year_and_equivalent_cutoff():
    coverage = build_coverage([
        (date(2024, 2, 3), 5),
        (date(2024, 7, 20), 29),
        (date(2025, 7, 19), 29),
    ])

    assert coverage == {
        "years": [2024, 2025],
        "min_date": "2024-02-03",
        "max_date": "2025-07-19",
        "max_week_by_year": {"2024": 29, "2025": 29},
    }

def test_claim_snapshot_record_rejects_exact_weekly_duplicates():
    seen = set()
    assert claim_snapshot_record(seen, "same-row") is True
    assert claim_snapshot_record(seen, "same-row") is False
    assert claim_snapshot_record(seen, "corrected-row") is True

def test_stable_record_key_only_collapses_identical_source_rows():
    first = {"HECHOS_ID": 42, "EDAD": 36, "PAIS_PERSONA": "COLOMBIA"}
    same = {"PAIS_PERSONA": "COLOMBIA", "EDAD": 36, "HECHOS_ID": 42}
    another_victim = {"HECHOS_ID": 42, "EDAD": 36, "PAIS_PERSONA": "VENEZUELA"}

    assert stable_record_key(first) == stable_record_key(same)
    assert stable_record_key(first) != stable_record_key(another_victim)
