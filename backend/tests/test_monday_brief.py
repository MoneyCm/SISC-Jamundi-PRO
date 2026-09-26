"""Resumen del lunes: cada pregunta responde con lo que ya dicen las señales, y el triage propone candidatos."""
from datetime import date
from types import SimpleNamespace

from services import monday_brief as mb


def sig(key, level, title, detail=""):
    return {"key": key, "level": level, "title": title, "detail": detail}


RUN = SimpleNamespace(cobertura_fin=date(2026, 9, 12))


def test_reliability_uses_police_cutoff_and_data_signals():
    signals = [sig("comparendos", "MEDIA", "Comparendos sin actualizar hace 126 días"), sig("fuentes", "OK", "Fuentes al día")]
    result = mb.reliability(signals, RUN, date(2026, 9, 28))
    assert result["level"] == "MEDIA"
    assert result["items"] == ["Sábana policial hasta el 12/09/2026 (16 días).", "Comparendos sin actualizar hace 126 días."]
    assert mb.reliability([], RUN, date(2026, 10, 10))["level"] == "ALTA"  # 28 días
    assert mb.reliability([], RUN, date(2026, 9, 15))["level"] == "OK"
    assert mb.reliability([], None, date(2026, 9, 15))["level"] == "ALTA"


def test_changes_and_places():
    signals = [
        sig("anomalia-r1-0", "ALTA", "Señal estadística: Hurto a motos sube"),
        sig("anomalia-r2-1", "MEDIA", "Señal estadística: Potrerito"),
        sig("radar-divergencia", "ALTA", "La zona advertida no sigue la tendencia"),
        sig("radar", "OK", "Sin divergencias"),
    ]
    changes = mb.changes(signals, RUN)
    assert changes["items"] == ["Hurto a motos sube"] and changes["level"] == "ALTA"
    assert mb.changes([], RUN)["answer"] == "Ninguna cifra municipal se sale de lo esperado (datos hasta el 12/09/2026)."
    places = mb.places(signals)
    assert len(places["items"]) == 2 and "Alerta Temprana de la Defensoría" in places["items"][1]


def test_pending_decisions_and_products(monkeypatch):
    signals = [sig("actas", "MEDIA", "19 actas leídas por confirmar", "Revisarlas."), sig("propuestas", "OK", "x")]
    monkeypatch.setattr(mb, "citizen_pending", lambda db: None)
    decisions = mb.pending_decisions(None, signals)
    assert decisions["items"] == ["19 actas leídas por confirmar. Revisarlas."]
    monkeypatch.setattr(mb, "citizen_pending", lambda db: "Participación ciudadana: 3 reportes seguros.")
    assert mb.pending_decisions(None, [])["items"] == ["Participación ciudadana: 3 reportes seguros."]
    calendar = {"items": [
        {"area": "Boletín", "status": "ATRASADO", "title": "Publicar el boletín mensual de agosto", "when": "hasta el día 7", "target": {"page": "boletin_replica"}},
        {"area": "Datos", "status": "PENDIENTE", "title": "Cargar la sábana", "when": "", "target": {}},
        {"area": "Consejo", "status": "HECHO", "title": "Informe", "when": "", "target": {}},
    ]}
    products = mb.products(calendar)
    assert products["level"] == "ALTA" and products["items"] == ["Publicar el boletín mensual de agosto (hasta el día 7) — atrasado"]


def test_alert_signal_downgrades_on_stale_comparendos(monkeypatch):
    """113 Alertas SISC sobre comparendos de hace meses no son 'actuar ya'."""
    from db.session import SessionLocal
    from services import observatory_service

    db = SessionLocal()
    try:
        rows = observatory_service.alert_signals(db, date(2031, 1, 1))  # lejos de cualquier comparendo cargado
    finally:
        db.close()
    row = next(item for item in rows if item["key"] == "alertas")
    if row["level"] != "OK":
        assert row["level"] == "MEDIA" and "actualice la fuente" in row["detail"]
