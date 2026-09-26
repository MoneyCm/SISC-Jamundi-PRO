"""Metas del PISCC: la tabla 16 tal cual y la regla con la que se lee cada indicador."""
from datetime import date

from services import observatory_service
from services import piscc_goals
from services.piscc_goals import GOALS, TABLE_16, evaluate


def test_table_16_matches_the_plan():
    assert {key: (base, goal) for key, _l, base, goal, _i in TABLE_16} == {
        "homicidios": (115, 105), "secuestro": (4, 3), "extorsion": (58, 55), "vif": (187, 180),
        "motos": (200, 180), "lesiones": (453, 430), "convivencia": (4798, 4000),
    }


def test_projection_above_goal_is_a_deviation():
    row = evaluate(78, date(2026, 9, 12), GOALS["homicidios"])
    assert row["days_elapsed"] == 255
    assert row["projection"] == 112
    assert row["status"] == "DESVIACION"


def test_projection_within_goal():
    assert evaluate(196, date(2026, 9, 12), GOALS["lesiones"])["status"] == "EN_META"


def test_small_goal_compares_accumulated_not_projection():
    row = evaluate(2, date(2026, 3, 31), GOALS["secuestro"])
    assert row["projection"] is None and row["compares"] == "acumulado"
    assert row["status"] == "EN_META"
    assert evaluate(4, date(2026, 2, 24), GOALS["secuestro"])["status"] == "SUPERADA"


def test_early_year_is_preliminary_unless_goal_already_passed():
    assert evaluate(30, date(2026, 1, 31), GOALS["homicidios"])["status"] == "PRELIMINAR"
    assert evaluate(120, date(2026, 1, 31), GOALS["homicidios"])["status"] == "SUPERADA"


def test_portada_names_off_track_goals(monkeypatch):
    fake = {
        "indicators": [
            {"id": "homicidios", "label": "Homicidios", "goal_2027": 105, "count": 78, "projection": 112,
             "compares": "proyeccion", "status": "DESVIACION"},
            {"id": "lesiones", "label": "Lesiones personales", "goal_2027": 430, "count": 196, "projection": 281,
             "compares": "proyeccion", "status": "EN_META"},
        ],
        "off_track": ["homicidios"],
    }
    monkeypatch.setattr(piscc_goals, "build_goals", lambda db, today: fake)
    [row] = observatory_service.piscc_signals(None, date(2026, 9, 25))
    assert row["title"] == "1 meta del PISCC presenta desviación"
    assert "Homicidios: ritmo de ≈112 (meta 105)" in row["detail"]
    assert row["level"] == "MEDIA"


def test_portada_ok_when_all_on_track(monkeypatch):
    fake = {"indicators": [{"id": "lesiones", "status": "EN_META"}, {"id": "vif", "status": "SIN_DATOS"}], "off_track": []}
    monkeypatch.setattr(piscc_goals, "build_goals", lambda db, today: fake)
    [row] = observatory_service.piscc_signals(None, date(2026, 9, 25))
    assert row["level"] == "OK" and "1 de 2" in row["detail"]
