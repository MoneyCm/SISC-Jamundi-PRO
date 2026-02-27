import pandas as pd
import io
import logging

logger = logging.getLogger("sisc_reader")

def smart_read_file(file_bytes: bytes) -> pd.DataFrame:
    """
    Intenta leer un archivo probando múltiples formatos y codificaciones.
    Incluye validación de integridad para archivos ZIP/XLSX.
    """
    # Validación de Integridad XLSX (ZIP)
    if file_bytes.startswith(b'PK\x03\x04'):
        # Buscar la firma de cierre PK\x05\x06 en los últimos 1024 bytes
        if b'PK\x05\x06' not in file_bytes[-1024:]:
            raise ValueError("ERROR_FILE_CORRUPT_XLSX: El archivo parece ser un Excel (.xlsx) pero está incompleto o corrupto (falta la firma de cierre ZIP). Por favor, vuelva a descargarlo o guárdelo nuevamente desde Excel.")

    # 1. Intento: Excel Moderno (.xlsx)
    try:
        return pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
    except Exception as e:
        logger.debug(f"Falló lectura openpyxl: {e}")

    # 2. Intento: Excel Antiguo (.xls)
    try:
        # Nota: requiere xlrd, si no está, fallará al except
        return pd.read_excel(io.BytesIO(file_bytes))
    except Exception as e:
        logger.debug(f"Falló lectura Excel genérica: {e}")

    # 3. Intento: CSV / Texto con detección de separador y codificación
    for enc in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1', 'utf-16']:
        try:
            # sep=None con engine='python' detecta automáticamente , ; 	 |
            df = pd.read_csv(io.BytesIO(file_bytes), encoding=enc, sep=None, engine='python')
            if df is not None and len(df.columns) > 1:
                logger.info(f"Archivo detectado como CSV con codificación {enc}")
                return df
        except:
            continue

    # 4. Intento: Tabla HTML (común en exportaciones de Oracle/SAP renombradas a .xls)
    try:
        dfs = pd.read_html(io.BytesIO(file_bytes))
        if dfs:
            logger.info("Archivo detectado como Tabla HTML")
            return dfs[0]
    except Exception as e:
        logger.debug(f"Falló lectura HTML: {e}")

    # Si todo falla, lanzamos la excepción final
    raise ValueError("El formato del archivo no es reconocido (no es Excel, CSV válido ni HTML)")
