"""Actualización automática de los indicadores del PISCC que salen de MinDefensa.

Secuestro, extorsión y violencia intrafamiliar (tabla 16 del PISCC) se toman de los datos
abiertos que MinDefensa publica en datos.gov.co, filtrados para Jamundí (DANE 76364), y se
guardan en data/piscc/mindefensa.json, que es lo que leen el boletín y el Centro de análisis:
- "actual": 1 de enero hasta el corte del año en curso.
- "anterior": el mismo periodo del año anterior.
- "ultimo_registro": corte de la publicación (último día del mes con datos).

La revisión corre sola una vez por semana (main.py) y deja constancia en el Centro de fuentes
(conector MINDEFENSA_PISCC). Las demás filas del archivo no se tocan.
"""
import calendar
import json
import logging
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

ARCHIVO = Path(__file__).resolve().parents[1] / "data" / "piscc" / "mindefensa.json"
DANE_JAMUNDI = "76364"
CONECTOR = "MINDEFENSA_PISCC"
CADA_CUANTO = timedelta(days=7)
DATASETS = {
    # palabra que identifica la fila en el archivo: (id en datos.gov.co, nombre)
    "secuestro": ("d7zw-hpf4", "Secuestro"),
    "extors": ("q2ib-t9am", "Extorsión"),
    "intrafamiliar": ("gepp-dxcs", "Violencia Intrafamiliar"),
}

logger = logging.getLogger("piscc_mindefensa")


def consultar(dataset: str, **parametros) -> List[dict]:
    url = f"https://www.datos.gov.co/resource/{dataset}.json?" + urllib.parse.urlencode(parametros)
    with urllib.request.urlopen(url, timeout=120) as respuesta:
        return json.loads(respuesta.read())


def _fecha(valor: str) -> date:
    return datetime.fromisoformat(valor[:10]).date()


def _un_anio_antes(valor: date) -> date:
    try:
        return valor.replace(year=valor.year - 1)
    except ValueError:
        return valor.replace(year=valor.year - 1, day=28)


def calcular_indicador(dataset: str, consulta: Callable = consultar) -> dict:
    ultimo = _fecha(consulta(dataset, **{"$select": "max(fecha_hecho) as corte"})[0]["corte"])
    corte = ultimo.replace(day=calendar.monthrange(ultimo.year, ultimo.month)[1])
    filas = consulta(dataset, cod_muni=DANE_JAMUNDI, **{"$limit": 50000})

    def suma(inicio: date, fin: date) -> int:
        return sum(int(float(f.get("cantidad") or 1)) for f in filas if inicio <= _fecha(f["fecha_hecho"]) <= fin)

    actual = suma(date(corte.year, 1, 1), corte)
    anterior = suma(date(corte.year - 1, 1, 1), _un_anio_antes(corte))
    casos = [_fecha(f["fecha_hecho"]) for f in filas if _fecha(f["fecha_hecho"]) <= corte]
    diferencia = actual - anterior
    return {
        "anterior": anterior,
        "actual": actual,
        "diffAbs": diferencia,
        "varPct": f"{diferencia / anterior * 100:+.1f}%" if anterior else "Sin base",
        "estado": "SUBE" if diferencia > 0 else ("BAJA" if diferencia < 0 else "IGUAL"),
        "ultimo_registro": corte.strftime("%d/%m/%Y"),
        "ultimo_caso_jamundi": max(casos).strftime("%d/%m/%Y") if casos else None,
        "fuente": f"MinDefensa, datos.gov.co/resource/{dataset}",
    }


def actualizar_archivo(consulta: Callable = consultar, archivo: Path = ARCHIVO, hoy: Optional[date] = None) -> Dict:
    """Consulta los tres indicadores y reescribe el archivo solo si algo cambió."""
    datos = json.loads(archivo.read_text(encoding="utf-8-sig"))
    filas = datos.setdefault("indicadores", [])
    cambios, resumen = [], {}
    for palabra, (dataset, nombre) in DATASETS.items():
        nuevo = calcular_indicador(dataset, consulta)
        fila = next((f for f in filas if palabra in str(f.get("delito", "")).lower()), None)
        if fila is None:
            fila = {"delito": nombre}
            filas.append(fila)
        clave = ("anterior", "actual", "ultimo_registro")
        if tuple(fila.get(k) for k in clave) != tuple(nuevo[k] for k in clave):
            cambios.append(f"{nombre}: {fila.get('actual')} → {nuevo['actual']} (corte {nuevo['ultimo_registro']})")
        fila.update(nuevo)
        resumen[nombre] = nuevo
    if cambios:
        datos["actualizacion_piscc"] = {
            "fecha": (hoy or date.today()).isoformat(),
            "indicadores": [nombre for _dataset, nombre in DATASETS.values()],
            "nota": "Estos tres tienen su propio corte (ultimo_registro); las demás filas conservan el corte de mes_corte.",
        }
        archivo.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cortes = [datetime.strptime(v["ultimo_registro"], "%d/%m/%Y").date() for v in resumen.values()]
    return {"cambios": cambios, "indicadores": resumen, "corte": min(cortes) if cortes else None}


def _estado(db):
    from db.models_source_center import SourceConnectorState
    estado = db.get(SourceConnectorState, CONECTOR)
    if estado is None:
        estado = SourceConnectorState(connector_code=CONECTOR, warnings=[], details={})
        db.add(estado)
    return estado


def sincronizar(db, consulta: Callable = consultar, archivo: Path = ARCHIVO, forzar: bool = False) -> Optional[Dict]:
    """Revisa MinDefensa si pasó una semana desde la última revisión y lo anota en el Centro de fuentes."""
    ahora = datetime.now(timezone.utc)
    estado = _estado(db)
    if not forzar and estado.last_checked_at and ahora - estado.last_checked_at < CADA_CUANTO:
        return None
    estado.last_checked_at = ahora
    try:
        resultado = actualizar_archivo(consulta, archivo)
    except Exception as error:
        estado.status = "ERROR"
        estado.warnings = [f"No se pudo consultar datos.gov.co: {error}"[:300]]
        db.commit()
        logger.warning(f"[PISCC MinDefensa] {error}")
        return {"error": str(error)}
    corte = resultado["corte"]
    estado.status = "CURRENT"
    estado.quality_status = "VALIDATED"
    estado.source_cutoff_date = corte
    estado.period_label = f"Corte al {corte.isoformat()} - secuestro, extorsión y violencia intrafamiliar" if corte else None
    estado.last_success_at = ahora
    estado.indicator_count = len(resultado["indicadores"])
    estado.record_count = sum(v["actual"] for v in resultado["indicadores"].values())
    estado.warnings = []
    estado.details = {"cambios": resultado["cambios"], "datasets": {n: d for d, n in DATASETS.values()},
                      "fuente": "datos.gov.co (MinDefensa)"}
    if resultado["cambios"]:
        estado.last_change_detected_at = ahora
        logger.info(f"[PISCC MinDefensa] Actualizado: {'; '.join(resultado['cambios'])}")
    db.commit()
    return resultado
