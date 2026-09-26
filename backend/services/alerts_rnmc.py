import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from sqlalchemy.dialects.postgresql import insert

from db.models_alerts import IntelligenceAlert
import os

logger = logging.getLogger("alerts_rnmc")

from services.alerts_prioritizer import compute_action_score


BACKLOG_STATES = ("EN PROCESO", "PENDIENTE")
RATIFIED_STATES = ("RATIFICADA", "MEDIDA RATIFICADA")


def mip_measures(db: Session, states, min_days: int, today) -> list:
    """Medidas de Inspecciones MIP en ciertos estados, con días desde su inicio (o su primera actuación).

    Ordenadas de la más antigua a la más reciente. El expediente sale enmascarado.
    """
    from sqlalchemy import text as sql_text

    rows = db.execute(sql_text("""
        SELECT m.id, m.nombre_medida, m.estado_actual, e.numero_expediente, e.localidad,
               COALESCE(m.fecha_inicio,
                        (SELECT MIN(a.fecha_actuacion)::date FROM inspeccion_actuaciones a WHERE a.medida_id = m.id)) AS inicio,
               COALESCE(f.valor_neto, 0) AS valor_neto, COALESCE(f.valor_pagado, 0) AS valor_pagado
        FROM inspeccion_medidas m
        JOIN inspeccion_expedientes e ON e.id = m.expediente_id
        LEFT JOIN inspeccion_finanzas f ON f.medida_id = m.id
        WHERE m.estado_actual = ANY(:states)
    """), {"states": list(states)}).fetchall()
    items = []
    for row in rows:
        if row.inicio is None or row.inicio > today:
            continue
        dias = (today - row.inicio).days
        if dias < min_days:
            continue
        expediente = str(row.numero_expediente or "")
        items.append({
            "id": str(row.id), "medida": row.nombre_medida or "", "estado": row.estado_actual or "",
            "expediente_mask": "***" + expediente[-4:] if len(expediente) > 4 else expediente,
            "localidad": row.localidad, "inicio": row.inicio.isoformat(), "dias": dias,
            "valor_neto": float(row.valor_neto or 0), "valor_pagado": float(row.valor_pagado or 0),
        })
    items.sort(key=lambda item: -item["dias"])
    return items

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

    # --- 1 y 2. Medidas de Inspecciones MIP ---
    # Fuente única de comparendos: las tablas de Inspecciones MIP (la antigua rnmc_measures dejó de cargarse).
    for item in mip_measures(db, BACKLOG_STATES, MIN_DIAS, now.date())[:50]:
        severity = "MEDIUM"
        if item["dias"] >= 60 or item["valor_neto"] >= HIGH_VALUE_THRESHOLD:
            severity = "HIGH"
        elif item["dias"] < 45:
            severity = "LOW"
        temp_alert = IntelligenceAlert(source="RNMC", alert_type="RNMC_BACKLOG",
                                       metrics={"dias": item["dias"], "valor_neto": item["valor_neto"], "estado": item["estado"]})
        alerts_to_upsert.append({
            "source": "RNMC",
            "alert_type": "RNMC_BACKLOG",
            "severity": severity,
            "title": f"RNMC: medida {item['estado'].lower()} hace {item['dias']} días — {item['medida'][:30]}",
            "body_md": (f"Medida en estado **{item['estado']}** desde hace {item['dias']} días (desde {item['inicio']}). "
                        f"Localidad: {item['localidad'] or 'sin dato'}. Expediente: {item['expediente_mask']}."),
            "entity_ref": {"medida_id": item["id"], "expediente": item["expediente_mask"]},
            "metrics": {"dias": item["dias"], "valor_neto": item["valor_neto"], "valor_pagado": item["valor_pagado"],
                        "localidad": item["localidad"], "medida": item["medida"], "fecha_inicio": item["inicio"],
                        "estado": item["estado"]},
            "dedupe_key": f"RNMC_BACKLOG|MIP|{item['id']}|{bucket}",
            "status": "OPEN",
            "updated_at": now,
            **compute_action_score(temp_alert),
        })

    for item in [row for row in mip_measures(db, RATIFIED_STATES, MIN_DIAS, now.date()) if not row["valor_pagado"]][:50]:
        severity = "HIGH" if item["valor_neto"] >= HIGH_VALUE_THRESHOLD else "MEDIUM"
        temp_alert = IntelligenceAlert(source="RNMC", alert_type="RNMC_RATIFICADA_SIN_PAGO",
                                       metrics={"dias": item["dias"], "valor_neto": item["valor_neto"], "estado": item["estado"]})
        alerts_to_upsert.append({
            "source": "RNMC",
            "alert_type": "RNMC_RATIFICADA_SIN_PAGO",
            "severity": severity,
            "title": f"RNMC: ratificada sin pago — {item['medida'][:30]}",
            "body_md": (f"Medida **RATIFICADA** sin pago registrado. Valor a recaudar: ${item['valor_neto']:,.0f}. "
                        f"Localidad: {item['localidad'] or 'sin dato'}. Expediente: {item['expediente_mask']}."),
            "entity_ref": {"medida_id": item["id"], "expediente": item["expediente_mask"]},
            "metrics": {"dias": item["dias"], "valor_neto": item["valor_neto"], "valor_pagado": item["valor_pagado"],
                        "localidad": item["localidad"], "medida": item["medida"], "fecha_inicio": item["inicio"],
                        "estado": item["estado"]},
            "dedupe_key": f"RNMC_RATIFICADA_SIN_PAGO|MIP|{item['id']}|{bucket}",
            "status": "OPEN",
            "updated_at": now,
            **compute_action_score(temp_alert),
        })

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
            "entity_ref": {"expediente_id": str(item.id), "numero": item.numero_expediente},
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
