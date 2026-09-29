"""Años cerrados del PISCC: semáforo frente a la meta 2027 y la línea base 2023."""
from datetime import date

from services import piscc_historico as h


def test_semaforo():
    # Homicidios: línea base 115, meta 105.
    assert h.semaforo(100, 115, 105) == "VERDE"
    assert h.semaforo(105, 115, 105) == "VERDE"
    assert h.semaforo(110, 115, 105) == "AMARILLO"
    assert h.semaforo(115, 115, 105) == "ROJO"
    assert h.semaforo(None, 115, 105) is None


def test_meses_sin_casos_valen_cero_y_el_anio_publicado_se_califica():
    datos = {"ultimo_mes": "2026-08", "series": {"secuestro": {"2024": {"1": 1, "7": 3, "8": 1}, "2026": {"1": 3}}}}
    anios = h.anios_cerrados("secuestro", 4, 3, date(2026, 9, 29), datos)
    assert anios == [
        {"anio": 2024, "total": 5, "completo": True, "semaforo": "ROJO", "semaforo_label": h.SEMAFORO["ROJO"]},
        {"anio": 2025, "total": 0, "completo": True, "semaforo": "VERDE", "semaforo_label": h.SEMAFORO["VERDE"]},
    ]
    assert h.serie_mensual("secuestro", 2026, datos) == [3, 0, 0, 0, 0, 0, 0, 0, None, None, None, None]
