"""Calendario operativo del Observatorio: qué toca esta semana (modelo operativo, secciones 3 y 4).

Junta las tareas con fecha del modelo operativo y dice, cuando el SISC puede saberlo, si ya se
hicieron: pedir datos, cargar la sábana, publicar los boletines, preparar el Consejo de
Seguridad, leer su acta y el seguimiento semestral del PISCC.

El Consejo sesiona en la última semana de cada mes, sin día fijo. La fecha de una sesión es, en
este orden: la registrada por el Observatorio, la del acta cargada de ese mes, o la última semana
del mes como estimación (7 días finales).
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

COUNCIL = "CONSEJO_SEGURIDAD"
RECOMMENDATIONS_DAYS_BEFORE = 10
REPORT_DAYS_BEFORE = 5
ACT_DAYS_AFTER = 3
STATUS_ORDER = {"ATRASADO": 0, "PENDIENTE": 1, "PROXIMO": 2, "HECHO": 3}
MONTHS = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre")


@dataclass
class Session_:
    start: date
    end: date
    source: str  # REGISTRADA | ACTA | ESTIMADA
    year: int
    month: int

    @property
    def label(self) -> str:
        if self.start == self.end:
            return f"{self.start.day} de {MONTHS[self.start.month - 1]}"
        return f"última semana de {MONTHS[self.month - 1]} ({self.start.day} al {self.end.day})"


def month_shift(year: int, month: int, delta: int):
    index = year * 12 + month - 1 + delta
    return index // 12, index % 12 + 1


def last_week(year: int, month: int):
    end = date(year, month, calendar.monthrange(year, month)[1])
    return end - timedelta(days=6), end


def plan_session(year: int, month: int, registered: List[date], acts: List[date]) -> Session_:
    in_month = lambda days: sorted(day for day in days if (day.year, day.month) == (year, month))
    for source, days in (("REGISTRADA", in_month(registered)), ("ACTA", in_month(acts))):
        if days:
            return Session_(days[0], days[0], source, year, month)
    start, end = last_week(year, month)
    return Session_(start, end, "ESTIMADA", year, month)


def sessions_around(today: date, registered: List[date], acts: List[date]):
    """(anterior, próxima) respecto a hoy."""
    current = plan_session(today.year, today.month, registered, acts)
    if today > current.end:
        return current, plan_session(*month_shift(today.year, today.month, 1), registered, acts)
    return plan_session(*month_shift(today.year, today.month, -1), registered, acts), current


def item(key: str, area: str, title: str, when: str, status: str, detail: str, target: Dict[str, str]) -> Dict[str, Any]:
    return {"key": key, "area": area, "title": title, "when": when, "status": status, "detail": detail, "target": target}


def _d(day: date) -> str:
    return f"{day.day}/{day.month:02d}"


def when_text(today: date, session: Session_) -> str:
    days = (session.start - today).days
    if session.source == "ESTIMADA" and session.start <= today <= session.end:
        return "esta semana"
    if days <= 0:
        return "hoy"
    return f"en {days} {'día' if days == 1 else 'días'}"


def council_items(today: date, previous: Session_, upcoming: Session_, proposals: int,
                  report_generated: bool, act_loaded: bool) -> List[Dict[str, Any]]:
    rows = []
    days_to = (upcoming.start - today).days
    rec_from = upcoming.start - timedelta(days=RECOMMENDATIONS_DAYS_BEFORE)
    report_from = upcoming.start - timedelta(days=REPORT_DAYS_BEFORE)
    target = {"tab": "recomendaciones"}
    if today < rec_from:
        rows.append(item("consejo-recomendaciones", "Consejo", "Decidir qué recomendaciones se presentan", f"desde el {_d(rec_from)}",
                         "PROXIMO", f"{proposals} propuestas por revisar." if proposals else "No hay propuestas pendientes.", target))
    else:
        rows.append(item("consejo-recomendaciones", "Consejo", "Decidir qué recomendaciones se presentan", f"antes del {_d(upcoming.start)}",
                         "PENDIENTE" if proposals else "HECHO",
                         f"{proposals} recomendaciones siguen como propuesta." if proposals else "No hay propuestas pendientes.", target))
    report_target = {"page": "council_commitments"}
    if report_generated:
        status, detail = "HECHO", "El informe para esta sesión ya se generó."
    elif today < report_from:
        status, detail = "PROXIMO", "Dos páginas: qué requiere decisión, situación, compromisos e intervenciones."
    else:
        status, detail = "PENDIENTE", f"El Consejo es {when_text(today, upcoming)}."
    rows.append(item("consejo-informe", "Consejo", "Informe para decisión del Consejo", f"desde el {_d(report_from)}", status, detail, report_target))

    after = (today - previous.end).days
    if not act_loaded and after >= 0 and after <= 30:
        late = after > ACT_DAYS_AFTER
        rows.append(item("consejo-acta", "Consejo", f"Leer el acta del Consejo de {MONTHS[previous.month - 1]}",
                         f"hasta el {_d(previous.end + timedelta(days=ACT_DAYS_AFTER))}", "ATRASADO" if late else "PENDIENTE",
                         "Cargar el acta, confirmar compromisos y enlazar las recomendaciones aceptadas.", {"page": "council_commitments"}))
    elif act_loaded and 0 <= after <= 7:
        rows.append(item("consejo-acta", "Consejo", f"Leer el acta del Consejo de {MONTHS[previous.month - 1]}", "hecho", "HECHO",
                         "El acta ya está cargada.", {"page": "council_commitments"}))
    return rows


def _council_inputs(db: Session, today: date):
    from db.models_auth import AuditLog
    from db.models_calendar import CouncilSession
    from db.models_council import CouncilActRead
    from db.models_observatory import ObservatoryRecommendation

    registered = [row.session_date for row in db.query(CouncilSession).filter(CouncilSession.instance == COUNCIL).all()]
    acts = [day for (day,) in db.query(CouncilActRead.act_date).filter(
        CouncilActRead.instance == COUNCIL, CouncilActRead.act_date.isnot(None)).all()]
    previous, upcoming = sessions_around(today, registered, acts)
    proposals = db.query(func.count(ObservatoryRecommendation.id)).filter(
        ObservatoryRecommendation.status == "PROPUESTA").scalar() or 0
    since = datetime.combine(upcoming.start - timedelta(days=RECOMMENDATIONS_DAYS_BEFORE), time.min)
    report_generated = db.query(AuditLog.id).filter(
        AuditLog.action == "COUNCIL_DECISION_REPORT", AuditLog.created_at >= since).first() is not None
    act_loaded = any((day.year, day.month) == (previous.year, previous.month) for day in acts)
    registered_ids = {row.session_date: str(row.id) for row in db.query(CouncilSession).filter(CouncilSession.instance == COUNCIL).all()}
    return previous, upcoming, int(proposals), report_generated, act_loaded, registered_ids


def weekly_items(db: Session, today: date) -> List[Dict[str, Any]]:
    from db.models_sisc_cifras import SiscCifrasPublication
    from services.data_requests import board
    from services.intervention_followup import latest_covering_run

    rows = []
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)

    requests = board(db, today)["counts"]
    due = requests["TOCA_PEDIR"] + requests["ATRASADA"]
    rows.append(item("pedir-datos", "Datos", "Pedir datos a Inspecciones y Comisarías", f"lunes {_d(monday)}",
                     "PENDIENTE" if due else "HECHO",
                     f"{due} dependencias por pedir o atrasadas." if due else "Todas pedidas o al día.", {"tab": "solicitudes"}))

    run = latest_covering_run(db)
    fresh = run is not None and (today - run.cobertura_fin).days <= 10
    rows.append(item("sabana", "Datos", "Cargar la sábana de la Policía", "cuando llegue (cada 1 o 2 semanas)",
                     "HECHO" if fresh else "PENDIENTE",
                     f"La última entrega llega hasta el {_d(run.cobertura_fin)}." if run else "No hay entregas completas.",
                     {"page": "boletin_replica"}))

    last_end = db.query(func.max(SiscCifrasPublication.period_end)).filter(
        SiscCifrasPublication.status == "PUBLISHED", SiscCifrasPublication.edition_type == "weekly").scalar()
    published = last_end is not None and (today - last_end).days <= 9
    rows.append(item("boletin-semanal", "Boletín", "Publicar el boletín semanal", f"viernes {_d(friday)}",
                     "HECHO" if published else ("ATRASADO" if today > friday else "PENDIENTE"),
                     f"La última edición semanal cubre hasta el {_d(last_end)}." if last_end else "No hay ediciones semanales.",
                     {"page": "boletin_replica"}))

    month_end = today.replace(day=1) - timedelta(days=1)
    month_start = month_end.replace(day=1)
    monthly = db.query(SiscCifrasPublication.id).filter(
        SiscCifrasPublication.status == "PUBLISHED", SiscCifrasPublication.edition_type == "monthly",
        SiscCifrasPublication.period_start == month_start, SiscCifrasPublication.period_end == month_end).first()
    if today.day <= 10 or not monthly:
        rows.append(item("boletin-mensual", "Boletín", f"Publicar el boletín mensual de {MONTHS[month_end.month - 1]}", "hasta el día 7",
                         "HECHO" if monthly else ("PENDIENTE" if today.day <= 7 else "ATRASADO"),
                         "Con la página de Medicina Legal.", {"page": "boletin_replica"}))
    return rows


def piscc_items(db: Session, today: date) -> List[Dict[str, Any]]:
    from services import piscc_actions as pa

    month = pa.month_in_semester(today)
    if month not in (5, 6, 1):
        return []
    semester = pa.semester_of(today) if month in (5, 6) else pa.previous_semester(pa.semester_of(today))
    if not pa.valid_semester(semester):
        return []
    totals = pa.build_tracking(db, semester)["totals"]
    missing = totals["actions"] - totals["reported"]
    status = "HECHO" if not missing else ("ATRASADO" if month == 1 else "PENDIENTE")
    return [item("piscc-semestral", "PISCC", f"Seguimiento semestral del PISCC {semester}",
                 "pedir en el mes 5, consolidar en el mes 6", status,
                 f"{totals['reported']} de {totals['actions']} acciones con reporte.", {"tab": "piscc"})]


def build(db: Session, today: Optional[date] = None) -> Dict[str, Any]:
    today = today or date.today()
    previous, upcoming, proposals, report_generated, act_loaded, registered_ids = _council_inputs(db, today)
    rows = weekly_items(db, today) + council_items(today, previous, upcoming, proposals, report_generated, act_loaded) + piscc_items(db, today)
    rows.sort(key=lambda row: STATUS_ORDER[row["status"]])
    monday = today - timedelta(days=today.weekday())
    return {
        "as_of": today.isoformat(),
        "week": {"start": monday.isoformat(), "end": (monday + timedelta(days=6)).isoformat()},
        "council": {
            "label": upcoming.label, "start": upcoming.start.isoformat(), "end": upcoming.end.isoformat(),
            "source": upcoming.source, "days_to": (upcoming.start - today).days,
            "session_id": registered_ids.get(upcoming.start) if upcoming.source == "REGISTRADA" else None,
        },
        "items": rows,
    }


def council_signals(db: Session, today: date) -> List[Dict[str, Any]]:
    """Para la portada: el informe de decisión cuando el Consejo está cerca y el acta atrasada."""
    data = build(db, today)
    rows = []
    days = data["council"]["days_to"]
    council = data["council"]
    session = Session_(date.fromisoformat(council["start"]), date.fromisoformat(council["end"]), council["source"], 0, 1)
    for row in data["items"]:
        if row["key"] == "consejo-informe" and row["status"] == "PENDIENTE":
            when = when_text(today, session)
            rows.append({"level": "ALTA" if days <= 2 else "MEDIA", "key": "calendario-informe",
                         "title": f"Consejo {when}: informe de decisión pendiente",
                         "detail": f"Sesión: {data['council']['label']}"
                                   + (" (estimada)." if data["council"]["source"] == "ESTIMADA" else ".")})
        if row["key"] == "consejo-acta" and row["status"] == "ATRASADO":
            rows.append({"level": "MEDIA", "key": "calendario-acta", "title": row["title"].replace("Leer el acta", "Acta") + " sin cargar",
                         "detail": row["detail"]})
    return rows
