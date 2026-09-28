"""Referencia nacional de MinDefensa para "Contexto comparado", desde datos.gov.co.

"Contexto comparado" ubica a Jamundí frente a municipios de Valle y Cauca y al país. Antes se
alimentaba de los Excel nacionales que descargaba el monitor de GitHub "monitor-mindefensa"
(scripts/sync_source_monitors.py). Ahora datos.gov.co devuelve cada delito ya sumado por
municipio y mes (una consulta por delito, unos segundos) y se guarda con el mismo formato y las
mismas llaves (services/mindefensa_reference_service.py), así que la sección no cambia.
La revisión semanal corre desde main.py y queda en el Centro de fuentes (conector MINDEFENSA_DATOS).
"""
import calendar
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from services.mindefensa_reference_service import persist_reference_payload
from services.piscc_mindefensa_sync import consultar

CONECTOR = "MINDEFENSA_DATOS"
CADA_CUANTO = timedelta(days=7)
DEPARTAMENTOS_REFERENCIA = {"76", "19"}  # Valle del Cauca y Cauca, como el monitor
# (id en datos.gov.co, tipo_delito con el que "Contexto comparado" ya guarda la serie)
DELITOS = [
    ("m8fd-ahd9", "Homicidio Intencional"),
    ("4rxi-8m8d", "Hurto Personas"),
    ("7i2x-h5vp", "Hurto Comercio"),
    ("7mn7-vzqp", "Hurto Residencias"),
    ("csb4-y6v2", "Hurto Vehiculos"),
    ("q2ib-t9am", "Extorsion"),
    ("gepp-dxcs", "Violencia Intrafamiliar"),
    ("jr6v-i33g", "Lesiones Personales"),
]

logger = logging.getLogger("mindefensa_referencia")


def armar_paquete(dataset: str, tipo_delito: str, consulta: Callable = consultar, hoy: Optional[date] = None) -> Dict:
    """Mismo paquete que ReferenceExporter._build_payload del monitor, a partir de conteos agregados."""
    hoy = hoy or date.today()
    desde = date(hoy.year - 2, 1, 1)
    filas = consulta(dataset, **{
        "$select": "cod_depto, departamento, cod_muni, municipio, date_extract_y(fecha_hecho) as anio, "
                   "date_extract_m(fecha_hecho) as mes, sum(cantidad) as cantidad",
        "$where": f"fecha_hecho >= '{desde.isoformat()}'",
        "$group": "cod_depto, departamento, cod_muni, municipio, anio, mes",
        "$limit": 50000,
    })
    ultimo = consulta(dataset, **{"$select": "max(fecha_hecho) as corte"})[0]["corte"]
    corte = datetime.fromisoformat(ultimo[:10]).date()
    corte = corte.replace(day=calendar.monthrange(corte.year, corte.month)[1])

    nacional: Dict[tuple, int] = defaultdict(int)
    regional: List[Dict] = []
    totales: Dict[tuple, Dict] = {}
    cobertura: Dict[int, set] = defaultdict(set)
    fin_por_anio: Dict[int, int] = defaultdict(int)
    for fila in filas:
        codigo = str(fila.get("cod_muni") or "").strip().zfill(5)
        if not codigo.isdigit() or len(codigo) != 5 or not fila.get("anio") or not fila.get("mes"):
            continue
        anio, mes = int(float(fila["anio"])), int(float(fila["mes"]))
        cantidad = max(int(round(float(fila.get("cantidad") or 0))), 0)
        municipio = (fila.get("municipio") or codigo).strip()
        departamento = (fila.get("departamento") or "NO INFORMADO").strip()
        nacional[(anio, mes)] += cantidad
        cobertura[anio].add(codigo)
        fin_por_anio[anio] = max(fin_por_anio[anio], mes)
        total = totales.setdefault((codigo, anio), {"codigo_dane": codigo, "municipio": municipio,
                                                    "departamento": departamento, "anio": anio, "cantidad": 0})
        total["cantidad"] += cantidad
        if codigo[:2] in DEPARTAMENTOS_REFERENCIA:
            regional.append({"codigo_dane": codigo, "municipio": municipio, "departamento": departamento,
                             "anio": anio, "mes": mes, "cantidad": cantidad})
    registros = [{"codigo_dane": "NACIONAL", "municipio": "Colombia", "departamento": "Colombia",
                  "anio": anio, "mes": mes, "cantidad": cantidad} for (anio, mes), cantidad in sorted(nacional.items())]
    registros += regional
    for total in totales.values():
        total["period_end_month"] = fin_por_anio[total["anio"]]
    return {
        "filename": f"datos.gov.co/{dataset}",
        "tipo_delito": tipo_delito,
        "source_cutoff": corte.isoformat(),
        "coverage": [{"anio": anio, "municipality_codes": sorted(codigos)} for anio, codigos in sorted(cobertura.items())],
        "municipal_totals": list(totales.values()),
        "records": registros,
    }


def actualizar(db: Session, consulta: Callable = consultar) -> Dict:
    resultado = {"delitos": {}, "corte": None}
    for dataset, tipo_delito in DELITOS:
        paquete = armar_paquete(dataset, tipo_delito, consulta)
        guardado = persist_reference_payload(db, paquete)
        corte = date.fromisoformat(paquete["source_cutoff"])
        resultado["delitos"][tipo_delito] = {"registros": guardado["records"], "corte": corte.isoformat(),
                                             "anios": guardado["coverage_years"]}
        resultado["corte"] = min(resultado["corte"], corte) if resultado["corte"] else corte
    return resultado


def _estado(db: Session):
    from db.models_source_center import SourceConnectorState
    estado = db.get(SourceConnectorState, CONECTOR)
    if estado is None:
        estado = SourceConnectorState(connector_code=CONECTOR, warnings=[], details={})
        db.add(estado)
    return estado


def sincronizar(db: Session, consulta: Callable = consultar, forzar: bool = False) -> Optional[Dict]:
    """Actualiza la referencia si pasó una semana desde la última revisión y lo anota en el Centro de fuentes."""
    ahora = datetime.now(timezone.utc)
    estado = _estado(db)
    if not forzar and estado.last_checked_at and ahora - estado.last_checked_at < CADA_CUANTO:
        return None
    try:
        resultado = actualizar(db, consulta)
    except Exception as error:
        db.rollback()
        estado = _estado(db)
        estado.last_checked_at = ahora
        estado.status = "ERROR"
        estado.warnings = [f"No se pudo actualizar la referencia nacional: {error}"[:300]]
        db.commit()
        logger.warning(f"[MinDefensa referencia] {error}")
        return {"error": str(error)}
    corte = resultado["corte"]
    anterior = estado.source_cutoff_date
    estado.last_checked_at = ahora
    estado.status = "CURRENT"
    estado.quality_status = "VALIDATED"
    estado.source_cutoff_date = corte
    estado.period_label = f"Corte al {corte.isoformat()} - {len(resultado['delitos'])} delitos, municipios y país"
    estado.last_success_at = ahora
    estado.indicator_count = len(resultado["delitos"])
    estado.record_count = sum(d["registros"] for d in resultado["delitos"].values())
    estado.warnings = []
    estado.details = {"fuente": "datos.gov.co (MinDefensa)", "delitos": resultado["delitos"]}
    if corte != anterior:
        estado.last_change_detected_at = ahora
    db.commit()
    return resultado
