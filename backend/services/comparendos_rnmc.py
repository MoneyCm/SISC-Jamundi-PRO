"""Conteo único de comparendos del RNMC (comportamientos contrarios a la convivencia).

Los reportes del RNMC entran por Inspecciones (services/inspeccion_service.py) a las tablas
inspeccion_*. Un mismo comparendo (expediente) puede tener varias actuaciones y medidas, así que
la cifra oficial cuenta cada expediente una sola vez, en la fecha de su primer registro (la del
hecho en el reporte de comparendos). La usan la meta del PISCC, SISC en cifras y el boletín.

Se excluyen los archivos de prueba y las fechas posteriores a hoy.
"""
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from db.models_inspecciones import InspeccionActuacion, InspeccionExpediente, InspeccionMedida


def filtros_publicos() -> List:
    nombre = func.lower(func.coalesce(InspeccionActuacion.fuente_archivo, ""))
    return [~nombre.like("%test%"), ~nombre.like("%prueba%")]


def _manana() -> datetime:
    return datetime.combine(date.today() + timedelta(days=1), datetime.min.time())


def primeras_fechas(db: Session):
    """Subconsulta (expediente_id, fecha): primer registro de cada comparendo."""
    return (
        db.query(InspeccionMedida.expediente_id.label("expediente_id"),
                 func.min(InspeccionActuacion.fecha_actuacion).label("fecha"))
        .join(InspeccionActuacion, InspeccionActuacion.medida_id == InspeccionMedida.id)
        .filter(*filtros_publicos(), InspeccionActuacion.fecha_actuacion < _manana())
        .group_by(InspeccionMedida.expediente_id)
        .subquery()
    )


def _limites(desde: date, hasta: date) -> Tuple[datetime, datetime]:
    return datetime.combine(desde, datetime.min.time()), datetime.combine(hasta + timedelta(days=1), datetime.min.time())


def contar(db: Session, desde: date, hasta: date) -> int:
    sub = primeras_fechas(db)
    inicio, fin = _limites(desde, hasta)
    return db.query(func.count(sub.c.expediente_id)).filter(sub.c.fecha >= inicio, sub.c.fecha < fin).scalar() or 0


def corte(db: Session, hasta: Optional[date] = None) -> Optional[date]:
    sub = primeras_fechas(db)
    query = db.query(func.max(sub.c.fecha))
    if hasta:
        query = query.filter(sub.c.fecha < _limites(hasta, hasta)[1])
    valor = query.scalar()
    return valor.date() if isinstance(valor, datetime) else valor


def agrupar(db: Session, columna, desde: date, hasta: date, filtros=(), minimo: int = 1, limite: int = 10):
    """Comparendos del periodo por una columna de la medida o del expediente (cada expediente una vez por valor)."""
    sub = primeras_fechas(db)
    inicio, fin = _limites(desde, hasta)
    total = func.count(func.distinct(sub.c.expediente_id))
    return (
        db.query(columna.label("nombre"), total.label("total"))
        .select_from(sub)
        .join(InspeccionExpediente, InspeccionExpediente.id == sub.c.expediente_id)
        .join(InspeccionMedida, InspeccionMedida.expediente_id == InspeccionExpediente.id)
        .filter(sub.c.fecha >= inicio, sub.c.fecha < fin, columna.isnot(None), columna != "", *filtros)
        .group_by(columna)
        .having(total >= minimo)
        .order_by(desc("total"))
        .limit(limite)
        .all()
    )
