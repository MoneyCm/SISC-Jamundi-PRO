"""Catálogo único de indicadores — unidad de conteo explícita.

Resuelve el riesgo central: la plataforma contaba filas del Excel mientras el
backend cuenta hechos únicos. Cada indicador declara:

- fuente
- unidad de conteo (REGISTRO_ORIGEN | HECHO | VICTIMA | CASO_PROCESO)
- regla de deduplicación
- fecha utilizada
- dimensiones permitidas

Un hecho con tres víctimas puede ser 3 registros, 1 hecho y 3 víctimas.
El indicador debe declarar cuál utiliza. Validado por Observatorio.

Metodología v1: POLICIA_SEMANAL cuenta HECHOS (COUNT DISTINCT hecho_key).
Nunca COUNT(*) de filas para cifras oficiales.
"""

from __future__ import annotations

METHODOLOGY_VERSION = "1"

# Unidades canónicas
UNIT_REGISTRO_ORIGEN = "REGISTRO_ORIGEN"  # una fila recibida
UNIT_HECHO = "HECHO"  # evento identificado según reglas de la fuente
UNIT_VICTIMA = "VICTIMA"  # persona afectada o cantidad reportada
UNIT_CASO_PROCESO = "CASO_PROCESO"  # unidad administrativa/judicial

INDICATOR_CATALOG = {
    "HOMICIDIO": {
        "code": "HOMICIDIO",
        "source": "POLICIA_SEMANAL",
        "unit": UNIT_HECHO,
        "unit_label": "hechos registrados",
        "deduplication": "COUNT DISTINCT canonical_hecho_key(id_fuente, fingerprint, id). "
        "Mismo HECHOS_ID = 1 hecho aunque traiga N víctimas/filas. "
        "Sin ID oficial: fallback a fingerprint (hecho+víctima); correspondencia marcada incierta.",
        "date_field": "fecha_evento",
        "dimensions": ["conducta_estandar", "barrio_normalizado", "zona", "arma_medio", "sexo", "grupo_edad"],
        "conducta_filter": ["Homicidio", "HOMICIDIO", "HOMICIDIO INTENCIONAL", "HOMICIDIO DOLOSO"],
        "territory": "JAMUNDI",
        "methodology_version": METHODOLOGY_VERSION,
        "notes": "Homicidio se cuenta en HECHOS, igual que el resto de conductas. "
        "Prohibido COUNT(id) por filas para este indicador (corrige inconsistencia histórica en chat/IA). "
        "Víctimas múltiples del mismo HECHOS_ID no suman al total; ver indicador HOMICIDIO_VICTIMAS si se requiere.",
    },
    "HOMICIDIO_VICTIMAS": {
        "code": "HOMICIDIO_VICTIMAS",
        "source": "POLICIA_SEMANAL",
        "unit": UNIT_VICTIMA,
        "unit_label": "víctimas",
        "deduplication": "COUNT filas con persona identificable + SUM(cantidad) cuando la fuente agrega. "
        "Solo para análisis de afectación; no sustituye HOMICIDIO (hechos).",
        "date_field": "fecha_evento",
        "dimensions": ["sexo", "grupo_edad", "barrio_normalizado"],
        "conducta_filter": ["Homicidio", "HOMICIDIO", "HOMICIDIO INTENCIONAL", "HOMICIDIO DOLOSO"],
        "territory": "JAMUNDI",
        "methodology_version": METHODOLOGY_VERSION,
    },
    "SEGURIDAD_TOTAL": {
        "code": "SEGURIDAD_TOTAL",
        "source": "POLICIA_SEMANAL",
        "unit": UNIT_HECHO,
        "unit_label": "hechos registrados",
        "deduplication": "COUNT DISTINCT canonical_hecho_key. Equivale a seguridad.total del boletín.",
        "date_field": "fecha_evento",
        "dimensions": ["conducta_estandar", "barrio_normalizado", "zona"],
        "conducta_filter": None,
        "territory": "JAMUNDI",
        "methodology_version": METHODOLOGY_VERSION,
    },
    "POLICIA_REGISTROS": {
        "code": "POLICIA_REGISTROS",
        "source": "POLICIA_SEMANAL",
        "unit": UNIT_REGISTRO_ORIGEN,
        "unit_label": "registros de origen",
        "deduplication": "COUNT(*) sin deduplicar. Solo diagnóstico de ingesta, nunca cifra oficial.",
        "date_field": "fecha_evento",
        "dimensions": [],
        "conducta_filter": None,
        "territory": "JAMUNDI",
        "methodology_version": METHODOLOGY_VERSION,
        "notes": "Uso interno: volumen de fuente, duplicadas, fuera de territorio. No publicar.",
    },
}


def get_indicator_meta(code: str) -> dict:
    meta = INDICATOR_CATALOG.get(code)
    if not meta:
        raise ValueError(f"Indicador desconocido: {code}. Ver INDICATOR_CATALOG.")
    return meta


def list_indicators() -> list[dict]:
    return list(INDICATOR_CATALOG.values())
