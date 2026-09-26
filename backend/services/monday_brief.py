"""Resumen del lunes: las ocho preguntas que el Observatorio debe responder en pocos minutos.

1. ¿El dato es confiable?          5. ¿Qué está pendiente de decisión?
2. ¿Qué cambió?                     6. ¿Qué compromisos están atrasados?
3. ¿Dónde cambió?                   7. ¿Qué intervención debe evaluarse?
4. ¿Qué merece análisis?            8. ¿Qué producto se entrega esta semana?

No calcula cifras nuevas: ordena lo que ya dicen la portada, el calendario y los módulos de
origen. La pregunta 4 aplica las reglas de triage del modelo operativo (sección 5) para proponer
candidatos a análisis; decidir cuáles se estudian sigue siendo del Observatorio.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

LEVEL_ORDER = {"ALTA": 0, "MEDIA": 1, "INFO": 2, "OK": 3}
POLICE_STALE_DAYS = 10
POLICE_VERY_STALE_DAYS = 21
REPEATED_THEME_MIN = 2


def _dmy(iso: Optional[str]) -> str:
    return date.fromisoformat(iso).strftime('%d/%m/%Y') if iso else ''


def worst(levels: List[str], default: str = "OK") -> str:
    return min(levels, key=lambda level: LEVEL_ORDER.get(level, 9)) if levels else default


def answer(key: str, question: str, level: str, text: str, items: Optional[List[str]] = None,
           target: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    return {"key": key, "question": question, "level": level, "answer": text, "items": items or [], "target": target or {}}


def _by_prefix(signals: List[Dict[str, Any]], *prefixes: str) -> List[Dict[str, Any]]:
    return [item for item in signals if item["key"].startswith(prefixes)]


def reliability(signals, run, today) -> Dict[str, Any]:
    items, levels = [], []
    if run is None:
        items.append("No hay una entrega completa de la sábana policial.")
        levels.append("ALTA")
    else:
        days = (today - run.cobertura_fin).days
        items.append(f"Sábana policial hasta el {run.cobertura_fin:%d/%m/%Y} ({days} días).")
        levels.append("ALTA" if days > POLICE_VERY_STALE_DAYS else "MEDIA" if days > POLICE_STALE_DAYS else "OK")
    for item in _by_prefix(signals, "fuentes", "comparendos", "anomalia-r3"):
        if item["level"] != "OK":
            items.append(item["title"] + ".")
            levels.append(item["level"])
    level = worst(levels)
    text = "Sí, con los cortes indicados." if level == "OK" else "Con reservas: revise estos cortes antes de interpretar."
    return answer("confiable", "¿El dato es confiable?", level, text, items, {"page": "sources"})


def changes(signals, run) -> Dict[str, Any]:
    municipal = _by_prefix(signals, "anomalia-r1")
    piscc = [item for item in _by_prefix(signals, "piscc-metas") if item["level"] != "OK"]
    cutoff = f" (datos hasta el {run.cobertura_fin:%d/%m/%Y})" if run else ""
    parts = [f"{len(municipal)} {'cifra municipal se sale' if len(municipal) == 1 else 'cifras municipales se salen'} de lo esperado"
             if municipal else f"Ninguna cifra municipal se sale de lo esperado{cutoff}"]
    parts += [item["title"] for item in piscc]
    items = [item["title"].removeprefix("Señal estadística: ") for item in municipal]
    items += [item["detail"].split(". Cada cifra")[0] for item in piscc]
    level = worst([item["level"] for item in municipal + piscc])
    return answer("cambio", "¿Qué cambió?", level, "; ".join(parts) + ".", items, {"tab": "anomalias"})


def places(signals) -> Dict[str, Any]:
    territorial = _by_prefix(signals, "anomalia-r2")
    defensoria = [item for item in _by_prefix(signals, "radar") if item["level"] != "OK" and item["key"] != "radar"]
    items = [item["title"] for item in territorial] + [f"{item['title']} (zona con Alerta Temprana de la Defensoría)" for item in defensoria]
    if not items:
        return answer("donde", "¿Dónde cambió?", "OK", "Ningún barrio, vereda o zona advertida se aparta de lo esperado.",
                      target={"tab": "territorios"})
    return answer("donde", "¿Dónde cambió?", worst([item["level"] for item in territorial + defensoria]),
                  f"{len(items)} lugares para mirar.", items, {"tab": "territorios"})


def analysis_candidates(db: Session, signals) -> Dict[str, Any]:
    """Triage (modelo operativo, sección 5): qué señales merecen convertirse en situación para análisis."""
    from db.models_council import CouncilCommitment
    from db.models_observatory import MAX_OPEN_STUDIES, OPEN_STUDY_STATUSES, ObservatoryStudy

    candidates = []
    for item in _by_prefix(signals, "anomalia-r1", "anomalia-r2"):
        if item["level"] == "ALTA":
            candidates.append(f"Señal estadística alta: {item['title'].removeprefix('Señal estadística: ')}")
    for item in _by_prefix(signals, "radar-"):
        if item["level"] == "ALTA":
            candidates.append(f"Zona con Alerta Temprana de la Defensoría: {item['title']}")
    themes = Counter(theme for (theme,) in db.query(CouncilCommitment.theme).filter(
        CouncilCommitment.mentions > 1, CouncilCommitment.theme.isnot(None)).all())
    for theme, count in themes.most_common(3):
        if count >= REPEATED_THEME_MIN:
            candidates.append(f"Tema que vuelve al Consejo: {theme} ({count} compromisos pedidos más de una vez)")
    for item in _by_prefix(signals, "piscc-metas"):
        if item["level"] != "OK":
            candidates.append(f"Metas del PISCC fuera de trayectoria: {item['detail'].split('. Cada cifra')[0]}")
    open_studies = db.query(ObservatoryStudy.id).filter(ObservatoryStudy.status.in_(OPEN_STUDY_STATUSES)).count()
    room = MAX_OPEN_STUDIES - open_studies
    capacity = (f"Hay cupo para {room} {'estudio' if room == 1 else 'estudios'}." if room > 0
                else "Tope de estudios abiertos alcanzado: para abrir otro, cierre o pause uno.")
    if not candidates:
        return answer("analisis", "¿Qué merece análisis?", "OK", "Ningún candidato según las reglas de triage. " + capacity,
                      target={"tab": "estudios"})
    return answer("analisis", "¿Qué merece análisis?", "MEDIA",
                  f"{len(candidates)} candidatos según las reglas de triage; decidir cuáles se estudian es del Observatorio. {capacity}",
                  candidates, {"tab": "estudios"})


def citizen_pending(db: Session) -> Optional[str]:
    """Reportes seguros sin cerrar y propuestas pendientes del portal."""
    from db.models import Proposal, SecureReport

    reports = db.query(SecureReport.created_at, SecureReport.estado).filter(SecureReport.estado != "CERRADO").all()
    proposals = db.query(Proposal.created_at).filter(Proposal.status == "PENDIENTE").all()
    if not reports and not proposals:
        return None
    parts = []
    if reports:
        oldest = min(day for day, _ in reports)
        untouched = sum(1 for _, state in reports if state == "RECIBIDO")
        parts.append(f"{len(reports)} {'reporte seguro abierto' if len(reports) == 1 else 'reportes seguros abiertos'}, "
                     f"{untouched} sin gestión (el más antiguo del {oldest:%d/%m/%Y})")
    if proposals:
        parts.append(f"{len(proposals)} {'propuesta ciudadana pendiente' if len(proposals) == 1 else 'propuestas ciudadanas pendientes'}")
    return "Participación ciudadana: " + "; ".join(parts) + "."


def pending_decisions(db: Session, signals) -> Dict[str, Any]:
    picked = [item for item in _by_prefix(signals, "sin-respuesta", "propuestas", "actas", "alertas", "sin-compromiso")
              if item["level"] != "OK"]
    items = [f"{item['title']}. {item['detail']}" for item in picked]
    citizens = citizen_pending(db)
    if citizens:
        items.append(citizens)
    if not items:
        return answer("decision", "¿Qué está pendiente de decisión?", "OK", "Nada pendiente de decidir.", target={"tab": "recomendaciones"})
    level = worst([item["level"] for item in picked] + (["MEDIA"] if citizens else []))
    return answer("decision", "¿Qué está pendiente de decisión?", level,
                  f"{len(items)} asuntos esperan una decisión.", items, {"tab": "recomendaciones"})


def overdue_commitments(db: Session, today: date) -> Dict[str, Any]:
    from db.models_council import CouncilCommitment
    from services import council_commitments_service as commitments

    rows = db.query(CouncilCommitment).all()
    data = commitments.summary(rows, today)
    target = {"page": "council_commitments"}
    if not data["overdue"]:
        return answer("compromisos", "¿Qué compromisos están atrasados?", "OK",
                      f"Ninguno atrasado de {data['open']} abiertos.", target=target)
    late = [item for item in (commitments.serialize(row, today) for row in rows) if "ATRASADO" in item["flags"]]
    late.sort(key=lambda item: item["deadline_date"] or "")
    items = [f"{item['code']}: {item['text'][:110]}{'…' if len(item['text']) > 110 else ''} "
             f"({item['responsible'] or 'sin responsable'}; plazo {_dmy(item['deadline_date']) or item['deadline_text'] or 'sin fecha'})"
             for item in late[:5]]
    return answer("compromisos", "¿Qué compromisos están atrasados?", "ALTA",
                  f"{data['overdue']} atrasados de {data['open']} abiertos; {data['repeated']} se han pedido más de una vez.",
                  items, target)


def interventions_to_evaluate(db: Session, signals) -> Dict[str, Any]:
    from db.models_interventions import InterventionCase

    finished = db.query(InterventionCase.id).filter(InterventionCase.status == "FINALIZADA").count()
    running = db.query(InterventionCase.id).filter(InterventionCase.status == "EN_EJECUCION").count()
    target = {"page": "council_commitments"}
    if finished:
        return answer("intervencion", "¿Qué intervención debe evaluarse?", "MEDIA",
                      f"{finished} finalizadas sin evaluar; {running} en ejecución con seguimiento a 30, 60 y 90 días.",
                      target=target)
    if running:
        return answer("intervencion", "¿Qué intervención debe evaluarse?", "INFO",
                      f"Ninguna por evaluar; {running} en ejecución con seguimiento a 30, 60 y 90 días.", target=target)
    note = next((item["detail"] for item in _by_prefix(signals, "intervenciones")), "")
    return answer("intervencion", "¿Qué intervención debe evaluarse?", "INFO", "Ninguna documentada. " + note, target=target)


def products(calendar: Dict[str, Any]) -> Dict[str, Any]:
    due = [item for item in calendar["items"] if item["status"] != "HECHO" and item["area"] in ("Boletín", "Consejo", "PISCC")]
    if not due:
        return answer("producto", "¿Qué producto se entrega esta semana?", "OK", "Los productos de la semana están al día.")
    items = [f"{item['title']} ({item['when']}){' — atrasado' if item['status'] == 'ATRASADO' else ''}" for item in due]
    level = "ALTA" if any(item["status"] == "ATRASADO" for item in due) else "MEDIA"
    return answer("producto", "¿Qué producto se entrega esta semana?", level, f"{len(due)} por entregar.", items,
                  due[0]["target"])


def build(db: Session, today: Optional[date] = None, include_reserved: bool = True) -> Dict[str, Any]:
    from services.intervention_followup import latest_covering_run
    from services.observatory_service import overview
    from services.operating_calendar import build as build_calendar

    today = today or date.today()
    signals = overview(db, today, include_reserved)["signals"]
    run = latest_covering_run(db)
    answers = [
        reliability(signals, run, today),
        changes(signals, run),
        places(signals),
        analysis_candidates(db, signals),
        pending_decisions(db, signals),
        overdue_commitments(db, today),
        interventions_to_evaluate(db, signals),
        products(build_calendar(db, today)),
    ]
    return {"as_of": today.isoformat(), "answers": answers,
            "attention": sum(1 for item in answers if item["level"] in ("ALTA", "MEDIA"))}
