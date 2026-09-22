"""Reglas deterministas de alerta semanal — intervalos iguales, cobertura y cero vs ausencia.

Diseño (metodología v1, propuesta):
- Ventanas medio-abiertas [inicio, fin): 7 días exactos contra 7 días exactos.
  (calculate_indicator usa <= inclusivo; se mapea fin_exclusivo - 1 día.)
- Cobertura anclada al corte: solo períodos completos (fin <= corte).
  Fuente atrasada → advertencia de cobertura, NUNCA una aparente disminución.
- Cero vs ausencia: cobertura completa + 0 = "cero casos"; período incompleto =
  "sin cobertura" (sin alerta); previo en 0 + actual > 0 = "aparición de casos"
  (sin variación porcentual inventada); ambos en 0 = sin alerta; descensos no
  generan alerta (quedan registrados como contexto).
- Cálculo único: `calculate_indicator` con entrega fija (último COMPLETED),
  metodología y unidad explícitas. La tabla legacy queda excluida de estos
  conteos (mezclaba unidades fila vs hecho); su reincorporación histórica
  requiere decisión de backfill.
- Evidencia reproducible por alerta: períodos, valores, cobertura, corte, regla,
  umbrales, entrega, metodología y query_hashes. Persistencia idempotente en
  `intelligence_alerts` vía `dedupe_key`.
- Umbrales P1/P2/P3 propuestos, pendientes de acuerdo con el Observatorio.
- La IA solo redacta a partir de esta evidencia; nunca calcula.

Primer entregable: alerta semanal reproducible para HOMICIDIO.
"""

from __future__ import annotations

from datetime import date, timedelta, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models_hechos_seguridad import HechoSeguridad, IngestionRun
from services.indicator_calculation import calculate_indicator
from services.indicator_catalog import METHODOLOGY_VERSION

# Umbrales y reglas propuestos (pendientes de acuerdo con el Observatorio).
# La aparición de casos tiene regla propia: sin base previa no hay porcentaje.
WEEKLY_THRESHOLDS = {
    "HOMICIDIO": {
        "p1_min_current": 3,
        "p1_min_increase_pct": 50.0,
        "p2_min_current": 2,
        "p2_min_increase_pct": 25.0,
        "aparicion": {
            "tier": "P2",
            "min_current": 1,
            "justification": (
                "Sin semana previa con casos no existe base para un porcentaje; "
                "1+ hechos en semana completa cubierta generan P2 preventiva "
                "(homicidio de alto impacto), 3+ escalan a P1 por volumen."
            ),
        },
    },
}

RULE_ID = "WEEKLY_COMPLETE_V1"
# Versión de reglas/umbrales: va en la evidencia y en la clave de deduplicación.
# Cambiar CUALQUIER umbral o regla exige subirla; las evaluaciones viejas quedan
# como historial y nunca se reutilizan bajo la nueva versión.
RULES_VERSION = "R1"


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def complete_weekly_windows(cutoff: date) -> Optional[Dict[str, date]]:
    """Últimas dos semanas completas [Mon, Mon) con fin <= corte.

    Si el corte cae a mitad de semana, esa semana está incompleta y se retrocede.
    """
    this_monday = monday_of(cutoff)
    # Semana en curso [this_monday, this_monday+7): completa solo si this_monday+7 <= cutoff+1?
    # En fechas: completa si (this_monday + 7 días) <= cutoff + 1 día, i.e. next_monday <= cutoff+1.
    # Simplificado: la semana [m, m+7) es completa si m+6 <= cutoff.
    if this_monday + timedelta(days=6) <= cutoff:
        cur_start = this_monday
    else:
        cur_start = this_monday - timedelta(days=7)
    prev_start = cur_start - timedelta(days=7)
    if prev_start < date(2000, 1, 1):
        return None
    return {
        "current_start": cur_start,
        "current_end_exclusive": cur_start + timedelta(days=7),
        "previous_start": prev_start,
        "previous_end_exclusive": cur_start,
        "cutoff": cutoff,
    }


def _latest_completed_run(db: Session) -> Optional[IngestionRun]:
    return (
        db.query(IngestionRun)
        .filter(IngestionRun.fuente_codigo == "POLICIA_SEMANAL", IngestionRun.status == "COMPLETED")
        .order_by(IngestionRun.fecha_fin.desc().nullslast(), IngestionRun.fecha_inicio.desc().nullslast())
        .first()
    )


def _cutoff(db: Session) -> Optional[date]:
    return (
        db.query(func.max(HechoSeguridad.fecha_evento))
        .filter(HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL")
        .scalar()
    )


def evaluate_weekly(
    db: Session,
    indicator: str = "HOMICIDIO",
    ref_date: Optional[date] = None,
    source_version_id: Optional[str] = None,
    methodology_version: str = METHODOLOGY_VERSION,
) -> Dict[str, Any]:
    """Evalúa la alerta semanal con evidencia reproducible (no persiste)."""
    if indicator not in WEEKLY_THRESHOLDS:
        raise ValueError(f"Sin regla semanal para {indicator}. Alcance actual: {sorted(WEEKLY_THRESHOLDS)}.")
    run = None
    if source_version_id:
        from uuid import UUID
        run = db.query(IngestionRun).filter(
            IngestionRun.id == UUID(str(source_version_id)),
            IngestionRun.fuente_codigo == "POLICIA_SEMANAL",
        ).first()
        if not run or run.status != "COMPLETED":
            return {"status": "SIN_COBERTURA", "reason": f"Entrega {source_version_id} inexistente o no utilizable.", "indicator": indicator}
    else:
        run = _latest_completed_run(db)
        if not run:
            return {"status": "SIN_COBERTURA", "reason": "Sin entregas COMPLETED.", "indicator": indicator}
    delivery = str(run.id)

    cutoff = _cutoff(db)
    if not cutoff:
        return {"status": "SIN_COBERTURA", "reason": "Sin corte disponible.", "indicator": indicator,
                "territory": "JAMUNDI",
                "source_version_id": delivery, "methodology_version": methodology_version,
                "rules_version": RULES_VERSION}
    # Ancla a lo disponible: una fecha de referencia futura no crea cobertura.
    anchor = min(ref_date or cutoff, cutoff)
    windows = complete_weekly_windows(anchor)
    if not windows:
        return {"status": "SIN_COBERTURA", "reason": "Sin historia suficiente.", "indicator": indicator,
                "territory": "JAMUNDI",
                "source_version_id": delivery, "methodology_version": methodology_version,
                "rules_version": RULES_VERSION}
    # Cobertura desde la ENTREGA declarada, no solo de las fechas de los hechos:
    # la fecha del último delito no demuestra hasta cuándo reportó la fuente.
    # Una semana sin registros solo es cero si la entrega declara cobertura para
    # esa semana; si no, es cobertura desconocida.
    declared = None
    if getattr(run, "cobertura_inicio", None) and getattr(run, "cobertura_fin", None):
        declared = {"start": run.cobertura_inicio.isoformat(), "end": run.cobertura_fin.isoformat()}
    base_evidence: Dict[str, Any] = {
        "rule_id": RULE_ID,
        "rules_version": RULES_VERSION,
        "indicator": indicator,
        "unit": "HECHO",
        "territory": "JAMUNDI",
        "current_period": {"start": windows["current_start"].isoformat(),
                           "end_exclusive": windows["current_end_exclusive"].isoformat(), "days": 7},
        "previous_period": {"start": windows["previous_start"].isoformat(),
                            "end_exclusive": windows["previous_end_exclusive"].isoformat(), "days": 7},
        "cutoff": cutoff.isoformat(),
        "declared_coverage": declared,
        "thresholds": {k: v for k, v in WEEKLY_THRESHOLDS[indicator].items()},
        "threshold_status": "PROPUESTOS_PENDIENTES_OBSERVATORIO",
        "source_version_id": delivery,
        "methodology_version": methodology_version,
    }
    cur_end = windows["current_end_exclusive"] - timedelta(days=1)
    prev_end = windows["previous_end_exclusive"] - timedelta(days=1)
    covered = (
        declared is not None
        and windows["previous_start"].isoformat() >= declared["start"]
        and prev_end.isoformat() <= declared["end"]
        and windows["current_start"].isoformat() >= declared["start"]
        and cur_end.isoformat() <= declared["end"]
        and cur_end <= cutoff
    )
    if not covered:
        missing = "la entrega no declara cobertura" if declared is None else (
            f"cobertura declarada {declared['start']}–{declared['end']} no cubre "
            f"las semanas {windows['previous_start']}–{cur_end}"
        )
        return {"status": "SIN_COBERTURA", "coverage": "DESCONOCIDA",
                "reason": f"Cobertura desconocida: {missing}. Sin esa evidencia no se interpreta el cero.",
                **base_evidence}
    # Fijar entrega: si ingresa otra durante la evaluación, el llamador reintenta (ver endpoint).
    cur = calculate_indicator(db, indicator=indicator,
                              period_start=windows["current_start"],
                              period_end=cur_end,
                              territory="JAMUNDI", source_version_id=delivery,
                              methodology_version=methodology_version)
    prev = calculate_indicator(db, indicator=indicator,
                               period_start=windows["previous_start"],
                               period_end=prev_end,
                               territory="JAMUNDI", source_version_id=delivery,
                               methodology_version=methodology_version)
    cur_v, prev_v = int(cur["value"]), int(prev["value"])
    th = WEEKLY_THRESHOLDS[indicator]
    evidence: Dict[str, Any] = {
        **base_evidence,
        "unit": cur["unit_code"],
        "current_value": cur_v,
        "previous_value": prev_v,
        "coverage": "COMPLETA",
        "query_hashes": {"current": cur["query_hash"], "previous": prev["query_hash"]},
    }

    if cur_v == 0 and prev_v == 0:
        return {"status": "SIN_ALERTA", "reason": "Cero casos en ambos períodos completos con cobertura declarada.", **evidence}
    if cur_v < prev_v:
        return {"status": "SIN_ALERTA", "reason": f"Descenso ({prev_v} → {cur_v}); los descensos no generan alerta.", **evidence}
    if prev_v == 0:  # cur_v > 0: regla explícita de aparición (sin porcentaje).
        ap = th["aparicion"]
        if cur_v < ap["min_current"]:
            return {"status": "SIN_ALERTA",
                    "reason": f"Bajo el mínimo de aparición ({cur_v} < {ap['min_current']}).",
                    "applied_rule": {"rule": "APARICION_DE_CASOS", **ap}, **evidence}
        return {"status": "ALERTA", "tier": ap["tier"], "kind": "APARICION_DE_CASOS",
                "reason": (f"Aparición de casos [{ap['tier']}]: {cur_v} hecho(s) en semana completa "
                           f"con cobertura declarada y sin casos en la previa. {ap['justification']}"),
                "variation_pct": None,
                "applied_rule": {"rule": "APARICION_DE_CASOS", **ap}, **evidence}
    pct = round((cur_v - prev_v) / prev_v * 100, 1)
    evidence["variation_pct"] = pct
    if cur_v >= th["p1_min_current"] or pct >= th["p1_min_increase_pct"]:
        tier = "P1"
    elif cur_v >= th["p2_min_current"] or pct >= th["p2_min_increase_pct"]:
        tier = "P2"
    else:
        return {"status": "SIN_ALERTA", "reason": f"Variación {pct}% bajo umbrales.", **evidence}
    return {"status": "ALERTA", "tier": tier, "kind": "INCREMENTO",
            "reason": f"Incremento {pct}% ({prev_v} → {cur_v}) en semanas completas con cobertura declarada.",
            "applied_rule": {"rule": "INCREMENTO", "tier": tier, "variation_pct": pct}, **evidence}


def lineage_key_for(indicator: str, territory: str, week_start: str) -> str:
    """Identidad común por indicador+territorio+período, independiente de la entrega."""
    return f"WEEKLY:{indicator}:{territory}:{week_start}"


REVIEW_TRANSITIONS = {
    "PENDIENTE": {"EN_ANALISIS", "DESCARTADA"},
    "EN_ANALISIS": {"REVISADA", "DESCARTADA", "PENDIENTE"},
    "REVISADA": {"EN_ANALISIS"},
    "DESCARTADA": {"EN_ANALISIS"},
}


def _delivery_time(db: Session, delivery_id) -> Optional[datetime]:
    """Orden definido de entregas (no momento de ejecución)."""
    from datetime import datetime as _dt
    if not delivery_id:
        return None
    try:
        from uuid import UUID as _UUID
        run = db.query(IngestionRun).filter(IngestionRun.id == _UUID(str(delivery_id))).first()
    except Exception:
        run = None
    if not run:
        return None
    return getattr(run, "fecha_fin", None) or getattr(run, "fecha_inicio", None)


def relate_lineage(
    db: Session,
    *,
    lineage_key: str,
    new_alert_id=None,
    delivery: str,
    outcome: str,
    only_older_than=None,
) -> Dict[str, Any]:
    """Relaciona evaluaciones retrospectivas sin heredar la revisión humana.

    - Solo sustituye evaluaciones de entregas de orden anterior o igual
      (`only_older_than`): reprocesar una entrega antigua jamás sustituye una
      evaluación más reciente. La vigencia responde al orden de entregas.
    - Las anteriores OPEN tocadas pasan a SUPERSEDED con nota y enlace.
    - Sus revisiones se conservan; la nueva evaluación nace PENDIENTE.
    """
    from db.models_alerts import IntelligenceAlert

    priors = db.query(IntelligenceAlert).filter(
        IntelligenceAlert.lineage_key == lineage_key,
        IntelligenceAlert.status == "OPEN",
    ).all()
    touched = []
    for p in priors:
        if new_alert_id is not None and str(p.id) == str(new_alert_id):
            continue
        if only_older_than is not None:
            prior_time = _delivery_time(db, (p.metrics or {}).get("source_version_id"))
            if prior_time is not None and prior_time > only_older_than:
                continue
        p.status = "SUPERSEDED"
        p.superseded_by = new_alert_id
        p.supersede_note = outcome
        touched.append(str(p.id))
    if touched:
        db.commit()
    return {"superseded": touched}


def review_alert(
    db: Session,
    *,
    alert_id: str,
    username: str,
    user_id: Optional[str],
    action: str,
    expected_version: int,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    """Registra la valoración humana con bloqueo optimista (fecha del servidor)."""
    from uuid import UUID as _UUID
    from fastapi import HTTPException as _HTTP
    from db.models_alerts import AlertReview, IntelligenceAlert

    action = (action or "").strip().upper()
    try:
        aid = _UUID(str(alert_id))
    except ValueError:
        raise _HTTP(status_code=422, detail="alert_id debe ser UUID.")
    row = db.query(IntelligenceAlert).filter(IntelligenceAlert.id == aid).first()
    if not row:
        raise _HTTP(status_code=404, detail="No existe la alerta.")
    current = row.review_state or "PENDIENTE"
    if int(row.review_version or 0) != int(expected_version):
        raise _HTTP(status_code=409, detail="Otro analista cambió el estado; recargue y reintente.")
    allowed = REVIEW_TRANSITIONS.get(current, set())
    if action not in allowed:
        raise _HTTP(status_code=422, detail=f"Transición {current} → {action} no permitida.")
    if action == "DESCARTADA" and not (comment or "").strip():
        raise _HTTP(status_code=422, detail="Descartar exige motivo (comment).")
    if int(row.review_version or 0) != int(expected_version):
        raise _HTTP(status_code=409, detail="Otro analista cambió el estado; recargue y reintente.")
    row.review_state = action
    row.review_version = int(row.review_version or 0) + 1
    db.add(AlertReview(alert_id=row.id, action=action, prev_state=current, new_state=action,
                       username=username, user_id=user_id, comment=(comment or None)))
    db.commit()
    db.refresh(row)
    return {"id": str(row.id), "review_state": row.review_state,
            "review_version": row.review_version, "reviewed_by": username}


def emit_weekly(db: Session, **kwargs) -> Dict[str, Any]:
    """Evalúa y persiste idempotentemente.

    La clave distingue semana, indicador, territorio, entrega, metodología y
    versión de reglas: al ampliar el motor o cambiar una regla no se confunden
    alertas distintas ni se reutilizan resultados viejos.
    """
    from db.models_alerts import IntelligenceAlert

    result = evaluate_weekly(db, **kwargs)
    lineage = lineage_key_for(
        result.get("indicator") or kwargs.get("indicator", "HOMICIDIO"),
        result.get("territory", "JAMUNDI"),
        (result.get("current_period") or {}).get("start", ""),
    )
    result["lineage_key"] = lineage
    new_time = _delivery_time(db, result.get("source_version_id"))
    if result["status"] != "ALERTA":
        # Sin alerta pero con cobertura completa: la entrega nueva deja sin efecto
        # evaluaciones anteriores ("ya no cumple la regla"). Con cobertura
        # desconocida no se puede afirmar: no se toca el linaje.
        if result.get("coverage") == "COMPLETA":
            prior = db.query(IntelligenceAlert).filter(
                IntelligenceAlert.lineage_key == lineage,
                IntelligenceAlert.status == "OPEN",
            ).order_by(IntelligenceAlert.created_at.desc()).first()
            result["previous_evaluation_id"] = str(prior.id) if prior else None
            rel = relate_lineage(db, lineage_key=lineage, new_alert_id=None,
                                 delivery=result.get("source_version_id", ""),
                                 outcome=(f"Ya no cumple la regla con entrega {result.get('source_version_id')} "
                                          f"({result.get('current_value')} vs {result.get('previous_value')})."),
                                 only_older_than=new_time)
            result["lineage"] = rel
        return result
    key = (
        f"WEEKLY:{result['indicator']}:{result['territory']}:"
        f"{result['current_period']['start']}:{result['source_version_id']}:"
        f"{result['methodology_version']}:{result['rules_version']}"
    )
    existing = db.query(IntelligenceAlert).filter(IntelligenceAlert.dedupe_key == key).first()
    if existing:
        result["persisted"] = {"id": str(existing.id), "duplicate": True}
        result["lineage"] = {"superseded": []}
        return result
    prior = db.query(IntelligenceAlert).filter(
        IntelligenceAlert.lineage_key == lineage,
        IntelligenceAlert.status == "OPEN",
    ).order_by(IntelligenceAlert.created_at.desc()).first()
    # Enlace con la evaluación anterior del linaje (cualquier estado): la nueva
    # evaluación siempre apunta a la previa para recorrer el historial.
    latest_in_lineage = db.query(IntelligenceAlert).filter(
        IntelligenceAlert.lineage_key == lineage,
    ).order_by(IntelligenceAlert.created_at.desc()).first()
    if prior is not None:
        # Vigencia por orden de entrega: si ya existe una evaluación OPEN de una
        # entrega posterior, esta evaluación (entrega antigua reprocesada) se guarda
        # como SUPERSEDED y no sustituye a la vigente.
        prior_time = _delivery_time(db, (prior.metrics or {}).get("source_version_id"))
        if new_time is not None and prior_time is not None and prior_time > new_time:
            row = IntelligenceAlert(
                source="SISC_WEEKLY",
                alert_type=f"WEEKLY_{result['indicator']}",
                severity="HIGH" if result["tier"] == "P1" else "MEDIUM",
                title=f"Alerta semanal {result['indicator']} ({result['tier']})",
                body_md=result["reason"],
                entity_ref={"indicator": result["indicator"], "territory": result["territory"]},
                metrics={k: result[k] for k in ("rule_id", "rules_version", "unit", "current_period", "previous_period",
                                                "current_value", "previous_value", "applied_rule",
                                                "variation_pct" if "variation_pct" in result else "kind",
                                                "coverage", "cutoff", "declared_coverage",
                                                "thresholds", "threshold_status",
                                                "source_version_id", "methodology_version", "query_hashes") if k in result},
                dedupe_key=key,
                status="SUPERSEDED",
                priority_tier=result["tier"],
                rationale_md=result["reason"],
                review_state="PENDIENTE",
                review_version=0,
                lineage_key=lineage,
                previous_evaluation_id=prior.id,
                superseded_by=prior.id,
                supersede_note=(f"Evaluación con entrega anterior a la vigente "
                                f"({result['source_version_id']} < {(prior.metrics or {}).get('source_version_id')}); "
                                f"no sustituye la evaluación vigente."),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            result["persisted"] = {"id": str(row.id), "duplicate": False, "stale": True}
            result["previous_evaluation_id"] = str(prior.id)
            result["lineage"] = {"superseded": []}
            return result
    row = IntelligenceAlert(
        source="SISC_WEEKLY",
        alert_type=f"WEEKLY_{result['indicator']}",
        severity="HIGH" if result["tier"] == "P1" else "MEDIUM",
        title=f"Alerta semanal {result['indicator']} ({result['tier']})",
        body_md=result["reason"],
        entity_ref={"indicator": result["indicator"], "territory": result["territory"]},
        metrics={k: result[k] for k in ("rule_id", "rules_version", "unit", "current_period", "previous_period",
                                        "current_value", "previous_value", "applied_rule",
                                        "variation_pct" if "variation_pct" in result else "kind",
                                        "coverage", "cutoff", "declared_coverage",
                                        "thresholds", "threshold_status",
                                        "source_version_id", "methodology_version", "query_hashes") if k in result},
        dedupe_key=key,
        status="OPEN",
        priority_tier=result["tier"],
        rationale_md=result["reason"],
        review_state="PENDIENTE",
        review_version=0,
        lineage_key=lineage,
        previous_evaluation_id=(latest_in_lineage.id if latest_in_lineage else None),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    result["persisted"] = {"id": str(row.id), "duplicate": False}
    result["previous_evaluation_id"] = str(latest_in_lineage.id) if latest_in_lineage else None
    # La revisión humana anterior se conserva pero no se hereda: la nueva nace PENDIENTE.
    result["lineage"] = relate_lineage(
        db, lineage_key=lineage, new_alert_id=row.id, delivery=result["source_version_id"],
        outcome=f"Sustituida por evaluación {key} con entrega {result['source_version_id']}.",
        only_older_than=new_time,
    )
    return result
