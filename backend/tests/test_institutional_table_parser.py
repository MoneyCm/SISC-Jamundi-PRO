"""Lectura verificada de tablas mensuales de informes de Comisarías.

El texto reproduce la estructura de un informe de gestión real (texto extraído de PDF):
etiquetas partidas en dos líneas, años pegados a la etiqueta, números de página, tablas
cuya etiqueta está antes del encabezado de meses y errores internos del propio informe.
"""

from services.institutional_agent_service import InstitutionalAgentService
from services.institutional_table_parser import extract_comisaria_tables, parse_monthly_rows

HEADER = "ENER FEB MAR ABR MAY JUN JUL AGO SEPT OCT NOV DIC total"

PAGES = [
    f"""NUEVOS CASOS DE VIOLENCIA EN EL CONTEXTO FAMILIAR
28/05/2026
{HEADER}
APERTURA NUEVO PROCESO POR
V.I.F.- 2026 28 26 22 29 23 0 0 0 0 0 0 0 128
2
En general, las cifras reflejan la persistencia de situaciones de violencia.""",
    f"""AUDIENCIAS REALIZADAS
AUDIENCIAS V.I.F. {HEADER}
REALIZADAS - 2026 25 19 33 26 26 0 0 0 0 0 0 0 129
V.I.F - -2025 16 20 3 7 6 0 0 0 0 0 0 0 52
TOTAL AUDIENCIAS REALIZADAS 41 39 36 33 32 0 0 0 0 0 0 0 181""",
    f"""MEDIDAS DE PROTECCIÓN
{HEADER}
MEDIDA DE PROTECCIÓN POLICIVA
URGENTE 26 25 18 14 21 0 0 0 0 0 0 0 104
MEDIDAS DEFINITIVAS 41 39 36 33 32 0 0 0 0 0 0 0 181
TOTAL 67 64 54 47 53 0 0 0 0 0 0 0 285""",
    f"""VIOLENCIA-GÉNERO {HEADER}
FEMENINO 25 21 18 21 18 0 0 0 0 0 0 0 103
MASCULINO 3 5 4 7 3 0 0 0 0 0 0 0 22
NO REGISTRA 0 0 0 1 2 0 0 0 0 0 0 0 3
TOTAL 28 26 22 29 23 0 0 0 0 0 0 0 128""",
    f"""GRUPO ETNICO {HEADER}
Afro 2 3 5 3 1 0 0 0 0 0 0 0 14
Mestizo 19 20 12 20 20 0 0 0 0 0 0 0 91
NO REGISTRA 7 3 5 1 1 0 0 0 0 0 0 0 17""",
    f"""TIPO DE CONSUMO {HEADER}
SUSTANCIAS PSICOACTIVAS 4 4 2 2 6 0 0 0 0 0 0 0 23
ALCOHOL 5 2 1 1 1 0 0 0 0 0 0 0 10
TOTAL V.I.F RECIBIDOS 28 26 20 29 15 0 0 0 0 0 0 0 128""",
    f"""PROCESO ADMINISTRATIVO
RESTABLECIMIENTO DE DERECHOS {HEADER}
PARD 11 10 1 5 8 0 0 0 0 0 0 0 35
NNA externado
8""",
    f"""DESPACHOS COMISARIOS
COMISARIA
SEGUNDA DE
FAMILIA
{HEADER}
0 3 1 0 1 0 0 0 0 0 0 0 3
28/05/2026""",
    f"""Durante el periodo se brindaron acompañamientos psicológicos.
VALORACIÓN -
PSICOLÓGICA {HEADER}
17 20 11 13 22 0 0 0 0 0 0 0 83
15""",
]


def _by_name(candidates):
    return {item.indicator: item for item in candidates}


def test_row_with_year_in_label_and_page_number_is_read_correctly():
    rows = parse_monthly_rows(PAGES[:1])
    assert len(rows) == 1
    assert rows[0].months[:5] == [28, 26, 22, 29, 23]
    assert rows[0].total == 128 and rows[0].consistent is True
    assert "APERTURA NUEVO PROCESO" in rows[0].label


def test_verified_values_are_extracted_and_public():
    candidates, _ = extract_comisaria_tables(PAGES)
    found = _by_name(candidates)
    expected = {
        "Nuevos procesos de violencia en el contexto familiar": 128,
        "Medidas de proteccion urgentes": 104,
        "Casos de violencia contra mujeres en el contexto familiar": 103,
        "Casos de violencia contra hombres en el contexto familiar": 22,
        "Procesos Administrativos de Restablecimiento de Derechos": 35,
        "Acompanamientos psicologicos": 83,
        "Audiencias realizadas": 181,
    }
    for indicator, value in expected.items():
        assert found[indicator].value == value, indicator
        assert found[indicator].public_allowed, indicator
        assert found[indicator].confidence >= 0.9, indicator


def test_months_not_matching_declared_total_is_withheld():
    candidates, findings = extract_comisaria_tables(PAGES)
    found = _by_name(candidates)
    spa = found["Casos asociados a consumo de sustancias psicoactivas"]
    assert spa.value == 18 and not spa.public_allowed
    despachos = found["Despachos comisorios recibidos"]  # etiqueta con errata "COMISARIOS"
    assert despachos.value == 5 and not despachos.public_allowed
    codes = [(item.code, tuple(item.indicators)) for item in findings]
    assert ("INFORME_SUMA_INCONSISTENTE", ("Casos asociados a consumo de sustancias psicoactivas",)) in codes


def test_copied_row_flags_only_the_unsupported_one():
    candidates, findings = extract_comisaria_tables(PAGES)
    found = _by_name(candidates)
    assert not found["Medidas de proteccion definitivas"].public_allowed
    # Audiencias es la suma de sus filas por año: es el dato respaldado, no la copia.
    assert found["Audiencias realizadas"].public_allowed
    duplicated = [item for item in findings if item.code == "INFORME_FILA_DUPLICADA"]
    assert [item.indicators for item in duplicated] == [["Medidas de proteccion definitivas"]]


def test_incomplete_breakdowns_are_detected():
    candidates, findings = extract_comisaria_tables(PAGES)
    found = _by_name(candidates)
    messages = " ".join(item.message for item in findings if item.code == "INFORME_DESGLOSE_INCOMPLETO")
    assert "grupo etnico" in messages and "abr: 24 de 29" in messages
    assert "tipo de consumo" in messages
    assert "genero" not in messages  # el desglose por género sí suma
    assert not found["Casos en poblacion mestiza"].public_allowed
    assert found["Casos de violencia contra mujeres en el contexto familiar"].public_allowed
    assert any(item.code == "INFORME_TOTAL_INCONSISTENTE" for item in findings)


def test_agent_prefers_verified_tables_over_proximity_rules():
    agent = InstitutionalAgentService(db=None)
    candidates = _by_name(agent._parse_reports(PAGES, "COMISARIAS", "2026-05"))
    # La regla por proximidad tomaba el número de página (2) como total de casos.
    assert candidates["Nuevos procesos de violencia en el contexto familiar"].value == 128
    assert candidates["Acompanamientos psicologicos"].value == 83
    assert any(item.code == "INFORME_FILA_DUPLICADA" for item in agent.table_findings)


def test_pdf_text_layer_detection():
    assert InstitutionalAgentService._has_usable_text(PAGES)
    assert not InstitutionalAgentService._has_usable_text(["", "  ", "Pagina 1"])


def test_breakdown_check_ignores_unrelated_rows_in_same_table():
    """Tabla única (p. ej. transcrita por OCR) con indicadores distintos y una fila de consumo."""
    page = f"""| | {' | '.join(HEADER.split())} |
| APERTURA NUEVO PROCESO POR V.I.F. | 10 | 12 | 9 | 11 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 50 |
| MEDIDA DE PROTECCIÓN POLICIVA URGENTE | 7 | 6 | 8 | 5 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 30 |
| SUSTANCIAS PSICOACTIVAS | 2 | 3 | 1 | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 12 |
| PARD | 3 | 4 | 2 | 5 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 15 |"""
    found = _by_name(extract_comisaria_tables([page])[0])
    assert found["Nuevos procesos de violencia en el contexto familiar"].public_allowed
    assert found["Medidas de proteccion urgentes"].public_allowed
    assert found["Procesos Administrativos de Restablecimiento de Derechos"].public_allowed
    assert not found["Casos asociados a consumo de sustancias psicoactivas"].public_allowed
