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


def test_palabras_del_reporte_mensual_y_texto():
    from services import reporte_mensual as rm
    assert rm.pide_reporte("reporte mensual para la secretaria") and not rm.pide_reporte("reporte semanal")
    reporte = {"titulo": "Reporte mensual de seguridad", "subtitulo": "Metas del PISCC 2026 y respuesta judicial",
               "metas": [{"nombre": "Homicidios", "van": 85, "limite": 105, "estado_texto": "En riesgo de pasar el límite",
                          "reciente": {"van": 104, "corte": "2026-11-06"}}],
               "fiscalia": {"filas": [{"nombre": "Homicidio doloso", "anio": "2024", "procesos": 245,
                                       "juicio_o_condena": 25, "porcentaje": 10.2}]},
               "fuentes": ["Metas: MinDefensa"]}
    texto = rm.texto(reporte)
    assert "• Homicidios: 85 (límite anual 105) — En riesgo de pasar el límite." in texto
    assert "Registro semanal de la Policía al 6 de noviembre de 2026: 104." in texto
    assert "Homicidio doloso, hechos de 2024: 25 de 245 (10,2 %)." in texto


def test_meta_de_homicidios_en_el_semanal(monkeypatch):
    from datetime import date
    from services import piscc_goals
    monkeypatch.setattr(piscc_goals, "build_goals", lambda db, corte, x: {"indicators": [
        {"id": "homicidios", "goal_2027": 105, "status": "DESVIACION", "status_label": "En riesgo"}]})
    meta = rs._meta_homicidios(None, date(2026, 11, 6), 104)
    assert meta["texto"] == "Meta del PISCC: máximo 105 homicidios en el año. Al 6 de noviembre van 104: queda 1 para llegar al límite."
    assert rs._meta_homicidios(None, date(2026, 11, 6), 108)["texto"].endswith("se pasó el límite en 3.")
