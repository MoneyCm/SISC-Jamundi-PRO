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

    assert list(converted.columns) == ["DTO", "MUNICIPIO", "LOCALIDAD", "LUGAR", "EXPEDIENTE", "MEDIDA", "ESTADO", "FECHA_ACTUACION",
                                       "ARTICULO", "COMPORTAMIENTO"]
    row = converted.iloc[0]
    assert row["FECHA_ACTUACION"] == "2026-04-19 00:00:00"  # fecha real del hecho, no la del día de carga
    assert row["ESTADO"] == "PENDIENTE"
    assert row["LOCALIDAD"] == "TERRANOVA"
    assert row["MUNICIPIO"] == "JAMUNDI"
    assert not {"INFRACTOR", "IDENTIFICACION", "TELEFONO", "DIRECCION_RESIDE", "RELATO_HECHOS", "POLICIA_IMPONE"} & set(converted.columns)


def test_rnmc_html_report_is_read_without_nested_rows_or_personal_data():
    """El RNMC exporta un HTML con extensión .xls; el relato puede traer tablas dentro de la celda."""
    html = (
        "<form><table><caption>POLICIA NACIONAL</caption>"
        "<tr><td>DTO</td><td>LUGAR</td><td>FECHA_HECHOS</td><td>EXPEDIENTE</td><td>COMPARENDO</td>"
        "<td>ARTICULO</td><td>COMPORTAMIENTO</td><td>MEDIDA</td><td>ESTADO_MEDIDA</td><td>BARRIO_HECHOS</td>"
        "<td>INFRACTOR</td><td>RELATO_HECHOS</td></tr>"
        "<tr><td>VALLE</td><td>JAMUNDI - CM</td><td>19/04/2026</td><td>76-364-6-2026-1</td><td>1</td>"
        "<td>Art. 35 - Relaciones con las autoridades</td><td>Irrespetar a las autoridades</td>"
        "<td>Multa General Tipo 4</td><td>PENDIENTE</td><td>CENTRO</td><td>PERSONA</td>"
        "<td><table><tr><td>relato</td></tr></table></td></tr>"
        "</table></form>"
    ).encode("latin-1")
    service = InspeccionService(db=None)

    frame, source_format = service.read_frame(html)

    assert source_format == "COMPARENDOS"
    assert len(frame) == 1
    row = frame.iloc[0]
    assert row["EXPEDIENTE"] == "76-364-6-2026-1"
    assert row["ARTICULO"].startswith("Art. 35")
    assert row["LOCALIDAD"] == "CENTRO"

    pending = pd.DataFrame([{"FECHA_HECHOS": "01/05/2026", "EXPEDIENTE": "76-364-6-2026-2", "COMPARENDO": "2",
                             "MEDIDA": None, "ESTADO_MEDIDA": "PENDIENTE"}])
    assert service.comparendos_to_rnmc(pending).iloc[0]["MEDIDA"] == "Medida por definir"
    assert not {"INFRACTOR", "RELATO_HECHOS"} & set(frame.columns)


def test_encabezado_mas_abajo_y_matriz_sin_columna_comparendo():
    """Reportes con títulos arriba (encabezado en la fila 4) y la MATRIZ RNMC, que no trae COMPARENDO."""
    import io
    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    hoja.append(["POLICIA NACIONAL - Reporte"])
    hoja.append([])
    hoja.append(["Periodo 2025"])
    hoja.append(["DTO", "LUGAR", "FECHA_HECHOS", "EXPEDIENTE", "ARTICULO", "MEDIDA", "ESTADO_MEDIDA", "BARRIO_HECHOS", "INFRACTOR"])
    hoja.append(["VALLE", "JAMUNDI - CM", "2025-03-01", "76-364-6-2025-9", "Art. 27 - Vida", None, "PENDIENTE", "CENTRO", "PERSONA"])
    salida = io.BytesIO()
    libro.save(salida)

    frame, source_format = InspeccionService(db=None).read_frame(salida.getvalue())

    assert source_format == "COMPARENDOS"
    assert list(frame["EXPEDIENTE"]) == ["76-364-6-2025-9"]
    assert frame.iloc[0]["MEDIDA"] == "Medida por definir"
    assert "INFRACTOR" not in frame.columns
