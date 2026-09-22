"""Preflight de la SABANA semanal: resolucion de alias de columnas.

El preflight debe aceptar los mismos encabezados que el procesador
(services/excel_policia_processor.py::COLUMN_ALIASES) para no bloquear
archivos que la ingesta real si puede consolidar.
"""
from api.ingesta import PREFLIGHT_REQUIRED, resolve_preflight_columns


def test_real_siedco_headers_resolve_all_required():
    columns = [
        "HECHOS_ID", "DESCRIPCION_CONDUCTA", "FECHA_HECHO", "NoSEMANA",
        "BARRIOS_HECHO", "MUNICIPIO_HECHO", "ZONA",
    ]
    resolved = resolve_preflight_columns(columns)
    missing = [key for key in PREFLIGHT_REQUIRED if not resolved[key]]
    assert missing == []


def test_processor_variants_resolve_in_preflight():
    columns = [
        "ID", "CONDUCTA_SITIO", "FECHA DEL HECHO", "SEMANA_DEL",
        "DESCRIPCION_BARRIO", "MPIO", "ZONA_HECHO",
    ]
    resolved = resolve_preflight_columns(columns)
    assert resolved["hecho_id"] == "ID"
    assert resolved["conducta"] == "CONDUCTA_SITIO"
    assert resolved["fecha"] == "FECHA DEL HECHO"
    assert resolved["semana"] == "SEMANA_DEL"
    assert resolved["barrio"] == "DESCRIPCION_BARRIO"
    assert resolved["municipio"] == "MPIO"
    assert resolved["zona"] == "ZONA_HECHO"


def test_accents_case_and_separators_are_ignored():
    resolved = resolve_preflight_columns(
        ["Hechos_Id", "Fecha del Hecho", "Nº Semana", "Barrio-Hecho"]
    )
    assert resolved["hecho_id"] == "Hechos_Id"
    assert resolved["fecha"] == "Fecha del Hecho"
    assert resolved["semana"] == "Nº Semana"
    assert resolved["barrio"] == "Barrio-Hecho"


def test_unknown_headers_resolve_to_none():
    resolved = resolve_preflight_columns(["2025", "2026", "CODIGO", "TOTAL"])
    assert all(value is None for value in resolved.values())
