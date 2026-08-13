import io

import pandas as pd

from services import dq_service


def excel_bytes(rows):
    output = io.BytesIO()
    pd.DataFrame(rows).to_excel(output, index=False)
    return output.getvalue()


def complete_police_row(**overrides):
    row = {
        "HECHOS_ID": "H-001",
        "DESCRIPCION_CONDUCTA": "HURTO A PERSONAS",
        "FECHA_HECHO": "2026-08-01",
        "NoSEMANA": 31,
        "BARRIOS_HECHO": "CENTRO",
        "ZONA": "URBANA",
        "MUNICIPIO": "JAMUNDI",
        "HORA24": "10:30",
        "MODALIDAD": "ATRACO",
        "ARMAS_MEDIOS": "SIN EMPLEO DE ARMAS",
    }
    row.update(overrides)
    return row


def test_police_profile_accepts_complete_weekly_file():
    report = dq_service.run_dq(
        excel_bytes([complete_police_row()]),
        "sabana.xlsx",
        source_name="POLICIA_SEMANAL",
        profile="POLICIA_SEMANAL",
    )

    assert report["semaforo"] == "VERDE"
    assert report["status"] == "READY"
    assert report["rows_total"] == 1
    assert report["score_completeness"] == 1.0


def test_police_profile_blocks_missing_critical_column():
    row = complete_police_row()
    row.pop("ZONA")

    report = dq_service.run_dq(
        excel_bytes([row]),
        "sabana_sin_zona.xlsx",
        source_name="POLICIA_SEMANAL",
        profile="POLICIA_SEMANAL",
    )

    assert report["semaforo"] == "ROJO"
    assert report["status"] == "BLOCKED"
    assert report["missing_cols"] == ["ZONA"]


def test_inspections_profile_warns_when_part_of_file_is_outside_jamundi():
    rows = [
        {
            "EXPEDIENTE": "E-001",
            "MEDIDA": "SUSPENSION",
            "FECHA_ACTUACION": "2026-07-10",
            "MUNICIPIO": "JAMUNDI",
            "LOCALIDAD": "CENTRO",
            "ESTADO": "ACTIVA",
        },
        {
            "EXPEDIENTE": "E-002",
            "MEDIDA": "MULTA",
            "FECHA_ACTUACION": "2026-07-11",
            "MUNICIPIO": "CALI",
            "LOCALIDAD": "SUR",
            "ESTADO": "ACTIVA",
        },
    ]

    report = dq_service.run_dq(
        excel_bytes(rows),
        "inspecciones.xlsx",
        source_name="INSPECCIONES_POLICIA",
        profile="INSPECCIONES",
    )

    assert report["semaforo"] == "AMARILLO"
    assert report["status"] == "REVIEW"
    assert any(issue["field"] == "MUNICIPIO" for issue in report["issues"])


def test_normalized_records_reject_empty_extraction():
    report = dq_service.run_records_dq([], "vacio.xlsx", "INTELLIGENCE_DESCONOCIDA")

    assert report["semaforo"] == "ROJO"
    assert report["rows_total"] == 0


def test_regional_records_do_not_require_every_row_to_be_jamundi():
    report = dq_service.run_records_dq(
        [
            {
                "source_id": "ASPERSION",
                "fecha_hecho": "2026-07-01",
                "municipio": "CALI",
                "cantidad": 2,
                "event_fingerprint": "regional-1",
            }
        ],
        "valle.xlsx",
        "INTELLIGENCE_ASPERSION",
    )

    assert report["semaforo"] == "VERDE"


def test_institutional_findings_are_visible_in_central_quality_history():
    report = dq_service.report_from_findings(
        "comisaria.xlsx",
        "INSTITUTIONAL_COMISARIAS",
        [
            {
                "agent_name": "privacy",
                "severity": "HIGH",
                "message": "Se detecto un dato que requiere revision.",
                "blocks_publication": True,
            }
        ],
        rows_total=4,
    )

    assert report["semaforo"] == "ROJO"
    assert report["status"] == "BLOCKED"
    assert report["issues"][0]["field"] == "PRIVACY"


def test_geo_profile_rejects_invalid_coordinates():
    report = dq_service.run_dq(
        excel_bytes(
            [
                {
                    "FECHA": "2026-07-01",
                    "HORA": "09:00",
                    "DELITO": "HURTO",
                    "LATITUD": 250,
                    "LONGITUD": -76.53,
                    "BARRIO": "CENTRO",
                    "DESCRIPCION": "PRUEBA",
                }
            ]
        ),
        "eventos.xlsx",
        source_name="EVENTOS_GEO_MANUAL",
        profile="EVENTOS_GEO",
    )

    assert report["semaforo"] == "ROJO"
    assert any(issue["field"] == "COORDENADAS" for issue in report["issues"])
