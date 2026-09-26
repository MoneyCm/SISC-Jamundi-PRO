"""Informe para decisión del Consejo: dos páginas que responden qué requiere decisión y qué se cumplió.

Todo sale de módulos del SISC que ya calculan sus cifras (sábana policial, radar de la
Defensoría, compromisos, recomendaciones del Observatorio, intervenciones). Nada lo
redacta la IA. Es un documento de trabajo reservado para la instancia.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from db.models_council import CouncilCommitment, CouncilCommitmentUpdate
from db.models_interventions import InterventionCase
from db.models_observatory import ObservatoryRecommendation, ObservatoryStudy
from services import council_commitments_service as commitments
from services import intervention_followup, observatory_service
from services.act_reader import INSTANCES
from services.indicator_calculation import calculate_indicator
from services.indicator_catalog import METHODOLOGY_VERSION, get_indicator_meta

MAX_DECISIONS = 3
RECENT_DAYS = 28
SMALL_BASE = 30
# Conductas del cuadro de situación, en el orden en que se leen en el Consejo.
SITUATION_INDICATORS = ["SEGURIDAD_TOTAL", "HOMICIDIO", "LESIONES", "HURTO_PERSONAS", "HURTO_MOTOS",
                        "HURTO_AUTOMOTORES", "HURTO_RESIDENCIAS", "HURTO_COMERCIO"]
# Un compromiso pedido tantas veces sin cumplirse ya no se resuelve repitiéndolo.
STUCK_MENTIONS = 3
RESERVED_NOTE = "Documento de trabajo reservado para la instancia. No publicar: contiene lecturas territoriales y compromisos en curso."


def _same_day_last_year(value: date) -> date:
    try:
        return value.replace(year=value.year - 1)
    except ValueError:  # 29 de febrero
        return value.replace(year=value.year - 1, day=28)


def compare(current: int, previous: int) -> Dict[str, Any]:
    difference = current - previous
    small = previous < SMALL_BASE
    return {"current": current, "previous": previous, "difference": difference, "small_base": small,
            "variation_pct": None if small or not previous else round(difference / previous * 100, 1)}


def situation(db: Session) -> Dict[str, Any]:
    run = intervention_followup.latest_covering_run(db)
    if not run:
        return {"status": "SIN_DATOS", "reason": "No hay una entrega policial completa con cobertura declarada.", "rows": []}
    cutoff = run.cobertura_fin
    windows = {
        "recent": (cutoff - timedelta(days=RECENT_DAYS - 1), cutoff),
        "year": (date(cutoff.year, 1, 1), cutoff),
    }
    comparable = {key: _same_day_last_year(start) >= run.cobertura_inicio for key, (start, _) in windows.items()}
    kwargs = dict(territory="JAMUNDI", source_version_id=str(run.id), methodology_version=METHODOLOGY_VERSION)

    def value(indicator, start, end):
        return int(calculate_indicator(db, indicator=indicator, period_start=start, period_end=end, **kwargs)["value"])

    rows = []
    for indicator in SITUATION_INDICATORS:
        row = {"indicator": indicator, "label": get_indicator_meta(indicator).get("label", indicator)}
        for key, (start, end) in windows.items():
            current = value(indicator, start, end)
            if comparable[key]:
                row[key] = compare(current, value(indicator, _same_day_last_year(start), _same_day_last_year(end)))
            else:
                row[key] = {"current": current, "previous": None, "difference": None, "variation_pct": None, "small_base": False}
        rows.append(row)
    return {
        "status": "OK",
        "cutoff": cutoff.isoformat(),
        "recent_label": f"{windows['recent'][0]:%d/%m} al {cutoff:%d/%m/%Y}",
        "year_label": f"1 de enero al {cutoff:%d/%m/%Y}",
        "source_version_id": str(run.id),
        "rows": rows,
        "unit": "hechos únicos registrados por la Policía en Jamundí, frente a las mismas fechas del año anterior",
    }


def _last_session(rows: List[CouncilCommitment], before: date) -> Optional[date]:
    dates = [d for row in rows for d in (row.origin_date, row.last_mention_date) if d and d < before]
    return max(dates) if dates else None


def attention(rows: List[CouncilCommitment], today: date, limit: int = 8) -> List[Dict[str, Any]]:
    """Atrasados primero (tienen fecha incumplida), luego los más repetidos."""
    items = [commitments.serialize(row, today) for row in rows]
    items = [item for item in items if {"ATRASADO", "REPETIDO"} & set(item["flags"])]
    items.sort(key=lambda item: ("ATRASADO" not in item["flags"], -(item["mentions"] or 1), item["deadline_date"] or ""))
    return items[:limit]


def commitments_block(db: Session, instance: str, session_date: date) -> Dict[str, Any]:
    rows = db.query(CouncilCommitment).filter(CouncilCommitment.instance == instance).all()
    data = commitments.summary(rows, session_date)
    last = _last_session(rows, session_date)
    fulfilled = []
    if last and rows:
        updates = (db.query(CouncilCommitmentUpdate, CouncilCommitment)
                   .join(CouncilCommitment, CouncilCommitment.id == CouncilCommitmentUpdate.commitment_id)
                   .filter(CouncilCommitment.instance == instance, CouncilCommitmentUpdate.new_status == "CUMPLIDO",
                           CouncilCommitmentUpdate.created_at >= last)
                   .order_by(CouncilCommitmentUpdate.created_at).all())
        seen = set()
        for update, row in updates:
            if row.code not in seen and row.status == "CUMPLIDO":
                seen.add(row.code)
                fulfilled.append({"code": row.code, "text": row.text, "responsible": row.responsible,
                                  "note": update.note, "evidence_url": update.evidence_url})
    return {
        "last_session": last.isoformat() if last else None,
        "open": data["open"], "overdue": data["overdue"], "repeated": data["repeated"],
        "without_information": data["without_information"], "without_deadline": data["without_deadline"],
        "fulfilled_since_last": fulfilled,
        "attention": attention(rows, session_date),
    }


def decisions(db: Session, instance: str, session_date: date, block: Dict[str, Any]) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    # 1. Recomendaciones del Observatorio que esperan respuesta.
    pending = (db.query(ObservatoryRecommendation, ObservatoryStudy.code)
               .outerjoin(ObservatoryStudy, ObservatoryStudy.id == ObservatoryRecommendation.study_id)
               .filter(ObservatoryRecommendation.status == "PRESENTADA")
               .order_by(ObservatoryRecommendation.presented_on).all())
    for rec, study_code in pending:
        items.append({
            "kind": "RECOMENDACION", "title": rec.title,
            "evidence": rec.text + (f" (Estudio {study_code}.)" if study_code else ""),
            "ask": "Aceptar, rechazar o pedir más análisis. Si se acepta: responsable, plazo y compromiso que la ejecuta.",
            "ref": rec.code,
        })
    # 2. Lo que el radar marca como prioritario en la zona advertida.
    for signal in observatory_service.territory_signals(db, session_date):
        if signal["level"] == "ALTA" and signal["key"].startswith("radar"):
            items.append({
                "kind": "TERRITORIO", "title": signal["title"], "evidence": signal["detail"],
                "ask": "¿Se ordena una intervención? Definir qué se hará, quién responde, en qué plazo y qué indicador debería cambiar.",
                "ref": None,
            })
    # 3. Compromisos que el Consejo repite sin que se cumplan.
    rows = db.query(CouncilCommitment).filter(CouncilCommitment.instance == instance,
                                              CouncilCommitment.mentions >= STUCK_MENTIONS).all()
    stuck = [commitments.serialize(row, session_date) for row in rows]
    stuck = sorted((item for item in stuck if "REPETIDO" in item["flags"]), key=lambda item: -(item["mentions"] or 1))
    for item in stuck:
        if (item["mentions"] or 1) >= STUCK_MENTIONS:
            items.append({
                "kind": "COMPROMISO", "title": f"Pedido {item['mentions']} veces sin cumplirse: {item['text']}",
                "evidence": f"Responsable: {item['responsible'] or 'sin definir'}. Estado: {item['status_label']}.",
                "ask": "Repetirlo no lo ha resuelto: reformularlo, cambiar el responsable o cerrarlo con una razón.",
                "ref": item["code"],
            })
    return {"items": items[:MAX_DECISIONS], "more": max(0, len(items) - MAX_DECISIONS)}


def interventions_block(db: Session, instance: str) -> List[Dict[str, Any]]:
    codes = [code for (code,) in db.query(CouncilCommitment.code).filter(CouncilCommitment.instance == instance).all()]
    cases = db.query(InterventionCase).filter(
        (InterventionCase.commitment_code.in_(codes)) | (InterventionCase.alert_id.isnot(None))
    ).order_by(InterventionCase.created_at.desc()).limit(8).all()
    result = []
    for case in cases:
        doc = case.document or {}
        follow = intervention_followup.followup(db, doc)
        measured = [w for w in follow.get("windows", []) if w["status"] == "MEDIDO"]
        result.append({
            "origin": case.commitment_code or (doc.get("alert_snapshot") or {}).get("title") or "Alerta",
            "intervention": doc.get("intervention") or doc.get("problem"),
            "responsible": doc.get("responsible"),
            "status": case.status,
            "indicator": follow.get("indicator_label"),
            "latest_window": measured[-1] if measured else None,
            "followup_status": follow.get("status"),
            "reason": follow.get("reason"),
        })
    return result


def data_quality(db: Session, today: date) -> List[Dict[str, Any]]:
    rows = []
    for builder in (observatory_service.source_signals, observatory_service.mip_signals, observatory_service.bulletin_signals):
        try:
            rows.extend(builder(db, today))
        except Exception:  # la calidad del dato no debe impedir el informe
            db.rollback()
    return [{"level": row["level"], "title": row["title"], "detail": row["detail"]} for row in rows]


def build_report(db: Session, instance: str = "CONSEJO_SEGURIDAD", session_date: Optional[date] = None) -> Dict[str, Any]:
    if instance not in INSTANCES:
        raise ValueError("Instancia no reconocida.")
    session_date = session_date or date.today()
    block = commitments_block(db, instance, session_date)
    return {
        "instance": instance,
        "instance_label": INSTANCES[instance]["label"],
        "session_date": session_date.isoformat(),
        "generated_on": date.today().isoformat(),
        "decisions": decisions(db, instance, session_date, block),
        "situation": situation(db),
        "commitments": block,
        "interventions": interventions_block(db, instance),
        "data_quality": data_quality(db, date.today()),
        "notes": [
            "Cifras en hechos únicos de la sábana policial, municipio de Jamundí. Con menos de 30 hechos el año anterior, "
            "se informa la diferencia en casos y no el porcentaje.",
            "Los resultados de intervenciones comparan periodos de igual duración antes y después del inicio: "
            "describen un cambio, no demuestran que la intervención lo causó.",
            RESERVED_NOTE,
        ],
    }
