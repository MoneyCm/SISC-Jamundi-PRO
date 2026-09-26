"""Salvedades del dato para el Inicio y comparendos sin ubicación fuera de las Alertas SISC."""
from datetime import date
from types import SimpleNamespace

from services import anomaly_radar, data_caveats, intervention_followup

RUN = SimpleNamespace(cobertura_fin=date(2026, 9, 12))


def patch(monkeypatch, run=RUN, anomalies=()):
    monkeypatch.setattr(intervention_followup, "latest_covering_run", lambda db: run)
    monkeypatch.setattr(anomaly_radar, "build_anomalies", lambda db: {"status": "OK", "anomalies": list(anomalies)})


def test_month_to_date_ending_at_cutoff_is_flagged(monkeypatch):
    r3 = {"rule": "R3", "title": "Semana del 30/08 al 05/09: solo 12 hechos registrados", "detail": "Lo esperado era 25,2.",
          "window": {"start": "2026-08-30", "end": "2026-09-05"}}
    patch(monkeypatch, anomalies=[r3])
    result = data_caveats.build_caveats(None, date(2026, 9, 1), date(2026, 9, 12), today=date(2026, 9, 26))
    assert result["incomplete"]
    assert any("últimos 7 días" in item for item in result["items"])
    assert any(item.startswith("Semana del 30/08") for item in result["items"])
    assert any("14 días" in item for item in result["items"])
    assert "no una mejora" in result["reading"]


def test_closed_period_far_from_cutoff_is_clean(monkeypatch):
    r3 = {"rule": "R3", "title": "x", "detail": "y", "window": {"start": "2026-08-30", "end": "2026-09-05"}}
    patch(monkeypatch, anomalies=[r3])
    result = data_caveats.build_caveats(None, date(2026, 7, 1), date(2026, 7, 31), today=date(2026, 9, 15))
    assert result == {"incomplete": False, "cutoff": "2026-09-12", "items": [], "reading": ""}


def test_period_past_cutoff_and_missing_delivery(monkeypatch):
    patch(monkeypatch)
    result = data_caveats.build_caveats(None, date(2026, 9, 1), date(2026, 9, 20), today=date(2026, 9, 20))
    assert any("después del corte" in item for item in result["items"])
    patch(monkeypatch, run=None)
    assert data_caveats.build_caveats(None, date(2026, 9, 1), date(2026, 9, 20))["incomplete"]


def test_geo_missing_is_data_quality_not_an_alert():
    """Los comparendos sin ubicación salen como calidad del dato y no suman a las Alertas SISC."""
    from db.models_alerts import IntelligenceAlert
    from db.session import SessionLocal
    from services import observatory_service

    db = SessionLocal()
    try:
        geo = db.query(IntelligenceAlert).filter(IntelligenceAlert.status == "OPEN",
                                                 IntelligenceAlert.alert_type == "RNMC_GEO_MISSING").count()
        others = db.query(IntelligenceAlert).filter(IntelligenceAlert.status == "OPEN",
                                                    IntelligenceAlert.alert_type != "RNMC_GEO_MISSING").count()
        rows = {row["key"]: row for row in observatory_service.alert_signals(db, date(2026, 9, 26))}
    finally:
        db.close()
    if geo:
        assert rows["comparendos-sin-ubicacion"]["count"] == geo and rows["comparendos-sin-ubicacion"]["group"] == "DATOS"
    else:
        assert "comparendos-sin-ubicacion" not in rows
    if others:
        assert rows["alertas"]["count"] == others
