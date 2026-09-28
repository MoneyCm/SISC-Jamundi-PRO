"""Contraste mensual oficial de la Policía Nacional, desde datos.gov.co, sin descargar archivos.

MinDefensa publica en datos.gov.co los registros oficiales de la Policía (SIEDCO) por delito. Se
consultan solo las filas de Jamundí (DANE 76364) de ocho delitos, se suma lo que va del año hasta
el corte de la publicación y el mismo periodo del año anterior, y se contrasta con los hechos
únicos de la sábana semanal en las mismas fechas. El resultado queda en el Centro de fuentes
(conector POLICIA_NACIONAL_DATOS), con la tabla de contraste en "Detalles".

Reemplaza al monitor de GitHub "monitor-policia", que descarga el Excel nacional (33 MB) y deja
de funcionar cuando la Policía cambia el formato. La revisión semanal corre desde main.py.
"""
import calendar
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from db.models_hechos_seguridad import HechoSeguridad
from services.entrega_vigente import filtro_hechos
from services.hechos_metrics import hechos_unicos_expr
from services.piscc_mindefensa_sync import DANE_JAMUNDI, _fecha, _un_anio_antes, consultar

CONECTOR = "POLICIA_NACIONAL_DATOS"
CADA_CUANTO = timedelta(days=7)
# (id en datos.gov.co, nombre, conductas de la sábana con las que se contrasta; None = la sábana no lo trae)
DELITOS = [
    ("m8fd-ahd9", "Homicidio", ["Homicidio"]),
    ("jr6v-i33g", "Lesiones personales", ["Lesiones personales"]),
    ("4rxi-8m8d", "Hurto a personas", ["Hurto a personas"]),
    ("csb4-y6v2", "Hurto de vehículos", ["Hurto a motocicletas", "Hurto a automotores"]),
    ("7mn7-vzqp", "Hurto a residencias", ["Hurto a residencias"]),
    ("7i2x-h5vp", "Hurto a comercio", ["Hurto a comercio"]),
    ("q2ib-t9am", "Extorsión", None),
    ("gepp-dxcs", "Violencia intrafamiliar", None),
]

logger = logging.getLogger("policia_datos")


def _oficial(dataset: str, consulta: Callable) -> Dict:
    ultimo = _fecha(consulta(dataset, **{"$select": "max(fecha_hecho) as corte"})[0]["corte"])
    corte = ultimo.replace(day=calendar.monthrange(ultimo.year, ultimo.month)[1])
    filas = consulta(dataset, cod_muni=DANE_JAMUNDI, **{"$limit": 50000})

    def suma(inicio: date, fin: date) -> int:
        return sum(int(float(f.get("cantidad") or 1)) for f in filas if inicio <= _fecha(f["fecha_hecho"]) <= fin)

    return {"corte": corte, "actual": suma(date(corte.year, 1, 1), corte),
            "anterior": suma(date(corte.year - 1, 1, 1), _un_anio_antes(corte))}


def _sabana(db: Session, conductas: List[str], inicio: date, fin: date) -> int:
    return int(db.query(hechos_unicos_expr()).filter(
        HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
        HechoSeguridad.conducta_estandar.in_(conductas),
        HechoSeguridad.fecha_evento.between(inicio, fin),
        filtro_hechos(db),
    ).scalar() or 0)


def contraste(db: Session, consulta: Callable = consultar) -> Dict:
    filas, cortes = [], []
    corte_sabana = db.query(HechoSeguridad.fecha_evento).filter(
        HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL").order_by(HechoSeguridad.fecha_evento.desc()).limit(1).scalar()
    for dataset, nombre, conductas in DELITOS:
        oficial = _oficial(dataset, consulta)
        corte = oficial["corte"]
        cortes.append(corte)
        fila = {"delito": nombre, "oficial_actual": oficial["actual"], "oficial_anterior": oficial["anterior"],
                "corte": corte.isoformat(), "sabana_actual": None, "diferencia": None, "dataset": dataset}
        # Solo se contrasta si la sábana cubre el corte oficial; si no, las cifras no son comparables.
        if conductas and corte_sabana and corte_sabana >= corte:
            fila["sabana_actual"] = _sabana(db, conductas, date(corte.year, 1, 1), corte)
            fila["diferencia"] = fila["sabana_actual"] - oficial["actual"]
        filas.append(fila)
    return {"corte": min(cortes) if cortes else None, "filas": filas,
            "corte_sabana": corte_sabana.isoformat() if corte_sabana else None}


def _estado(db: Session):
    from db.models_source_center import SourceConnectorState
    estado = db.get(SourceConnectorState, CONECTOR)
    if estado is None:
        estado = SourceConnectorState(connector_code=CONECTOR, warnings=[], details={})
        db.add(estado)
    return estado


def sincronizar(db: Session, consulta: Callable = consultar, forzar: bool = False) -> Optional[Dict]:
    """Consulta datos.gov.co si pasó una semana desde la última revisión y lo anota en el Centro de fuentes."""
    ahora = datetime.now(timezone.utc)
    estado = _estado(db)
    if not forzar and estado.last_checked_at and ahora - estado.last_checked_at < CADA_CUANTO:
        return None
    estado.last_checked_at = ahora
    try:
        resultado = contraste(db, consulta)
    except Exception as error:
        estado.status = "ERROR"
        estado.warnings = [f"No se pudo consultar datos.gov.co: {error}"[:300]]
        db.commit()
        logger.warning(f"[Policía Nacional] {error}")
        return {"error": str(error)}
    corte = resultado["corte"]
    anterior = estado.source_cutoff_date
    estado.status = "CURRENT"
    estado.quality_status = "VALIDATED"
    estado.source_cutoff_date = corte
    estado.period_label = f"Corte al {corte.isoformat()} - {len(resultado['filas'])} indicadores" if corte else None
    estado.last_success_at = ahora
    estado.indicator_count = len(resultado["filas"])
    estado.record_count = sum(f["oficial_actual"] for f in resultado["filas"])
    grandes = [f"{f['delito']}: la sábana tiene {f['sabana_actual']} y el registro oficial {f['oficial_actual']}"
               for f in resultado["filas"]
               if f["diferencia"] is not None and abs(f["diferencia"]) > max(5, 0.15 * max(f["oficial_actual"], 1))]
    estado.warnings = grandes[:3]
    estado.details = {"fuente": "datos.gov.co (MinDefensa / Policía Nacional)", "contraste": resultado["filas"],
                      "corte_sabana": resultado["corte_sabana"]}
    if corte and corte != anterior:
        estado.last_change_detected_at = ahora
    db.commit()
    return resultado
