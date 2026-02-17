from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.models import get_db, Event, EventType
from sqlalchemy import func
import os
import httpx
from typing import Optional
from api.auth import analyst_or_admin

router = APIRouter()

# Configuración de Modelos
GEMINI_MODEL = "gemini-2.0-flash"
MISTRAL_MODEL = "open-mistral-7b"

# Configuración desde .env
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
AI_PROVIDER = os.getenv("AI_PROVIDER", "GEMINI").upper()

print(f"SISC Jamundí AI: Iniciando con Proveedor: {AI_PROVIDER}")

# Cache simple en memoria para evitar Rate Limits
ia_cache = {
    "insight": None,
    "timestamp": 0,
    "last_total": 0,
    "provider": None
}

async def call_gemini(contexto):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": contexto}]}]}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        return result['candidates'][0]['content']['parts'][0]['text']

async def call_mistral(contexto):
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MISTRAL_MODEL,
        "messages": [{"role": "user", "content": contexto}],
        "max_tokens": 150
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']

@router.get("/insights", dependencies=[Depends(analyst_or_admin)])
async def get_ai_insights(db: Session = Depends(get_db)):
    """
    Genera un análisis narrativo basado en los datos actuales usando el proveedor configurado.
    """
    # Validar llaves según proveedor
    if AI_PROVIDER == "GEMINI" and not GEMINI_API_KEY:
        return {"insight": "Falta GEMINI_API_KEY", "status": "error"}
    if AI_PROVIDER == "MISTRAL" and not MISTRAL_API_KEY:
        return {"insight": "Falta MISTRAL_API_KEY", "status": "error"}

    total = db.query(Event).count()
    
    # Cache Check
    import time
    ahora = time.time()
    if ia_cache["insight"] and (ahora - ia_cache["timestamp"] < 1800) and (ia_cache["last_total"] == total) and (ia_cache["provider"] == AI_PROVIDER):
        return {
            "insight": ia_cache["insight"],
            "status": "success",
            "provider": AI_PROVIDER,
            "cached": True
        }

    homicidios = db.query(Event).join(EventType).filter(EventType.category == "HOMICIDIO").count()
    top_barrio = db.query(Event.barrio, func.count(Event.id)).group_by(Event.barrio).order_by(func.count(Event.id).desc()).first()
    
    contexto = f"""
    Eres el analista experto del Sistema de Información para la Seguridad y Convivencia (SISC) de Jamundí. 
    Analiza estos datos actuales y da un resumen ejecutivo de un párrafo corto:
    - Total de incidentes registrados: {total}
    - Homicidios: {homicidios}
    - Barrio con mayor incidencia: {top_barrio[0] if top_barrio else 'N/A'} ({top_barrio[1] if top_barrio else 0} casos).
    IMPORTANTE: Responde en español, tono profesional. Máximo 60 palabras. 
    USA SIEMPRE el nombre 'SISC Jamundí' y NUNCA uses 'Observatorio del Delito'.
    NO uses asteriscos ni formato Markdown, solo texto plano.
    """

    try:
        if AI_PROVIDER == "MISTRAL":
            insight_text = await call_mistral(contexto)
        else:
            insight_text = await call_gemini(contexto)
        
        # Update Cache
        ia_cache["insight"] = insight_text
        ia_cache["timestamp"] = ahora
        ia_cache["last_total"] = total
        ia_cache["provider"] = AI_PROVIDER
        
        return {
            "insight": insight_text,
            "status": "success",
            "provider": AI_PROVIDER,
            "cached": False
        }
    except Exception as e:
        print(f"Error con IA ({AI_PROVIDER}): {e}")
        return {
            "insight": f"El analista del SISC ({AI_PROVIDER}) está saturado. Reintentando en breve...",
            "status": "error",
            "detail": str(e)
        }

@router.get("/alertas", dependencies=[Depends(analyst_or_admin)])
async def get_ai_alerts(db: Session = Depends(get_db)):
    """
    Sistema de Alertas Tempranas: Detecta incrementos anómalos en delitos.
    """
    # 1. Definir periodos (Últimos 7 días vs 7 días anteriores)
    from datetime import timedelta, datetime
    hoy = datetime.now().date()
    hace_7 = hoy - timedelta(days=7)
    hace_14 = hoy - timedelta(days=14)

    # 2. Conteo periodo actual
    actual_stats = db.query(
        EventType.category,
        func.count(Event.id).label('total')
    ).join(Event).filter(Event.occurrence_date >= hace_7).group_by(EventType.category).all()

    # 3. Conteo periodo anterior
    anterior_stats = db.query(
        EventType.category,
        func.count(Event.id).label('total')
    ).join(Event).filter(Event.occurrence_date >= hace_14, Event.occurrence_date < hace_7).group_by(EventType.category).all()

    anterior_dict = {s.category: s.total for s in anterior_stats}
    
    alertas = []
    for s in actual_stats:
        prev = anterior_dict.get(s.category, 0)
        incremento = ((s.total - prev) / prev * 100) if prev > 0 else 100 if s.total > 0 else 0
        
        if incremento >= 20: # Umbral del 20%
            alertas.append({
                "categoria": s.category,
                "nivel": "CRÍTICO" if incremento > 50 else "ADVERTENCIA",
                "mensaje": f"Incremento del {round(incremento)}% en {s.category} detectado en la última semana.",
                "actual": s.total,
                "anterior": prev
            })

    return {
        "alertas": alertas,
        "count": len(alertas),
        "timestamp": datetime.now().isoformat()
    }
@router.post("/chat_ciudadano")
async def citizen_chat(data: dict, db: Session = Depends(get_db)):
    """
    Chatbot público para ciudadanos: Proporciona información sobre rutas y convivencia.
    Ahora incluye contexto de datos reales para responder preguntas estadísticas básicas.
    """
    user_message = data.get("message", "")
    if not user_message:
        return {"response": "Hola, ¿en qué puedo ayudarte?"}

    # Obtener algunos datos estadísticos básicos (Públicos)
    total_incidentes = db.query(Event).count()
    homicidios = db.query(Event).join(EventType).filter(func.upper(EventType.category) == "HOMICIDIO").count()
    
    # Tendencia por año
    tendencia_anual = db.query(
        func.extract('year', Event.occurrence_date).label('year'),
        func.count(Event.id)
    ).group_by('year').all()
    stats_anuales = ", ".join([f"{int(y)}: {c} casos" for y, c in tendencia_anual])

    # Detalle mensual de HOMICIDIOS (para preguntas específicas de mes/año)
    meses_hom = db.query(
        func.extract('year', Event.occurrence_date).label('year'),
        func.extract('month', Event.occurrence_date).label('month'),
        func.count(Event.id)
    ).join(EventType).filter(func.upper(EventType.category) == "HOMICIDIO").group_by('year', 'month').order_by('year', 'month').all()
    
    # Formatear meses para el prompt: "Ene 2024: 5 casos, Feb 2024: 3 casos..."
    nombres_meses = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    stats_mensuales = ", ".join([f"{nombres_meses[int(m)]} {int(y)}: {c} casos" for y, m, c in meses_hom])

    contexto = f"""
    Eres el Asistente Virtual del SISC Jamundí (Sistema de Información para la Seguridad y Convivencia).
    Tu objetivo es guiar a los ciudadanos y responder dudas sobre seguridad con DATOS REALES.

    DATOS ACTUALES DEL SISTEMA (USA ESTO PARA RESPONDER):
    - Total histórico de incidentes en plataforma: {total_incidentes}
    - Total de homicidios registrados: {homicidios}
    - Resumen por años: {stats_anuales}
    - Detalle mensual de homicidios: {stats_mensuales}
    - Población de Jamundí: 150,000 habitantes.

    REGLAS DE RESPUESTA:
    1. Sé amable, empático y profesional.
    2. SIEMPRE indica llamar al 123 ante emergencias.
    3. PUEDES compartir las cifras estadísticas mencionadas arriba.
    4. IMPORTANTE: Si el ciudadano pregunta por un mes o año que NO aparece en la lista anterior, responde que en ese periodo específico se registraron 0 casos en el sistema. NO digas que no tienes la información; usa el 0 como referente.
    5. NO inventes cifras que no estén en la lista ni menciones nombres de víctimas.
    6. Tus respuestas deben ser breves (máximo 120 palabras).
    
    El ciudadano te pregunta: "{user_message}"
    """

    try:
        if AI_PROVIDER == "MISTRAL":
            response_text = await call_mistral(contexto)
        else:
            response_text = await call_gemini(contexto)
        
        return {"response": response_text}
    except Exception as e:
        print(f"Error en Chat Ciudadano ({AI_PROVIDER}): {e}")
        return {"response": "Lo siento, tengo dificultades técnicas. Por favor, consulta los tableros de datos en el portal o llama al 123 en caso de emergencia."}
