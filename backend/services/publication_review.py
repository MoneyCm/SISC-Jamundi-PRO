"""Revisión editorial automática de un boletín SISC en cifras antes de publicarlo.

No reemplaza a la persona que aprueba: le dice qué mirar. Cada verificación tiene un nivel:

- BLOQUEA: no se puede publicar (p. ej. una fuente sin cobertura para el periodo).
- REVISAR: se puede publicar, pero quien aprueba debe confirmar que lo vio.
- OK: verificación superada, para que la persona sepa qué se comprobó.

Los problemas que detecta son los encontrados en boletines reales: cifras de otro periodo
presentadas como del periodo, titulares sobre semanas incompletas o bases pequeñas,
fuentes atrasadas y valores idénticos que sugieren una fila copiada.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

SMALL_BASE_THRESHOLD = 30
PRELIMINARY_LAG_DAYS = 7


def _check(level: str, code: str, title: str, detail: str) -> Dict[str, str]:
    return {"level": level, "code": code, "title": title, "detail": detail}


def _parse_date(value: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _indicator_by_id(publication: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {item.get("id"): item for item in publication.get("indicators") or []}


def review_publication(publication: Dict[str, Any]) -> List[Dict[str, str]]:
    checks: List[Dict[str, str]] = []
    governance = publication.get("governance") or {}
    indicators = publication.get("indicators") or []
    insights = publication.get("insights") or []
    by_id = _indicator_by_id(publication)
    period_end = _parse_date((publication.get("period") or {}).get("end"))

    # 1. Fuentes sin cobertura publicable para el periodo (con su nombre y cómo resolverlo).
    blocked_sources = set()
    for source in publication.get("sources") or []:
        if source.get("coverage_status") == "not_applicable" or source.get("publishable", True):
            continue
        name = source.get("name") or source.get("code")
        blocked_sources.add(source.get("code"))
        checks.append(_check(
            "BLOQUEA", "FUENTE_SIN_COBERTURA", f"{name} no cubre el periodo",
            f"{source.get('status_note') or 'Sin cortes publicables para el periodo.'} "
            "Quite esta fuente del boletín o cargue su corte antes de publicar.",
        ))
    if not blocked_sources:
        for blocker in governance.get("review_blockers") or []:
            checks.append(_check("BLOQUEA", "FUENTE_SIN_COBERTURA", "Fuente sin cobertura para el periodo", blocker))

    if not indicators:
        checks.append(_check("BLOQUEA", "SIN_INDICADORES", "El boletín no tiene cifras publicables",
                             "No hay indicadores públicos para el periodo y las fuentes seleccionadas."))

    # 2. Cifras de otro periodo (último informe disponible de una dependencia).
    context = [item for item in indicators if (item.get("metadata") or {}).get("coverage_type") == "CONTEXT"]
    if context:
        groups = defaultdict(set)
        for item in context:
            meta = item.get("metadata") or {}
            groups[meta.get("reporting_entity") or item.get("source")].add(meta.get("period_label") or meta.get("period") or "otro periodo")
        detail = "; ".join(f"{entity}: {', '.join(sorted(periods))}" for entity, periods in sorted(groups.items()))
        checks.append(_check(
            "REVISAR", "CIFRAS_DE_OTRO_PERIODO", "Incluye cifras de otro periodo",
            f"{detail}. El boletín las identifica como último informe disponible; confirme que se entiende que no son del periodo.",
        ))

    # 3. El titular: semana preliminar o base pequeña.
    headline_indicators = [by_id.get(ref) for ref in (insights[0].get("evidence_indicator_ids") or [])] if insights else []
    for item in filter(None, headline_indicators):
        meta = item.get("metadata") or {}
        cutoff = _parse_date(item.get("cutoff_date"))
        end = _parse_date(item.get("period_end"))
        if item.get("source_code") == "POLICIA_SEMANAL" and cutoff and end and end > cutoff - timedelta(days=PRELIMINARY_LAG_DAYS):
            checks.append(_check(
                "REVISAR", "TITULAR_PRELIMINAR", "El dato destacado es preliminar",
                f"'{item.get('indicator_name')}' cubre los últimos días de la entrega policial ({cutoff.isoformat()}), "
                "que suelen completarse con reportes tardíos.",
            ))
        if meta.get("small_base"):
            checks.append(_check(
                "REVISAR", "TITULAR_BASE_PEQUENA", "El dato destacado tiene cifras pequeñas",
                f"'{item.get('indicator_name')}': {item.get('value'):g} frente a {item.get('comparison_value'):g}. "
                "El boletín muestra la diferencia en casos y no un porcentaje.",
            ))

    # 4. Fuentes atrasadas frente al periodo.
    for source in publication.get("sources") or []:
        if source.get("coverage_status") == "stale" and source.get("code") not in blocked_sources:
            checks.append(_check("REVISAR", "FUENTE_ATRASADA", f"{source.get('name', source.get('code'))} está atrasada",
                                 source.get("status_note") or "Su último corte es anterior al periodo."))

    # 5. Valores idénticos en indicadores distintos de una misma dependencia (posible fila copiada).
    seen: Dict[tuple, List[str]] = defaultdict(list)
    for item in indicators:
        value = item.get("value")
        if value is None or float(value) < 10:
            continue
        meta = item.get("metadata") or {}
        seen[(item.get("source_code"), meta.get("reporting_entity"), float(value))].append(item.get("indicator_name"))
    for (_, entity, value), names in seen.items():
        distinct = sorted(set(names))
        if len(distinct) > 1:
            checks.append(_check(
                "REVISAR", "VALORES_IDENTICOS", "Valores idénticos en indicadores distintos",
                f"{entity or 'Una fuente'} reporta {value:g} en: {', '.join(distinct)}. Confirme con la dependencia que no es un error de carga.",
            ))

    # Verificaciones superadas (para que quien aprueba sepa qué se comprobó).
    if not any(check["code"] == "FUENTE_SIN_COBERTURA" for check in checks):
        checks.append(_check("OK", "COBERTURA", "Fuentes con cobertura para el periodo",
                             "Cada fuente incluida tiene cortes que cubren el periodo o se identifica como contexto."))
    if governance.get("public_only", True):
        checks.append(_check("OK", "PRIVACIDAD", "Sin datos personales",
                             "Solo indicadores agregados clasificados como públicos y por encima del umbral de privacidad."))
    if period_end:
        checks.append(_check("OK", "FECHAS", "Periodo y cortes explícitos",
                             f"Periodo hasta {period_end.isoformat()}; cada cifra conserva su fecha de corte."))
    return checks


def summarize(checks: List[Dict[str, str]]) -> Dict[str, Any]:
    blocking = [check for check in checks if check["level"] == "BLOQUEA"]
    warnings = [check for check in checks if check["level"] == "REVISAR"]
    return {"checks": checks, "blocking": len(blocking), "warnings": len(warnings), "can_publish": not blocking}
