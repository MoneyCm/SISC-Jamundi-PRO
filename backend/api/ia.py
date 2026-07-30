from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.models import get_db, Event, EventType
from db.models_hechos_seguridad import HechoSeguridad, IngestionRun, SabanaSnapshotRow
from services.hechos_metrics import hechos_unicos_expr
from sqlalchemy import func
import os
import re
import httpx
from datetime import datetime, date, timedelta
from api.auth import analyst_or_admin, institutional_access

router = APIRouter()

# Configuración de Modelos
GEMINI_MODEL = "gemini-2.0-flash-lite"
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


MONTH_NAMES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}

MONTH_LOOKUP = {name: number for number, name in MONTH_NAMES.items()}
MONTH_LOOKUP.update({"setiembre": 9})


def _extract_requested_periods(message: str, default_year: int):
    normalized = (message or "").lower()
    years = []
    for raw_year in re.findall(r"\b(20\d{2})\b", normalized):
        year = int(raw_year)
        if year not in years:
            years.append(year)
    if not years:
        years = [default_year]

    months = []
    for name, number in MONTH_LOOKUP.items():
        if re.search(rf"\b{name}\b", normalized) and number not in months:
            months.append(number)
    return years, months


def _requested_conducta(message: str):
    normalized = (message or "").lower()
    if "homicid" in normalized:
        return "HOMICIDIO", "homicidios"
    if "hurto" in normalized:
        return "HURTO", "hurtos"
    if "lesion" in normalized or "lesiones" in normalized:
        return "LESIONES", "lesiones personales"
    if "violencia intrafamiliar" in normalized or re.search(r"\bvif\b", normalized):
        return "VIF", "violencia intrafamiliar"
    return None, None


def _format_monthly_direct_answer(user_message: str, monthly_summary: dict, fecha_corte_date, fecha_corte: str, fuente_corte: str):
    if not fecha_corte_date:
        return None

    requested_years, months = _extract_requested_periods(user_message, fecha_corte_date.year)
    if not months:
        return None

    conducta_key, conducta_label = _requested_conducta(user_message)
    unavailable = []
    available_lines = []
    for requested_year in requested_years:
        for month in months:
            month_label = f"{MONTH_NAMES[month].capitalize()} {requested_year}"
            if month == 12:
                requested_period_end = date(requested_year, 12, 31)
            else:
                requested_period_end = date(requested_year, month + 1, 1) - timedelta(days=1)

            if requested_period_end > fecha_corte_date:
                unavailable.append(month_label)
                continue

            info = monthly_summary.get((requested_year, month))
            if not info:
                available_lines.append(f"- **{month_label}:** no hay dato mensual desagregado suficiente en el contexto del asistente.")
                continue

            if conducta_key:
                count = int(info["conductas"].get(conducta_key, 0))
                available_lines.append(f"- **{month_label}:** {count} {conducta_label} registrados.")
                continue

            principales = sorted(info["conductas"].items(), key=lambda item: item[1], reverse=True)[:4]
            detalle = ", ".join([f"{name}: {count}" for name, count in principales])
            available_lines.append(f"- **{month_label}:** {info['total']} casos consolidados. Principales conductas: {detalle}.")

    intro = f"Con corte al **{fecha_corte}** ({fuente_corte}), el SISC registra esta informacion para los meses consultados:"
    parts = [intro]
    if available_lines:
        parts.append("\n".join(available_lines))
    if unavailable:
        parts.append(f"Aun no hay datos cargados para: **{', '.join(unavailable)}**. No se reportan como 0 casos.")
    parts.append("Para emergencias, llama al **123**.")
    return "\n\n".join(parts)


def _format_cutoff_answer(user_message: str, fecha_corte: str, fuente_corte: str):
    normalized = (user_message or "").lower()
    if not any(term in normalized for term in ["corte", "actualizado", "actualizacion", "hasta cuando", "hasta que fecha"]):
        return None
    return f"El SISC tiene datos cargados para consulta ciudadana hasta el **{fecha_corte}**. Fuente usada: **{fuente_corte}**. Para emergencias, llama al **123**."


async def call_gemini(contexto):
    url = f"https://generativelanguage.googleapis.com/v1/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": contexto}]}]}
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            print(f"Error llamando a Gemini: {e}")
            raise

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
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            print(f"Error llamando a Mistral: {e}")
            raise

@router.get("/insights", dependencies=[Depends(institutional_access)])
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
    if total == 0:
        return {
            "insight": "El sistema se encuentra a la espera de nuevos datos para generar la Perspectiva de Seguridad.",
            "status": "success",
            "provider": AI_PROVIDER
        }

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

    # Estadísticas para el INSIGHT (Año Actual 2026) - AGREGACIÓN DEDUPLICADA
    current_year = datetime.now().year

    # 1. Obtener conteos diarios de HOMICIDIOS de ambas fuentes para el año actual
    hom_mod_daily = db.query(HechoSeguridad.fecha_evento, hechos_unicos_expr()).filter(
        func.extract('year', HechoSeguridad.fecha_evento) == current_year,
        HechoSeguridad.categoria_delito == "HOMICIDIO"
    ).group_by(HechoSeguridad.fecha_evento).all()

    hom_leg_daily = db.query(Event.occurrence_date, func.count(Event.id)).join(EventType).filter(
        func.extract('year', Event.occurrence_date) == current_year,
        EventType.category == "HOMICIDIO"
    ).group_by(Event.occurrence_date).all()

    # Unificar por fecha (DEDUPLICACIÓN POR DÍA)
    daily_hom = {}
    for d, c in hom_leg_daily: daily_hom[d] = c
    # Priorizar fuente Policial (Sobrescribe si hay dato el mismo día)
    for d, c in hom_mod_daily: daily_hom[d] = c
    homicidios_2026 = sum(daily_hom.values())

    # 2. Conteo de Incidentes Totales (Aproximación por mayor fuente)
    total_legacy = db.query(Event).filter(func.extract('year', Event.occurrence_date) == current_year).count()
    total_moderno = db.query(hechos_unicos_expr()).filter(func.extract('year', HechoSeguridad.fecha_evento) == current_year).scalar() or 0
    total_real_2026 = total_moderno if total_moderno > 0 else total_legacy

    # 3. Barrios (Priorizar la base más poblada)
    if total_moderno > 0:
        top_barrio_2026 = db.query(HechoSeguridad.barrio_normalizado, hechos_unicos_expr()).filter(
            func.extract('year', HechoSeguridad.fecha_evento) == current_year
        ).group_by(HechoSeguridad.barrio_normalizado).order_by(hechos_unicos_expr().desc()).first()
    else:
        top_barrio_2026 = db.query(Event.barrio, func.count(Event.id)).filter(
            func.extract('year', Event.occurrence_date) == current_year
        ).group_by(Event.barrio).order_by(func.count(Event.id).desc()).first()

    contexto = f"""
    Eres el analista experto del Sistema de Información para la Seguridad y Convivencia (SISC) de Jamundí.
    Analiza estos datos del AÑO ACTUAL {current_year} (Cifras Consolidadas y Sin Duplicados):
    - Incidentes registrados en {current_year}: {total_real_2026}
    - Homicidios totales unificados (Policía + MinDefensa): {homicidios_2026}
    - Zona con mayor criticidad este año: {top_barrio_2026[0] if top_barrio_2026 else 'N/A'} ({top_barrio_2026[1] if top_barrio_2026 else 0} casos).

    IMPORTANTE: Has detectado un traslape de fuentes y has priorizado la información de la Policía por su actualización.
    Responde en español, tono institucional firme. Máximo 60 palabras.
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

from services.alert_engine import AlertEngine

@router.get("/alertas", dependencies=[Depends(institutional_access)])
async def get_ai_alerts(db: Session = Depends(get_db)):
    """
    Sistema de Alertas Tempranas (SAT): Detecta incrementos anómalos en delitos
    para la Secretaría de Seguridad de Jamundí.
    """
    try:
        # Usar el nuevo motor de alertas deductivo y unificado
        alertas = AlertEngine.calculate_alerts(db)

        return {
            "alertas": alertas,
            "count": len(alertas),
            "timestamp": datetime.now().isoformat(),
            "status": "active",
            "jurisdiccion": "Jamundi, Valle"
        }
    except Exception as e:
        print(f"Error en SAT: {e}")
        raise HTTPException(status_code=500, detail="Error al generar alertas del sistema.")
@router.post("/chat_ciudadano")
async def citizen_chat(data: dict, db: Session = Depends(get_db)):
    """
    Chatbot público para ciudadanos: Proporciona información sobre rutas y convivencia.
    Ahora incluye contexto de datos reales para responder preguntas estadísticas básicas.
    """
    user_message = data.get("message", "")
    if not user_message:
        return {"response": "Hola, ¿en qué puedo ayudarte?"}

    # 1. Total Incidentes (Legacy + Moderno)
    total_legacy = db.query(Event).count()
    total_moderno = db.query(hechos_unicos_expr()).scalar() or 0
    total_incidentes = total_moderno if total_moderno > 0 else total_legacy

    # 2. Homicidios Totales (DEDUPLICACIÓN DIARIA)
    hom_legacy = db.query(Event.occurrence_date, func.count(Event.id)).join(EventType).filter(EventType.category == "HOMICIDIO").group_by(Event.occurrence_date).all()
    hom_moderno = db.query(HechoSeguridad.fecha_evento, hechos_unicos_expr()).filter(HechoSeguridad.categoria_delito == "HOMICIDIO").group_by(HechoSeguridad.fecha_evento).all()

    daily_hom_total = {}
    for d, c in hom_legacy: daily_hom_total[d] = c
    for d, c in hom_moderno: daily_hom_total[d] = c
    homicidios = sum(daily_hom_total.values())

    # 3. Resumen por Año (Unificado con Deduplicación)
    anual_dict = {}
    # Simplificación: tomar el máximo entre tablas para cada año si no queremos hacer el loop diario aquí también
    # Pero para ser precisos, usamos la lógica de años existentes
    all_years = db.query(func.extract('year', Event.occurrence_date)).distinct().all()
    for (year,) in all_years:
        # Para cada año, calculamos el total del mismo modo de de-duplicación diaria
        y_int = int(year)
        d_legacy = db.query(Event.occurrence_date, func.count(Event.id)).filter(func.extract('year', Event.occurrence_date) == y_int).group_by(Event.occurrence_date).all()
        d_moderno = db.query(HechoSeguridad.fecha_evento, hechos_unicos_expr()).filter(func.extract('year', HechoSeguridad.fecha_evento) == y_int).group_by(HechoSeguridad.fecha_evento).all()

        y_daily = {}
        for d, c in d_legacy: y_daily[d] = c
        for d, c in d_moderno: y_daily[d] = c
        anual_dict[y_int] = sum(y_daily.values())

    stats_anuales = ", ".join([f"{y}: {c} casos" for y, c in sorted(anual_dict.items())])

    # 4. Detalle por Año y Delitos Clave (DEDUPLICADO POR DÍA)
    current_year = datetime.now().year
    years_to_track = [current_year, current_year - 1, current_year - 2]

    delitos_prioritarios = {
        'HOMICIDIO': ['HOMICIDIO', 'HOMICIDIO INTENCIONAL', 'Homicidio'],
        'HURTO': ['HURTO_PERSONAS', 'HURTO A PERSONAS', 'Hurto a personas', 'HURTO'],
        'VIF': ['VIOLENCIA INTRAFAMILIAR', 'VIF', 'Violencia intrafamiliar'],
        'LESIONES': ['LESIONES PERSONALES', 'LESIONES COMUNES', 'Lesiones', 'LESIONES']
    }

    stats_detalladas = []
    for year in years_to_track:
        year_data = []
        for name, aliases in delitos_prioritarios.items():
            # Sumar de ambas tablas con de-duplicación diaria
            d_l = db.query(Event.occurrence_date, func.count(Event.id)).join(EventType).filter(func.extract('year', Event.occurrence_date) == year, EventType.category.in_(aliases)).group_by(Event.occurrence_date).all()
            d_m = db.query(HechoSeguridad.fecha_evento, hechos_unicos_expr()).filter(func.extract('year', HechoSeguridad.fecha_evento) == year, HechoSeguridad.categoria_delito.in_(aliases)).group_by(HechoSeguridad.fecha_evento).all()

            y_d = {}
            for d, c in d_l: y_d[d] = c
            for d, c in d_m: y_d[d] = c
            count = sum(y_d.values())
            year_data.append(f"{name}: {count}")
        stats_detalladas.append(f"AÑO {year} [{', '.join(year_data)}]")
    stats_contexto_detallado = " | ".join(stats_detalladas)

    nombres_meses = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

    # Fecha real de cobertura para el chat: usa la fuente cargada mas reciente y evita declarar periodos como cero si no estan cargados.
    latest_snapshot = db.query(SabanaSnapshotRow.ingestion_id).join(
        IngestionRun, IngestionRun.id == SabanaSnapshotRow.ingestion_id
    ).filter(
        IngestionRun.fuente_codigo == "POLICIA_SEMANAL",
        IngestionRun.status == "COMPLETED",
    ).order_by(IngestionRun.fecha_fin.desc(), IngestionRun.fecha_inicio.desc()).first()

    snapshot_id = latest_snapshot[0] if latest_snapshot else None
    max_snapshot_date = None
    if snapshot_id:
        max_snapshot_date = db.query(func.max(SabanaSnapshotRow.fecha_evento)).filter(
            SabanaSnapshotRow.ingestion_id == snapshot_id
        ).scalar()

    max_modern_date = db.query(func.max(HechoSeguridad.fecha_evento)).filter(
        HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL"
    ).scalar()
    max_legacy_date = db.query(func.max(Event.occurrence_date)).scalar()

    use_modern_source = bool(max_modern_date and (not max_snapshot_date or max_modern_date > max_snapshot_date))
    fecha_corte_date = max_modern_date if use_modern_source else (max_snapshot_date or max_legacy_date)
    fecha_corte = fecha_corte_date.isoformat() if fecha_corte_date else "sin datos cargados"
    fuente_corte = "hechos de sabana cargada" if use_modern_source else ("sabana publica consolidada" if max_snapshot_date else "tabla interna historica")

    requested_years_for_context, requested_months_for_context = _extract_requested_periods(user_message, fecha_corte_date.year if fecha_corte_date else datetime.now().year)
    years_for_monthly_context = requested_years_for_context if requested_months_for_context else ([fecha_corte_date.year] if fecha_corte_date else [datetime.now().year])

    monthly_rows = []
    if fecha_corte_date and use_modern_source:
        monthly_rows = db.query(
            func.extract('year', HechoSeguridad.fecha_evento).label('year'),
            func.extract('month', HechoSeguridad.fecha_evento).label('month'),
            HechoSeguridad.categoria_delito.label('conducta'),
            hechos_unicos_expr().label('total'),
        ).filter(
            HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
            func.extract('year', HechoSeguridad.fecha_evento).in_(years_for_monthly_context),
        ).group_by('year', 'month', HechoSeguridad.categoria_delito).order_by('year', 'month').all()
    elif fecha_corte_date and snapshot_id:
        monthly_rows = db.query(
            func.extract('year', SabanaSnapshotRow.fecha_evento).label('year'),
            func.extract('month', SabanaSnapshotRow.fecha_evento).label('month'),
            SabanaSnapshotRow.categoria_delito.label('conducta'),
            func.count(func.distinct(SabanaSnapshotRow.hecho_key)).label('total'),
        ).filter(
            SabanaSnapshotRow.ingestion_id == snapshot_id,
            func.extract('year', SabanaSnapshotRow.fecha_evento).in_(years_for_monthly_context),
        ).group_by('year', 'month', SabanaSnapshotRow.categoria_delito).order_by('year', 'month').all()

    monthly_summary = {}
    for year, month, conducta, total in monthly_rows:
        key = (int(year), int(month))
        monthly_summary.setdefault(key, {"total": 0, "conductas": {}})
        monthly_summary[key]["total"] += int(total or 0)
        label = conducta or "SIN CLASIFICAR"
        monthly_summary[key]["conductas"][label] = monthly_summary[key]["conductas"].get(label, 0) + int(total or 0)

    stats_mensuales = []
    for (year, month), info in sorted(monthly_summary.items()):
        principales = sorted(info["conductas"].items(), key=lambda item: item[1], reverse=True)[:4]
        detalle = ", ".join([f"{name}: {count}" for name, count in principales])
        stats_mensuales.append(f"{nombres_meses[month]} {year}: total {info['total']} casos ({detalle})")
    stats_mensuales = " | ".join(stats_mensuales) if stats_mensuales else "No hay resumen mensual consolidado disponible"

    direct_cutoff_response = _format_cutoff_answer(user_message, fecha_corte, fuente_corte)
    if direct_cutoff_response:
        return {"response": direct_cutoff_response}

    direct_monthly_response = _format_monthly_direct_answer(user_message, monthly_summary, fecha_corte_date, fecha_corte, fuente_corte)
    if direct_monthly_response:
        return {"response": direct_monthly_response}

    contexto = f"""
    Eres el Asistente Virtual del SISC Jamundí (Sistema de Información para la Seguridad y Convivencia).
    Tu objetivo es guiar a los ciudadanos y responder dudas sobre seguridad con DATOS REALES.

    DATOS ACTUALES DEL SISTEMA (USA ESTO PARA RESPONDER):
    - Total histórico de incidentes en plataforma: {total_incidentes}
    - Total de homicidios registrados: {homicidios}
    - Casos totales por año: {stats_anuales}
    - DETALLE POR CATEGORÍA Y AÑO: {stats_contexto_detallado}
    - Resumen mensual consolidado de la fuente mas reciente: {stats_mensuales}
    - Fecha de corte de los datos cargados para consulta ciudadana: {fecha_corte}
    - Fuente usada para la fecha de corte: {fuente_corte}
    - Poblacion de Jamundi: 180,942 habitantes (Proyeccion 2026).

    REGLAS DE RESPUESTA:
    1. Se amable, empatico y profesional.
    2. SIEMPRE indica llamar al 123 ante emergencias.
    3. PUEDES compartir solo las cifras estadisticas mencionadas arriba.
    4. IMPORTANTE: Si el ciudadano pregunta por un mes, anio o periodo posterior a la fecha de corte de consulta ciudadana, responde que el SISC aun no tiene datos cargados para ese periodo. NO lo reportes como 0 casos.
    5. Si un periodo esta dentro de la cobertura y aparece en el resumen mensual consolidado, responde con esos totales y conductas principales. Si esta dentro de la cobertura pero no aparece en el resumen, explica que no hay dato desagregado suficiente en el contexto del asistente. NO inventes cifras.
    6. NO menciones nombres de victimas, direcciones exactas, telefonos, placas ni datos personales.
    7. NO inventes enlaces, dominios, correos, telefonos ni canales de atencion. Para emergencias menciona solo la linea 123.
    8. Tus respuestas deben ser breves (maximo 120 palabras) y faciles de leer.

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
