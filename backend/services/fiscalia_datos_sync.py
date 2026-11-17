"""Capa judicial de la Fiscalía (SPOA V3) desde datos.gov.co, con conteos hechos en el servidor.

La Fiscalía publica en datos.gov.co sus procesos, víctimas y procesados (SPOA, "V3"). Para hechos
ocurridos en Jamundí (DANE 76364) se piden solo conteos agregados, sin bajar registros:
- procesos (noticias criminales) del año en curso y del mismo periodo del año anterior, por
  capítulo del Código Penal;
- en qué va la respuesta judicial de los procesos del año (indagación, juicio, ejecución de penas);
- víctimas y procesados en los mismos periodos.
El resultado queda en el Centro de fuentes (conector FISCALIA_DATOS), con las tablas en "Detalles".
Reemplaza al monitor de GitHub "monitor-fiscalia-spoa-v3". La revisión semanal corre desde main.py.
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Dict, Optional

from sqlalchemy.orm import Session

from services.piscc_mindefensa_sync import consultar

CONECTOR = "FISCALIA_DATOS"
CADA_CUANTO = timedelta(days=7)
# Tras un error (p. ej. datos.gov.co caído) se reintenta en la siguiente vuelta del programador
# (cada 6 horas), no a la semana.
REINTENTO_TRAS_ERROR = timedelta(hours=5)
DANE = "76364"
PROCESOS, VICTIMAS, PROCESADOS = "dbdv-iihs", "hr73-zqjf", "piva-db2c"
CAPITULOS_MOSTRADOS = 8

logger = logging.getLogger("fiscalia_datos")
ARTICULOS = ("de las ", "de los ", "de la ", "del ", "de ")
NOMBRES = {
    "Homicidio": "Homicidio (incluye culposos)",
    "Injuria y la calumnia": "Injuria y calumnia",
    "Concierto, el terrorismo, las amenazas y la instigacion": "Concierto para delinquir, terrorismo y amenazas",
    "Delitos contra la autonomia personal": "Delitos contra la autonomía personal",
    "Trafico de estupefacientes y otras infracciones": "Tráfico de estupefacientes",
    "Daño": "Daño en bien ajeno",
}


def nombre_capitulo(capitulo: str) -> str:
    """'De La Violencia Intrafamiliar' -> 'Violencia intrafamiliar'."""
    texto = (capitulo or "Sin información").strip()
    for articulo in ARTICULOS:
        if texto.lower().startswith(articulo):
            texto = texto[len(articulo):]
            break
    texto = texto[:1].upper() + texto[1:].lower()
    return NOMBRES.get(texto, texto)


def _corte(consulta: Callable) -> date:
    fila = consulta(PROCESOS, **{"$select": "fecha_corte_datos", "$where": f"cod_dane_hecho='{DANE}'", "$limit": 1})
    return datetime.strptime(fila[0]["fecha_corte_datos"], "%d/%m/%Y").date()


def _periodo(anio: int, mes: int, sufijo: str = "") -> str:
    return f"a_o_hecho{sufijo}='{anio}' AND mes_hecho{sufijo}<='{mes:02d}'"


def resumen(consulta: Callable = consultar) -> Dict:
    corte = _corte(consulta)
    anio, mes = corte.year, corte.month
    donde = f"cod_dane_hecho='{DANE}'"

    def por_capitulo(anio_consulta: int) -> Dict[str, int]:
        filas = consulta(PROCESOS, **{"$select": "capitulo_delito, count(*) as n",
                                     "$where": f"{donde} AND {_periodo(anio_consulta, mes)}",
                                     "$group": "capitulo_delito", "$limit": 500})
        return {f["capitulo_delito"]: int(f["n"]) for f in filas}

    actual, anterior = por_capitulo(anio), por_capitulo(anio - 1)
    capitulos = sorted(actual, key=lambda c: -actual[c])[:CAPITULOS_MOSTRADOS]
    tabla = [{"delito": nombre_capitulo(c), "actual": actual[c], "anterior": anterior.get(c, 0)} for c in capitulos]
    tabla.append({"delito": "Total de procesos", "actual": sum(actual.values()), "anterior": sum(anterior.values())})

    etapas = consulta(PROCESOS, **{"$select": "estado, etapa, count(*) as n",
                                  "$where": f"{donde} AND {_periodo(anio, mes)}", "$group": "estado, etapa", "$limit": 100})
    respuesta = {}
    for f in etapas:
        clave = f"{f['etapa']} ({f['estado'].lower()})"
        respuesta[clave] = respuesta.get(clave, 0) + int(f["n"])

    def total(dataset: str, anio_consulta: int) -> int:
        fila = consulta(dataset, **{"$select": "count(*) as n",
                                   "$where": f"cod_dane_hecho_origen='{DANE}' AND {_periodo(anio_consulta, mes, '_origen')}"})
        return int(fila[0]["n"]) if fila else 0

    personas = [{"delito": "Víctimas", "actual": total(VICTIMAS, anio), "anterior": total(VICTIMAS, anio - 1)},
                {"delito": "Procesados", "actual": total(PROCESADOS, anio), "anterior": total(PROCESADOS, anio - 1)}]
    return {"corte": corte, "procesos": tabla, "respuesta_judicial": respuesta, "personas": personas,
            "seguimiento": seguimiento_judicial(consulta, corte)}


# Etapas del SPOA agrupadas para leer la respuesta judicial. "Indagación" inactiva suele ser archivo,
# pero el dato abierto no dice el motivo; por eso se muestra aparte de la indagación activa.
def _grupo_etapa(etapa: str, estado: str) -> str:
    etapa = (etapa or "").strip().lower()
    if etapa.startswith("indagaci"):
        return "indagacion_inactiva" if (estado or "").strip().lower() == "inactivo" else "indagacion_activa"
    if etapa.startswith("investigaci"):
        return "investigacion"
    if etapa.startswith("juicio"):
        return "juicio"
    if etapa.startswith("ejecuci"):
        return "condena"
    return "sin_informacion"


GRUPOS = ("indagacion_inactiva", "indagacion_activa", "investigacion", "juicio", "condena", "sin_informacion")


def _vacio() -> Dict[str, int]:
    return {g: 0 for g in GRUPOS}


def _con_totales(conteo: Dict[str, int]) -> Dict[str, int]:
    return {**conteo, "total": sum(conteo[g] for g in GRUPOS), "juicio_o_condena": conteo["juicio"] + conteo["condena"]}


def seguimiento_judicial(consulta: Callable, corte: date) -> Dict:
    """En qué etapa van los procesos por hechos en Jamundí de los dos años anteriores y del año en curso.

    Los años anteriores ya tuvieron tiempo de avanzar; el año en curso (hasta el corte) es muy reciente
    y no sirve para medir resultados. Se separa el homicidio doloso del culposo (casi todo de tránsito).
    """
    anios = [corte.year - 2, corte.year - 1, corte.year]
    lista = ", ".join(f"'{a}'" for a in anios)
    donde = f"cod_dane_hecho='{DANE}' AND a_o_hecho in ({lista})"

    todos = {a: _vacio() for a in anios}
    for f in consulta(PROCESOS, **{"$select": "a_o_hecho, etapa, estado, count(*) as n", "$where": donde,
                                   "$group": "a_o_hecho, etapa, estado", "$limit": 1000}):
        todos[int(f["a_o_hecho"])][_grupo_etapa(f.get("etapa"), f.get("estado"))] += int(f["n"])

    homicidio = {tipo: {a: _vacio() for a in anios} for tipo in ("doloso", "culposo")}
    for f in consulta(PROCESOS, **{"$select": "a_o_hecho, delito, etapa, estado, count(*) as n",
                                   "$where": f"{donde} AND capitulo_delito='Del Homicidio'",
                                   "$group": "a_o_hecho, delito, etapa, estado", "$limit": 5000}):
        tipo = "culposo" if "CULPOSO" in (f.get("delito") or "").upper() else "doloso"
        homicidio[tipo][int(f["a_o_hecho"])][_grupo_etapa(f.get("etapa"), f.get("estado"))] += int(f["n"])

    # Delitos con más procesos en el último año completo, con cuántos llegaron a juicio o condena.
    por_capitulo: Dict[str, Dict[int, Dict[str, int]]] = {}
    for f in consulta(PROCESOS, **{"$select": "a_o_hecho, capitulo_delito, etapa, estado, count(*) as n",
                                   "$where": f"cod_dane_hecho='{DANE}' AND a_o_hecho in ('{anios[0]}', '{anios[1]}')",
                                   "$group": "a_o_hecho, capitulo_delito, etapa, estado", "$limit": 5000}):
        capitulo = por_capitulo.setdefault(f.get("capitulo_delito") or "Sin información",
                                           {anios[0]: _vacio(), anios[1]: _vacio()})
        capitulo[int(f["a_o_hecho"])][_grupo_etapa(f.get("etapa"), f.get("estado"))] += int(f["n"])
    principales = sorted(por_capitulo, key=lambda c: -sum(por_capitulo[c][anios[1]].values()))[:CAPITULOS_MOSTRADOS]

    return {
        "anios": anios,
        "anio_en_curso": corte.year,
        "todos": {str(a): _con_totales(todos[a]) for a in anios},
        "homicidio_doloso": {str(a): _con_totales(homicidio["doloso"][a]) for a in anios},
        "homicidio_culposo": {str(a): _con_totales(homicidio["culposo"][a]) for a in anios},
        "por_delito": [{"delito": nombre_capitulo(c),
                        **{str(a): _con_totales(por_capitulo[c][a]) for a in anios[:2]}} for c in principales],
    }


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
    espera = REINTENTO_TRAS_ERROR if estado.status == "ERROR" else CADA_CUANTO
    if not forzar and estado.last_checked_at and ahora - estado.last_checked_at < espera:
        return None
    estado.last_checked_at = ahora
    try:
        resultado = resumen(consulta)
    except Exception as error:
        estado.status = "ERROR"
        estado.warnings = [f"No se pudo consultar datos.gov.co: {error}"[:300]]
        db.commit()
        logger.warning(f"[Fiscalía] {error}")
        return {"error": str(error)}
    corte = resultado["corte"]
    anterior = estado.source_cutoff_date
    total = resultado["procesos"][-1]
    estado.status = "CURRENT"
    estado.quality_status = "VALIDATED"
    estado.source_cutoff_date = corte
    estado.period_label = f"Corte al {corte.isoformat()} - {total['actual']} procesos por hechos en Jamundi este año"
    estado.last_success_at = ahora
    estado.indicator_count = len(resultado["procesos"]) - 1
    estado.record_count = total["actual"]
    estado.warnings = []
    # Misma forma de tabla que el contraste de la Policía, para mostrarla en "Detalles".
    filas = [{"delito": f["delito"], "oficial_actual": f["actual"], "oficial_anterior": f["anterior"],
              "sabana_actual": None, "diferencia": None, "corte": corte.isoformat()}
             for f in resultado["procesos"] + resultado["personas"]]
    estado.details = {"fuente": "datos.gov.co (Fiscalía General de la Nación, SPOA V3)", "contraste": filas,
                      "respuesta_judicial": resultado["respuesta_judicial"], "tipo_tabla": "judicial",
                      "seguimiento": resultado["seguimiento"]}
    if corte != anterior:
        estado.last_change_detected_at = ahora
    db.commit()
    return resultado
