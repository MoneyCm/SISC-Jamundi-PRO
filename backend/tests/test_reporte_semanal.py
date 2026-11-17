"""Reporte semanal para la Secretaria: palabras que lo piden y texto para WhatsApp."""
from services import reporte_semanal as rs


def test_palabras_que_piden_el_reporte():
    for p in ("reporte semanal para la secretaria", "dame el informe semanal", "el reporte de la secretaria"):
        assert rs.pide_reporte(p)
    assert not rs.pide_reporte("cuantos homicidios van en 2026")


def test_texto_para_whatsapp():
    reporte = {"titulo": "Así va la seguridad en Jamundí", "periodo": "Del 1 de enero al 6 de noviembre de 2026",
               "anio_anterior": 2025, "semana": "Del 31 de octubre al 6 de noviembre", "fuente": "Policía Nacional",
               "filas": [{"nombre": "Homicidios", "anio": 104, "anio_anterior": 105, "diferencia": -1, "semana": 2},
                         {"nombre": "Hurto de motos", "anio": 147, "anio_anterior": 136, "diferencia": 11, "semana": 4}]}
    texto = rs.texto(reporte)
    assert "• Homicidios: *104* (mismo periodo de 2025: 105; bajó 1). Última semana: 2." in texto
    assert "subió 11" in texto and "Cifras preliminares" in texto


def test_variacion():
    assert rs._variacion(59, 50) == {"diferencia": 9, "porcentaje": 18.0}
    assert rs._variacion(3, 0)["porcentaje"] is None
