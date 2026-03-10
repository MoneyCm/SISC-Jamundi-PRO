import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, and_
from sqlalchemy.dialects.postgresql import insert
from db.models_intelligence import RNMCMeasure
from db.models_alerts import IntelligenceAlert
import os

logger = logging.getLogger("alerts_rnmc")

from services.alerts_prioritizer import compute_action_score

def generate_rnmc_alerts(db: Session):
    """
    Genera y deduplica alertas para el módulo RNMC con scoring Fase 3.
    """
    now = datetime.now()
    
    # ... (mismo código inicial hasta for alerts) ...
    MIN_DIAS = int(os.getenv("RNMC_ALERT_MIN_DIAS", 30))
    HIGH_VALUE_THRESHOLD = float(os.getenv("RNMC_HIGH_VALUE_THRESHOLD", 500000))
    iso_week = now.isocalendar()[1]
    bucket = f"{now.year}-W{iso_week:02d}"
    
    alerts_to_upsert = []

    # --- 1. Rezago EN PROCESO ---
    backlog_items = db.query(RNMCMeasure).filter(
        RNMCMeasure.estado == "EN PROCESO",
        RNMCMeasure.dias >= MIN_DIAS
    ).order_by(desc(RNMCMeasure.dias)).limit(50).all()

    for item in backlog_items:
        severity = "MEDIUM"
        if item.dias >= 60 or (item.valor_neto or 0) >= HIGH_VALUE_THRESHOLD:
            severity = "HIGH"
        elif item.dias < 45:
            severity = "LOW"

        exp = str(item.expediente)
        masked_exp = "***" + exp[-4:] if len(exp) > 4 else exp
        
        # Objeto base para scoring
        temp_alert = IntelligenceAlert(
            source="RNMC",
            alert_type="RNMC_BACKLOG",
            metrics={
                "dias": item.dias,
                "valor_neto": float(item.valor_neto or 0),
                "estado": item.estado
            }
        )
        score_res = compute_action_score(temp_alert)

        alert_data = {
            "source": "RNMC",
            "alert_type": "RNMC_BACKLOG",
            "severity": severity,
            "title": f"RNMC: Rezago EN PROCESO ({item.dias} días) — {item.medida[:30]}",
            "body_md": f"Medida en estado **EN PROCESO** por más de {MIN_DIAS} días. Localidad: {item.localidad}. Valor neto: ${item.valor_neto:,.0f}. Expediente: {masked_exp}.",
            "entity_ref": {"source_id": item.source_id, "event_fingerprint": item.event_fingerprint},
            "metrics": {
                "dias": item.dias,
                "valor_neto": float(item.valor_neto or 0),
                "valor_pagado": float(item.valor_pagado or 0),
                "localidad": item.localidad,
                "medida": item.medida,
                "fecha_actuacion": item.fecha_actuacion.strftime("%Y-%m-%d"),
                "estado": item.estado
            },
            "dedupe_key": f"RNMC_BACKLOG|{item.source_id}|{item.event_fingerprint}|{bucket}",
            "status": "OPEN",
            "updated_at": now,
            **score_res
        }
        alerts_to_upsert.append(alert_data)

    # --- 2. Ratificadas sin pago ---
    ratificadas_sin_pago = db.query(RNMCMeasure).filter(
        RNMCMeasure.estado == "RATIFICADA",
        or_(RNMCMeasure.valor_pagado == 0, RNMCMeasure.valor_pagado == None),
        RNMCMeasure.dias >= MIN_DIAS
    ).order_by(desc(RNMCMeasure.valor_neto)).limit(50).all()

    for item in ratificadas_sin_pago:
        severity = "HIGH" if (item.valor_neto or 0) >= HIGH_VALUE_THRESHOLD else "MEDIUM"
        
        exp = str(item.expediente)
        masked_exp = "***" + exp[-4:] if len(exp) > 4 else exp

        temp_alert = IntelligenceAlert(
            source="RNMC",
            alert_type="RNMC_RATIFICADA_SIN_PAGO",
            metrics={
                "dias": item.dias,
                "valor_neto": float(item.valor_neto or 0),
                "estado": item.estado
            }
        )
        score_res = compute_action_score(temp_alert)

        alert_data = {
            "source": "RNMC",
            "alert_type": "RNMC_RATIFICADA_SIN_PAGO",
            "severity": severity,
            "title": f"RNMC: Ratificada sin pago — {item.medida[:30]}",
            "body_md": f"Medida **RATIFICADA** sin registro de pago. Valor a recaudar: ${item.valor_neto:,.0f}. Localidad: {item.localidad}. Expediente: {masked_exp}.",
            "entity_ref": {"source_id": item.source_id, "event_fingerprint": item.event_fingerprint},
            "metrics": {
                "dias": item.dias,
                "valor_neto": float(item.valor_neto or 0),
                "valor_pagado": float(item.valor_pagado or 0),
                "localidad": item.localidad,
                "medida": item.medida,
                "fecha_actuacion": item.fecha_actuacion.strftime("%Y-%m-%d"),
                "estado": item.estado
            },
            "dedupe_key": f"RNMC_RATIFICADA_SIN_PAGO|{item.source_id}|{item.event_fingerprint}|{bucket}",
            "status": "OPEN",
            "updated_at": now,
            **score_res
        }
        alerts_to_upsert.append(alert_data)

    # --- 3. Fallos de Geocodificación (NUEVO) ---
    from db.models_inspecciones import InspeccionExpediente
    from sqlalchemy import text
    non_geocoded = db.query(InspeccionExpediente).filter(
        text("geom_punto IS NULL"),
        InspeccionExpediente.created_at <= now - timedelta(hours=48)
    ).limit(50).all()

    for item in non_geocoded:
        alert_data = {
            "source": "RNMC",
            "alert_type": "RNMC_GEO_MISSING",
            "severity": "LOW",
            "title": f"MIP: Expediente sin GPS (>48h) — {item.numero_expediente}",
            "body_md": f"El expediente **{item.numero_expediente}** en **{item.localidad}** no ha sido geocodificado automáticamente después de 48 horas. Verifique la ortografía de la localidad en el archivo fuente.",
            "entity_ref": {"expediente_id": item.id, "numero": item.numero_expediente},
            "metrics": {
                "expediente": item.numero_expediente,
                "localidad": item.localidad,
                "created_at": item.created_at.strftime("%Y-%m-%d %H:%M")
            },
            "dedupe_key": f"RNMC_GEO_MISSING|{item.id}|{bucket}",
            "status": "OPEN",
            "updated_at": now,
            "action_score": 30.0,
            "priority_tier": "P3",
            "recommended_action": "Revisar catálogo de geocodificación para la localidad '" + item.localidad + "'.",
            "rationale_md": "Detección de inconsistencia geográfica persistente.",
            "scored_at": now
        }
        alerts_to_upsert.append(alert_data)

    # --- UPSERT ---
    if alerts_to_upsert:
        for alert in alerts_to_upsert:
            stmt = insert(IntelligenceAlert).values(alert)
            update_dict = {
                "metrics": alert["metrics"],
                "body_md": alert["body_md"],
                "severity": alert["severity"],
                "updated_at": alert["updated_at"],
                "action_score": alert["action_score"],
                "priority_tier": alert["priority_tier"],
                "recommended_action": alert["recommended_action"],
                "rationale_md": alert["rationale_md"],
                "scored_at": alert["scored_at"]
            }
            stmt = stmt.on_conflict_do_update(
                index_elements=['dedupe_key'],
                set_=update_dict,
                where=(IntelligenceAlert.status == 'OPEN')
            )
            db.execute(stmt)
        db.commit()

    return {"status": "success", "count": len(alerts_to_upsert)}
