"""Comparación pública: Jamundí frente a otros municipios, el Valle y Colombia (tasa por 100.000 habitantes).

Fuente: MinDefensa / Policía Nacional (datos.gov.co, tabla national_crime_stats con source_id
MINDEFENSA_MUNICIPAL_TOTAL), la misma de "Contexto comparado". Todos los municipios se comparan en el
mismo periodo (enero al último mes publicado del año), con la población DANE del año.
"""
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models_intelligence import NationalCrimeStats
from services.national_context_service import national_municipal_ranking, rate_per_100k

FUENTE = "MinDefensa / Policía Nacional (datos.gov.co)"
SOURCE_ID = "MINDEFENSA_MUNICIPAL_TOTAL"
JAMUNDI = "76364"
VALLE = "76"
# Delito que se muestra -> tipo de delito en MinDefensa.
DELITOS = {
    "homicidio": ("Homicidio", "Homicidio Intencional"),
    "hurto_personas": ("Hurto a personas", "Hurto Personas"),
    "hurto_vehiculos": ("Hurto de motos y carros", "Hurto Vehiculos"),
    "hurto_residencias": ("Hurto a residencias", "Hurto Residencias"),
    "hurto_comercio": ("Hurto a comercio", "Hurto Comercio"),
    "lesiones": ("Lesiones personales", "Lesiones Personales"),
    "vif": ("Violencia intrafamiliar", "Violencia Intrafamiliar"),
    "extorsion": ("Extorsión", "Extorsion"),
}
# Vecinos de Jamundí y municipios grandes del Valle.
REFERENCIA = ("76001", "76892", "76520", "76130", "19698", "19573", "76109", "76834", "76111", "76147")
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]


MINUSCULAS = {"de", "del", "la", "las", "los", "el", "y"}


def _nombre(municipio: str) -> str:
    palabras = str(municipio or "").split()
    return " ".join(p.lower() if i and p.lower() in MINUSCULAS else p.capitalize() for i, p in enumerate(palabras))


def anios_disponibles(db: Session) -> List[int]:
    return [int(a) for (a,) in db.query(NationalCrimeStats.anio).filter(NationalCrimeStats.source_id == SOURCE_ID)
            .distinct().order_by(NationalCrimeStats.anio.desc()).all()]


def comparar(db: Session, delito: str = "homicidio", anio: Optional[int] = None) -> Dict:
    if delito not in DELITOS:
        delito = "homicidio"
    etiqueta, tipo = DELITOS[delito]
    anios = anios_disponibles(db)
    if not anios:
        return {"available": False, "reason": "Todavía no hay cifras municipales de MinDefensa cargadas."}
    anio = anio if anio in anios else anios[0]
    filtros = [NationalCrimeStats.source_id == SOURCE_ID, NationalCrimeStats.anio == anio,
               NationalCrimeStats.tipo_delito == tipo]
    ultimo_mes, corte = db.query(func.max(NationalCrimeStats.mes), func.max(NationalCrimeStats.fecha_corte_mindefensa)).filter(*filtros).one()
    if not ultimo_mes:
        return {"available": False, "reason": f"MinDefensa no tiene cifras de {etiqueta.lower()} para {anio}."}
    totales = {codigo: int(total) for codigo, total in db.query(
        NationalCrimeStats.codigo_dane, func.sum(NationalCrimeStats.cantidad)).filter(*filtros).group_by(NationalCrimeStats.codigo_dane)}
    ranking = national_municipal_ranking(year=anio, target_code=JAMUNDI, totals_by_code=totales)
    por_codigo = {fila["codigo_dane"]: fila for fila in ranking}

    def fila(codigo: str) -> Optional[Dict]:
        r = por_codigo.get(codigo)
        if not r or not r.get("poblacion"):
            return None
        return {"codigo": codigo, "municipio": _nombre(r["municipio"]), "departamento": _nombre(r["departamento"]),
                "casos": r["casos"], "poblacion": r["poblacion"], "tasa": r["tasa_por_100k"], "es_jamundi": codigo == JAMUNDI}

    def agregado(nombre: str, filas: List[Dict]) -> Dict:
        casos = sum(int(f["casos"]) for f in filas)
        poblacion = sum(int(f["poblacion"] or 0) for f in filas)
        return {"nombre": nombre, "casos": casos, "poblacion": poblacion, "tasa": rate_per_100k(casos, poblacion)}

    valle = [f for f in ranking if str(f["codigo_dane"]).startswith(VALLE) and f.get("poblacion")]
    valle_orden = sorted(valle, key=lambda f: -(f["tasa_por_100k"] or 0))
    puesto = next((i for i, f in enumerate(valle_orden, start=1) if f["codigo_dane"] == JAMUNDI), None)
    municipios = [f for f in (fila(c) for c in (JAMUNDI, *REFERENCIA)) if f]
    municipios.sort(key=lambda f: -(f["tasa"] or 0))
    completo = ultimo_mes == 12
    periodo = f"enero a diciembre de {anio}" if completo else f"enero a {MESES[ultimo_mes - 1]} de {anio}"
    return {
        "available": True,
        "delito": delito, "delito_nombre": etiqueta, "anio": anio, "anios": anios,
        "delitos": [{"id": k, "nombre": v[0]} for k, v in DELITOS.items()],
        "periodo": periodo, "anio_completo": completo, "corte": corte.isoformat() if corte else None,
        "fuente": FUENTE,
        "municipios": municipios,
        "valle": agregado("Valle del Cauca", [{"casos": f["casos"], "poblacion": f["poblacion"]} for f in valle]),
        "colombia": agregado("Colombia", [{"casos": f["casos"], "poblacion": f["poblacion"] or 0} for f in ranking]),
        "puesto_valle": {"puesto": puesto, "de": len(valle_orden)},
        "nota": ("Tasa por cada 100.000 habitantes con la población DANE del año, en el mismo periodo para todos. "
                 "MinDefensa cuenta víctimas; por eso puede diferir de la sábana de hechos del SISC. "
                 "El puesto 1 es la tasa más alta del Valle."),
    }

