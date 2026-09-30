"""Qué meses trae completos la sábana de la Policía cargada en el SISC.

Un mes cuenta como completo si hay hechos en sus primeros y en sus últimos días (margen de 5 días;
el mes en curso se revisa solo hasta el corte). Sin esto, un total que no incluye diciembre se
vería como una baja real (por ejemplo, 2025 sin diciembre).
"""
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models_hechos_seguridad import HechoSeguridad
from services.asistente_periodos import MESES, fin_de_mes, meses_de
from services.entrega_vigente import filtro_hechos

MARGEN = 5


def limites(db: Session, hoy: Optional[date] = None) -> Tuple[Optional[date], Optional[date]]:
    """Primer y último día con hechos (el último es el corte)."""
    filtros = [HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL", filtro_hechos(db)]
    if hoy:
        filtros.append(HechoSeguridad.fecha_evento <= hoy)
    return db.query(func.min(HechoSeguridad.fecha_evento), func.max(HechoSeguridad.fecha_evento)).filter(*filtros).one()


def meses_incompletos(db: Session, inicio: date, fin: date, corte: Optional[date] = None) -> List[date]:
    """Primer día de cada mes del periodo que la sábana no trae completo (hasta el corte)."""
    if corte is None:
        _primero, corte = limites(db)
    if corte is None:
        return [inicio.replace(day=1)]
    fin = min(fin, corte)
    faltan = []
    for a, _b in meses_de(inicio, fin) if inicio <= fin else []:
        desde, hasta = a.replace(day=1), min(fin_de_mes(a.year, a.month), corte)
        primero, ultimo = db.query(func.min(HechoSeguridad.fecha_evento), func.max(HechoSeguridad.fecha_evento)).filter(
            HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL", filtro_hechos(db),
            HechoSeguridad.fecha_evento.between(desde, hasta)).one()
        if not primero or primero > desde + timedelta(days=MARGEN) or ultimo < hasta - timedelta(days=MARGEN):
            faltan.append(desde)
    return faltan


def nombre_mes(valor: date) -> str:
    return f"{MESES[valor.month - 1]} de {valor.year}"


def cobertura(db: Session, inicio: Optional[date], fin: Optional[date]) -> Dict:
    """Resumen para las pantallas: si el periodo está completo y, si no, qué meses faltan."""
    primero, corte = limites(db)
    if corte is None:
        return {"completa": False, "meses_incompletos": [], "corte": None,
                "mensaje": "Todavía no hay sábana de la Policía cargada."}
    inicio, fin = inicio or primero, fin or corte
    faltan = []
    if inicio < primero:
        faltan.append(f"antes del {primero.day} de {MESES[primero.month - 1]} de {primero.year}")
    faltan += [nombre_mes(m) for m in meses_incompletos(db, max(inicio, primero), fin, corte)]
    mensaje = None
    if faltan:
        mensaje = ("La sábana de la Policía cargada no trae completo: " + ", ".join(faltan) +
                   ". Los totales de este periodo están incompletos; conviene pedir esos datos a la Policía.")
    return {"completa": not faltan, "meses_incompletos": faltan, "corte": corte.isoformat(), "mensaje": mensaje}
