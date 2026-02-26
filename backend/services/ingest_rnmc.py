import pandas as pd
import unicodedata
import hashlib
import logging
import re
from datetime import datetime, date
from typing import List, Dict, Generator, Optional, Tuple
import io
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from db.models_intelligence import RNMCMeasure, IngestionFile, RNMCStatusHistory

logger = logging.getLogger("sisc_api")

# --- Heurística robusta para localizar la tabla RNMC en cualquier hoja ---

REQUIRED_KEYS = {"FECHA_ACTUACION", "MEDIDA", "ESTADO"}  # Mínimo obligatorio
ID_KEYS = {"EXPEDIENTE", "ID_REGISTRA", "ID_REGISTRO"}   # Algún identificador

ALIASES = {
    # Fechas de actuación
    "FECHA ACTUACION": "FECHA_ACTUACION",
    "FECHA_ACTUACION": "FECHA_ACTUACION",
    "FECHA ACTUACIÓN": "FECHA_ACTUACION",
    "FECHA_ACTUACIÓN": "FECHA_ACTUACION",
    # Identificadores
    "EXPEDIENTE": "EXPEDIENTE",
    "ID REGISTRA": "ID_REGISTRA",
    "ID_REGISTRA": "ID_REGISTRA",
    "ID REGISTRO": "ID_REGISTRO",
    "ID_REGISTRO": "ID_REGISTRO",
    # Ubicación
    "MUNICIPIO": "MUNICIPIO",
    "MPIO": "MUNICIPIO",
    "LOCALIDAD": "LOCALIDAD",
    # Medida / Estado
    "MEDIDA": "MEDIDA",
    "ESTADO": "ESTADO",
}

def to_key(s: str) -> str:
    """Normaliza un texto para comparaciones (sin tildes, mayúsculas, sin espacios extra)."""
    s = (str(s) if s is not None else "").strip().upper()
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return " ".join(s.split())

def _norm_header(val: str) -> str:
    """Normaliza un nombre de columna a un identificador estable."""
    if val is None:
        return ""
    s = str(val).strip().upper()
    s = re.sub(r"\s+", " ", s)
    return ALIASES.get(s, s.replace(" ", "_"))


def find_rnmc_table_in_excel(file_bytes: bytes) -> Tuple[str, int]:
    """
    Escanea todas las hojas y devuelve (sheet_name, header_row_index) para la tabla RNMC.
    header_row_index es 0-based (útil para header=<idx> en read_excel).
    """
    # Usamos un buffer BytesIO para no depender de paths
    xls = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")

    best: Optional[Tuple[str, int, int]] = None  # (sheet, header_row, score)

    for sheet in xls.sheet_names:
        # Preview limitado para detectar fila de encabezados
        preview = pd.read_excel(
            xls, sheet_name=sheet, header=None, nrows=60, engine="openpyxl"
        )

        max_rows_to_scan = min(30, len(preview))
        for r in range(max_rows_to_scan):
            row_vals = preview.iloc[r].tolist()
            headers = [
                _norm_header(v)
                for v in row_vals
                if str(v).strip() not in ("", "nan", "None")
            ]
            if not headers:
                continue

            headers_set = set(headers)
            has_required = REQUIRED_KEYS.issubset(headers_set)
            has_id = len(headers_set.intersection(ID_KEYS)) > 0
            score = (
                len(headers_set.intersection(REQUIRED_KEYS))
                + len(headers_set.intersection(ID_KEYS))
            )

            if has_required and has_id:
                if best is None or score > best[2]:
                    best = (sheet, r, score)

    if not best:
        raise ValueError(
            "No se detectó una tabla RNMC: faltan columnas mínimas "
            "(FECHA_ACTUACION, MEDIDA, ESTADO + EXPEDIENTE/ID_REGISTRA/ID_REGISTRO)."
        )

    sheet_name, header_row, _ = best
    logger.info(f"[RNMCIngestor] Tabla RNMC detectada en hoja '{sheet_name}' (fila encabezado={header_row})")
    return sheet_name, header_row


def read_rnmc_dataframe(file_bytes: bytes) -> Tuple[pd.DataFrame, str, int]:
    """
    Lee el Excel, auto-detecta hoja y fila de encabezado y devuelve:
    (DataFrame normalizado, sheet_name, header_row_index).
    """
    sheet, header_row = find_rnmc_table_in_excel(file_bytes)

    df = pd.read_excel(
        io.BytesIO(file_bytes),
        sheet_name=sheet,
        header=header_row,
        engine="openpyxl",
    )

    # Normalizar nombres de columnas
    df.columns = [_norm_header(c) for c in df.columns]
    # Eliminar filas completamente vacías
    df = df.dropna(how="all")

    return df, sheet, header_row


class RNMCIngestor:
    def __init__(self, db: Session):
        self.db = db

    def normalize_text(self, text: str) -> str:
        if not isinstance(text, str):
            return str(text) if text is not None else ""
        
        # Eliminar diacríticos y normalizar a NFD
        text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8')
        # Mayúsculas + trim
        text = text.upper().strip()
        # Colapsar espacios: "  A   B  " -> "A B"
        text = " ".join(text.split())
        return text

    def _parse_date(self, val) -> Optional[datetime]:
        if pd.isna(val):
            return None
        if isinstance(val, (datetime, date)):
            return pd.to_datetime(val)
        try:
            return pd.to_datetime(str(val), dayfirst=True)
        except:
            return None

    def _generate_fingerprint(self, row: Dict) -> str:
        """
        Refined fingerprint (Idempotency without status):
        FECHA_ACTUACION + EXPEDIENTE + MEDIDA
        """
        fecha_act = self._parse_date(row.get('FECHA_ACTUACION'))
        fecha_str = fecha_act.isoformat() if fecha_act else "NO_DATE"
        
        expediente = str(row.get('EXPEDIENTE', '')).strip()
        medida = self.normalize_text(str(row.get('MEDIDA', '')))
        
        if expediente and expediente.lower() != 'nan' and expediente != '':
            raw = f"{fecha_str}|{expediente}|{medida}"
        else:
            id_registra = str(row.get('ID_REGISTRA', row.get('ID_REGISTRO', ''))).strip()
            raw = f"{fecha_str}|{id_registra}|{medida}"
            
        return hashlib.sha256(raw.encode()).hexdigest()

    def process_file(self, file_content: bytes, filename: str) -> Dict:
        # 1. Auto-detectar hoja y fila de encabezados robustamente
        try:
            df, detected_sheet, header_row = read_rnmc_dataframe(file_content)
        except ValueError as e:
            logger.error(f"[RNMCIngestor] {e} en archivo {filename}")
            return {
                "inserted": 0,
                "updated": 0,
                "total": 0,
                "detected_sheet": None,
                "header_row": None,
                "columns_detected": [],
                "error": str(e),
            }

        if df.empty:
            logger.warning(
                f"[RNMCIngestor] DataFrame vacío después de detectar hoja '{detected_sheet}' "
                f"en archivo {filename} (fila encabezado={header_row})."
            )
            return {
                "inserted": 0,
                "updated": 0,
                "total": 0,
                "detected_sheet": detected_sheet,
                "header_row": header_row,
                "columns_detected": list(df.columns),
            }

        # 2. Diagnóstico y Filtro de Municipio
        df["MUNICIPIO_KEY"] = df["MUNICIPIO"].astype(str).map(to_key) if "MUNICIPIO" in df.columns else ""
        
        logger.info("RNMC df shape: %s", df.shape)
        logger.info("RNMC columns: %s", list(df.columns))
        
        raw_uniques = df["MUNICIPIO"].dropna().unique().tolist()[:10] if "MUNICIPIO" in df.columns else []
        key_uniques = df["MUNICIPIO_KEY"].dropna().unique().tolist()[:10]
        
        logger.info("RNMC municipio raw uniques: %s", raw_uniques)
        logger.info("RNMC municipio key uniques: %s", key_uniques)

        before = len(df)
        df = df[df["MUNICIPIO_KEY"] == "JAMUNDI"].copy()
        logger.info("RNMC rows before/after municipio filter: %s -> %s", before, len(df))

        if df.empty:
            logger.warning(
                f"[RNMCIngestor] DataFrame vacío tras filtrar por municipio 'JAMUNDI' en {filename}."
            )
            return {
                "inserted": 0,
                "updated": 0,
                "total": 0,
                "detected_sheet": detected_sheet,
                "header_row": header_row,
                "columns_detected": list(df.columns),
                "df_shape": (before, len(df.columns)),
                "municipio_uniques": raw_uniques,
                "detail": f"Se encontraron {before} filas, pero ninguna coincide con 'JAMUNDI'. Municipios detectados: {raw_uniques}"
            }

        records_to_upsert = []
        source_id = "INSPECCION_MEDIDAS_RNMC"
        
        inserted = 0
        updated = 0
        
        for _, row_raw in df.iterrows():
            row = row_raw.to_dict()
            
            # Normalización de campos clave
            muni = self.normalize_text(str(row.get('MUNICIPIO', '')))
            dto = self.normalize_text(str(row.get('DTO', row.get('DEPARTAMENTO', ''))))
            medida = self.normalize_text(str(row.get('MEDIDA', '')))
            estado = self.normalize_text(str(row.get('ESTADO', '')))
            tipo_seg = self.normalize_text(str(row.get('TIPO_SEGUIMIENTO', '')))
            localidad = self.normalize_text(str(row.get('LOCALIDAD', '')))
            
            # Fechas
            f_act = self._parse_date(row.get('FECHA_ACTUACION'))
            f_ini = self._parse_date(row.get('FECHA_INICIO'))
            f_fin = self._parse_date(row.get('FECHA_FIN'))
            f_pago = self._parse_date(row.get('FECHA_PAGO'))
            f_liq = self._parse_date(row.get('FECHA_LIQUIDACION'))
            
            # Valores
            def to_float(v):
                if pd.isna(v): return 0.0
                try: return float(v)
                except: return 0.0

            v_neto = to_float(row.get('VALOR_NETO'))
            v_pagado = to_float(row.get('VALOR_PAGADO'))
            
            # Días
            try:
                dias = int(row.get('DIAS', 0))
            except:
                dias = 0

            fingerprint = self._generate_fingerprint(row)
            
            record = {
                "source_id": source_id,
                "departamento": dto,
                "municipio": muni,
                "localidad": localidad,
                "expediente": str(row.get('EXPEDIENTE', '')),
                "medida": medida,
                "fecha_actuacion": f_act,
                "fecha_inicio": f_ini.date() if f_ini else None,
                "fecha_fin": f_fin.date() if f_fin else None,
                "dias": dias,
                "tipo_seguimiento": tipo_seg,
                "estado": estado,
                "fecha_pago": f_pago.date() if f_pago else None,
                "entidad_pago": self.normalize_text(str(row.get('ENTIDAD_PAGO', ''))),
                "valor_neto": v_neto,
                "valor_pagado": v_pagado,
                "fecha_liquidacion": f_liq.date() if f_liq else None,
                "event_fingerprint": fingerprint,
                "fuente_archivo": filename,
                "fecha_ingesta": datetime.utcnow()
            }
            
            records_to_upsert.append(record)

        if not records_to_upsert:
            return {"inserted": 0, "updated": 0, "total": 0}

        # PERFORMANCE: Pre-cargar registros existentes para evitar N+1 selects
        fingerprints = [r["event_fingerprint"] for r in records_to_upsert]
        existing_map = {
            m.event_fingerprint: m 
            for m in self.db.query(RNMCMeasure).filter(
                RNMCMeasure.source_id == source_id,
                RNMCMeasure.event_fingerprint.in_(fingerprints)
            ).all()
        }

        # TRANSACTIONAL PROCESSING
        try:
            for rec in records_to_upsert:
                fp = rec["event_fingerprint"]
                existing = existing_map.get(fp)

                if existing:
                    # Detectar cambio de estado para trazabilidad
                    if existing.estado != rec["estado"]:
                        history = RNMCStatusHistory(
                            measure_id=existing.id,
                            source_id=existing.source_id,
                            event_fingerprint=existing.event_fingerprint,
                            estado_anterior=existing.estado,
                            estado_nuevo=rec["estado"],
                            fecha_reportada=existing.fecha_actuacion,
                            changed_at=datetime.utcnow(),
                            fuente_archivo=rec["fuente_archivo"]
                        )
                        self.db.add(history)
                    updated += 1
                else:
                    inserted += 1

                # UPSERT core execution
                stmt = insert(RNMCMeasure).values(**rec)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['source_id', 'event_fingerprint'],
                    set_={k: v for k, v in rec.items() if k not in ['source_id', 'event_fingerprint', 'fecha_ingesta']}
                )
                self.db.execute(stmt)
            
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error en transacción de ingesta RNMC: {e}")
            raise e
        
        return {
            "inserted": inserted,
            "updated": updated,
            "total": len(records_to_upsert)
        }
