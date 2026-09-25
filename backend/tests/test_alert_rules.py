"""Alertas semanales deterministas: ventanas, cobertura, ceros, prioridades."""
import os, sys
from datetime import date
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.alert_rules import RULE_ID, WEEKLY_THRESHOLDS, complete_weekly_windows, evaluate_weekly


def test_windows_are_exactly_seven_days_half_open():
    w = complete_weekly_windows(date(2026, 7, 8))  # miércoles; semana en curso incompleta
    assert w["current_start"] == date(2026, 6, 29)
    assert w["current_end_exclusive"] == date(2026, 7, 6)
    assert (w["current_end_exclusive"] - w["current_start"]).days == 7
    assert (w["previous_end_exclusive"] - w["previous_start"]).days == 7
    assert w["previous_end_exclusive"] == w["current_start"]  # sin solapes ni huecos


def test_complete_week_when_cutoff_is_sunday():
    w = complete_weekly_windows(date(2026, 7, 5))  # domingo: semana 29/6-6/7 completa
    assert w["current_start"] == date(2026, 6, 29)
    assert w["current_end_exclusive"] == date(2026, 7, 6)


def test_thresholds_are_proposed_not_agreed():
    assert WEEKLY_THRESHOLDS["HOMICIDIO"]["p1_min_current"] == 3
    assert RULE_ID == "WEEKLY_COMPLETE_V1"


def _db_with_weeks(cur_vals, prev_vals, cutoff):
    """Mock mínimo: calculate_indicator por rango -> valores fijos; corte fijo."""
    from unittest.mock import MagicMock
    import services.alert_rules as rules
    calls = {}

    def fake_calc(db, **kw):
        key = (str(kw["period_start"]), str(kw["period_end"]))
        calls[key] = kw
        from datetime import date as _d
        s = kw["period_start"] if isinstance(kw["period_start"], _d) else _d.fromisoformat(kw["period_start"])
        # período actual = el que termina más tarde
        val = cur_vals if s >= date(2026, 6, 29) else prev_vals
        return {"value": val, "unit": "hechos registrados", "unit_code": "HECHO",
                "query_hash": f"qh-{s}", "period": {"start": kw["period_start"], "end": kw["period_end"]}}

    db = MagicMock()
    q = MagicMock()
    db.query.return_value = q
    q.filter.return_value = q
    q.order_by.return_value = q
    run = MagicMock()
    run.id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    run.status = "COMPLETED"
    run.cobertura_inicio = date(2026, 6, 1)
    run.cobertura_fin = date(2026, 7, 5)
    q.first.return_value = run
    # max(fecha_evento): el cutoff se resuelve por _cutoff -> scalar del segundo query
    q.scalar.return_value = cutoff
    return db, calls, fake_calc


def test_aparicion_de_casos_sin_porcentaje_inventado(monkeypatch):
    import services.alert_rules as rules
    db, calls, fake = _db_with_weeks(2, 0, date(2026, 7, 5))
    monkeypatch.setattr(rules, "calculate_indicator", fake)
    monkeypatch.setattr(rules, "_cutoff", lambda db: date(2026, 7, 5))
    r = rules.evaluate_weekly(db, "HOMICIDIO", ref_date=date(2026, 7, 5))
    assert r["status"] == "ALERTA" and r["kind"] == "APARICION_DE_CASOS"
    assert r.get("variation_pct") is None
    assert r["tier"] == "P2"
    # Regla explícita de aparición: igual en código, prueba y evidencia.
    ap = r["applied_rule"]
    assert ap["rule"] == "APARICION_DE_CASOS" and ap["tier"] == "P2" and ap["min_current"] == 1
    assert "justification" in ap and ap["justification"]
    assert "sin casos en la previa" in r["reason"]
    assert "no existe base para un porcentaje" in r["reason"]
    assert r["source_version_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert r["methodology_version"] == "1"
    assert r["rules_version"] == rules.RULES_VERSION
    assert r["coverage"] == "COMPLETA"
    assert r["declared_coverage"] == {"start": "2026-06-01", "end": "2026-07-05"}


def test_ceros_en_ambos_sin_alerta(monkeypatch):
    import services.alert_rules as rules
    db, calls, fake = _db_with_weeks(0, 0, date(2026, 7, 5))
    monkeypatch.setattr(rules, "calculate_indicator", fake)
    monkeypatch.setattr(rules, "_cutoff", lambda db: date(2026, 7, 5))
    r = rules.evaluate_weekly(db, "HOMICIDIO", ref_date=date(2026, 7, 5))
    assert r["status"] == "SIN_ALERTA" and "Cero casos" in r["reason"]


def test_descenso_no_genera_alerta(monkeypatch):
    import services.alert_rules as rules
    db, calls, fake = _db_with_weeks(1, 4, date(2026, 7, 5))
    monkeypatch.setattr(rules, "calculate_indicator", fake)
    monkeypatch.setattr(rules, "_cutoff", lambda db: date(2026, 7, 5))
    r = rules.evaluate_weekly(db, "HOMICIDIO", ref_date=date(2026, 7, 5))
    assert r["status"] == "SIN_ALERTA" and "Descenso" in r["reason"]


def test_p1_por_volumen(monkeypatch):
    import services.alert_rules as rules
    db, calls, fake = _db_with_weeks(3, 2, date(2026, 7, 5))
    monkeypatch.setattr(rules, "calculate_indicator", fake)
    monkeypatch.setattr(rules, "_cutoff", lambda db: date(2026, 7, 5))
    r = rules.evaluate_weekly(db, "HOMICIDIO", ref_date=date(2026, 7, 5))
    assert r["status"] == "ALERTA" and r["tier"] == "P1"


def test_sin_entrega_utilizable():
    from unittest.mock import MagicMock
    db = MagicMock()
    q = MagicMock()
    db.query.return_value = q
    q.filter.return_value = q
    q.first.return_value = None
    r = evaluate_weekly(db, "HOMICIDIO", source_version_id="00000000-0000-0000-0000-000000000000")
    assert r["status"] == "SIN_COBERTURA"


def test_indicador_fuera_de_alcance():
    from unittest.mock import MagicMock
    import pytest
    with pytest.raises(ValueError):
        evaluate_weekly(MagicMock(), "HURTO")


def test_cobertura_desconocida_sin_declaracion(monkeypatch):
    """Sin cobertura declarada por la entrega: DESCONOCIDA, aunque haya fechas."""
    from unittest.mock import MagicMock
    import services.alert_rules as rules
    db = MagicMock()
    q = MagicMock()
    db.query.return_value = q
    q.filter.return_value = q
    q.order_by.return_value = q
    run = MagicMock()
    run.id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    run.status = "COMPLETED"
    run.cobertura_inicio = None
    run.cobertura_fin = None
    q.first.return_value = run
    monkeypatch.setattr(rules, "_cutoff", lambda db: date(2026, 7, 5))
    r = rules.evaluate_weekly(db, "HOMICIDIO", ref_date=date(2026, 7, 5))
    assert r["status"] == "SIN_COBERTURA" and r["coverage"] == "DESCONOCIDA"
    assert "no declara cobertura" in r["reason"]


def test_dedupe_distingue_todas_las_dimensiones(monkeypatch):
    import services.alert_rules as rules
    from unittest.mock import MagicMock
    db, calls, fake = _db_with_weeks(2, 0, date(2026, 7, 5))
    added = {}
    real_query = db.query
    db.add = lambda row: added.setdefault("row", row)
    # query() se usa para run y cutoff; el de alertas devuelve None (sin duplicado)
    q_alert = MagicMock()
    q_alert.filter.return_value = q_alert
    q_alert.first.return_value = None
    db.query = MagicMock(side_effect=lambda *a, **k: q_alert if a and getattr(a[0], "__tablename__", "") == "intelligence_alerts" else real_query(*a, **k))
    monkeypatch.setattr(rules, "calculate_indicator", fake)
    monkeypatch.setattr(rules, "_cutoff", lambda db: date(2026, 7, 5))
    r = rules.emit_weekly(db, indicator="HOMICIDIO", ref_date=date(2026, 7, 5))
    key = added["row"].dedupe_key
    for part in ("WEEKLY", "HOMICIDIO", "JAMUNDI", "2026-06-29",
                 "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "1", rules.RULES_VERSION):
        assert part in key, key


def test_get_consulta_post_ejecuta():
    from api.ia import router
    routes = {(r.path, tuple(sorted(r.methods))) for r in router.routes if hasattr(r, "methods")}
    assert ("/alertas-semanales", ("GET",)) in routes
    assert ("/alertas-semanales", ("POST",)) in routes


def test_referencia_futura_no_crea_cobertura(monkeypatch):
    """Un ref_date posterior al corte se ancla a lo disponible (rezago → sin cobertura aparente)."""
    import services.alert_rules as rules
    db, calls, fake = _db_with_weeks(2, 0, date(2026, 7, 5))
    monkeypatch.setattr(rules, "calculate_indicator", fake)
    monkeypatch.setattr(rules, "_cutoff", lambda db: date(2026, 7, 5))
    r = rules.evaluate_weekly(db, "HOMICIDIO", ref_date=date(2026, 12, 31))
    assert r["current_period"]["start"] == "2026-06-29"
    assert r["coverage"] == "COMPLETA"
