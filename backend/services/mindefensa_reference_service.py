"""Persistencia de la referencia agregada de MinDefensa (nacional, territorial y municipal).

La usan dos caminos con la misma lógica:
- El endpoint /intelligence/reference-aggregate-upload (monitor en GitHub o remoto).
- El sincronizador local (scripts/sync_source_monitors.py), que lee los libros ya
  descargados por el monitor en este equipo y escribe directo en la base local,
  sin credenciales de usuario.
"""
from __future__ import annotations

from datetime import date, datetime
import hashlib
from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from db.models_intelligence import NationalCrimeStats, NationalReferenceCoverage
from services.excel_processor import NationalStatsProcessor
from services.national_context_service import normalize_municipality_code

COMPACT_REFERENCE_SOURCE = "MINDEFENSA_REFERENCE_COMPACT"
MUNICIPAL_REFERENCE_SOURCE = "MINDEFENSA_MUNICIPAL_TOTAL"
MAX_RECORDS = 30_000
MAX_MUNICIPAL_TOTALS = 10_000


def _get(item: Any, key: str):
    return item.get(key) if isinstance(item, Mapping) else getattr(item, key)


def _as_date(value) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _align_id_sequences(db: Session) -> None:
    """Corrige secuencias de id desfasadas (p. ej. tras restaurar un respaldo).

    Si la secuencia quedó por debajo del id máximo, PostgreSQL intenta reutilizar
    ids existentes y la inserción falla con UniqueViolation en la llave primaria.
    """
    for table in ("national_crime_stats", "national_reference_coverage"):
        # Dejar la secuencia en el id máximo es seguro aunque estuviera adelantada:
        # el siguiente id será MAX(id) + 1, que nunca existe.
        db.execute(text(
            f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
            f"(SELECT GREATEST(COALESCE(MAX(id), 0), 1) FROM {table})) "
            f"WHERE pg_get_serial_sequence('{table}', 'id') IS NOT NULL"
        ))


def persist_reference_payload(db: Session, payload: Any) -> dict:
    """Valida y guarda un paquete de referencia. No hace commit.

    Devuelve {"records": n, "coverage_years": [...]}. Lanza ValueError si el
    paquete está vacío o excede los límites operativos.
    """
    filename = _get(payload, "filename")
    tipo_delito = _get(payload, "tipo_delito")
    source_cutoff = _as_date(_get(payload, "source_cutoff"))
    raw_records = _get(payload, "records") or []
    raw_totals = _get(payload, "municipal_totals") or []
    raw_coverage = _get(payload, "coverage") or []

    if not raw_records:
        raise ValueError("La referencia agregada no contiene registros.")
    if len(raw_records) > MAX_RECORDS or len(raw_totals) > MAX_MUNICIPAL_TOTALS:
        raise ValueError("La referencia agregada excede el límite operativo.")

    processor = NationalStatsProcessor()
    now = datetime.utcnow()
    records = []
    for item in raw_records:
        raw_code = str(_get(item, "codigo_dane"))
        code = "NACIONAL" if raw_code.upper() == "NACIONAL" else normalize_municipality_code(raw_code)
        anio, mes, cantidad = int(_get(item, "anio")), int(_get(item, "mes")), int(_get(item, "cantidad"))
        if not code or not 1 <= mes <= 12 or anio < 2000 or cantidad < 0:
            continue
        municipio = str(_get(item, "municipio") or "").strip()
        fingerprint = hashlib.sha256(
            f"{COMPACT_REFERENCE_SOURCE}|{tipo_delito}|{code}|{anio}|{mes}".encode()
        ).hexdigest()
        records.append({
            "source_id": COMPACT_REFERENCE_SOURCE,
            "departamento": str(_get(item, "departamento") or "").strip() or "NO INFORMADO",
            "municipio": municipio or code,
            "municipio_normalizado": processor.normalize_text(municipio or code),
            "codigo_dane": code,
            "fecha_hecho": date(anio, mes, 1),
            "fecha_corte_mindefensa": source_cutoff,
            "anio": anio,
            "mes": mes,
            "tipo_delito": tipo_delito,
            "cantidad": cantidad,
            "fuente_archivo": filename,
            "event_fingerprint": fingerprint,
            "hash_registro": fingerprint,
            "fecha_ingesta": now,
        })
    for item in raw_totals:
        code = normalize_municipality_code(_get(item, "codigo_dane"))
        anio = int(_get(item, "anio"))
        mes = int(_get(item, "period_end_month"))
        cantidad = int(_get(item, "cantidad"))
        if not code or not 1 <= mes <= 12 or anio < 2000 or cantidad < 0:
            continue
        municipio = str(_get(item, "municipio") or "").strip()
        fingerprint = hashlib.sha256(
            f"{MUNICIPAL_REFERENCE_SOURCE}|{tipo_delito}|{code}|{anio}".encode()
        ).hexdigest()
        records.append({
            "source_id": MUNICIPAL_REFERENCE_SOURCE,
            "departamento": str(_get(item, "departamento") or "").strip() or "NO INFORMADO",
            "municipio": municipio or code,
            "municipio_normalizado": processor.normalize_text(municipio or code),
            "codigo_dane": code,
            "fecha_hecho": date(anio, mes, 1),
            "fecha_corte_mindefensa": source_cutoff,
            "anio": anio,
            "mes": mes,
            "tipo_delito": tipo_delito,
            "cantidad": cantidad,
            "fuente_archivo": filename,
            "event_fingerprint": fingerprint,
            "hash_registro": fingerprint,
            "fecha_ingesta": now,
        })
    if not records:
        raise ValueError("No hay registros agregados válidos.")

    coverage = []
    for period in raw_coverage:
        codes = sorted({
            code for raw_code in (_get(period, "municipality_codes") or [])
            if (code := normalize_municipality_code(raw_code))
        })
        if codes:
            coverage.append({
                "source_id": COMPACT_REFERENCE_SOURCE,
                "tipo_delito": tipo_delito,
                "anio": int(_get(period, "anio")),
                "municipality_codes": codes,
                "fecha_corte_mindefensa": source_cutoff,
                "fuente_archivo": filename,
                "fecha_ingesta": now,
            })

    _align_id_sequences(db)
    municipal_years = {r["anio"] for r in records if r["source_id"] == MUNICIPAL_REFERENCE_SOURCE}
    with db.begin_nested():
        if municipal_years:
            db.query(NationalCrimeStats).filter(
                NationalCrimeStats.source_id == MUNICIPAL_REFERENCE_SOURCE,
                NationalCrimeStats.tipo_delito == tipo_delito,
                NationalCrimeStats.anio.in_(municipal_years),
            ).delete(synchronize_session=False)
        for offset in range(0, len(records), 500):
            statement = insert(NationalCrimeStats).values(records[offset:offset + 500])
            statement = statement.on_conflict_do_update(
                index_elements=["source_id", "event_fingerprint"],
                set_={
                    "cantidad": statement.excluded.cantidad,
                    "fecha_corte_mindefensa": statement.excluded.fecha_corte_mindefensa,
                    "fuente_archivo": statement.excluded.fuente_archivo,
                    "fecha_ingesta": statement.excluded.fecha_ingesta,
                },
            )
            db.execute(statement)
        for item in coverage:
            statement = insert(NationalReferenceCoverage).values(item)
            statement = statement.on_conflict_do_update(
                index_elements=["source_id", "tipo_delito", "anio"],
                set_={
                    "municipality_codes": statement.excluded.municipality_codes,
                    "fecha_corte_mindefensa": statement.excluded.fecha_corte_mindefensa,
                    "fuente_archivo": statement.excluded.fuente_archivo,
                    "fecha_ingesta": statement.excluded.fecha_ingesta,
                },
            )
            db.execute(statement)

    return {"records": len(records), "coverage_years": sorted({c["anio"] for c in coverage})}
