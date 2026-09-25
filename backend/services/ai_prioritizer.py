import logging
from api.ia import redactar_verificado, AI_PROVIDER
from db.models_alerts import IntelligenceAlert

logger = logging.getLogger("ai_prioritizer")

async def build_ai_rationale(alert: IntelligenceAlert, scoring_output: dict) -> dict:
    """
    Genera una explicación narrativa usando IA sobre por qué se priorizó una alerta.
    Solo usa datos agregados y el score calculado. No incluye PII.
    """
    metrics = alert.metrics or {}
    
    contexto = f"""
    Como analista experto del SISC Jamundí, explica brevemente por qué esta alerta de RNMC ha sido clasificada con prioridad {scoring_output['priority_tier']}.
    
    DATOS DE LA ALERTA:
    - Título: {alert.title}
    - Antigüedad: {metrics.get('dias')} días
    - Valor Neto: ${metrics.get('valor_neto', 0):,.0f}
    - Estado Actual: {metrics.get('estado')}
    - Localidad: {metrics.get('localidad')}
    - Score Calculado: {scoring_output['action_score']}/100
    
    REGLAS:
    1. Responde en español, tono profesional y directo.
    2. Máximo 50 palabras.
    3. No inventes datos adicionales.
    4. Enfócate en el impacto operativo y financiero.
    5. No uses asteriscos excesivos. Solo texto con negritas para enfatizar.
    """
    
    # Solo los datos de la alerta (no las reglas) cuentan como fuente de cifras.
    datos = contexto.split("REGLAS:")[0]
    resultado = await redactar_verificado(contexto, datos, respaldo=None)
    if resultado["fallback"]:
        logger.warning(f"AI Rationale descartado: {resultado['problems']}")
        return {"ai_rationale_md": None, "ai_provider": AI_PROVIDER, "ai_request_id": "rejected"}
    return {
        "ai_rationale_md": resultado["text"],
        "ai_provider": f"{AI_PROVIDER}:{resultado['model']}",
        "ai_request_id": "gen_" + alert.id.hex[:8]
    }
