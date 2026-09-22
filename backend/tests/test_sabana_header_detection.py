"""Deteccion de la fila de encabezado en sabanas con titulos arriba.

Las sabanas SIEDCO suelen traer filas de titulo antes del encabezado real.
El preflight y el procesador deben encontrarlo en vez de leer los titulos
como columnas.
"""
import io

import pandas as pd

from api.ingesta import PREFLIGHT_ALIASES, PREFLIGHT_REQUIRED, resolve_preflight_columns
from services.excel_policia_processor import COLUMN_ALIASES
from services.file_reader import detect_header_row_index, promote_header_row, select_sheet_frame

# Encabezados reales de la sabana del usuario (tal cual vienen en el Excel).
USER_HEADERS = [
    "JURIS.METROPOLITANA / DEPTO", "DESCRIPCION_CONDUCTA", "HECHOS_ID", "AÑO",
    "MES", "FECHA_HECHO", "NoSEMANA", "SEMANA_HECHO", "DIA_SEMANA",
    "INTERVALOS_HORA", "GENERO", "Hechos.MUNICIPIO", "MUNICIPIO_HECHO",
    "BARRIOS_HECHO", "JURIS.DISTRITO / SECCIONAL", "JURIS.ESTACIÓN / ÁREA",
    "JURIS.CAI", "JURIS.DEPENDENCIA", "MODALIDAD", "ARMAS_MEDIOS", "ZONA",
    "MOVIL_AGRESOR", "MOVIL_VICTIMA", "EDAD", "CAUSAS_LESION_MUERTE_PERSONA",
    "SPOA_CARACTERIZACION", "CLASE_SITIO", "CONDUCTAS_ESPECIALES", "TURNO",
    "HORA24", "MODUS_HECHO", "NRO_FUENTE_HECHO", "HORA_HECHO",
    "AGRUPA_EDAD_PERSONA", "SPOA_MOTIVACION", "GRUPOS_VULNERABLES_PERSONA",
    "MEDIO_CONOCIMIENTO", "CLASE_EMPLEADO_DESCRIPCION", "CARGO_PERSONA",
    "PROFESIONES", "GRADO_INSTRUCCION_PERSONA", "PAIS_PERSONA", "UNIDAD_APOYA",
    "RAZON_SOCIAL", "GESTION_ESTATAL", "FECHA_CREACION", "2025", "2026",
]


def test_detects_header_below_title_rows():
    raw = pd.DataFrame([
        ["POLICIA NACIONAL - SABANA SEMANAL", None, None],
        ["Jamundi, Valle del Cauca", None, None],
        ["HECHOS_ID", "FECHA_HECHO", "BARRIO"],
        ["A-1", "2026-08-15", "CENTRO"],
    ])
    assert detect_header_row_index(raw, COLUMN_ALIASES) == 2
    frame = promote_header_row(raw, 2)
    assert list(frame.columns) == ["HECHOS_ID", "FECHA_HECHO", "BARRIO"]
    assert len(frame) == 1
    assert frame.iloc[0]["HECHOS_ID"] == "A-1"


def test_header_in_first_row_returns_zero():
    raw = pd.DataFrame([
        ["HECHOS_ID", "FECHA_HECHO", "BARRIO"],
        ["A-1", "2026-08-15", "CENTRO"],
    ])
    assert detect_header_row_index(raw, COLUMN_ALIASES) == 0


def test_garbage_rows_return_zero():
    raw = pd.DataFrame([
        ["REPORTE DE NOVEDADES", None],
        ["Elaborado por la estacion", None],
        ["TOTAL", 30],
    ])
    assert detect_header_row_index(raw, COLUMN_ALIASES) == 0


def test_user_real_headers_resolve_all_required_below_titles():
    raw = pd.DataFrame(
        [["SABANA SEMANAL POLICIA JAMUNDI"] + [None] * (len(USER_HEADERS) - 1)]
        + [USER_HEADERS]
        + [["X"] * len(USER_HEADERS)]
    )
    assert detect_header_row_index(raw, COLUMN_ALIASES) == 1
    frame = promote_header_row(raw, 1)
    resolved = resolve_preflight_columns(list(frame.columns))
    missing = [key for key in PREFLIGHT_REQUIRED if not resolved[key]]
    assert missing == []


def test_duplicate_headers_get_unique_suffix():
    raw = pd.DataFrame([
        ["HECHOS_ID", "ZONA", "ZONA"],
        ["A-1", "URBANA", "RURAL"],
    ])
    frame = promote_header_row(raw, 0)
    assert list(frame.columns) == ["HECHOS_ID", "ZONA", "ZONA_1"]


def _two_sheet_workbook():
    pivot = pd.DataFrame([
        ["DESCRIPCION_CONDUCTA", "HOMICIDIO"],
        ["AÑO", "2026"],
        ["Etiquetas de fila", "Cuenta de NoSEMANA"],
        ["10", 5],
        ["11", 3],
    ])
    base = pd.DataFrame([
        ["HECHOS_ID", "DESCRIPCION_CONDUCTA", "FECHA_HECHO", "NoSEMANA", "BARRIOS_HECHO", "ZONA"],
        ["A-1", "HURTO A PERSONAS", "2026-08-15", 33, "CENTRO", "URBANA"],
        ["A-2", "HOMICIDIO", "2026-08-16", 33, "NORTE", "URBANA"],
    ])
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pivot.to_excel(writer, sheet_name="Pivote", index=False, header=False)
        base.to_excel(writer, sheet_name="Base", index=False, header=False)
    return buffer.getvalue()


def test_selects_base_sheet_over_pivot_first_sheet():
    sheet, frame = select_sheet_frame(_two_sheet_workbook(), "sabana.xlsx", PREFLIGHT_ALIASES)
    assert sheet == "Base"
    assert len(frame) == 2
    resolved = resolve_preflight_columns(list(frame.columns))
    missing = [key for key in PREFLIGHT_REQUIRED if not resolved[key]]
    assert missing == []


def test_processor_aliases_also_prefer_base_sheet():
    sheet, frame = select_sheet_frame(_two_sheet_workbook(), "sabana.xlsx", COLUMN_ALIASES)
    assert sheet == "Base"
    assert "HECHOS_ID" in list(frame.columns)
    assert len(frame) == 2


def test_run_dq_rescues_base_sheet_from_pivot_first_workbook():
    from services import dq_service

    report = dq_service.run_dq(
        _two_sheet_workbook(), "sabana.xlsx",
        source_name="POLICIA_SEMANAL", profile="POLICIA_SEMANAL",
    )
    assert report["rows_total"] == 2
    assert report["missing_cols"] == []
    assert report["semaforo"] in ("VERDE", "AMARILLO")


def test_run_dq_still_blocks_garbage():
    from services import dq_service

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame([["REPORTE", None], ["TOTAL", 30]]).to_excel(
            writer, sheet_name="Hoja1", index=False, header=False
        )
    report = dq_service.run_dq(
        buffer.getvalue(), "sabana.xlsx",
        source_name="POLICIA_SEMANAL", profile="POLICIA_SEMANAL",
    )
    assert report["semaforo"] == "ROJO"
    assert report["missing_cols"] != []


def test_garbage_workbook_falls_back_to_first_sheet():
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame([["REPORTE", None], ["TOTAL", 30]]).to_excel(
            writer, sheet_name="Hoja1", index=False, header=False
        )
    sheet, frame = select_sheet_frame(buffer.getvalue(), "sabana.xlsx", PREFLIGHT_ALIASES)
    assert sheet == "Hoja1"
    assert list(frame.columns) == ["REPORTE", "COLUMNA_1"]
    assert len(frame) == 1
