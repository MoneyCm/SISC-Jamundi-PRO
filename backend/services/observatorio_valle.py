"""Cifras de Jamundí del Observatorio del Delito del Valle, desde lo que ya extrae su monitor.

El monitor de GitHub "monitor-valle" entra al portal (con el usuario asignado a la Secretaría) y
guarda en cada revisión el archivo jamundi_analytics_master.csv: copias de los gráficos de Looker
Studio sin nombres de columna (col_0 = etiqueta, col_1 = valor, col_9 = año o "Initial"), con
algunos valores repetidos por gráfico. Aquí solo se toma lo que se puede leer sin ambigüedad:
- el corte: la fecha AAAA-MM-DD que trae la vista inicial;
- por delito, el total del año en curso hasta el corte y los años anteriores completos
  (cuando un gráfico repite el dato, se toma el mayor, como hace el propio monitor).
La sincronización local (scripts/sync_source_monitors.py) lo guarda en la tarjeta OBSERVATORIO_VALLE.
"""
import csv
import io
import re
from datetime import date
from typing import Dict, List, Optional

# Etiqueta en el portal -> nombre en el SISC
DELITOS = [
    ("Homicidio", "Homicidio"),
    ("Lesiones Personales", "Lesiones personales"),
    ("Hurto Personas", "Hurto a personas"),
    ("Hurto Motocicletas", "Hurto de motocicletas"),
    ("Hurto Automotores", "Hurto de automotores"),
    ("Hurto Residencias", "Hurto a residencias"),
    ("Hurto Entidades Comerciales", "Hurto a comercio"),
    ("Violencia Intrafamiliar", "Violencia intrafamiliar"),
    ("Extorsión", "Extorsión"),
    ("Secuestro", "Secuestro"),
    ("Acceso Carnal O Acto Sexual Violento", "Acceso carnal o acto sexual violento"),
    ("Actos Sexuales Con Menor De 14 Años", "Actos sexuales con menor de 14 años"),
]
FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _numero(valor) -> Optional[float]:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def tabla_desde_csv(texto: str) -> Dict:
    filas = list(csv.DictReader(io.StringIO(texto)))
    fechas = [f["col_0"] for f in filas if f.get("col_9") == "Initial" and FECHA.match(str(f.get("col_0") or ""))]
    if not fechas:
        raise ValueError("El archivo del Observatorio no trae la fecha de corte.")
    corte = max(date.fromisoformat(f) for f in fechas)
    anio = corte.year

    def valor(etiqueta: str, anio_consulta: int) -> Optional[int]:
        valores = [_numero(f.get("col_1")) for f in filas
                   if f.get("col_0") == etiqueta and f.get("col_9") == str(anio_consulta)
                   and str(f.get("is_compare")).lower() != "true"]
        valores = [v for v in valores if v is not None]
        return int(max(valores)) if valores else None

    resultado: List[Dict] = []
    for etiqueta, nombre in DELITOS:
        actual = valor(etiqueta, anio)
        if actual is None:
            continue
        resultado.append({"delito": nombre, "oficial_actual": actual,
                          "oficial_anterior": valor(etiqueta, anio - 1),
                          "anterior_2": valor(etiqueta, anio - 2),
                          "sabana_actual": None, "diferencia": None, "corte": corte.isoformat()})
    if not resultado:
        raise ValueError("El archivo del Observatorio no trae cifras por delito reconocibles.")
    return {"corte": corte, "filas": resultado}
