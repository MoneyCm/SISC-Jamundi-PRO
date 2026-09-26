"""La portada no llama "alerta temprana" a lo que calcula el SISC."""
from datetime import date

from services import anomaly_radar, observatory_service, sat_radar_service


def test_radar_output_is_a_statistical_signal(monkeypatch):
    fake = {"status": "OK", "anomalies": [{"rule": "R1", "level": "MEDIA", "title": "Hurto a motos sube", "detail": "12 frente a 5."}]}
    monkeypatch.setattr(anomaly_radar, "build_anomalies", lambda db: fake)
    [row] = observatory_service.anomaly_signals(None, date(2026, 9, 26))
    assert row["title"] == "Señal estadística: Hurto a motos sube"
    assert "alerta" not in row["title"].lower()


def test_defensoria_contrast_is_labeled_as_contrast(monkeypatch):
    fake = {"status": "OK", "generated_for": {"cutoff": "2026-09-12"},
            "signals": [{"kind": "DIVERGENCIA", "title": "La zona advertida no sigue la tendencia del municipio", "detail": "Sube 20 %."}]}
    monkeypatch.setattr(sat_radar_service, "build_sat_radar", lambda db: fake)
    [row] = observatory_service.territory_signals(None, date(2026, 9, 26))
    assert "Alerta Temprana de la Defensoría, no una alerta nueva" in row["detail"]
    monkeypatch.setattr(sat_radar_service, "build_sat_radar", lambda db: {"status": "SIN_DATOS", "reason": "Sin zonas."})
    [empty] = observatory_service.territory_signals(None, date(2026, 9, 26))
    assert empty["title"] == "Cruce con las Alertas Tempranas de la Defensoría sin base"

