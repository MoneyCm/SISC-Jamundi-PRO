import pandas as pd
import io
import logging
import re
import unicodedata

logger = logging.getLogger("sisc_reader")


def normalize_sheet_token(value):
    """Normaliza un texto de celda para comparar encabezados (igual que el preflight)."""
    text = unicodedata.normalize("NFKD", str(value if value is not None else ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^A-Z0-9]+", "", text.upper())


def score_header_match(df_raw, alias_map, max_scan_rows=10):
    """Devuelve (indice_fila, puntaje, tiene_ancla) de la mejor fila candidata."""
    best_idx = 0
    best_score = 0
    best_has_anchor = False
    total = min(len(df_raw), max_scan_rows)
    for idx in range(total):
        hits = set()
        for value in df_raw.iloc[idx].tolist():
            token = normalize_sheet_token(value)
            if not token:
                continue
            for canonical, aliases in alias_map.items():
                if any(normalize_sheet_token(alias) == token for alias in aliases):
                    hits.add(canonical)
                    break
        score = len(hits)
        has_anchor = "hecho_id" in hits or "id_fuente" in hits
        if (has_anchor and not best_has_anchor) or (
            has_anchor == best_has_anchor and score > best_score
        ):
            best_idx, best_score, best_has_anchor = idx, score, has_anchor
    return best_idx, best_score, best_has_anchor


def select_sheet_frame(file_bytes, filename, alias_map):
    """Lee el libro y devuelve (nombre_hoja, frame) de la hoja que mejor matchea.

    Los libros SIEDCO traen pivotes junto a la base; pandas leería la primera
    hoja. Si ninguna hoja califica, devuelve la primera con encabezado en la
    fila 0 (comportamiento anterior).
    """
    lower = (filename or "").lower()
    if lower.endswith(".csv"):
        frames = {"datos": pd.read_csv(io.BytesIO(file_bytes), header=None)}
    else:
        try:
            frames = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None, header=None, engine="openpyxl")
        except Exception:
            frames = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None, header=None)
        if isinstance(frames, pd.DataFrame):
            frames = {"datos": frames}
    names = [name for name, raw in (frames or {}).items() if raw is not None and len(raw) > 0]
    if not names:
        raise ValueError("El archivo no contiene hojas legibles.")
    best_key = None
    best_pick = None
    for name in names:
        raw = frames[name]
        idx, score, anchor = score_header_match(raw, alias_map)
        key = (1 if anchor else 0, score)
        if best_key is None or key > best_key:
            best_key = key
            best_pick = (name, raw, idx, score, anchor)
    name, raw, idx, score, anchor = best_pick
    if not (anchor or score >= 5):
        first = frames[names[0]]
        return names[0], promote_header_row(first, 0)
    return name, promote_header_row(raw, idx)


def detect_header_row_index(df_raw, alias_map, max_scan_rows=10):
    """Devuelve el índice de la fila que parece ser el encabezado.

    Las sábanas SIEDCO suelen traer filas de título arriba. Se puntúa cada
    fila por la cantidad de claves canónicas distintas que aparecen y se exige
    ancla (hecho_id/id_fuente) o puntaje alto, para no confundir un título
    con el encabezado. Si ninguna fila califica, devuelve 0.
    """
    best_idx, best_score, best_has_anchor = score_header_match(df_raw, alias_map, max_scan_rows)
    if best_has_anchor or best_score >= 5:
        return best_idx
    return 0


def promote_header_row(df_raw, header_idx):
    """Convierte la fila indicada en encabezado y descarta las filas superiores."""
    header = []
    for value in df_raw.iloc[header_idx].tolist():
        text = "" if value is None else str(value).strip()
        header.append("" if text in {"", "nan", "None"} else text)
    seen = {}
    columns = []
    for pos, name in enumerate(header):
        if not name:
            name = f"COLUMNA_{pos}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        columns.append(name)
    data = df_raw.iloc[header_idx + 1:].reset_index(drop=True)
    data.columns = columns
    return data

def read_html_table(file_bytes: bytes):
    """Primera tabla de un HTML guardado como .xls (así exporta la Policía los reportes del RNMC).

    Usa BeautifulSoup con el analizador de Python: no depende de lxml. La primera fila es el encabezado.
    """
    head = file_bytes[:2048].lstrip().lower()
    if not (head.startswith(b"<") and b"<table" in file_bytes[:200000].lower()):
        return None
    from bs4 import BeautifulSoup

    for encoding in ("utf-8", "latin-1"):
        try:
            text = file_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    table = BeautifulSoup(text, "html.parser").find("table")
    if table is None:
        return None
    # Solo las filas y celdas propias de la tabla: el relato de algunos hechos trae tablas anidadas.
    trs = [tr for tr in table.find_all("tr") if tr.find_parent("table") is table]
    rows = [[cell.get_text(" ", strip=True) for cell in tr.find_all(["th", "td"], recursive=False)] for tr in trs]
    rows = [row for row in rows if any(row)]
    if len(rows) < 2:
        return None
    columns = rows[0]
    body = [(row + [""] * len(columns))[:len(columns)] for row in rows[1:]]
    return pd.DataFrame(body, columns=columns).replace("", None)


def smart_read_file(file_bytes: bytes, header=0) -> pd.DataFrame:
    """
    Intenta leer un archivo probando múltiples formatos y codificaciones.
    Incluye validación de integridad para archivos ZIP/XLSX.
    """
    # Validación de Integridad XLSX (ZIP)
    if file_bytes.startswith(b'PK\x03\x04'):
        # Buscar la firma de cierre PK\x05\x06 en los últimos 1024 bytes
        if b'PK\x05\x06' not in file_bytes[-1024:]:
            raise ValueError("ERROR_FILE_CORRUPT_XLSX: El archivo parece ser un Excel (.xlsx) pero está incompleto o corrupto (falta la firma de cierre ZIP). Por favor, vuelva a descargarlo o guárdelo nuevamente desde Excel.")

    # 0. Un HTML guardado como .xls (reportes del RNMC): leerlo como tabla antes de que el
    #    intento de CSV lo tome por texto separado.
    if file_bytes[:2048].lstrip()[:1] == b"<":
        try:
            frame = read_html_table(file_bytes)
            if frame is not None:
                return frame
        except Exception as e:
            logger.debug(f"Falló lectura HTML propia: {e}")

    # 1. Intento: Excel Moderno (.xlsx)
    try:
        return pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl", header=header)
    except Exception as e:
        logger.debug(f"Falló lectura openpyxl: {e}")

    # 2. Intento: Excel Antiguo (.xls)
    try:
        # Nota: requiere xlrd, si no está, fallará al except
        return pd.read_excel(io.BytesIO(file_bytes), header=header)
    except Exception as e:
        logger.debug(f"Falló lectura Excel genérica: {e}")

    # 3. Intento: CSV / Texto con detección de separador y codificación
    for enc in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1', 'utf-16']:
        try:
            # sep=None con engine='python' detecta automáticamente , ; 	 |
            df = pd.read_csv(io.BytesIO(file_bytes), encoding=enc, sep=None, engine='python', header=header)
            if df is not None and len(df.columns) > 1:
                logger.info(f"Archivo detectado como CSV con codificación {enc}")
                return df
        except:
            continue

    # 4. Intento: Tabla HTML (común en exportaciones de Oracle/SAP renombradas a .xls)
    try:
        dfs = pd.read_html(io.BytesIO(file_bytes), header=header)
        if dfs:
            logger.info("Archivo detectado como Tabla HTML")
            return dfs[0]
    except Exception as e:
        logger.debug(f"Falló lectura HTML: {e}")
    try:
        frame = read_html_table(file_bytes)
        if frame is not None:
            logger.info("Archivo detectado como Tabla HTML (lector propio)")
            return frame
    except Exception as e:
        logger.debug(f"Falló lectura HTML propia: {e}")

    # Si todo falla, lanzamos la excepción final
    raise ValueError("El formato del archivo no es reconocido (no es Excel, CSV válido ni HTML)")
