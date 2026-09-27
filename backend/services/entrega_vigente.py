"""Qué hechos del histórico cuentan: los de la última entrega de la Policía, en las fechas que cubre.

Cada sábana semanal trae el año en curso hasta el corte y el año anterior hasta la misma fecha.
Si la Policía retira o reclasifica un hecho, desaparece de la sábana siguiente, pero el histórico
consolidado (hechos_seguridad) lo conserva. Para que tablero, estadísticas, boletín y hoja
ejecutiva digan lo mismo que el cálculo oficial (services/indicator_calculation.py):

- dentro de las fechas que cubre la última entrega, solo cuentan los hechos que están en ella, y
  con la conducta que ella trae (si la Policía reclasificó un hurto como lesiones, cuenta como lesiones);
- fuera de esas fechas (por ejemplo 2024, o el resto de 2025) se usa el histórico.
"""
from dataclasses import dataclass
from datetime import date
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import extract, func, not_, or_, select, true, tuple_
from sqlalchemy.orm import Session

from db.models_hechos_seguridad import HechoSeguridad, IngestionRun, SabanaSnapshotRow
from services.hechos_metrics import hecho_key_expr


@dataclass(frozen=True)
class EntregaVigente:
    run_id: UUID
    filename: Optional[str]
    ventanas: Tuple[Tuple[date, date], ...]  # (inicio, fin) por año cubierto


def entrega_vigente(db: Session) -> Optional[EntregaVigente]:
    run = (
        db.query(IngestionRun)
        .filter(IngestionRun.fuente_codigo == "POLICIA_SEMANAL", IngestionRun.status == "COMPLETED",
                IngestionRun.id.in_(select(SabanaSnapshotRow.ingestion_id).distinct()))
        .order_by(IngestionRun.fecha_fin.desc().nullslast(), IngestionRun.fecha_inicio.desc().nullslast())
        .first()
    )
    if run is None:
        return None
    anio = extract("year", SabanaSnapshotRow.fecha_evento)
    filas = (
        db.query(func.min(SabanaSnapshotRow.fecha_evento), func.max(SabanaSnapshotRow.fecha_evento))
        .filter(SabanaSnapshotRow.ingestion_id == run.id, SabanaSnapshotRow.fecha_evento.isnot(None))
        .group_by(anio).order_by(anio).all()
    )
    # Cada año cubierto va desde el 1 de enero hasta el último día que trae la entrega.
    ventanas = tuple((date(fin.year, 1, 1), fin) for _inicio, fin in filas)
    return EntregaVigente(run.id, run.filename, ventanas)


def filtro_hechos(db: Session, model=HechoSeguridad, entrega: Optional[EntregaVigente] = None):
    """Condición SQLAlchemy para consultas sobre hechos_seguridad."""
    entrega = entrega or entrega_vigente(db)
    if entrega is None or not entrega.ventanas:
        return true()
    en_ventana = or_(*[model.fecha_evento.between(inicio, fin) for inicio, fin in entrega.ventanas])
    pares = select(SabanaSnapshotRow.hecho_key, SabanaSnapshotRow.conducta_estandar).where(
        SabanaSnapshotRow.ingestion_id == entrega.run_id)
    return or_(model.fecha_evento.is_(None), not_(en_ventana),
               tuple_(hecho_key_expr(model), model.conducta_estandar).in_(pares))


def filtro_sql(db: Session, columna_fecha: str = "fecha_evento", prefijo: str = "",
               entrega: Optional[EntregaVigente] = None) -> str:
    """La misma condición para SQL escrito a mano. Los valores salen de la base (fechas y UUID)."""
    entrega = entrega or entrega_vigente(db)
    if entrega is None or not entrega.ventanas:
        return ""
    p = f"{prefijo}." if prefijo else ""
    fecha = f"{p}{columna_fecha}"
    ventanas = " OR ".join(f"{fecha} BETWEEN DATE '{i.isoformat()}' AND DATE '{f.isoformat()}'"
                           for i, f in entrega.ventanas)
    clave = (f"CASE WHEN NULLIF(BTRIM({p}id_fuente), '') IS NOT NULL THEN 'ID:' || BTRIM({p}id_fuente) "
             f"WHEN NULLIF(BTRIM({p}fingerprint), '') IS NOT NULL THEN 'FP:' || BTRIM({p}fingerprint) "
             f"ELSE 'ROW:' || {p}id::text END")
    run_id = str(UUID(str(entrega.run_id)))
    return (f" AND ({fecha} IS NULL OR NOT ({ventanas}) OR ({clave}, {p}conducta_estandar) IN "
            f"(SELECT hecho_key, conducta_estandar FROM sabana_snapshot_rows WHERE ingestion_id = '{run_id}'))")
