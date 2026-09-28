"""Lectura de las cifras de Jamundí que extrae el monitor del Observatorio del Valle."""
import pytest

from services.observatorio_valle import tabla_desde_csv

CABECERA = "fecha_extraccion,fuente,municipio,metodo_extraccion,is_compare,compare_index,col_0,col_9,hash_registro,col_1,col_2\n"


def fila(col_0, col_9, col_1="", is_compare="False"):
    return f"2026-09-25,API,Jamundi,API,{is_compare},0,{col_0},{col_9},h,{col_1},\n"


def test_toma_corte_anio_en_curso_y_anios_completos_sin_duplicar():
    texto = CABECERA + "".join([
        fila("2026-09-17", "Initial"),
        fila("Homicidio", "2026", "82"), fila("Homicidio", "2025", "127"), fila("Homicidio", "2025", "124"),
        fila("Homicidio", "2024", "119"), fila("Homicidio", "2025", "999", is_compare="True"),
        fila("Hurto Personas", "2026", "311"), fila("Hurto Personas", "2026", "306"),
        fila("00:00 - 05:59", "2026", "50"),
    ])
    r = tabla_desde_csv(texto)
    assert r["corte"].isoformat() == "2026-09-17"
    homicidio = r["filas"][0]
    assert (homicidio["delito"], homicidio["oficial_actual"], homicidio["oficial_anterior"], homicidio["anterior_2"]) == ("Homicidio", 82, 127, 119)
    assert r["filas"][1]["oficial_actual"] == 311 and r["filas"][1]["oficial_anterior"] is None
    assert [f["delito"] for f in r["filas"]] == ["Homicidio", "Hurto a personas"]


def test_sin_fecha_de_corte_no_inventa():
    with pytest.raises(ValueError):
        tabla_desde_csv(CABECERA + fila("Homicidio", "2026", "82"))
