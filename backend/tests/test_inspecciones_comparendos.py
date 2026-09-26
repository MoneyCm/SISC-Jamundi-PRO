import pandas as pd

from services.inspeccion_service import InspeccionService


def test_comparendos_export_keeps_only_operational_columns():
    service = InspeccionService(db=None)
    raw = pd.DataFrame([{
        "DTO": "VALLE", "LUGAR": "JAMUNDI - CM", "FECHA_HECHOS": "2026-04-19 00:00:00",
        "EXPEDIENTE": "76-364-6-2026-2045", "COMPARENDO": "123", "ESTADO_COMPARENDO": "EN PROCESO",
        "MEDIDA": "Multa General Tipo 4", "ESTADO_MEDIDA": "PENDIENTE", "BARRIO_HECHOS": "TERRANOVA",
        # Datos personales del infractor y del procedimiento: no deben pasar.
        "INFRACTOR": "PERSONA", "IDENTIFICACION": "1234567", "TELEFONO": "3000000000",
        "DIRECCION_RESIDE": "CALLE 1", "RELATO_HECHOS": "relato", "POLICIA_IMPONE": "AGENTE",
    }])
    raw.columns = [service.normalize_text(column).replace(' ', '_') for column in raw.columns]
    assert service.COMPARENDOS_MARKERS.issubset(raw.columns)

    converted = service.comparendos_to_rnmc(raw)

    assert list(converted.columns) == ["DTO", "MUNICIPIO", "LOCALIDAD", "LUGAR", "EXPEDIENTE", "MEDIDA", "ESTADO", "FECHA_ACTUACION"]
    row = converted.iloc[0]
    assert row["FECHA_ACTUACION"] == "2026-04-19 00:00:00"  # fecha real del hecho, no la del día de carga
    assert row["ESTADO"] == "PENDIENTE"
    assert row["LOCALIDAD"] == "TERRANOVA"
    assert row["MUNICIPIO"] == "JAMUNDI"
    assert not {"INFRACTOR", "IDENTIFICACION", "TELEFONO", "DIRECCION_RESIDE", "RELATO_HECHOS", "POLICIA_IMPONE"} & set(converted.columns)
