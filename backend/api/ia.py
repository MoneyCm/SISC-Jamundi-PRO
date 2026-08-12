from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.models import get_db, Event, EventType
from db.models_hechos_seguridad import HechoSeguridad, IngestionRun, SabanaSnapshotRow
from db.models_institutional import InstitutionalDataBatch, InstitutionalIndicator
from services.institutional_agent_service import InstitutionalAgentService
from services.hechos_metrics import hechos_unicos_expr
from sqlalchemy import Integer, cast, func
from pydantic import BaseModel, Field
from typing import List
import os
import re
import httpx
from datetime import datetime, date, timedelta
from api.auth import analyst_or_admin, institutional_access

router = APIRouter()

# ConfiguraciÃ³n de Modelos
GEMINI_MODEL = "gemini-2.0-flash-lite"
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-2603")

# ConfiguraciÃ³n desde .env
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
AI_PROVIDER = os.getenv("AI_PROVIDER", "GEMINI").upper()

print(f"SISC JamundÃ­ AI: Iniciando con Proveedor: {AI_PROVIDER}")

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


HOMICIDE_ALIASES = ["HOMICIDIO", "Homicidio", "HOMICIDIO INTENCIONAL", "HOMICIDIO DOLOSO"]
NON_PUBLIC_TERRITORY_VALUES = {
    "BARRIO PENDIENTE POR ASIGNAR",
    "PENDIENTE POR ASIGNAR",
    "SIN ASIGNAR",
    "SIN BARRIO",
    "SIN COMUNA",
    "SIN ESPECIFICAR",
    "SIN LOCALIDAD",
    "NO APLICA",
    "NO APLICA LOCALIDAD",
    "NO APLICA LOCALIDAD - COMUNA",
    "NO DEFINIDO",
    "NO REPORTA",
    "NO REGISTRA",
    "N/A",
}


class CitizenChatMessage(BaseModel):
    sender: str = Field(default="", max_length=20)
    text: str = Field(default="", max_length=1000)


class CitizenChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: List[CitizenChatMessage] = Field(default_factory=list, max_length=8)


NON_PUBLIC_TERRITORY_PATTERNS = (
    "PENDIENTE",
    "POR ASIGNAR",
    "NO APLICA",
    "NO DEFINIDO",
    "SIN LOCALIDAD",
    "SIN COMUNA",
)


def _is_public_territory_name(value):
    if not value:
        return False
    clean = " ".join(str(value).strip().upper().split())
    if not clean or clean in NON_PUBLIC_TERRITORY_VALUES:
        return False
    return not any(pattern in clean for pattern in NON_PUBLIC_TERRITORY_PATTERNS)


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


def _wants_monthly_breakdown(message: str):
    normalized = (message or "").lower()
    return any(term in normalized for term in [" por mes", "meses", "mensual", "mes a mes", "cada mes"])


def _wants_recent_years(message: str):
    normalized = (message or "").lower()
    return "ultimo" in normalized or "ultim" in normalized or "reciente" in normalized


def _requested_period_is_after_cutoff(year: int, month: int, cutoff):
    if not cutoff:
        return False
    return date(year, month, 1) > cutoff


def _conversation_text(data: dict):
    history = data.get("history") or []
    if not isinstance(history, list):
        return data.get("message", "") or ""
    parts = []
    for item in history[-6:]:
        if not isinstance(item, dict):
            continue
        sender = item.get("sender") or item.get("role") or ""
        text = item.get("text") or item.get("content") or ""
        if text:
            parts.append(f"{sender}: {text}")
    current = data.get("message", "") or ""
    if current:
        parts.append(f"user: {current}")
    return "\n".join(parts)


def _extract_years_for_followup(message: str, conversation_text: str, default_year: int):
    years = []
    for source in [message or "", conversation_text or ""]:
        for raw_year in re.findall(r"\b(20\d{2})\b", source.lower()):
            year = int(raw_year)
            if year not in years:
                years.append(year)
        if years:
            break
    return years or [default_year]


def _format_year_monthly_breakdown_answer(user_message: str, conversation_text: str, monthly_summary: dict, fecha_corte_date, fecha_corte: str, fuente_corte: str):
    if not fecha_corte_date or not _wants_monthly_breakdown(user_message):
        return None

    requested_years, explicit_months = _extract_requested_periods(user_message, fecha_corte_date.year)
    if _wants_recent_years(user_message) and not re.search(r"\b20\d{2}\b", user_message or ""):
        years_in_context = sorted({year for year, _month in monthly_summary.keys()}, reverse=True)
        requested_years = sorted(years_in_context[:3]) if years_in_context else requested_years
    elif not re.search(r"\b20\d{2}\b", user_message or "") and not explicit_months:
        requested_years = _extract_years_for_followup(user_message, conversation_text, fecha_corte_date.year)

    if explicit_months:
        return None

    conducta_key, conducta_label = _requested_conducta(user_message)
    parts = [f"Con corte al **{fecha_corte}** ({fuente_corte}), el SISC registra este desglose mensual:"]

    for year in requested_years:
        lines = []
        annual_total = 0
        months_with_data = []
        for month in range(1, 13):
            period_start = date(year, month, 1)
            if period_start > fecha_corte_date:
                continue
            info = monthly_summary.get((year, month))
            if not info:
                continue
            months_with_data.append(month)
            if conducta_key:
                raw_count = int(info["conductas"].get(conducta_key, 0))
                record_count = int(info["conductas"].get(f"{conducta_key}_REGISTROS", raw_count))
                count = max(raw_count, record_count) if conducta_key == "HOMICIDIO" else raw_count
                unique_count = min(raw_count, record_count) if conducta_key == "HOMICIDIO" else raw_count
                annual_total += count
                extra = f" ({unique_count} hechos unicos)" if conducta_key == "HOMICIDIO" and unique_count and unique_count != count else ""
                lines.append(f"- **{MONTH_NAMES[month].capitalize()}:** {count} {conducta_label}{extra}.")
            else:
                annual_total += int(info["total"] or 0)
                lines.append(f"- **{MONTH_NAMES[month].capitalize()}:** {int(info['total'] or 0)} casos.")

        label = conducta_label if conducta_key else "delitos/casos consolidados"
        if lines:
            available_range = f"{MONTH_NAMES[min(months_with_data)]}-{MONTH_NAMES[max(months_with_data)]}" if months_with_data else "meses disponibles"
            parts.append(f"**{year}: {annual_total} {label} en los meses disponibles ({available_range}).**")
            parts.append("\n".join(lines))
            if year < fecha_corte_date.year and max(months_with_data) < 12:
                missing = ", ".join(MONTH_NAMES[m] for m in range(max(months_with_data) + 1, 13))
                parts.append(f"En esta entrega publica no hay datos mensuales cargados para {missing} de {year}.")
        else:
            parts.append(f"**{year}:** no hay dato mensual desagregado suficiente en el contexto del asistente.")

    parts.append("Para emergencias, llama al **123**.")
    return "\n\n".join(parts)


def _format_monthly_direct_answer(user_message: str, monthly_summary: dict, fecha_corte_date, fecha_corte: str, fuente_corte: str, conversation_text: str = ""):
    if not fecha_corte_date:
        return None

    requested_years, months = _extract_requested_periods(user_message, fecha_corte_date.year)
    if not months:
        return None

    has_explicit_year = bool(re.search(r"\b20\d{2}\b", user_message or ""))
    if not has_explicit_year:
        years_for_months = sorted({year for year, month in monthly_summary.keys() if month in months})
        if years_for_months:
            requested_years = years_for_months

    conducta_key, conducta_label = _requested_conducta(user_message)
    unavailable = []
    available_lines = []
    for requested_year in requested_years:
        for month in months:
            month_label = f"{MONTH_NAMES[month].capitalize()} {requested_year}"
            if _requested_period_is_after_cutoff(requested_year, month, fecha_corte_date):
                unavailable.append(month_label)
                continue

            info = monthly_summary.get((requested_year, month))
            if not info:
                available_lines.append(f"- **{month_label}:** no hay dato mensual desagregado suficiente en el contexto del asistente.")
                continue

            if conducta_key:
                raw_count = int(info["conductas"].get(conducta_key, 0))
                record_count = int(info["conductas"].get(f"{conducta_key}_REGISTROS", raw_count))
                count = max(raw_count, record_count) if conducta_key == "HOMICIDIO" else raw_count
                unique_count = min(raw_count, record_count) if conducta_key == "HOMICIDIO" else raw_count
                extra = f" ({unique_count} hechos unicos)" if conducta_key == "HOMICIDIO" and unique_count and unique_count != count else ""
                available_lines.append(f"- **{month_label}:** {count} {conducta_label} registrados{extra}.")
                continue

            public_conductas = {k: v for k, v in info["conductas"].items() if not k.endswith("_REGISTROS")}
            principales = sorted(public_conductas.items(), key=lambda item: item[1], reverse=True)[:4]
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


def _wants_available_dates_answer(message: str):
    normalized = (message or "").lower()
    return any(term in normalized for term in [
        "quÃ© fechas", "que fechas", "de quÃ© fechas", "de cuÃ¡ndo fechas", "desde cuÃ¡ndo", "desde cuÃ¡ndo", "rango", "perÃ­odo disponible", "perÃ­odos disponibles", "fechas disponibles", "informaciÃ³n de quÃ©", "informaciÃ³n de quiÃ©n"
    ])


def _wants_annual_records_answer(message: str):
    normalized = (message or "").lower()
    return (
        any(term in normalized for term in ["por aÃ±o", "por aÃ±o", "por aÃ±o", "por aÃ±o", "anuales", "cada aÃ±o", "cada aÃ±o", "cada aÃ±o"])
        and any(term in normalized for term in ["registro", "registros", "delito", "delitos", "casos", "hechos"])
    )


def _format_available_dates_answer(user_message: str, min_date, max_date, fuente_corte: str, annual_summary: dict):
    if not _wants_available_dates_answer(user_message):
        return None
    if not min_date or not max_date:
        return "Aun no hay datos cargados para consulta ciudadana. Para emergencias, llama al **123**."

    years = sorted(annual_summary)
    if years:
        year_text = ", ".join(str(year) for year in years)
        annual_text = "\n".join(f"- **{year}:** {annual_summary[year]} hechos." for year in years)
    else:
        year_text = "sin resumen anual disponible"
        annual_text = "- No hay resumen anual disponible."

    return (
        f"El SISC tiene informacion para consulta ciudadana desde el **{min_date.isoformat()}** "
        f"hasta el **{max_date.isoformat()}**. Fuente: **{fuente_corte}**.\n\n"
        f"Anios disponibles en la base maestra: **{year_text}**.\n\n"
        f"{annual_text}\n\n"
        "No tengo soporte para afirmar cobertura desde 2000. Para emergencias, llama al **123**."
    )


def _format_annual_records_answer(user_message: str, min_date, max_date, fuente_corte: str, annual_summary: dict):
    if not _wants_annual_records_answer(user_message):
        return None
    if not annual_summary:
        return "Aun no hay resumen anual consolidado disponible. Para emergencias, llama al **123**."

    lines = [
        f"Con corte al **{max_date.isoformat()}** ({fuente_corte}), la base maestra registra:",
        "",
    ]
    for year in sorted(annual_summary):
        suffix = ""
        if max_date and year == max_date.year:
            suffix = f" (hasta {max_date.isoformat()})"
        lines.append(f"- **{year}:** {annual_summary[year]} hechos{suffix}.")
    lines.extend([
        "",
        f"Rango publicado: **{min_date.isoformat()}** a **{max_date.isoformat()}**.",
        "Para emergencias, llama al **123**.",
    ])
    return "\n".join(lines)



def _wants_data_summary_answer(message: str):
    normalized = (message or "").lower()
    return any(term in normalized for term in [
        "resume que informacion", "resumen de informacion", "que informacion tienes",
        "que datos tienes", "informacion tienes", "datos tienes", "que tiene el sisc",
    ])


def _format_data_summary_answer(user_message: str, min_date, max_date, fuente_corte: str, annual_summary: dict, total_hechos: int, total_registros: int):
    if not _wants_data_summary_answer(user_message):
        return None
    if not min_date or not max_date:
        return "Aun no hay datos cargados para consulta ciudadana. Para emergencias, llama al **123**."

    years = sorted(annual_summary)
    annual_lines = "\n".join(f"- **{year}:** {annual_summary[year]} hechos." for year in years) if years else "- No hay resumen anual disponible."
    year_text = f"{years[0]} a {years[-1]}" if years else "sin anios consolidados"

    return (
        f"Tengo informacion ciudadana agregada del SISC Jamundi con corte al **{max_date.isoformat()}**.\n\n"
        f"- **Rango disponible:** {min_date.isoformat()} a {max_date.isoformat()} ({year_text}).\n"
        f"- **Base publicada:** {total_hechos} hechos consolidados y {total_registros} registros de sabanas.\n"
        f"- **Fuente:** {fuente_corte}.\n"
        f"- **Puedo consultar:** totales por anio, meses, conductas, barrios/corregimientos y zona urbana/rural.\n"
        f"- **Privacidad:** solo informacion agregada; no nombres, direcciones exactas, telefonos, placas ni datos personales.\n\n"
        f"Resumen por anio:\n{annual_lines}\n\n"
        "Para emergencias, llama al **123**."
    )

def _format_institutional_answer(message: str, db: Session):
    """Answer public institutional questions only with approved aggregate indicators."""
    normalized = (message or "").lower()
    inspection_terms = [
        "inspeccion", "inspecci\u00f3n", "recaud", "tramite", "tr\u00e1mite",
        "certificado", "vecindad", "defuncion", "defunci\u00f3n", "proceso verbal",
        "pva", "despacho comisorio", "actuacion", "actuaci\u00f3n",
    ]
    family_terms = [
        "comisaria", "comisar\u00eda", "violencia intrafamiliar", "violencia familiar",
        "medida de protecci", "pard", "restablecimiento", "psicolog", "trabajo social",
    ]

    if any(term in normalized for term in inspection_terms):
        program = "INSPECCIONES"
        program_label = "Inspecciones de Polic\u00eda"
    elif any(term in normalized for term in family_terms):
        program = "COMISARIAS"
        program_label = "Comisar\u00edas de Familia"
    else:
        return None

    rows = db.query(InstitutionalDataBatch, InstitutionalIndicator).join(
        InstitutionalIndicator, InstitutionalIndicator.batch_id == InstitutionalDataBatch.id
    ).filter(
        InstitutionalDataBatch.program == program,
        InstitutionalDataBatch.validation_status == "APPROVED",
        InstitutionalIndicator.is_public.is_(True),
        InstitutionalIndicator.value >= InstitutionalIndicator.privacy_threshold,
    ).order_by(
        InstitutionalDataBatch.period.desc(),
        InstitutionalDataBatch.reporting_entity.asc(),
        InstitutionalIndicator.indicator.asc(),
    ).all()

    requested_entity = None
    if program == "COMISARIAS":
        if "primera" in normalized:
            requested_entity = "COMISARIA PRIMERA DE FAMILIA"
        elif "segunda" in normalized:
            requested_entity = "COMISARIA SEGUNDA DE FAMILIA"
    elif program == "INSPECCIONES":
        if "segunda" in normalized:
            requested_entity = "INSPECCION SEGUNDA"
        elif "tercera" in normalized:
            requested_entity = "INSPECCION TERCERA"
    if requested_entity:
        rows = [
            (batch, indicator) for batch, indicator in rows
            if InstitutionalAgentService._normalize(batch.reporting_entity) == requested_entity
        ]

    explicit_years = [int(value) for value in re.findall(r"\b(20\d{2})\b", normalized)]
    _, requested_months = _extract_requested_periods(message, date.today().year)
    if explicit_years:
        requested_periods = {
            f"{year}-{month:02d}"
            for year in explicit_years
            for month in (requested_months or range(1, 13))
        }
        rows = [(batch, indicator) for batch, indicator in rows if batch.period in requested_periods]
        if not rows:
            period_label = ", ".join(sorted(requested_periods))
            return (
                f"El SISC no tiene indicadores institucionales aprobados para **{period_label}**. "
                "No se reemplaza el periodo solicitado con cifras de otro mes o ano. "
                "Para emergencias, llama al **123**."
            )

    if not rows:
        return (
            f"El SISC todav\u00eda no tiene indicadores aprobados de **{program_label}** "
            "para responder esta consulta. Las cargas pendientes no se muestran al p\u00fablico. "
            "Cuando el Observatorio revise y apruebe un informe, el asistente se actualizar\u00e1 autom\u00e1ticamente. "
            "Para emergencias, llama al **123**."
        )

    latest_period_by_entity = {}
    latest_rows = []
    for batch, indicator in rows:
        entity_key = batch.reporting_entity.strip().upper()
        latest_period_by_entity.setdefault(entity_key, batch.period)
        if batch.period == latest_period_by_entity[entity_key]:
            latest_rows.append((batch, indicator))

    indicator_filters = []
    if "recaud" in normalized:
        indicator_filters = ["RECAUDO"]
    elif "audien" in normalized:
        indicator_filters = ["AUDIENCIA"]
    elif "medida de protecci" in normalized:
        indicator_filters = ["MEDIDA DE PROTECCION"]
    elif "pard" in normalized or "restablecimiento" in normalized:
        indicator_filters = ["RESTABLECIMIENTO", "PARD"]
    elif "psicolog" in normalized:
        indicator_filters = ["PSICOLOG"]
    elif "trabajo social" in normalized:
        indicator_filters = ["TRABAJO SOCIAL"]
    elif any(term in normalized for term in ["tramite", "tr\u00e1mite", "certificado", "vecindad", "defuncion", "defunci\u00f3n"]):
        indicator_filters = ["TRAMITE", "CERTIFICADO", "CONSTANCIA", "RESOLUCION"]

    if indicator_filters:
        filtered_rows = [
            (batch, indicator)
            for batch, indicator in latest_rows
            if any(term in indicator.indicator.upper() for term in indicator_filters)
        ]
    else:
        filtered_rows = latest_rows

    if not filtered_rows:
        return (
            f"Hay datos aprobados de **{program_label}**, pero no existe un indicador p\u00fablico "
            "que corresponda exactamente a esta pregunta. No se reemplaza con cifras de delitos ni se estima. "
            "Para emergencias, llama al **123**."
        )

    grouped = {}
    for batch, indicator in filtered_rows:
        grouped.setdefault(str(batch.id), {"batch": batch, "indicators": []})
        grouped[str(batch.id)]["indicators"].append(indicator)

    sections = []
    for item in grouped.values():
        batch = item["batch"]
        basis = "acumulado" if batch.reporting_basis == "CUMULATIVE" else "mensual"
        lines = []
        for indicator in item["indicators"]:
            indicator_label = (indicator.indicator
                .replace("psicologia", "psicolog\u00eda")
                .replace("proteccion", "protecci\u00f3n")
                .replace("institucionalizacion", "institucionalizaci\u00f3n")
                .replace("genero", "g\u00e9nero")
                .replace("verificacion", "verificaci\u00f3n")
            )
            value = float(indicator.value)
            if indicator.unit.upper() == "COP":
                value_text = "$" + f"{value:,.0f}".replace(",", ".") + " COP"
            else:
                value_text = f"{value:,.0f}".replace(",", ".") if value.is_integer() else f"{value:,.2f}"
                value_text = f"{value_text} {indicator.unit}"
            lines.append(f"- **{indicator_label}:** {value_text}.")
        sections.append(
            f"**{batch.reporting_entity}** - periodo **{batch.period}**, reporte {basis}, "
            f"corte **{batch.cutoff_date.isoformat()}**:\n" + "\n".join(lines)
        )

    closing = (
        "Los informes acumulados de distintas dependencias se presentan por separado y no se suman autom\u00e1ticamente. "
        "Solo se muestran cargas aprobadas y cifras agregadas. Para emergencias, llama al **123**."
    )
    return "\n\n".join(sections + [closing])

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
    Genera un anÃ¡lisis narrativo basado en los datos actuales usando el proveedor configurado.
    """
    # Validar llaves segÃºn proveedor
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

    # EstadÃ­sticas para el INSIGHT (AÃ±o Actual 2026) - AGREGACIÃ“N DEDUPLICADA
    current_year = datetime.now().year

    # 1. Obtener conteos diarios de HOMICIDIOS de ambas fuentes para el aÃ±o actual
    hom_mod_daily = db.query(HechoSeguridad.fecha_evento, hechos_unicos_expr()).filter(
        func.extract('year', HechoSeguridad.fecha_evento) == current_year,
        HechoSeguridad.categoria_delito == "HOMICIDIO"
    ).group_by(HechoSeguridad.fecha_evento).all()

    hom_leg_daily = db.query(Event.occurrence_date, func.count(Event.id)).join(EventType).filter(
        func.extract('year', Event.occurrence_date) == current_year,
        EventType.category == "HOMICIDIO"
    ).group_by(Event.occurrence_date).all()

    # Unificar por fecha (DEDUPLICACIÃ“N POR DÃA)
    daily_hom = {}
    for d, c in hom_leg_daily: daily_hom[d] = c
    # Priorizar fuente Policial (Sobrescribe si hay dato el mismo dÃ­a)
    for d, c in hom_mod_daily: daily_hom[d] = c
    homicidios_2026 = sum(daily_hom.values())

    # 2. Conteo de Incidentes Totales (AproximaciÃ³n por mayor fuente)
    total_legacy = db.query(Event).filter(func.extract('year', Event.occurrence_date) == current_year).count()
    total_moderno = db.query(hechos_unicos_expr()).filter(func.extract('year', HechoSeguridad.fecha_evento) == current_year).scalar() or 0
    total_real_2026 = total_moderno if total_moderno > 0 else total_legacy

    # 3. Barrios (Priorizar la base mÃ¡s poblada)
    if total_moderno > 0:
        top_barrio_2026 = db.query(HechoSeguridad.barrio_normalizado, hechos_unicos_expr()).filter(
            func.extract('year', HechoSeguridad.fecha_evento) == current_year,
            HechoSeguridad.barrio_normalizado.isnot(None),
            HechoSeguridad.barrio_normalizado != "",
            func.upper(func.trim(HechoSeguridad.barrio_normalizado)).notin_(NON_PUBLIC_TERRITORY_VALUES),
            ~func.upper(HechoSeguridad.barrio_normalizado).like("%PENDIENTE%"),
            ~func.upper(HechoSeguridad.barrio_normalizado).like("%POR ASIGNAR%"),
            ~func.upper(HechoSeguridad.barrio_normalizado).like("%NO APLICA%"),
            ~func.upper(HechoSeguridad.barrio_normalizado).like("%NO DEFINIDO%"),
        ).group_by(HechoSeguridad.barrio_normalizado).order_by(hechos_unicos_expr().desc()).first()
    else:
        top_barrio_2026 = db.query(Event.barrio, func.count(Event.id)).filter(
            func.extract('year', Event.occurrence_date) == current_year,
            Event.barrio.isnot(None),
            Event.barrio != "",
            func.upper(func.trim(Event.barrio)).notin_(NON_PUBLIC_TERRITORY_VALUES),
            ~func.upper(Event.barrio).like("%PENDIENTE%"),
            ~func.upper(Event.barrio).like("%POR ASIGNAR%"),
            ~func.upper(Event.barrio).like("%NO APLICA%"),
            ~func.upper(Event.barrio).like("%NO DEFINIDO%"),
        ).group_by(Event.barrio).order_by(func.count(Event.id).desc()).first()
    if top_barrio_2026 and not _is_public_territory_name(top_barrio_2026[0]):
        top_barrio_2026 = None

    contexto = f"""
    Eres el analista experto del Sistema de InformaciÃ³n para la Seguridad y Convivencia (SISC) de JamundÃ­.
    Analiza estos datos del AÃ‘O ACTUAL {current_year} (Cifras Consolidadas y Sin Duplicados):
    - Incidentes registrados en {current_year}: {total_real_2026}
    - Homicidios totales unificados (PolicÃ­a + MinDefensa): {homicidios_2026}
    - Zona con mayor criticidad este aÃ±o: {top_barrio_2026[0] if top_barrio_2026 else 'N/A'} ({top_barrio_2026[1] if top_barrio_2026 else 0} casos).

    IMPORTANTE: Has detectado un traslape de fuentes y has priorizado la informaciÃ³n de la PolicÃ­a por su actualizaciÃ³n.
    Responde en espaÃ±ol, tono institucional firme. MÃ¡ximo 60 palabras.
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
            "insight": f"El analista del SISC ({AI_PROVIDER}) estÃ¡ saturado. Reintentando en breve...",
            "status": "error"
        }

from services.alert_engine import AlertEngine

@router.get("/alertas", dependencies=[Depends(institutional_access)])
async def get_ai_alerts(db: Session = Depends(get_db)):
    """
    Sistema de Alertas Tempranas (SAT): Detecta incrementos anÃ³malos en delitos
    para la SecretarÃ­a de Seguridad de JamundÃ­.
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
async def citizen_chat(data: CitizenChatRequest, db: Session = Depends(get_db)):
    """
    Chatbot pÃºblico para ciudadanos: Proporciona informaciÃ³n sobre rutas y convivencia.
    Ahora incluye contexto de datos reales para responder preguntas estadÃ­sticas bÃ¡sicas.
    """
    payload = data.model_dump()
    user_message = data.message.strip()
    conversation_text = _conversation_text(payload)
    if not user_message:
        return {"response": "Hola, Â¿en quÃ© puedo ayudarte?"}

    direct_institutional_response = _format_institutional_answer(user_message, db)
    if direct_institutional_response:
        return {"response": direct_institutional_response}
    # 1. Base maestra consolidada para consulta ciudadana
    total_incidentes = db.query(hechos_unicos_expr()).filter(
        HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL"
    ).scalar() or 0

    total_registros = db.query(func.count(HechoSeguridad.id)).filter(
        HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL"
    ).scalar() or 0

    homicidios = db.query(func.count(HechoSeguridad.id)).filter(
        HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
        HechoSeguridad.conducta_estandar.in_(HOMICIDE_ALIASES),
    ).scalar() or 0

    min_modern_date = db.query(func.min(HechoSeguridad.fecha_evento)).filter(
        HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL"
    ).scalar()
    max_modern_date = db.query(func.max(HechoSeguridad.fecha_evento)).filter(
        HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL"
    ).scalar()

    annual_rows = db.query(
        func.extract('year', HechoSeguridad.fecha_evento).label('year'),
        hechos_unicos_expr().label('total'),
    ).filter(
        HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL"
    ).group_by('year').order_by('year').all()
    anual_dict = {int(year): int(total or 0) for year, total in annual_rows}
    stats_anuales = ", ".join([f"{y}: {c} casos" for y, c in sorted(anual_dict.items())]) or "No hay resumen anual consolidado disponible"

    current_year = datetime.now().year
    years_to_track = sorted(anual_dict.keys(), reverse=True)[:3] or [current_year]

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
            metric = func.count(HechoSeguridad.id) if name == "HOMICIDIO" else hechos_unicos_expr()
            filters = [
                HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
                func.extract('year', HechoSeguridad.fecha_evento) == year,
            ]
            if name == "HOMICIDIO":
                filters.append(HechoSeguridad.conducta_estandar.in_(HOMICIDE_ALIASES))
            else:
                filters.append(HechoSeguridad.categoria_delito.in_(aliases))
            count = db.query(metric).filter(*filters).scalar() or 0
            year_data.append(f"{name}: {count}")
        stats_detalladas.append(f"ANIO {year} [{', '.join(year_data)}]")
    stats_contexto_detallado = " | ".join(stats_detalladas)

    nombres_meses = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

    # Fecha real de cobertura para el chat: usa la fuente cargada mas reciente y evita declarar periodos como cero si no estan cargados.
    snapshot_id = None
    max_modern_date = max_modern_date or db.query(func.max(HechoSeguridad.fecha_evento)).filter(
        HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL"
    ).scalar()
    max_legacy_date = db.query(func.max(Event.occurrence_date)).scalar()

    use_modern_source = bool(max_modern_date)
    fecha_corte_date = max_modern_date or max_legacy_date
    fecha_corte = fecha_corte_date.isoformat() if fecha_corte_date else "sin datos cargados"
    fuente_corte = "base maestra consolidada de sabanas oficiales" if use_modern_source else "tabla interna historica"

    requested_years_for_context, requested_months_for_context = _extract_requested_periods(user_message, fecha_corte_date.year if fecha_corte_date else datetime.now().year)
    wants_monthly_breakdown = _wants_monthly_breakdown(user_message)
    has_explicit_year = bool(re.search(r"\b20\d{2}\b", user_message or ""))
    if requested_months_for_context and not has_explicit_year:
        available_years = sorted(anual_dict.keys())
        requested_years_for_context = available_years if available_years else requested_years_for_context
    elif wants_monthly_breakdown and _wants_recent_years(user_message) and not has_explicit_year:
        available_years = sorted(anual_dict.keys(), reverse=True)
        requested_years_for_context = sorted(available_years[:3]) if available_years else requested_years_for_context
    elif wants_monthly_breakdown and not has_explicit_year and not requested_months_for_context:
        requested_years_for_context = _extract_years_for_followup(user_message, conversation_text, fecha_corte_date.year if fecha_corte_date else datetime.now().year)

    if requested_months_for_context or wants_monthly_breakdown or has_explicit_year:
        years_for_monthly_context = requested_years_for_context
    else:
        years_for_monthly_context = [fecha_corte_date.year] if fecha_corte_date else [datetime.now().year]

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
        label = conducta or "SIN CLASIFICAR"
        monthly_summary[key]["conductas"][label] = monthly_summary[key]["conductas"].get(label, 0) + int(total or 0)

    monthly_total_rows = []
    if fecha_corte_date and use_modern_source:
        monthly_total_rows = db.query(
            func.extract('year', HechoSeguridad.fecha_evento).label('year'),
            func.extract('month', HechoSeguridad.fecha_evento).label('month'),
            hechos_unicos_expr().label('total'),
        ).filter(
            HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
            func.extract('year', HechoSeguridad.fecha_evento).in_(years_for_monthly_context),
        ).group_by('year', 'month').order_by('year', 'month').all()
    elif fecha_corte_date and snapshot_id:
        monthly_total_rows = db.query(
            func.extract('year', SabanaSnapshotRow.fecha_evento).label('year'),
            func.extract('month', SabanaSnapshotRow.fecha_evento).label('month'),
            func.count(func.distinct(SabanaSnapshotRow.hecho_key)).label('total'),
        ).filter(
            SabanaSnapshotRow.ingestion_id == snapshot_id,
            func.extract('year', SabanaSnapshotRow.fecha_evento).in_(years_for_monthly_context),
        ).group_by('year', 'month').order_by('year', 'month').all()

    for year, month, total in monthly_total_rows:
        key = (int(year), int(month))
        monthly_summary.setdefault(key, {"total": 0, "conductas": {}})
        monthly_summary[key]["total"] = int(total or 0)

    # No se usa respaldo historico cuando existe base maestra; evita publicar periodos no soportados.
    if not use_modern_source:
        legacy_monthly_rows = db.query(
            func.extract('year', Event.occurrence_date).label('year'),
            func.extract('month', Event.occurrence_date).label('month'),
            EventType.category.label('conducta'),
            func.count(Event.id).label('total'),
        ).join(EventType).filter(
            func.extract('year', Event.occurrence_date).in_(years_for_monthly_context),
        ).group_by('year', 'month', EventType.category).order_by('year', 'month').all()

        for year, month, conducta, total in legacy_monthly_rows:
            key = (int(year), int(month))
            label = conducta or "SIN CLASIFICAR"
            monthly_summary.setdefault(key, {"total": 0, "conductas": {}})
            monthly_summary[key]["conductas"][label] = monthly_summary[key]["conductas"].get(label, 0) + int(total or 0)
            monthly_summary[key]["total"] += int(total or 0)

    if use_modern_source:
        homicide_monthly_rows = db.query(
            func.extract('year', HechoSeguridad.fecha_evento).label('year'),
            func.extract('month', HechoSeguridad.fecha_evento).label('month'),
            func.count(HechoSeguridad.id).label('total'),
        ).filter(
            HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
            HechoSeguridad.conducta_estandar.in_(HOMICIDE_ALIASES),
            func.extract('year', HechoSeguridad.fecha_evento).in_(years_for_monthly_context),
        ).group_by('year', 'month').order_by('year', 'month').all()

        for year, month, total in homicide_monthly_rows:
            key = (int(year), int(month))
            monthly_summary.setdefault(key, {"total": 0, "conductas": {}})
            monthly_summary[key]["conductas"]["HOMICIDIO"] = int(total or 0)

        cantidad_snapshot_expr = cast(
            func.coalesce(
                func.nullif(SabanaSnapshotRow.datos_normalizados.op("->>")("cantidad"), ""),
                "1",
            ),
            Integer,
        )
        homicide_snapshot_base = db.query(
            func.extract('year', SabanaSnapshotRow.fecha_evento).label('year'),
            func.extract('month', SabanaSnapshotRow.fecha_evento).label('month'),
            SabanaSnapshotRow.record_key.label('record_key'),
            func.max(cantidad_snapshot_expr).label('cantidad'),
        ).join(
            IngestionRun, IngestionRun.id == SabanaSnapshotRow.ingestion_id
        ).filter(
            IngestionRun.fuente_codigo == "POLICIA_SEMANAL",
            IngestionRun.status == "COMPLETED",
            SabanaSnapshotRow.conducta_estandar.in_(HOMICIDE_ALIASES),
            func.extract('year', SabanaSnapshotRow.fecha_evento).in_(years_for_monthly_context),
        ).group_by('year', 'month', SabanaSnapshotRow.record_key).subquery()

        homicide_snapshot_rows = db.query(
            homicide_snapshot_base.c.year,
            homicide_snapshot_base.c.month,
            func.sum(homicide_snapshot_base.c.cantidad).label('total'),
        ).group_by(
            homicide_snapshot_base.c.year,
            homicide_snapshot_base.c.month,
        ).order_by(
            homicide_snapshot_base.c.year,
            homicide_snapshot_base.c.month,
        ).all()

        for year, month, total in homicide_snapshot_rows:
            key = (int(year), int(month))
            monthly_summary.setdefault(key, {"total": 0, "conductas": {}})
            monthly_summary[key]["conductas"]["HOMICIDIO_REGISTROS"] = int(total or 0)

    stats_mensuales = []
    for (year, month), info in sorted(monthly_summary.items()):
        principales = sorted(info["conductas"].items(), key=lambda item: item[1], reverse=True)[:4]
        detalle = ", ".join([f"{name}: {count}" for name, count in principales])
        stats_mensuales.append(f"{nombres_meses[month]} {year}: total {info['total']} casos ({detalle})")
    stats_mensuales = " | ".join(stats_mensuales) if stats_mensuales else "No hay resumen mensual consolidado disponible"

    direct_available_dates_response = _format_available_dates_answer(user_message, min_modern_date, fecha_corte_date, fuente_corte, anual_dict)
    if direct_available_dates_response:
        return {"response": direct_available_dates_response}

    direct_annual_records_response = _format_annual_records_answer(user_message, min_modern_date, fecha_corte_date, fuente_corte, anual_dict)
    if direct_annual_records_response:
        return {"response": direct_annual_records_response}

    direct_data_summary_response = _format_data_summary_answer(user_message, min_modern_date, fecha_corte_date, fuente_corte, anual_dict, total_incidentes, total_registros)
    if direct_data_summary_response:
        return {"response": direct_data_summary_response}

    direct_cutoff_response = _format_cutoff_answer(user_message, fecha_corte, fuente_corte)
    if direct_cutoff_response:
        return {"response": direct_cutoff_response}

    direct_year_monthly_response = _format_year_monthly_breakdown_answer(user_message, conversation_text, monthly_summary, fecha_corte_date, fecha_corte, fuente_corte)
    if direct_year_monthly_response:
        return {"response": direct_year_monthly_response}

    direct_monthly_response = _format_monthly_direct_answer(user_message, monthly_summary, fecha_corte_date, fecha_corte, fuente_corte, conversation_text)
    if direct_monthly_response:
        return {"response": direct_monthly_response}

    contexto = f"""
    Eres el Asistente Virtual del SISC JamundÃ­ (Sistema de InformaciÃ³n para la Seguridad y Convivencia).
    Tu objetivo es guiar a los ciudadanos y responder dudas sobre seguridad con DATOS REALES.

    DATOS ACTUALES DEL SISTEMA (USA ESTO PARA RESPONDER):
    - Total histÃ³rico de incidentes en plataforma: {total_incidentes}
    - Total de homicidios registrados: {homicidios}
    - Casos totales por aÃ±o: {stats_anuales}
    - DETALLE POR CATEGORÃA Y AÃ‘O: {stats_contexto_detallado}
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
        return {"response": "Lo siento, tengo dificultades tÃ©cnicas. Por favor, consulta los tableros de datos en el portal o llama al 123 en caso de emergencia."}

