import os
from datetime import datetime
from db.models_alerts import IntelligenceAlert


def clamp(value, min_val, max_val):
    return max(min_val, min(max_val, value))


def get_scoring_config() -> dict:
    """
    Configuración centralizada del scoring RNMC.

    Se expone para:
    - Uso consistente en compute_action_score
    - Exportación (sheet Config / snapshots)
    - Transparencia en UI
    """
    return {
        "MAX_DIAS": int(os.getenv("RNMC_SCORE_MAX_DIAS", 90)),
        "MAX_VALOR": float(os.getenv("RNMC_SCORE_MAX_VALOR", 2000000)),
        "W_AGE": float(os.getenv("RNMC_W_AGE", 0.35)),
        "W_VALUE": float(os.getenv("RNMC_W_VALUE", 0.35)),
        "W_STATE": float(os.getenv("RNMC_W_STATE", 0.20)),
        "W_ZONE": float(os.getenv("RNMC_W_ZONE", 0.10)),
        "P1_THRESHOLD": float(os.getenv("P1_THRESHOLD", 75)),
        "P2_THRESHOLD": float(os.getenv("P2_THRESHOLD", 45)),
    }


def compute_action_score(alert: IntelligenceAlert) -> dict:
    """
    Calcula el Action Score (0-100) y Priority Tier (P1-P3) de forma determinista.
    """
    config = get_scoring_config()

    metrics = alert.metrics or {}
    dias = int(metrics.get("dias", 0))
    valor_neto = float(metrics.get("valor_neto", 0))
    
    # Configuración de pesos y umbrales
    MAX_DIAS = config["MAX_DIAS"]
    MAX_VALOR = config["MAX_VALOR"]
    W_AGE = config["W_AGE"]
    W_VALUE = config["W_VALUE"]
    W_STATE = config["W_STATE"]
    W_ZONE = config["W_ZONE"]
    P1_THRESHOLD = config["P1_THRESHOLD"]
    P2_THRESHOLD = config["P2_THRESHOLD"]
    
    # 1. Age Score (0..1)
    age_score = clamp(dias / MAX_DIAS, 0, 1)
    
    # 2. Value Score (0..1)
    value_score = clamp(valor_neto / MAX_VALOR, 0, 1)
    
    # 3. State Score (0..1)
    state_score = 0.4 # Neutral
    if alert.alert_type == "RNMC_RATIFICADA_SIN_PAGO":
        state_score = 1.0
    elif metrics.get("estado") == "EN PROCESO":
        state_score = 0.7
        
    # 4. Zone Score (opcional). Si no viene, neutral 0.5.
    raw_zone = metrics.get("zone_score", 0.5)
    try:
        zone_score = float(raw_zone)
    except (TypeError, ValueError):
        zone_score = 0.5
    zone_score = clamp(zone_score, 0, 1)
    
    final_score = round(100 * (
        W_AGE * age_score + 
        W_VALUE * value_score + 
        W_STATE * state_score + 
        W_ZONE * zone_score
    ), 2)
    
    # Tiering
    tier = "P3"
    if final_score >= P1_THRESHOLD:
        tier = "P1"
    elif final_score >= P2_THRESHOLD:
        tier = "P2"
        
    # Recomendación determinista
    rec = "Monitorear y reevaluar en el próximo ciclo."
    if tier == "P1":
        rec = "Priorizar gestión inmediata y activar ruta de cobro coactivo."
    elif tier == "P2":
        rec = "Programar gestión y seguimiento dentro del ciclo semanal."
        
    # Rationale MD
    rationale = f"**Análisis de Prioridad:**\n"
    rationale += f"- **Antigüedad:** {dias} días ({round(age_score*100)}% del límite operativo)\n"
    rationale += f"- **Impacto Financiero:** ${valor_neto:,.0f} ({round(value_score*100)}% del techo de scoring)\n"
    rationale += f"- **Estado Crítico:** {'Sí' if state_score >= 0.7 else 'Medio'}\n"
    rationale += f"\nResultado: **Tier {tier}** con un score de {final_score}/100."
    
    return {
        "action_score": final_score,
        "priority_tier": tier,
        "recommended_action": rec,
        "rationale_md": rationale,
        "scored_at": datetime.now()
    }
