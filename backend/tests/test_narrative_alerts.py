"""Alertas Narrativas: periodos, criterio de variación significativa, cruce con compromisos y redacción."""
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from services import narrative_alerts as na

LABELS = {"HURTO_PERSONAS": "Hurto a personas", "LESIONES": "Lesiones personales",
          "HURTO_RESIDENCIAS": "Hurto a residencias"}
CUTOFF = date(2026, 9, 12)


def events(day: date, count: int, conducta="HURTO_PERSONAS", lugar="BONANZA", hora=20):
    return [{"fecha": day, "conducta": conducta, "lugar": lugar, "hora": hora} for _ in range(count)]


def weekly_history(current: int, previous: int, older: int, **kwargs):
    """Una cifra por semana: la actual, la anterior y tres más antiguas (base de 4 periodos)."""
    rows = events(CUTOFF, current, **kwargs) + events(CUTOFF - timedelta(days=7), previous, **kwargs)
    for back in (2, 3, 4):
        rows += events(CUTOFF - timedelta(days=7 * back), older, **kwargs)
    return rows


def test_periodos_semanal_y_mensual():
    week = na.periods("SEMANAL", CUTOFF)
    assert week["current"] == (date(2026, 9, 6), CUTOFF)
    assert week["previous"] == (date(2026, 8, 30), date(2026, 9, 5))
    assert len(week["baseline"]) == 4 and week["baseline"][0] == week["previous"]
    month = na.periods("MENSUAL", CUTOFF)  # septiembre aún incompleto
    assert month["current"] == (date(2026, 8, 1), date(2026, 8, 31))
    assert month["previous"] == (date(2026, 7, 1), date(2026, 7, 31))
    assert na.periods("MENSUAL", date(2026, 8, 31))["current"] == (date(2026, 8, 1), date(2026, 8, 31))
    assert na.periods("MENSUAL", date(2026, 1, 10))["previous"] == (date(2025, 11, 1), date(2025, 11, 30))


def test_prueba_binomial():
    assert na.binomial_two_sided(5, 5) == 1.0
    assert na.binomial_two_sided(0, 0) == 1.0
    assert na.binomial_two_sided(15, 3) < 0.01
    assert na.binomial_two_sided(3, 15) == pytest.approx(na.binomial_two_sided(15, 3))
    assert na.binomial_two_sided(8, 4) > 0.05  # el doble, pero con pocos hechos puede ser azar


def test_franjas():
    assert [na.franja_of(h) for h in (0, 5, 6, 12, 17, 18, 23, None)] == [
        "MADRUGADA", "MADRUGADA", "MANANA", "TARDE", "TARDE", "NOCHE", "NOCHE", None]


def test_alza_significativa_por_delito_barrio_y_franja():
    rows = weekly_history(16, 3, 3)
    result = na.evaluate(rows, "SEMANAL", na.periods("SEMANAL", CUTOFF))
    dims = [t["dimension"] for t in result["selected"]]
    assert sorted(dims) == ["BARRIO", "DELITO", "FRANJA"]
    assert all(t["kind"] == "AUMENTO" and t["current"] == 16 and t["previous"] == 3 for t in result["selected"])
    barrio = next(t for t in result["selected"] if t["dimension"] == "BARRIO")
    assert barrio["top_conducta"] == "HURTO_PERSONAS"


def test_filtros_de_tamano_y_azar():
    plan = na.periods("SEMANAL", CUTOFF)
    small = na.evaluate(weekly_history(4, 1, 1), "SEMANAL", plan)
    assert small["significant"] == [] and small["selected"] == []
    noisy = na.evaluate(weekly_history(9, 5, 5), "SEMANAL", plan)
    assert noisy["significant"] == []
    assert noisy["tests"] == 3 and noisy["totals"] == {"current": 9, "previous": 5}


def test_rebote_no_cuenta():
    # La semana anterior fue atípicamente baja (2) frente a lo normal (12): volver a 12 no es un alza.
    rows = weekly_history(12, 2, 12)
    result = na.evaluate(rows, "SEMANAL", na.periods("SEMANAL", CUTOFF))
    assert result["selected"] == []


def test_maximo_dos_por_dimension_y_alzas_primero():
    rows = []
    for place in ("BONANZA", "TERRANOVA", "LIBERTADORES"):
        rows += weekly_history(14, 2, 2, lugar=place, conducta=f"C_{place}", hora=None)
    rows += weekly_history(2, 20, 20, lugar="SIN LUGAR", conducta="LESIONES", hora=None)
    result = na.evaluate(rows, "SEMANAL", na.periods("SEMANAL", CUTOFF), place_ok=lambda n: n != "SIN LUGAR")
    dims = [t["dimension"] for t in result["selected"]]
    assert dims.count("BARRIO") <= 2 and dims.count("DELITO") <= 2 and len(dims) == 3
    assert result["selected"][0]["kind"] == "AUMENTO"
    assert all(t["category"] != "SIN LUGAR" for t in result["significant"])


def commitment(code, status="SIN_INFORMACION", deadline=None, text="", territory=None, fulfilled_on=None):
    return {"code": code, "status": status, "deadline_date": deadline, "text": text, "territory": territory,
            "responsible": "Secretaría", "fulfilled_on": fulfilled_on}


def test_estados_y_relacion_de_compromisos():
    today = date(2026, 9, 26)
    selected = [
        {"dimension": "BARRIO", "category": "CGTO EL GUABAL", "kind": "AUMENTO"},
        {"dimension": "DELITO", "category": "HURTO_PERSONAS", "kind": "AUMENTO"},
        {"dimension": "FRANJA", "category": "NOCHE", "kind": "AUMENTO"},
    ]
    rows = [
        commitment("CS-1", deadline=date(2026, 9, 1), text="Patrullajes en El Guabal"),
        commitment("CS-2", deadline=date(2026, 10, 5), text="Campaña contra los hurtos a personas"),
        commitment("CS-3", status="CUMPLIDO", text="Operativo nocturno", fulfilled_on=date(2026, 9, 24)),
        commitment("CS-4", status="CUMPLIDO", text="Operativo nocturno", fulfilled_on=date(2026, 6, 1)),
        commitment("CS-5", status="DESCARTADO", text="Guabal"),
        commitment("CS-6", deadline=date(2026, 12, 1), text="Recuperar el parque"),
    ]
    cross = na.cross_commitments(selected, rows, today, "SEMANAL")
    assert cross["overdue"] == ["CS-1"] and cross["due_soon"] == ["CS-2"]
    assert cross["fulfilled_recent"] == ["CS-3"] and cross["open"] == 3
    assert [[i["code"] for i in items] for items in cross["related"]] == [["CS-1"], ["CS-2"], ["CS-3"]]


def test_mensaje_maximo_seis_lineas_y_accion_sugerida():
    plan = na.periods("SEMANAL", CUTOFF)
    selected = [
        {"dimension": "DELITO", "category": "HURTO_PERSONAS", "kind": "AUMENTO", "current": 31, "previous": 18},
        {"dimension": "BARRIO", "category": "BONANZA", "kind": "AUMENTO", "current": 9, "previous": 2,
         "top_conducta": "HURTO_PERSONAS"},
        {"dimension": "FRANJA", "category": "NOCHE", "kind": "CAIDA", "current": 3, "previous": 15},
    ]
    cross = {"overdue": ["CS-1"], "due_soon": [], "fulfilled_recent": ["CS-3"], "fulfilled_window_days": 7, "open": 4,
             "related": [[], [{"code": "CS-1", "state": "VENCIDO", "deadline_date": "2026-09-01"}], []]}
    message = na.compose("SEMANAL", plan, CUTOFF, selected, cross, LABELS)
    lines = message.split("\n")
    assert len(lines) == 6
    assert lines[0] == "*SISC Jamundí · Alerta semanal* (6 al 12 de septiembre; datos policiales al 12/09/2026)."
    assert lines[1] == "Hurto a personas subió de 18 a 31 hechos frente a la semana anterior."
    assert lines[2] == "En Bonanza los hechos subieron de 2 a 9 frente a la semana anterior, sobre todo hurto a personas."
    assert lines[3] == "En la noche (18:00 a 23:59) los hechos bajaron de 15 a 3 frente a la semana anterior."
    assert lines[4].startswith("Compromisos del Consejo: 1 vencido, 0 vencen en los próximos 15 días y 1 cumplido")
    assert lines[5] == ("El alza en Bonanza tiene 1 compromiso vencido (CS-1): se sugiere pedir su avance "
                        "antes del próximo Consejo.")
    # Sin compromiso abierto relacionado: se sugiere llevarlo al Consejo.
    cross["related"] = [[], [], []]
    assert na.compose("SEMANAL", plan, CUTOFF, selected, cross, LABELS).split("\n")[-1] == (
        "El alza de hurto a personas no tiene compromiso abierto del Consejo: se sugiere llevarla a la próxima sesión.")


def test_mensaje_sin_variaciones_no_rellena():
    plan = na.periods("MENSUAL", CUTOFF)
    cross = {"overdue": [], "due_soon": [], "fulfilled_recent": [], "fulfilled_window_days": 30, "open": 0,
             "related": []}
    lines = na.compose("MENSUAL", plan, CUTOFF, [], cross, LABELS).split("\n")
    assert lines[0].startswith("*SISC Jamundí · Alerta mensual* (agosto de 2026")
    assert lines[1] == "Ninguna variación por delito, barrio u horario es significativa frente a julio."
    assert len(lines) == 3


def test_porcentaje_solo_con_base_suficiente():
    plan = na.periods("SEMANAL", CUTOFF)
    line = na.variation_line({"dimension": "DELITO", "category": "LESIONES", "kind": "AUMENTO", "current": 45,
                              "previous": 30}, "SEMANAL", plan["previous"][0], LABELS)
    assert line == "Lesiones personales subió de 30 a 45 hechos (+50 %) frente a la semana anterior."


def test_etiquetas_de_lugar():
    assert na.place_label("CGTO EL GUABAL") == "corregimiento El Guabal"
    assert na.place_label("SACHAMATE (URB MUNICIPAL)") == "Sachamate"
    assert na.place_core("CONJUNTO RES. ALFAGUARA") == "ALFAGUARA"
    assert na.place_label("VIA JAMUNDI/POTRERITO/RIO CLARO") == "Via Jamundi/Potrerito/Rio Claro"


def test_validacion_del_texto_editado():
    assert na.validate_text("  uno\n\ndos \n") == "uno\ndos"
    with pytest.raises(ValueError, match="7 líneas"):
        na.validate_text("\n".join(["x"] * 7))
    with pytest.raises(ValueError, match="vacío"):
        na.validate_text("   ")
    with pytest.raises(ValueError, match="caracteres"):
        na.validate_text("x" * (na.MAX_CHARS + 1))


def test_hora_programada():
    tz = na.TZ
    monday_8 = datetime(2026, 9, 28, 8, 0, tzinfo=tz)
    assert na.slot_start("SEMANAL", monday_8) == datetime(2026, 9, 28, 7, 0, tzinfo=tz)
    monday_6 = datetime(2026, 9, 28, 6, 0, tzinfo=tz)
    assert na.slot_start("SEMANAL", monday_6) == datetime(2026, 9, 21, 7, 0, tzinfo=tz)
    assert na.slot_start("MENSUAL", datetime(2026, 10, 1, 6, 0, tzinfo=tz)) == datetime(2026, 9, 1, 7, 0, tzinfo=tz)
    assert na.slot_start("MENSUAL", datetime(2026, 1, 1, 6, 0, tzinfo=tz)) == datetime(2025, 12, 1, 7, 0, tzinfo=tz)


def test_tarea_en_el_calendario_del_centro_de_analisis():
    from services.operating_calendar import narrative_item

    wednesday = date(2026, 9, 30)
    draft = {"status": "BORRADOR", "period_label": "13 al 19 de septiembre", "created_on": date(2026, 9, 28), "sent_on": None}
    assert narrative_item("SEMANAL", draft, date(2026, 9, 28))["status"] == "PENDIENTE"
    late = narrative_item("SEMANAL", draft, wednesday)
    assert late["status"] == "ATRASADO" and late["target"] == {"page": "narrative_alerts"} and late["area"] == "Alerta"
    sent = {**draft, "status": "ENVIADO", "sent_on": date(2026, 9, 28)}
    assert narrative_item("SEMANAL", sent, wednesday)["status"] == "HECHO"
    old = {**sent, "created_on": date(2026, 9, 21)}
    assert "no hay mensaje nuevo" in narrative_item("SEMANAL", old, wednesday)["detail"]
    assert narrative_item("SEMANAL", None, wednesday)["status"] == "PENDIENTE"
    # La mensual figura a comienzo de mes, o después si sigue en borrador.
    monthly = {**draft, "period_label": "agosto de 2026"}
    monthly = {**monthly, "created_on": date(2026, 9, 1)}
    assert narrative_item("MENSUAL", monthly, date(2026, 9, 3))["status"] == "PENDIENTE"
    assert narrative_item("MENSUAL", monthly, date(2026, 9, 3))["when"] == "hasta el 5/09"
    assert narrative_item("MENSUAL", monthly, date(2026, 9, 20))["status"] == "ATRASADO"
    # Un borrador recién generado no nace atrasado.
    assert narrative_item("SEMANAL", {**draft, "created_on": wednesday}, wednesday)["status"] == "PENDIENTE"
    assert narrative_item("MENSUAL", {**monthly, "status": "ENVIADO"}, date(2026, 9, 20)) is None


@pytest.fixture
def db():
    from sqlalchemy.orm import Session
    from db.session import engine

    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def fake_compute(source, end=date(2031, 3, 15)):
    def compute(db, frequency, today=None, occasion=None):
        plan = na.periods(frequency, end)
        return {"frequency": frequency, "plan": plan, "cutoff": end, "source_version_id": source,
                "text": f"{frequency} {source}", "evidence": {},
                "occasion_date": occasion[0] if occasion else None, "occasion_label": occasion[1] if occasion else None}
    return compute


@pytest.fixture
def fake_run(monkeypatch):
    from services import intervention_followup

    monkeypatch.setattr(intervention_followup, "latest_covering_run",
                        lambda db: SimpleNamespace(cobertura_fin=date(2031, 3, 15)))


def test_al_cargar_la_sabana_se_generan_borradores_y_no_se_repite_lo_enviado(db, monkeypatch, fake_run):
    from db.models_narrative_alerts import NarrativeAlert

    monkeypatch.setattr(na, "compute", fake_compute("entrega-1"))
    assert sorted(na.generate_after_upload(db, "cargador")) == [
        "ANUAL:2030-12-31", "MENSUAL:2031-02-28", "SEMANAL:2031-03-15", "SEMESTRAL:2030-12-31"]
    weekly = db.query(NarrativeAlert).filter_by(source_version_id="entrega-1", frequency="SEMANAL").one()
    assert weekly.trigger == "CARGA" and weekly.created_by == "cargador" and weekly.status == "BORRADOR"
    assert na.generate_after_upload(db, "cargador") == []  # la misma entrega no duplica

    # Se envía la semanal; llega otra entrega con el mismo corte.
    na.mark_sent(db, str(weekly.id), weekly.version, "analista")
    monkeypatch.setattr(na, "compute", fake_compute("entrega-2"))
    assert na.generate_after_upload(db, "cargador") == []  # la enviada no se repropone; los balances ya existen
    monthly = db.query(NarrativeAlert).filter_by(source_version_id="entrega-1", frequency="MENSUAL").one()
    assert monthly.status == "BORRADOR"
    # El botón sí genera otra versión del mes con la entrega nueva, y reemplaza el borrador anterior.
    alert, created = na.generate(db, "MENSUAL", "analista")
    assert created and alert.source_version_id == "entrega-2"
    db.refresh(monthly)
    assert monthly.status == "REEMPLAZADO" and monthly.superseded_by == alert.id


def test_alerta_del_consejo_una_por_sesion_y_actualizar_borrador(db, monkeypatch, fake_run):
    from db.models_narrative_alerts import NarrativeAlertRevision

    monkeypatch.setattr(na, "compute", fake_compute("entrega-1"))
    session = (date(2031, 3, 27), "27 de marzo", date(2031, 2, 26))
    alert, created = na.generate(db, "CONSEJO", "SISTEMA", trigger="PROGRAMADA", occasion=session)
    assert created and alert.occasion_date == date(2031, 3, 27) and alert.period_end == date(2031, 3, 15)
    assert na.generate(db, "CONSEJO", "SISTEMA", occasion=session)[1] is False
    # Otra sesión con los mismos datos sí tiene su propia alerta.
    assert na.generate(db, "CONSEJO", "SISTEMA", occasion=(date(2031, 4, 24), "24 de abril", date(2031, 3, 27)))[1]

    edited = na.edit(db, str(alert.id), "Texto editado a mano", alert.version, "analista")
    monkeypatch.setattr(na, "compute", fake_compute("entrega-2"))
    monkeypatch.setattr(na, "council_sessions", lambda db, today: (SimpleNamespace(start=date(2031, 2, 26)), None))
    refreshed = na.refresh(db, str(alert.id), edited.version, "analista")
    assert refreshed.text == "CONSEJO entrega-2" and refreshed.source_version_id == "entrega-2"
    actions = [r.action for r in db.query(NarrativeAlertRevision).filter_by(alert_id=alert.id)
               .order_by(NarrativeAlertRevision.version)]
    assert actions == ["GENERADO", "EDITADO", "ACTUALIZADO"]
    with pytest.raises(PermissionError):
        na.refresh(db, str(alert.id), 0, "analista")  # versión vieja


def test_periodos_consejo_semestral_y_anual():
    council = na.periods("CONSEJO", CUTOFF)
    assert council["current"] == (date(2026, 8, 16), CUTOFF)
    assert council["previous"] == (date(2026, 7, 19), date(2026, 8, 15))
    semester = na.periods("SEMESTRAL", CUTOFF)
    assert semester["current"] == (date(2026, 1, 1), date(2026, 6, 30))
    assert semester["previous"] == (date(2025, 1, 1), date(2025, 6, 30))
    assert na.periods("SEMESTRAL", date(2026, 3, 1))["current"] == (date(2025, 7, 1), date(2025, 12, 31))
    assert na.periods("SEMESTRAL", date(2026, 6, 30))["current"] == (date(2026, 1, 1), date(2026, 6, 30))
    year = na.periods("ANUAL", CUTOFF)
    assert year["current"] == (date(2025, 1, 1), date(2025, 12, 31)) and year["previous"][0] == date(2024, 1, 1)
    assert na.periods("ANUAL", date(2025, 12, 31))["current"][0] == date(2025, 1, 1)
    assert na.period_label("SEMESTRAL", *semester["current"]) == "primer semestre de 2026"
    assert na.previous_label("SEMESTRAL", semester["previous"][0]) == "el primer semestre de 2025"
    assert na.previous_label("CONSEJO", council["previous"][0]) == "los 28 días anteriores"


def test_base_sin_datos_no_cuenta_como_ceros():
    plan = na.periods("ANUAL", CUTOFF)  # 2025 frente a 2024; de la base (2021-2024) solo 2024 tiene datos
    rows = events(date(2025, 5, 1), 30, lugar="X", hora=None) + events(date(2024, 5, 1), 10, lugar="X", hora=None)
    result = na.evaluate(rows, "ANUAL", plan, data_start=date(2024, 1, 1))
    assert result["baseline_periods"] == 1
    assert sorted(t["category"] for t in result["selected"]) == ["HURTO_PERSONAS", "X"]


def test_mensaje_largo_con_otras_fuentes_y_limite_de_lineas():
    plan = na.periods("MENSUAL", CUTOFF)
    selected = [{"dimension": "DELITO", "category": "HURTO_PERSONAS", "kind": "AUMENTO", "current": 40, "previous": 25}]
    cross = {"overdue": [], "due_soon": [], "fulfilled_recent": [], "fulfilled_window_days": 30, "open": 0,
             "related": [[{"code": "CS-1", "state": "ABIERTO", "deadline_date": None}]]}
    context = [{"line": f"Fuente {n}."} for n in range(1, 10)]
    lines = na.compose("MENSUAL", plan, CUTOFF, selected, cross, LABELS, context).split("\n")
    assert len(lines) == 10
    assert lines[2] == "No hubo otras variaciones significativas frente a julio."
    assert lines[3:9] == [f"Fuente {n}." for n in range(1, 7)]  # caben 6; las demás se omiten en orden
    assert lines[-1].startswith("Compromisos del Consejo")


def test_encabezados_por_tipo():
    assert na.header_line("SEMESTRAL", na.periods("SEMESTRAL", CUTOFF), CUTOFF) == (
        "*SISC Jamundí · Balance semestral* (primer semestre de 2026 frente al mismo semestre de 2025; "
        "datos policiales al 12/09/2026).")
    assert na.header_line("ANUAL", na.periods("ANUAL", CUTOFF), CUTOFF).startswith(
        "*SISC Jamundí · Balance anual* (2025 frente a 2024")
    council = na.header_line("CONSEJO", na.periods("CONSEJO", CUTOFF), CUTOFF, date(2026, 9, 28), "29 de septiembre")
    assert council == ("*SISC Jamundí · Alerta para el Consejo de Seguridad* · sesión: 29 de septiembre. Últimos 28 días "
                       "(16 de agosto al 12 de septiembre); datos policiales al 12/09/2026, con 16 días de retraso.")
    assert na.against("SEMESTRAL", date(2025, 1, 1)) == "frente al primer semestre de 2025"


def test_limite_de_lineas_por_tipo():
    na.validate_text("\n".join(["x"] * 12), "CONSEJO")
    with pytest.raises(ValueError, match="máximo es 6"):
        na.validate_text("\n".join(["x"] * 7), "SEMANAL")
    with pytest.raises(ValueError, match="máximo es 15"):
        na.validate_text("\n".join(["x"] * 16), "ANUAL")


def test_zona_con_alerta_temprana():
    alert = {"id": "AT-005-24", "numero": "005-24",
             "conductas_advertidas": [{"codigo_siedco": "HOMICIDIO"}, {"codigo_siedco": "HURTO_VEHICULOS"},
                                      {"codigo_siedco": None}]}
    classify = lambda place: ("AT", "Potrerito") if place == "POTRERITO" else ("URBANO", place)
    plan = na.periods("MENSUAL", CUTOFF)
    rows = (events(date(2026, 8, 5), 3, conducta="HOMICIDIO", lugar="POTRERITO")
            + events(date(2026, 8, 6), 2, conducta="HURTO_VEHICULOS", lugar="POTRERITO")
            + events(date(2026, 8, 7), 9, conducta="HURTO_PERSONAS", lugar="POTRERITO")  # no advertida
            + events(date(2026, 8, 8), 4, conducta="HOMICIDIO", lugar="BONANZA")  # fuera de la zona
            + events(date(2026, 7, 8), 2, conducta="HOMICIDIO", lugar="POTRERITO"))
    item = na.at_zone_line(rows, plan, "MENSUAL", classify, alert, LABELS)
    assert item["line"] == ("Zona con Alerta Temprana 005-24 de la Defensoría: 5 hechos de las conductas advertidas "
                            "(2 en julio), 3 homicidios; más hechos en Potrerito (5).")


def test_marca_de_alerta_temprana_en_la_variacion():
    plan = na.periods("SEMANAL", CUTOFF)
    line = na.variation_line({"dimension": "BARRIO", "category": "POTRERITO", "kind": "AUMENTO", "current": 9,
                              "previous": 2, "alerta_temprana": True}, "SEMANAL", plan["previous"][0], LABELS)
    assert line.endswith("frente a la semana anterior, en territorio con Alerta Temprana de la Defensoría.")


def test_alerta_del_consejo_se_genera_el_dia_anterior():
    tz = na.TZ
    assert not na.council_due(datetime(2026, 9, 28, 6, 59, tzinfo=tz), date(2026, 9, 29), date(2026, 9, 29))
    assert na.council_due(datetime(2026, 9, 28, 7, 0, tzinfo=tz), date(2026, 9, 29), date(2026, 9, 29))
    assert not na.council_due(datetime(2026, 9, 30, 8, 0, tzinfo=tz), date(2026, 9, 29), date(2026, 9, 29))


def test_tarea_de_la_alerta_del_consejo_en_el_calendario():
    from services.operating_calendar import Session_, council_alert_item, narrative_item

    session = Session_(date(2026, 9, 29), date(2026, 9, 29), "REGISTRADA", 2026, 9)
    assert council_alert_item(None, date(2026, 9, 20), session) is None
    assert council_alert_item(None, date(2026, 9, 26), session)["status"] == "PENDIENTE"
    assert council_alert_item({"status": "BORRADOR"}, date(2026, 9, 29), session)["status"] == "ATRASADO"
    assert council_alert_item({"status": "ENVIADO"}, date(2026, 9, 29), session)["status"] == "HECHO"
    draft = {"status": "BORRADOR", "period_label": "primer semestre de 2026", "created_on": date(2026, 9, 20),
             "sent_on": None}
    assert narrative_item("SEMESTRAL", draft, date(2026, 9, 26))["status"] == "PENDIENTE"
    assert narrative_item("SEMESTRAL", {**draft, "status": "ENVIADO"}, date(2026, 9, 26)) is None
