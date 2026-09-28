"""Respaldo cuando la sábana de la Policía no llega.

La sábana semanal es la única fuente con barrio y hora, y depende de que la Policía la entregue.
Si su último dato tiene más de DIAS_ALERTA días, el SISC lo avisa y, si MinDefensa (datos.gov.co,
cargado cada semana por services/mindefensa_referencia_datos.py) ya tiene un corte posterior,
muestra esas cifras oficiales de Jamundí mientras tanto: año a la fecha frente al mismo periodo
del año anterior, sin barrios ni horarios.
"""
from datetime import date
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models_intelligence import NationalCrimeStats
from services.entrega_vigente import entrega_vigente
from services.mindefensa_reference_service import COMPACT_REFERENCE_SOURCE

DIAS_ALERTA = 21
DANE_JAMUNDI = "76364"
# Nombre en la hoja y el tablero -> tipo_delito guardado por la referencia de MinDefensa.
DELITOS = [
    ("Homicidios", "Homicidio Intencional"),
    ("Lesiones personales", "Lesiones Personales"),
    ("Hurto a personas", "Hurto Personas"),
    ("Hurto de motos y carros", "Hurto Vehiculos"),
    ("Hurto a residencias", "Hurto Residencias"),
    ("Hurto a comercio", "Hurto Comercio"),
    ("Extorsión", "Extorsion"),
    ("Violencia intrafamiliar", "Violencia Intrafamiliar"),
]


def _corte_sabana(db: Session) -> Optional[date]:
    entrega = entrega_vigente(db)
    return entrega.ventanas[-1][1] if entrega and entrega.ventanas else None


def _cifras_mindefensa(db: Session) -> Dict:
    base = db.query(NationalCrimeStats).filter(
        NationalCrimeStats.source_id == COMPACT_REFERENCE_SOURCE,
        NationalCrimeStats.codigo_dane == DANE_JAMUNDI,
    )
    corte = base.with_entities(func.max(NationalCrimeStats.fecha_corte_mindefensa)).scalar()
    ultimo_mes = base.with_entities(func.max(NationalCrimeStats.fecha_hecho)).scalar()
    if not corte or not ultimo_mes:
        return {"corte": None, "filas": []}
    anio, mes = ultimo_mes.year, ultimo_mes.month
    filas: List[Dict] = []
    for nombre, tipo in DELITOS:
        def suma(anio_consulta: int) -> int:
            return int(base.filter(NationalCrimeStats.tipo_delito == tipo, NationalCrimeStats.anio == anio_consulta,
                                   NationalCrimeStats.mes <= mes)
                       .with_entities(func.coalesce(func.sum(NationalCrimeStats.cantidad), 0)).scalar() or 0)
        filas.append({"delito": nombre, "actual": suma(anio), "anterior": suma(anio - 1)})
    return {"corte": corte, "filas": filas}


def estado(db: Session, hoy: Optional[date] = None) -> Dict:
    hoy = hoy or date.today()
    corte_sabana = _corte_sabana(db)
    dias = (hoy - corte_sabana).days if corte_sabana else None
    atrasada = corte_sabana is None or dias > DIAS_ALERTA
    respaldo = {"corte": None, "filas": []}
    if atrasada:
        respaldo = _cifras_mindefensa(db)
    disponible = bool(respaldo["corte"] and (corte_sabana is None or respaldo["corte"] > corte_sabana))
    return {
        "sabana_corte": corte_sabana.isoformat() if corte_sabana else None,
        "dias_retraso": dias,
        "dias_alerta": DIAS_ALERTA,
        "atrasada": atrasada,
        "respaldo_disponible": disponible,
        "respaldo_corte": respaldo["corte"].isoformat() if disponible else None,
        "respaldo": respaldo["filas"] if disponible else [],
        "fuente_respaldo": "MinDefensa / Policía Nacional (datos.gov.co)",
    }
