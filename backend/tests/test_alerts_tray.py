"""Bandeja operativa: integridad de arranque, revisiones, linaje, permisos."""
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException


def test_arranque_importa_todos_los_modelos():
    """El espejo legacy falló por un import ausente en un script; en arranque normal
    create_tables() importa estos módulos. Si falta uno, las FK quedan huérfanas."""
    import db.models  # noqa (create_tables importa el resto)
    import db.models_alerts, db.models_auth, db.models_dq, db.models_hechos_seguridad  # noqa
    import db.models_inspecciones, db.models_institutional, db.models_intelligence  # noqa
    import db.models_mindefensa, db.models_policia, db.models_source_center  # noqa
    import db.models_fiscalia_spoa  # noqa
    from db.session import Base
    tables = set(Base.metadata.tables)
    for table in Base.metadata.tables.values():
        for fk in table.foreign_keys:
            assert fk.column.table.name in tables, f"FK huérfana: {table.name} -> {fk.column}"


def _row(state="PENDIENTE", version=0):
    r = MagicMock()
    r.id = "11111111-2222-3333-4444-555555555555"
    r.review_state = state
    r.review_version = version
    return r


def _db_with_row(row):
    db = MagicMock()
    q = MagicMock()
    db.query.return_value = q
    q.filter.return_value = q
    q.order_by.return_value = q
    q.first.return_value = row
    q.all.return_value = []
    return db


def test_revision_guarda_autoria_y_version():
    from services.alert_rules import review_alert
    row = _row("PENDIENTE", 0)
    out = review_alert(_db_with_row(row), alert_id=row.id, username="analista_1",
                       user_id="u-1", action="EN_ANALISIS", expected_version=0, comment="lo miro")
    assert out["review_state"] == "EN_ANALISIS" and out["review_version"] == 1
    assert out["reviewed_by"] == "analista_1"
    assert row.review_state == "EN_ANALISIS"


def test_descarte_exige_motivo():
    from services.alert_rules import review_alert
    with pytest.raises(HTTPException) as e:
        review_alert(_db_with_row(_row("EN_ANALISIS", 1)), alert_id="11111111-2222-3333-4444-555555555555",
                     username="a", user_id="u", action="DESCARTADA", expected_version=1, comment=" ")
    assert e.value.status_code == 422


def test_version_obsoleta_rechazada():
    from services.alert_rules import review_alert
    # Transición válida (REVISADA → EN_ANALISIS) pero versión vieja → 409.
    with pytest.raises(HTTPException) as e:
        review_alert(_db_with_row(_row("REVISADA", 2)), alert_id="11111111-2222-3333-4444-555555555555",
                     username="analista_2", user_id="u2", action="EN_ANALISIS", expected_version=1, comment="reabro")
    assert e.value.status_code == 409


def test_transicion_invalida():
    from services.alert_rules import review_alert
    with pytest.raises(HTTPException) as e:
        review_alert(_db_with_row(_row("PENDIENTE", 0)), alert_id="11111111-2222-3333-4444-555555555555",
                     username="a", user_id="u", action="REVISADA", expected_version=0)
    assert e.value.status_code == 422


def test_revisada_no_significa_resuelto():
    assert "REVISADA" in __import__("services.alert_rules", fromlist=["REVIEW_TRANSITIONS"]).REVIEW_TRANSITIONS["EN_ANALISIS"]


def test_linaje_supersede_sin_heredar():
    from services.alert_rules import relate_lineage
    old = MagicMock()
    old.id = "aaaaaaaa-0000-0000-0000-000000000001"
    old.status = "OPEN"
    db = MagicMock()
    q = MagicMock()
    db.query.return_value = q
    q.filter.return_value = q
    q.all.return_value = [old]
    out = relate_lineage(db, lineage_key="WEEKLY:HOMICIDIO:JAMUNDI:2026-06-29",
                         new_alert_id="bbbbbbbb-0000-0000-0000-000000000002",
                         delivery="run-nueva", outcome="Ya no cumple la regla.")
    assert out["superseded"] == [str(old.id)]
    assert old.status == "SUPERSEDED" and old.supersede_note.startswith("Ya no cumple")


def test_tray_endpoints_existen():
    from api.alerts_tray import router
    paths = {(r.path, tuple(sorted(r.methods))) for r in router.routes if hasattr(r, "methods")}
    assert ("/", ("GET",)) in paths
    assert ("/{alert_id}", ("GET",)) in paths
    assert ("/{alert_id}/review", ("POST",)) in paths


def test_contrato_bandeja_widget_dashboard():
    """Lo que pinta DashboardV2/AlertsPanel debe existir en el serializador y la evidencia."""
    import inspect
    from api import alerts_tray
    src = inspect.getsource(alerts_tray._serialize)
    for key in ("tier", "title", "reason", "status", "review_state", "lineage_key",
                "previous_evaluation_id", "superseded_by", "supersede_note",
                "evidence", "created_at"):
        assert f'"{key}"' in src, key
    import services.alert_rules as rules
    msrc = inspect.getsource(rules.emit_weekly)
    # Campos de evidencia que usa la tarjeta
    for key in ("current_period", "previous_value", "current_value", "unit",
                "coverage", "cutoff"):
        assert key in msrc, key


class _Q:
    def __init__(self, result):
        self._result = result
    def filter(self, *a, **k):
        return self
    def order_by(self, *a, **k):
        return self
    def first(self):
        return self._result() if callable(self._result) else self._result
    def all(self):
        r = self.first()
        return r if isinstance(r, list) else ([r] if r else [])


def test_reproceso_entrega_antigua_no_sustituye_vigente(monkeypatch):
    """La vigencia responde al orden de entregas, no al momento de ejecución."""
    import services.alert_rules as rules
    from datetime import datetime

    old_run = MagicMock()
    old_run.id = "11111111-1111-1111-1111-111111111111"
    old_run.status = "COMPLETED"
    old_run.fecha_fin = datetime(2026, 7, 6)
    old_run.fecha_inicio = datetime(2026, 7, 6)
    old_run.cobertura_inicio = __import__("datetime").date(2026, 6, 22)
    old_run.cobertura_fin = __import__("datetime").date(2026, 7, 5)

    prior = MagicMock()
    prior.id = "33333333-3333-3333-3333-333333333333"
    prior.status = "OPEN"
    prior.metrics = {"source_version_id": "22222222-2222-2222-2222-222222222222"}

    new_run = MagicMock()
    new_run.id = "22222222-2222-2222-2222-222222222222"
    new_run.status = "COMPLETED"
    new_run.fecha_fin = datetime(2026, 7, 10)
    new_run.fecha_inicio = datetime(2026, 7, 10)

    runs = {"11111111-1111-1111-1111-111111111111": old_run, "22222222-2222-2222-2222-222222222222": new_run}

    from db.models_alerts import IntelligenceAlert
    from db.models_hechos_seguridad import IngestionRun

    db = MagicMock()
    alert_calls = {"n": 0}

    def query(model, *a, **k):
        if model is IngestionRun:
            class RQ:
                def filter(self2, *aa, **kk):
                    return self2
                def order_by(self2, *aa, **kk):
                    return self2
                def first(self2):
                    return old_run  # _latest_completed_run no se usa (entrega explícita)
            return RQ()
        if model is IntelligenceAlert:
            class AQ:
                def filter(self2, *aa, **kk):
                    return self2
                def order_by(self2, *aa, **kk):
                    return self2
                def first(self2):
                    alert_calls["n"] += 1
                    # 1ª: dedupe (nada), 2ª: prior vigente (nueva)
                    return None if alert_calls["n"] == 1 else prior
                def all(self2):
                    return []
            return AQ()
        return _Q(None)

    db.query = MagicMock(side_effect=query)
    saved = {}

    def fake_add(row):
        saved["row"] = row
    db.add = fake_add

    def fake_calc(db_, **kw):
        start = str(kw["period_start"])
        val = 3 if start == "2026-06-29" else 1
        return {"value": val, "unit": "hechos", "unit_code": "HECHO",
                "query_hash": f"qh-{start}", "period": {"start": kw["period_start"], "end": kw["period_end"]}}
    monkeypatch.setattr(rules, "calculate_indicator", fake_calc)
    monkeypatch.setattr(rules, "_cutoff", lambda db_: __import__("datetime").date(2026, 7, 5))
    # _delivery_time real: resuelve runs por id vía db.query(IngestionRun).filter().first()
    # Nuestro dispatch devuelve old_run siempre; lo diferenciamos por lookup directo:
    times = {"11111111-1111-1111-1111-111111111111": datetime(2026, 7, 6),
             "22222222-2222-2222-2222-222222222222": datetime(2026, 7, 10)}
    monkeypatch.setattr(rules, "_delivery_time", lambda db_, did: times.get(str(did)))

    out = rules.emit_weekly(db, indicator="HOMICIDIO",
                            source_version_id="11111111-1111-1111-1111-111111111111",
                            ref_date=__import__("datetime").date(2026, 7, 5))
    assert out["persisted"]["stale"] is True
    assert saved["row"].status == "SUPERSEDED"
    assert "anterior a la vigente" in saved["row"].supersede_note
