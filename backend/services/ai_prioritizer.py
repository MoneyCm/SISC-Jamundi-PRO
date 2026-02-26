import logging
from api.ia import call_gemini, call_mistral, AI_PROVIDER
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
    
    try:
        if AI_PROVIDER == "MISTRAL":
            rationale = await call_mistral(contexto)
        else:
            rationale = await call_gemini(contexto)
            
        return {
            "ai_rationale_md": rationale,
            "ai_provider": AI_PROVIDER,
            "ai_request_id": "gen_" + alert.id.hex[:8]
        }
    except Exception as e:
        logger.error(f"Error generando AI Rationale: {e}")
        return {
            "ai_rationale_md": None,
            "ai_provider": AI_PROVIDER,
            "ai_request_id": "error"
        }
