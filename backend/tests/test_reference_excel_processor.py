from datetime import date
from io import BytesIO

import pandas as pd

from services.excel_processor import NationalStatsProcessor


def _reference_workbook() -> bytes:
    frame = pd.DataFrame([
        {
            "COD_MUNI": 76364,
            "MUNICIPIO": "Jamundí",
            "DEPARTAMENTO": "Valle del Cauca",
            "FECHA_HECHO": "2025-01-15",
            "CANTIDAD": 3,
        },
        {
            "COD_MUNI": 76364,
            "MUNICIPIO": "Jamundí",
            "DEPARTAMENTO": "Valle del Cauca",
            "FECHA_HECHO": "2025-01-20",
            "CANTIDAD": 2,
        },
        {
            "COD_MUNI": 76001,
            "MUNICIPIO": "Cali",
            "DEPARTAMENTO": "Valle del Cauca",
            "FECHA_HECHO": "2025-01-24",
            "CANTIDAD": 7,
        },
    ])
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False)
    return output.getvalue()


def test_reference_processor_keeps_all_coded_municipalities_as_monthly_aggregates():
    records = list(NationalStatsProcessor().process_reference_excel(
        _reference_workbook(),
        "HURTO PERSONAS 2025.xlsx",
        source_cutoff=date(2025, 1, 31),
    ))

    assert len(records) == 2
    jamundi = next(record for record in records if record["codigo_dane"] == "76364")
    cali = next(record for record in records if record["codigo_dane"] == "76001")
    assert jamundi["cantidad"] == 5
    assert cali["cantidad"] == 7
    assert all(record["source_id"] == "MINDEFENSA_REFERENCE" for record in records)
    assert all(record["fecha_corte_mindefensa"] == date(2025, 1, 31) for record in records)
    assert all("barrio" not in record for record in records)
