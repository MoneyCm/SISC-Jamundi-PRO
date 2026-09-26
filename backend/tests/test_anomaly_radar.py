"""Radar de anomalías: la prueba estadística y las reglas publicadas."""
import math
from collections import namedtuple
from datetime import date, timedelta

import pytest

from services import anomaly_radar as radar


def test_poisson_tails_match_the_formula():
    # P(X >= 1 | 2) = 1 - e^-2 ; P(X <= 0 | 2) = e^-2
    assert radar.poisson_upper(1, 2.0) == pytest.approx(1 - math.exp(-2))
    assert radar.poisson_lower(0, 2.0) == pytest.approx(math.exp(-2))
    assert radar.poisson_upper(0, 3.0) == 1.0


def test_increase_needs_improbable_relevant_and_minimum():
    assert radar.test_increase(3, 2.0, 3) is None          # no llega al doble
    assert radar.test_increase(2, 0.1, 3) is None          # muy pocos hechos, aunque improbable
    high = radar.test_increase(10, 1.0, 3)
    assert high["level"] == "ALTA" and high["ratio"] == 10.0
    medium = radar.test_increase(6, 1.5, 3)
    assert medium["level"] == "MEDIA"                      # p entre 0,1 % y 1 %


def test_drop_only_where_normal_is_large():
    assert radar.test_drop(2, 6.0) is None                  # lo normal es poco: no se juzga
    drop = radar.test_drop(5, 25.0)
    assert drop["kind"] == "CAIDA" and drop["level"] == "ALTA"


Row = namedtuple("Row", "identity fecha conducta lugar")


def test_build_flags_a_territory_burst_and_publishes_rules(monkeypatch):
    cutoff = date(2026, 9, 12)
    rows = []
    # Historia tranquila: ~25 hechos semanales repartidos, uno cada 6 semanas en Arizona.
    for day in range(1, 300):
        when = cutoff - timedelta(days=day)
        for n in range(3):
            rows.append(Row(f"h{day}-{n}", when, "HURTO_PERSONAS", "CENTRO"))
        if day % 42 == 0:
            rows.append(Row(f"a{day}", when, "LESIONES", "ARIZONA"))
    # Ráfaga reciente en Arizona.
    for n in range(8):
        rows.append(Row(f"burst{n}", cutoff - timedelta(days=n), "HURTO_PERSONAS", "ARIZONA"))
    monkeypatch.setattr(radar, "_events", lambda db: rows)
    monkeypatch.setattr(radar, "load_registry", lambda: {"alertas": []})
    monkeypatch.setattr(radar, "_classifier", lambda registry: (
        lambda place: ("URBANO", place.title()), None))

    data = radar.build_anomalies(None, cutoff)
    territories = [item for item in data["anomalies"] if item["rule"] == "R2"]
    assert [item["territory"] for item in territories] == ["Arizona"]
    assert territories[0]["level"] == "ALTA"
    assert "Probabilidad de verlo por azar" in territories[0]["detail"]
    assert {rule["code"] for rule in data["rules"]} >= {"R1", "R2", "R3", "PRUEBA", "LIMITES"}
    assert data["expected_false_alarms"] == round(data["tests"] * radar.MEDIUM_P, 1)
