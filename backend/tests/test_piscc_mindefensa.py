"""Homicidios, motos y lesiones del PISCC se miden con MinDefensa (misma fuente y unidad que la meta)."""
from datetime import date

from services import piscc_goals


def _datos(ultimo="2026-08"):
    meses = {str(m): 10 for m in range(1, 13)}
    return {"ultimo_mes": ultimo, "series": {
        clave: {"2025": dict(meses), "2026": {str(m): 12 for m in range(1, 9)}}
        for clave in ("homicidios", "motos", "lesiones")}}


def test_usa_meses_cerrados_publicados():
    filas = piscc_goals._mindefensa_rows(None, date(2026, 9, 30), _datos())
    fila = filas["homicidios"]
    assert fila["cutoff"] == "2026-08-31" and fila["count"] == 96 and fila["previous"] == 80
    assert fila["source"] == piscc_goals.FUENTE_MINDEFENSA


def test_a_mitad_de_mes_no_cuenta_el_mes_en_curso():
    fila = piscc_goals._mindefensa_rows(None, date(2026, 8, 15), _datos())["motos"]
    assert fila["cutoff"] == "2026-07-31" and fila["count"] == 84


def test_sin_meses_del_ano_en_curso_se_deja_la_sabana():
    assert piscc_goals._mindefensa_rows(None, date(2026, 1, 20), _datos("2025-12")) == {}
    assert piscc_goals._mindefensa_rows(None, date(2026, 9, 30), {}) == {}


def test_la_sabana_queda_como_dato_reciente(monkeypatch):
    monkeypatch.setattr(piscc_goals, "_police_rows", lambda db, today, sv=None: {
        "homicidios": {**piscc_goals.evaluate(78, date(2026, 9, 12), 105), "source": "Sábana policial (hechos únicos)"}})
    monkeypatch.setattr(piscc_goals, "_external_rows", lambda db, today: {})
    monkeypatch.setattr(piscc_goals, "_convivencia_anios", lambda db, base, meta, hoy: [])
    from services import piscc_historico
    monkeypatch.setattr(piscc_historico, "cargar", lambda archivo=None: _datos())
    metas = {g["id"]: g for g in piscc_goals.build_goals(None, date(2026, 9, 30))["indicators"]}
    assert metas["homicidios"]["count"] == 96
    assert metas["homicidios"]["reciente"] == {"count": 78, "cutoff": "2026-09-12", "source": "Sábana policial (hechos únicos)"}
