"""Alertas Narrativas: periodos, criterio de variación significativa, cruce con compromisos y redacción."""
from datetime import date, datetime, timedelta

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
