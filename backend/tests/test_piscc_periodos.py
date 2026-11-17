"""Metas del PISCC por periodo (mes, trimestre, semestre o rango)."""
from datetime import date

import pytest

from services import piscc_periodos as p

DATOS = {"ultimo_mes": "2026-09", "series": {
    "homicidios": {"2025": {"7": 8, "8": 12, "9": 6, "10": 8}, "2026": {"1": 12, "2": 9, "3": 13, "4": 15, "5": 10,
                                                                       "6": 9, "7": 6, "8": 5, "9": 6}},
    "secuestro": {"2025": {"5": 2}, "2026": {"1": 3, "8": 1}},
}}
HOY = date(2026, 11, 14)


def _meta(resultado, clave):
    return next(i for i in resultado["indicators"] if i["id"] == clave)


def test_meses_y_texto_del_periodo():
    assert p.parse_mes("2026-07") == (2026, 7)
    assert p.meses_entre((2025, 11), (2026, 2)) == [(2025, 11), (2025, 12), (2026, 1), (2026, 2)]
    assert p.texto_periodo((2026, 9), (2026, 9)) == "septiembre de 2026"
    assert p.texto_periodo((2026, 7), (2026, 9)) == "julio a septiembre de 2026"
    assert p.texto_periodo((2025, 11), (2026, 2)) == "noviembre de 2025 a febrero de 2026"
    for malo in ("2026", "2026-13", "2019-01", "abc-de"):
        with pytest.raises(ValueError):
            p.parse_mes(malo)
    with pytest.raises(ValueError):
        p.meses_entre((2026, 5), (2026, 4))
    with pytest.raises(ValueError):
        p.meses_entre((2024, 1), (2026, 6))


def test_trimestre_compara_con_los_mismos_meses_del_anio_anterior():
    homicidios = _meta(p.seguimiento((2026, 7), (2026, 9), DATOS, hoy=HOY), "homicidios")
    assert homicidios["value"] == 17 and homicidios["previous"] == 26
    assert homicidios["diferencia"] == -9 and homicidios["variacion_pct"] == -34.6
    assert homicidios["year_to_date"] == 85 and homicidios["goal_2027"] == 105
    # Meta anual 105: a tres meses les corresponden 26,2 y a enero-septiembre 78,8. Van 85: por encima del ritmo.
    assert homicidios["goal_share"] == 26.2 and homicidios["year_to_date_reference"] == 78.8
    assert homicidios["status"] == "SOBRE_RITMO"
    assert homicidios["series"][1] == {"anio": 2026, "valores": [12, 9, 13, 15, 10, 9, 6, 5, 6, None, None, None]}


def test_mes_sin_casos_vale_cero_y_meta_pequena_no_se_reparte():
    secuestro = _meta(p.seguimiento((2026, 9), (2026, 9), DATOS, hoy=HOY), "secuestro")
    assert secuestro["value"] == 0 and secuestro["previous"] == 0 and secuestro["variacion_pct"] is None
    assert secuestro["goal_share"] is None and secuestro["year_to_date_reference"] is None
    assert secuestro["year_to_date"] == 4 and secuestro["status"] == "SUPERADA"  # meta anual: 3
    enero = _meta(p.seguimiento((2025, 5), (2025, 5), DATOS, hoy=HOY), "secuestro")
    assert enero["year_to_date"] == 2 and enero["status"] == "SIN_REFERENCIA"


def test_periodo_mas_alla_de_lo_publicado_se_recorta_o_queda_sin_datos():
    recortado = _meta(p.seguimiento((2026, 7), (2026, 12), DATOS, hoy=HOY), "homicidios")
    assert recortado["months_requested"] == 6 and recortado["months_counted"] == 3 and recortado["value"] == 17
    assert "se recortó" in recortado["detail"]
    futuro = _meta(p.seguimiento((2026, 10), (2026, 10), DATOS, hoy=HOY), "homicidios")
    assert futuro["status"] == "SIN_DATOS" and futuro["value"] is None


def test_el_mes_en_curso_no_cuenta_aunque_la_fuente_lo_traiga():
    datos = {"ultimo_mes": "2026-11", "series": {"homicidios": {"2026": {"10": 8, "11": 3}}}}
    homicidios = _meta(p.seguimiento((2026, 10), (2026, 11), datos, hoy=HOY), "homicidios")
    assert homicidios["months_counted"] == 1 and homicidios["value"] == 8


def test_convivencia_usa_el_rnmc_y_un_mes_sin_reporte_no_es_cero():
    rnmc = {(2026, 9): 400, (2026, 10): 520, (2025, 10): 300}
    con = _meta(p.seguimiento((2026, 10), (2026, 10), DATOS, rnmc, (2026, 10), HOY), "convivencia")
    assert con["value"] == 520 and con["previous"] == 300 and con["goal_share"] == 333.3
    assert con["status"] == "SOBRE_RITMO" and con["year_to_date"] is None  # faltan meses del año en el RNMC
    sin = _meta(p.seguimiento((2026, 8), (2026, 8), DATOS, rnmc, (2026, 10), HOY), "convivencia")
    assert sin["status"] == "SIN_DATOS"


def test_opciones_y_periodo_por_defecto():
    assert p.periodo_por_defecto(DATOS, HOY) == ((2026, 9), (2026, 9))
    opciones = p.opciones(DATOS, HOY)
    assert opciones["ultimo_mes"] == "2026-09"
    etiquetas = {o["label"]: (o["desde"], o["hasta"]) for o in opciones["periodos"]}
    assert etiquetas["Septiembre de 2026"] == ("2026-09", "2026-09")
    assert etiquetas["Trimestre 3 de 2026"] == ("2026-07", "2026-09")
    assert etiquetas["Semestre 2 de 2026"] == ("2026-07", "2026-09")
    assert etiquetas["Año 2025"] == ("2025-01", "2025-12")
    assert "Trimestre 4 de 2026" not in etiquetas and "Octubre de 2026" not in etiquetas


SABANA = {"homicidios": {(2026, 10): 14, (2025, 10): 9}, "motos": {(2026, 10): 20}}


def test_mes_sin_mindefensa_usa_la_sabana_como_preliminar():
    octubre = p.seguimiento((2026, 10), (2026, 10), DATOS, hoy=HOY, preliminar=SABANA, preliminar_hasta=(2026, 10))
    homicidios = _meta(octubre, "homicidios")
    assert homicidios["status"] == "PRELIMINAR" and homicidios["preliminary"] is True
    assert homicidios["value"] == 14 and homicidios["previous"] == 9 and homicidios["diferencia"] == 5
    assert homicidios["year_to_date"] is None and "víctimas" in homicidios["source"]
    assert homicidios["series"][1]["valores"][9] == 14 and homicidios["series"][1]["preliminares"] == [9]
    assert homicidios["series"][1]["valores"][8] == 6  # septiembre sigue siendo de MinDefensa
    motos = _meta(octubre, "motos")
    assert motos["value"] == 20 and motos["previous"] is None and motos["variacion_pct"] is None
    assert _meta(octubre, "lesiones")["status"] == "SIN_DATOS"  # la sábana no trajo el mes
    assert _meta(octubre, "extorsion")["status"] == "SIN_DATOS"  # sin fuente preliminar


def test_un_periodo_que_cruza_el_corte_no_mezcla_fuentes():
    cruzado = _meta(p.seguimiento((2026, 9), (2026, 10), DATOS, hoy=HOY, preliminar=SABANA,
                                  preliminar_hasta=(2026, 10)), "homicidios")
    assert cruzado["value"] == 6 and cruzado["months_counted"] == 1 and cruzado["status"] != "PRELIMINAR"
    assert "preliminary" not in cruzado


def test_opciones_ofrecen_el_mes_preliminar():
    opciones = p.opciones(DATOS, HOY, (2026, 10))
    etiquetas = {o["label"]: o for o in opciones["periodos"]}
    assert etiquetas["Octubre de 2026 (preliminar)"]["desde"] == "2026-10"
    assert etiquetas["Trimestre 4 de 2026 (preliminar)"]["hasta"] == "2026-10"
    assert etiquetas["Semestre 2 de 2026"]["hasta"] == "2026-09"  # el semestre empieza en lo publicado: se recorta
    assert opciones["ultimo_mes"] == "2026-09" and opciones["ultimo_mes_consulta"] == "2026-10"
    assert "Noviembre de 2026 (preliminar)" not in etiquetas
