"""Ficha territorial: todo lo que el SISC sabe de un barrio, vereda o sector, en un solo lugar.

Uso interno. Reúne hechos (sábana policial), comparendos (Inspecciones MIP), alertas,
anomalías, advertencias de la Defensoría, compromisos del Consejo, intervenciones y
estudios del Observatorio. Solo cifras agregadas: ningún dato de personas.
No compara territorios entre sí ni produce un ranking.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from db.models_alerts import IntelligenceAlert
from db.models_council import CouncilCommitment
from db.models_inspecciones import InspeccionExpediente, InspeccionMedida
from db.models_interventions import InterventionCase
from db.models_observatory import ObservatoryRecommendation, ObservatoryStudy
from services import anomaly_radar
from services import council_commitments_service as commitments
from services.geocoding_service import GeocodingService
from services.sat_radar_service import CONDUCTA_LABELS, GROUP_LABELS, _classifier, _events, load_registry

SMALL_BASE = 30
MONTHS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
ANALYZED_GROUPS = {"AT", "SECTOR_AT", "RURAL_NO_AT", "URBANO"}


def _same_day_last_year(value: date) -> date:
    try:
        return value.replace(year=value.year - 1)
    except ValueError:
        return value.replace(year=value.year - 1, day=28)


def _compare(current: int, previous: int) -> Dict[str, Any]:
    small = previous < SMALL_BASE
    diff = current - previous
    return {"current": current, "previous": previous, "difference": diff, "small_base": small,
            "variation_pct": None if small or not previous else round(diff / previous * 100, 1)}


def _parts(text: Optional[str]) -> List[str]:
    return [part.strip() for part in re.split(r"[,;/]| y ", text or "") if part.strip()]


def resolve(name: str):
    """Nombre oficial y grupo de un territorio, con la misma clasificación del radar de la Defensoría."""
    classify, _ = _classifier(load_registry())
    group, display = classify(name)
    if group not in ANALYZED_GROUPS:
        return None, None, classify
    return display, group, classify


def list_territories(db: Session) -> List[Dict[str, Any]]:
    """Territorios con al menos un hecho ubicado, en orden alfabético (no es un ranking)."""
    classify, _ = _classifier(load_registry())
    names = {}
    for row in _events(db):
        group, display = classify(row.lugar)
        if group in ANALYZED_GROUPS:
            names[display] = group
    return [{"name": name, "group": group, "group_label": GROUP_LABELS[group]}
            for name, group in sorted(names.items(), key=lambda item: GeocodingService.normalize_name(item[0]))]


def facts_block(events: List[Dict[str, Any]], cutoff: date) -> Dict[str, Any]:
    year_start = date(cutoff.year, 1, 1)
    prev_start, prev_end = _same_day_last_year(year_start), _same_day_last_year(cutoff)
    current = Counter(e["conducta"] for e in events if year_start <= e["fecha"] <= cutoff)
    previous = Counter(e["conducta"] for e in events if prev_start <= e["fecha"] <= prev_end)
    by_conduct = [
        {"conducta": code, "label": CONDUCTA_LABELS.get(code, code.capitalize()), **_compare(current[code], previous[code])}
        for code in sorted(set(current) | set(previous), key=lambda code: -current[code])
    ]
    total = _compare(sum(current.values()), sum(previous.values()))

    # Serie mensual de los últimos 12 meses (el mes del corte puede estar incompleto).
    months = []
    year, month = cutoff.year, cutoff.month
    for _ in range(12):
        months.append((year, month))
        year, month = (year - 1, 12) if month == 1 else (year, month - 1)
    counts = Counter((e["fecha"].year, e["fecha"].month) for e in events if e["fecha"] <= cutoff)
    series = [{"label": f"{MONTHS[m - 1]} {str(y)[2:]}", "value": counts[(y, m)], "partial": (y, m) == (cutoff.year, cutoff.month)}
              for y, m in reversed(months)]

    # Últimos 28 días frente a lo esperado (misma regla R2 del radar de anomalías).
    window_start = cutoff - timedelta(days=anomaly_radar.TERRITORY_WINDOW - 1)
    base_start = window_start - timedelta(days=anomaly_radar.TERRITORY_BASELINE_DAYS)
    recent = sum(1 for e in events if window_start <= e["fecha"] <= cutoff)
    base = sum(1 for e in events if base_start <= e["fecha"] < window_start)
    expected = (base + anomaly_radar.SMOOTHING) * anomaly_radar.TERRITORY_WINDOW / anomaly_radar.TERRITORY_BASELINE_DAYS
    anomaly = anomaly_radar.test_increase(recent, expected, anomaly_radar.TERRITORY_MIN_OBSERVED)
    return {
        "year_label": f"1 de enero al {cutoff:%d/%m/%Y} frente al mismo periodo de {cutoff.year - 1}",
        "total": total,
        "by_conduct": by_conduct,
        "monthly": series,
        "recent": {"observed": recent, "expected": round(expected, 1), "anomaly": anomaly},
    }


def comparendos_block(db: Session, display: str, classify, today: date) -> Dict[str, Any]:
    rows = (db.query(InspeccionMedida.id, InspeccionMedida.estado_actual, InspeccionMedida.fecha_inicio,
                     InspeccionMedida.nombre_medida, InspeccionExpediente.id, InspeccionExpediente.localidad)
            .join(InspeccionExpediente, InspeccionExpediente.id == InspeccionMedida.expediente_id).all())
    mine = [row for row in rows if classify(row[5] or "SIN DATO")[1] == display and classify(row[5] or "SIN DATO")[0] in ANALYZED_GROUPS]
    year_ago = today - timedelta(days=365)
    recent = [row for row in mine if row[2] and year_ago <= row[2] <= today]
    measure_ids = {str(row[0]) for row in mine}
    expediente_ids = {str(row[4]) for row in mine}
    alerts = Counter()
    for alert_type, entity in (db.query(IntelligenceAlert.alert_type, IntelligenceAlert.entity_ref)
                               .filter(IntelligenceAlert.status == "OPEN", IntelligenceAlert.source == "RNMC").all()):
        entity = entity or {}
        if str(entity.get("medida_id")) in measure_ids or str(entity.get("expediente_id")) in expediente_ids:
            alerts[alert_type] += 1
    last = max((row[2] for row in mine if row[2] and row[2] <= today), default=None)
    return {
        "total": len(mine),
        "last_12_months": len(recent),
        "by_status": dict(Counter((row[1] or "SIN ESTADO").upper() for row in mine).most_common()),
        "top_measures": [{"label": name, "count": n} for name, n in Counter(row[3] for row in recent if row[3]).most_common(5)],
        "last_date": last.isoformat() if last else None,
        "open_alerts": dict(alerts),
    }


def decisions_block(db: Session, display: str, classify, today: date) -> Dict[str, Any]:
    def mentions(text: Optional[str]) -> bool:
        return any(classify(part)[1] == display for part in _parts(text))

    rows = [row for row in db.query(CouncilCommitment).all() if mentions(row.territory)]
    items = [commitments.serialize(row, today) for row in rows]
    codes = [item["code"] for item in items]
    cases = db.query(InterventionCase).filter(InterventionCase.commitment_code.in_(codes)).all() if codes else []
    studies = [row for row in db.query(ObservatoryStudy).filter(ObservatoryStudy.access_level != "RESERVADO").all()
               if mentions(row.territory)]
    study_ids = [row.id for row in studies]
    recs = db.query(ObservatoryRecommendation).filter(ObservatoryRecommendation.study_id.in_(study_ids)).all() if study_ids else []
    return {
        "commitments": sorted(items, key=lambda item: (item["status"] in commitments.CLOSED_STATUSES, item["code"])),
        "interventions": [{"id": str(case.id), "commitment_code": case.commitment_code, "status": case.status,
                           "intervention": (case.document or {}).get("intervention") or (case.document or {}).get("problem")}
                          for case in cases],
        "studies": [{"code": row.code, "title": row.title, "status": row.status} for row in studies],
        "recommendations": [{"code": row.code, "title": row.title, "status": row.status} for row in recs],
    }


def defensoria_block(display: str) -> List[Dict[str, Any]]:
    result = []
    for alert in load_registry()["alertas"]:
        official = alert.get("territorios_oficiales", [])
        sectors = [sector.get("etiqueta") for sector in alert.get("sectores_sisc", [])]
        if display in official or display in sectors:
            result.append({"id": alert.get("id"), "title": " ".join(str(v) for v in (alert.get("tipo"), alert.get("numero")) if v),
                           "date": alert.get("fecha_emision"), "status": alert.get("estado"), "url": alert.get("url")})
    return result


def build_profile(db: Session, name: str, today: Optional[date] = None) -> Optional[Dict[str, Any]]:
    display, group, classify = resolve(name)
    if not display:
        return None
    today = today or date.today()
    rows = _events(db)
    cutoff = min(max(row.fecha for row in rows), today) if rows else today
    events = [{"fecha": row.fecha, "conducta": row.conducta} for row in rows
              if row.fecha <= cutoff and classify(row.lugar)[1] == display and classify(row.lugar)[0] == group]
    return {
        "name": display,
        "group": group,
        "group_label": GROUP_LABELS[group],
        "cutoff": cutoff.isoformat(),
        "defensoria": defensoria_block(display),
        "facts": facts_block(events, cutoff),
        "comparendos": comparendos_block(db, display, classify, today),
        "decisions": decisions_block(db, display, classify, today),
        "notes": [
            "Hechos únicos registrados por la Policía y ubicados en este territorio; los que no tienen ubicación oficial no se cuentan.",
            "Con menos de 30 hechos el año anterior se informa la diferencia en casos y no el porcentaje.",
            "Uso interno: la ficha no compara territorios ni produce un ranking, y no contiene datos de personas.",
        ],
    }
