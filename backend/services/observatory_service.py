"""Centro de Análisis: qué merece atención hoy en Jamundí.

Reúne señales que ya calcula el SISC (fuentes, cruce con las Alertas Tempranas de la Defensoría, Consejo,
alertas, intervenciones, boletín) y las del propio Observatorio (estudios y
recomendaciones). No produce cifras nuevas: cada señal cuenta lo que el módulo
de origen ya calculó y dice a qué página ir para verlo completo.

Niveles: ALTA (actuar ya), MEDIA (revisar esta semana), INFO (contexto), OK (al día).
"""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models_observatory import ObservatoryRecommendation, ObservatoryStudy

logger = logging.getLogger(__name__)

GROUPS = (
    ("DATOS", "Datos", "¿Podemos confiar en lo que vemos?"),
    ("TERRITORIO", "Territorio", "¿Qué está cambiando y dónde?"),
    ("DECISIONES", "Decisiones", "¿Qué se decidió y qué falta cumplir?"),
    ("CONOCIMIENTO", "Conocimiento", "¿Qué está investigando y recomendando el Observatorio?"),
)
LEVEL_ORDER = {"ALTA": 0, "MEDIA": 1, "INFO": 2, "OK": 3}
MIP_STALE_DAYS = 45
GEO_MISSING = "RNMC_GEO_MISSING"
BULLETIN_STALE_DAYS = 14
# El boletín mensual del mes vencido se publica en la primera semana (modelo operativo, sección 4).
MONTHLY_BULLETIN_DAYS = 7
MONTH_NAMES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
               "septiembre", "octubre", "noviembre", "diciembre")
# Una recomendación presentada sin decisión en este plazo se señala: nadie la está respondiendo.
RECOMMENDATION_UNANSWERED_DAYS = 30
ATTENTION_SOURCE_STATUSES = {"ERROR", "NOT_CONNECTED", "UPDATE_AVAILABLE", "NEEDS_REVIEW", "EXPIRED"}


def signal(group: str, key: str, level: str, title: str, detail: str, page: str,
           count: Optional[int] = None) -> Dict[str, Any]:
    return {"group": group, "key": key, "level": level, "title": title, "detail": detail,
            "page": page, "count": count}


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


# --- Datos -----------------------------------------------------------------------------------

def source_signals(db: Session, today: date) -> List[Dict[str, Any]]:
    from services.source_center_service import SourceCenterService

    data = SourceCenterService.summary(db)
    attention = [c for c in data["connectors"] if c.get("status") in ATTENTION_SOURCE_STATUSES]
    if not attention:
        return [signal("DATOS", "fuentes", "OK", "Fuentes externas al día",
                       f"Las {data['totals']['total']} fuentes del Centro de fuentes están al día.", "sources")]
    names = ", ".join(c["name"] for c in attention[:4])
    level = "ALTA" if any(c.get("status") == "ERROR" for c in attention) else "MEDIA"
    return [signal("DATOS", "fuentes", level, _plural(len(attention), "fuente necesita revisión", "fuentes necesitan revisión"),
                   f"{names}. Sin fuentes al día, los contrastes y el boletín pueden quedar incompletos.",
                   "sources", len(attention))]


def mip_signals(db: Session, today: date) -> List[Dict[str, Any]]:
    from db.models_inspecciones import InspeccionActuacion

    last = db.query(func.max(InspeccionActuacion.fecha_actuacion)).filter(
        func.date(InspeccionActuacion.fecha_actuacion) <= today).scalar()
    if not last:
        return [signal("DATOS", "comparendos", "MEDIA", "Sin comparendos cargados",
                       "Inspecciones (MIP) no tiene comparendos: las alertas de convivencia no tienen base.", "inspecciones")]
    days = (today - last.date()).days
    if days <= MIP_STALE_DAYS:
        return [signal("DATOS", "comparendos", "OK", "Comparendos al día",
                       f"Los comparendos llegan hasta el {last.date():%d/%m/%Y}.", "inspecciones")]
    return [signal("DATOS", "comparendos", "MEDIA", f"Comparendos sin actualizar hace {days} días",
                   f"El dato más reciente de Inspecciones es del {last.date():%d/%m/%Y}. "
                   "Hasta cargar los meses siguientes, las alertas de convivencia y el boletín van sin esta fuente.",
                   "inspecciones", days)]


def bulletin_signals(db: Session, today: date) -> List[Dict[str, Any]]:
    from db.models_sisc_cifras import SiscCifrasPublication

    last = db.query(func.max(SiscCifrasPublication.period_end)).filter(
        SiscCifrasPublication.status == "PUBLISHED", SiscCifrasPublication.edition_type == "weekly").scalar()
    if not last:
        rows = [signal("DATOS", "boletin", "MEDIA", "No hay boletín semanal publicado",
                       "El Boletín institucional todavía no tiene una edición semanal publicada.", "boletin_replica")]
    elif (days := (today - last).days) <= BULLETIN_STALE_DAYS:
        rows = [signal("DATOS", "boletin", "OK", "Boletín semanal al día",
                       f"La última edición semanal cubre hasta el {last:%d/%m/%Y}.", "boletin_replica")]
    else:
        rows = [signal("DATOS", "boletin", "MEDIA", f"Boletín semanal sin publicar hace {days} días",
                       f"La última edición semanal cubre hasta el {last:%d/%m/%Y}.", "boletin_replica", days)]
    return rows + monthly_bulletin_signals(db, today)


def monthly_bulletin_signals(db: Session, today: date) -> List[Dict[str, Any]]:
    """El mensual del mes vencido se publica en la primera semana; después se señala como atrasado."""
    from db.models_sisc_cifras import SiscCifrasPublication

    month_end = today.replace(day=1) - timedelta(days=1)
    month_start = month_end.replace(day=1)
    name = f"{MONTH_NAMES[month_end.month - 1]} de {month_end.year}"
    published = db.query(SiscCifrasPublication.id).filter(
        SiscCifrasPublication.status == "PUBLISHED", SiscCifrasPublication.edition_type == "monthly",
        SiscCifrasPublication.period_start == month_start, SiscCifrasPublication.period_end == month_end,
    ).first()
    if published:
        return [signal("DATOS", "boletin-mensual", "OK", f"Boletín mensual de {name} publicado",
                       "La edición mensual del mes vencido ya está en la web.", "boletin_replica")]
    if today.day <= MONTHLY_BULLETIN_DAYS:
        return [signal("DATOS", "boletin-mensual", "MEDIA", f"Toca el boletín mensual de {name}",
                       f"Se publica en la primera semana del mes (hasta el día {MONTHLY_BULLETIN_DAYS}). "
                       "Elija «Mensual» en el Boletín institucional.", "boletin_replica")]
    return [signal("DATOS", "boletin-mensual", "ALTA", f"Boletín mensual de {name} atrasado",
                   f"Debía publicarse antes del día {MONTHLY_BULLETIN_DAYS}; van {today.day - MONTHLY_BULLETIN_DAYS} días de retraso.",
                   "boletin_replica", today.day - MONTHLY_BULLETIN_DAYS)]


# --- Territorio ------------------------------------------------------------------------------

def territory_signals(db: Session, today: date) -> List[Dict[str, Any]]:
    from services.sat_radar_service import build_sat_radar

    radar = build_sat_radar(db)
    if radar.get("status") != "OK":
        return [signal("TERRITORIO", "radar", "INFO", "Cruce con las Alertas Tempranas de la Defensoría sin base",
                       radar.get("reason") or "No hay datos suficientes.", "alerts")]
    cutoff = radar["generated_for"]["cutoff"]
    rows = []
    # El radar ya redacta sus hallazgos a partir de los conteos: se muestran tal cual.
    for item in radar.get("signals", [])[:3]:
        level = "ALTA" if item.get("kind") in ("LETALIDAD", "DIVERGENCIA") else "MEDIA"
        rows.append(signal("TERRITORIO", f"radar-{item.get('kind', '').lower()}", level, item["title"],
                           f"{item['detail']} Corte: {date.fromisoformat(cutoff):%d/%m/%Y}. Contraste del SISC con la "
                           "Alerta Temprana de la Defensoría, no una alerta nueva.", "alerts"))
    if not rows:
        rows.append(signal("TERRITORIO", "radar", "OK", "Sin divergencias en la zona advertida",
                           "El radar no encuentra cambios que distingan la zona advertida del resto del municipio.", "alerts"))
    return rows


def anomaly_signals(db: Session, today: date) -> List[Dict[str, Any]]:
    from services.anomaly_radar import build_anomalies

    data = build_anomalies(db)
    if data["status"] != "OK":
        return []
    rows = []
    for item in data["anomalies"][:3]:
        group = "DATOS" if item["rule"] == "R3" else "TERRITORIO"
        rows.append(signal(group, f"anomalia-{item['rule'].lower()}-{len(rows)}", item["level"],
                           f"Señal estadística: {item['title']}", item["detail"], "observatory"))
    return rows


def alert_signals(db: Session, today: date) -> List[Dict[str, Any]]:
    from db.models_alerts import IntelligenceAlert

    open_alerts = db.query(IntelligenceAlert).filter(IntelligenceAlert.status == "OPEN")
    # Un comparendo sin ubicación es un problema de calidad del dato, no una alerta de gestión.
    geo_missing = open_alerts.filter(IntelligenceAlert.alert_type == GEO_MISSING).count()
    counts = dict(open_alerts.filter(IntelligenceAlert.alert_type != GEO_MISSING)
                  .with_entities(IntelligenceAlert.severity, func.count(IntelligenceAlert.id))
                  .group_by(IntelligenceAlert.severity).all())
    high = counts.get("HIGH", 0) + counts.get("CRITICAL", 0)
    total = sum(counts.values())
    quality = [signal("DATOS", "comparendos-sin-ubicacion", "MEDIA",
                      _plural(geo_missing, "comparendo sin ubicación geográfica", "comparendos sin ubicación geográfica"),
                      "No se pueden ubicar en un barrio o vereda: corrija la dirección en Inspecciones para que cuenten en el territorio.",
                      "inspecciones", geo_missing)] if geo_missing else []
    if not total:
        return quality + [signal("TERRITORIO", "alertas", "OK", "Sin alertas SISC abiertas", "La bandeja de Alertas SISC está vacía.", "alerts")]
    detail = f"{high} de prioridad alta. Revisarlas es decidir si merecen una intervención o se descartan."
    level = "ALTA" if high else "MEDIA"
    # Las Alertas SISC salen de los comparendos: si la fuente está vieja, no describen el presente.
    from db.models_inspecciones import InspeccionActuacion
    last = db.query(func.max(InspeccionActuacion.fecha_actuacion)).filter(
        func.date(InspeccionActuacion.fecha_actuacion) <= today).scalar()
    if last and (today - last.date()).days > MIP_STALE_DAYS:
        level = "MEDIA"
        detail = (f"Calculadas sobre comparendos que llegan hasta el {last.date():%d/%m/%Y} "
                  f"({(today - last.date()).days} días de atraso): actualice la fuente antes de gestionarlas. {high} de prioridad alta.")
    return quality + [signal("TERRITORIO", "alertas", level,
                             f"{_plural(total, 'Alerta SISC abierta', 'Alertas SISC abiertas')} sin gestionar", detail, "alerts", total)]


# --- Decisiones ------------------------------------------------------------------------------

def council_signals(db: Session, today: date) -> List[Dict[str, Any]]:
    from db.models_council import CouncilActRead, CouncilCommitment
    from services import council_commitments_service

    data = council_commitments_service.summary(db.query(CouncilCommitment).all(), today)
    rows = []
    if data["overdue"] or data["repeated"]:
        rows.append(signal("DECISIONES", "compromisos", "ALTA",
                           f"{_plural(data['overdue'], 'compromiso atrasado', 'compromisos atrasados')}",
                           f"{_plural(data['repeated'], 'compromiso se ha', 'compromisos se han')} pedido más de una vez "
                           f"sin cumplirse. {data['open']} abiertos en total.", "council_commitments", data["overdue"]))
    if data["without_information"]:
        rows.append(signal("DECISIONES", "sin-informacion", "MEDIA",
                           f"{_plural(data['without_information'], 'compromiso', 'compromisos')} sin reporte de avance",
                           "Nadie ha informado cómo van desde que se registraron.", "council_commitments", data["without_information"]))
    pending = db.query(func.count(CouncilActRead.id)).filter(CouncilActRead.status == "PENDIENTE").scalar() or 0
    if pending:
        rows.append(signal("DECISIONES", "actas", "MEDIA", f"{_plural(pending, 'acta leída', 'actas leídas')} por confirmar",
                           "Sus compromisos no cuentan hasta que alguien los revise y confirme.", "council_commitments", pending))
    if not rows:
        rows.append(signal("DECISIONES", "compromisos", "OK", "Compromisos al día",
                           f"{data['open']} abiertos, ninguno atrasado ni repetido.", "council_commitments"))
    return rows


def intervention_signals(db: Session, today: date) -> List[Dict[str, Any]]:
    from db.models_interventions import InterventionCase

    counts = dict(db.query(InterventionCase.status, func.count(InterventionCase.id)).group_by(InterventionCase.status).all())
    total = sum(counts.values())
    if not total:
        return [signal("DECISIONES", "intervenciones", "INFO", "Ninguna intervención documentada",
                       "Sin intervenciones registradas no se puede evaluar qué funcionó. "
                       "Cada compromiso en ejecución debería tener su intervención documentada.", "council_commitments")]
    detail = ", ".join(f"{n} {status.lower().replace('_', ' ')}" for status, n in sorted(counts.items()))
    return [signal("DECISIONES", "intervenciones", "INFO", _plural(total, "intervención documentada", "intervenciones documentadas"),
                   detail + ".", "council_commitments", total)]


# --- Conocimiento ----------------------------------------------------------------------------

def knowledge_signals(db: Session, today: date, include_reserved: bool) -> List[Dict[str, Any]]:
    studies = db.query(ObservatoryStudy)
    if not include_reserved:
        studies = studies.filter(ObservatoryStudy.access_level != "RESERVADO")
    active = studies.filter(ObservatoryStudy.status.in_(("ABIERTO", "EN_CURSO"))).count()
    rows = []
    for study in studies.filter(ObservatoryStudy.review_on.isnot(None), ObservatoryStudy.review_on <= today).order_by(
            ObservatoryStudy.review_on).all():
        late = (today - study.review_on).days
        rows.append(signal("CONOCIMIENTO", f"revision-{study.code}", "MEDIA",
                           f"Toca la revisión posterior del estudio {study.code}",
                           f"«{study.title}»: ¿se aplicaron sus recomendaciones y qué cambió? "
                           + (f"Prevista para el {study.review_on:%d/%m/%Y}." if late else "Prevista para hoy."),
                           "observatory"))
    limit = today - timedelta(days=RECOMMENDATION_UNANSWERED_DAYS)
    unanswered = db.query(ObservatoryRecommendation).filter(
        ObservatoryRecommendation.status == "PRESENTADA", ObservatoryRecommendation.presented_on <= limit).count()
    if unanswered:
        rows.append(signal("CONOCIMIENTO", "sin-respuesta", "ALTA",
                           f"{_plural(unanswered, 'recomendación', 'recomendaciones')} sin respuesta",
                           f"Presentadas hace más de {RECOMMENDATION_UNANSWERED_DAYS} días y nadie ha decidido si se aceptan.",
                           "observatory", unanswered))
    draft = db.query(ObservatoryRecommendation).filter(ObservatoryRecommendation.status == "PROPUESTA").count()
    if draft:
        rows.append(signal("CONOCIMIENTO", "propuestas", "MEDIA",
                           f"{_plural(draft, 'recomendación', 'recomendaciones')} por presentar",
                           "Redactadas por el Observatorio; falta llevarlas a la instancia que decide.", "observatory", draft))
    accepted_unlinked = db.query(ObservatoryRecommendation).filter(
        ObservatoryRecommendation.status.in_(("ACEPTADA", "EN_EJECUCION")),
        ObservatoryRecommendation.commitment_code.is_(None)).count()
    if accepted_unlinked:
        rows.append(signal("CONOCIMIENTO", "sin-compromiso", "MEDIA",
                           f"{_plural(accepted_unlinked, 'recomendación aceptada', 'recomendaciones aceptadas')} sin compromiso",
                           "Se aceptaron, pero no están enlazadas al compromiso que las ejecuta: no se les podrá hacer seguimiento.",
                           "observatory", accepted_unlinked))
    rows.append(signal("CONOCIMIENTO", "estudios", "INFO",
                       _plural(active, "estudio en curso", "estudios en curso") if active else "Ningún estudio abierto",
                       ("Con dos estudios abiertos se llega al tope del Observatorio: para abrir otro, cierre o pause uno."
                        if active >= 2 else "Cada estudio responde una pregunta concreta sobre un fenómeno y un territorio.")
                       if active else "Abra un estudio cuando una señal merezca más que una lectura rápida.",
                       "observatory", active))
    return rows


def piscc_signals(db: Session, today: date) -> List[Dict[str, Any]]:
    from services.piscc_goals import build_goals, short_text

    data = build_goals(db, today)
    off = [item for item in data["indicators"] if item["id"] in data["off_track"]]
    if not off:
        measured = sum(1 for item in data["indicators"] if item["status"] != "SIN_DATOS")
        return [signal("DECISIONES", "piscc-metas", "OK", "Metas del PISCC en trayectoria",
                       f"{measured} de {len(data['indicators'])} indicadores de resultado medidos; ninguno se aparta de su meta.",
                       "observatory")]
    title = _plural(len(off), "meta del PISCC presenta desviación", "metas del PISCC presentan desviación")
    return [signal("DECISIONES", "piscc-metas", "MEDIA", title,
                   "; ".join(short_text(item) for item in off) + ". Cada cifra con su fuente y su corte.",
                   "observatory", len(off))]


def data_request_signals(db: Session, today: date) -> List[Dict[str, Any]]:
    from services.data_requests import signals

    return [signal("DATOS", f"solicitudes-{index}", item["level"], item["title"], item["detail"], "observatory",
                   item.get("count")) for index, item in enumerate(signals(db, today))]


def calendar_signals(db: Session, today: date) -> List[Dict[str, Any]]:
    from services.operating_calendar import council_signals

    return [signal("DECISIONES", item["key"], item["level"], item["title"], item["detail"], "council_commitments")
            for item in council_signals(db, today)]


def piscc_action_signals(db: Session, today: date) -> List[Dict[str, Any]]:
    from services.piscc_actions import signals

    return [signal("DECISIONES", "piscc-acciones", item["level"], item["title"], item["detail"], "observatory",
                   item.get("count")) for item in signals(db, today)]


def _safe(builder: Callable[..., List[Dict[str, Any]]], group: str, label: str, *args) -> List[Dict[str, Any]]:
    try:
        return builder(*args)
    except Exception:  # una fuente caída no debe tumbar la portada
        logger.exception("Centro de Análisis: no se pudo leer %s", label)
        db = args[0]
        db.rollback()
        return [signal(group, f"error-{label}", "MEDIA", f"No se pudo leer {label}",
                       "El módulo de origen falló; revíselo directamente.", "dashboard")]


def overview(db: Session, today: Optional[date] = None, include_reserved: bool = False) -> Dict[str, Any]:
    today = today or date.today()
    signals: List[Dict[str, Any]] = []
    for builder, group, label in (
        (source_signals, "DATOS", "fuentes"),
        (mip_signals, "DATOS", "comparendos"),
        (bulletin_signals, "DATOS", "boletín"),
        (data_request_signals, "DATOS", "solicitudes de datos"),
        (territory_signals, "TERRITORIO", "radar"),
        (anomaly_signals, "TERRITORIO", "anomalías"),
        (alert_signals, "TERRITORIO", "alertas"),
        (council_signals, "DECISIONES", "compromisos"),
        (calendar_signals, "DECISIONES", "calendario del Consejo"),
        (intervention_signals, "DECISIONES", "intervenciones"),
        (piscc_signals, "DECISIONES", "metas del PISCC"),
        (piscc_action_signals, "DECISIONES", "plan de acción del PISCC"),
    ):
        signals.extend(_safe(builder, group, label, db, today))
    signals.extend(_safe(knowledge_signals, "CONOCIMIENTO", "estudios", db, today, include_reserved))
    signals.sort(key=lambda item: LEVEL_ORDER.get(item["level"], 9))
    counts = {level: sum(1 for item in signals if item["level"] == level) for level in LEVEL_ORDER}
    return {
        "as_of": today.isoformat(),
        "groups": [{"key": key, "label": label, "question": question} for key, label, question in GROUPS],
        "signals": signals,
        "counts": counts,
        "rule": "El Centro de Análisis no calcula cifras propias: cada señal repite lo que calculó su módulo de origen.",
    }


# --- Códigos ---------------------------------------------------------------------------------

def next_code(db: Session, model, prefix: str, today: Optional[date] = None) -> str:
    year = (today or date.today()).year
    stem = f"{prefix}-{year}-"
    codes = [code for (code,) in db.query(model.code).filter(model.code.like(f"{stem}%")).all()]
    numbers = [int(match.group(1)) for code in codes if (match := re.fullmatch(rf"{stem}(\d+)", code))]
    return f"{stem}{(max(numbers) + 1 if numbers else 1):03d}"
