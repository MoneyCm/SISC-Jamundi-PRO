from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from db.models import get_db, Event, EventType
from db.models_hechos_seguridad import HechoSeguridad, IngestionRun, SabanaSnapshotRow
from db.models_institutional import InstitutionalDataBatch, InstitutionalIndicator
from services.indicator_catalog import METHODOLOGY_VERSION
from services.institutional_agent_service import InstitutionalAgentService
from services.hechos_metrics import hechos_unicos_expr
from sqlalchemy import Integer, cast, func
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import re
import httpx
from datetime import datetime, date, timedelta
from api.auth import analyst_or_admin, institutional_access

router = APIRouter()

# ConfiguraciÃ³n de Modelos
# gemini-2.0-flash-lite fue retirado por Google; el modelo se configura por entorno.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
# La cuenta no tiene cupo para mistral-small (límite 0 por minuto); ministral-8b sí (188 por minuto).
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "ministral-8b-latest")

# ConfiguraciÃ³n desde .env
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
AI_PROVIDER = os.getenv("AI_PROVIDER", "GEMINI").upper()
AI_MODEL = MISTRAL_MODEL if AI_PROVIDER == "MISTRAL" else GEMINI_MODEL

print(f"SISC JamundÃ­ AI: Iniciando con Proveedor: {AI_PROVIDER}")

# Cache simple en memoria para evitar Rate Limits
ia_cache = {
    "insight": None,
    "timestamp": 0,
    "last_total": 0,
    "provider": None,
    "period": None,
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
    # La llave va en un encabezado, no en la URL: los errores de httpx imprimen la URL
    # y la dejaban expuesta en los registros.
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    headers = {"x-goog-api-key": GEMINI_API_KEY or "", "Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": contexto}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024},
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            candidate = response.json()['candidates'][0]
            if candidate.get('finishReason') == 'MAX_TOKENS':
                raise RuntimeError("Respuesta de Gemini truncada por limite de tokens.")
            # Sin texto (por ejemplo, cuando no hay nada pertinente) llega sin 'content'.
            return "".join(part.get('text', '') for part in (candidate.get('content') or {}).get('parts', []))
        except httpx.HTTPStatusError as e:
            print(f"Error llamando a Gemini ({GEMINI_MODEL}): HTTP {e.response.status_code}")
            raise
        except Exception as e:
            print(f"Error llamando a Gemini ({GEMINI_MODEL}): {type(e).__name__}")
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
        # 150 tokens cortaba respuestas de 70-120 palabras a mitad de frase.
        "max_tokens": 400,
        "temperature": 0.2,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            choice = result['choices'][0]
            if choice.get('finish_reason') == 'length':
                raise RuntimeError("Respuesta de Mistral truncada por limite de tokens.")
            return choice['message']['content']
        except Exception as e:
            print(f"Error llamando a Mistral: {e}")
            raise

async def redactar_verificado(contexto: str, datos: str, respaldo: Optional[str] = None, extra_allowed=()) -> dict:
    """Redacta con la IA configurada y verifica el texto contra `datos` antes de usarlo.

    `datos` son solo las cifras entregadas en el prompt (no las instrucciones). Si la IA
    falla, se corta o altera una cifra o el sentido de un cambio, se usa `respaldo`
    (texto calculado sin IA) y se informa el motivo.
    """
    from services.ai_output_guard import verify_ai_text

    import asyncio

    base = {"provider": AI_PROVIDER, "model": AI_MODEL}
    texto = None
    # Un reintento ante saturación temporal del proveedor (429 / 5xx).
    for intento in range(2):
        try:
            texto = await (call_mistral(contexto) if AI_PROVIDER == "MISTRAL" else call_gemini(contexto))
            break
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if intento == 0 and (status == 429 or status >= 500):
                await asyncio.sleep(2)
                continue
            print(f"Error con IA ({AI_PROVIDER}): HTTP {status}")
        except Exception as exc:
            print(f"Error con IA ({AI_PROVIDER}): {type(exc).__name__}")
        return {**base, "text": respaldo, "verified": False, "fallback": True, "problems": ["La IA no respondio."]}
    texto = (texto or "").strip()
    guard = verify_ai_text(texto, datos, extra_allowed=extra_allowed)
    if not guard.ok:
        print(f"Texto de IA descartado por verificacion: {guard.problems}")
        return {**base, "text": respaldo, "verified": False, "fallback": True, "problems": guard.problems}
    return {**base, "text": texto, "verified": True, "fallback": False, "problems": []}


@router.get("/insights", dependencies=[Depends(institutional_access)])
async def get_ai_insights(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """
    Genera un anÃ¡lisis narrativo basado en los datos actuales usando el proveedor configurado.
    """
    # Validar llaves segÃºn proveedor
    if AI_PROVIDER == "GEMINI" and not GEMINI_API_KEY:
        return {"insight": "Falta GEMINI_API_KEY", "status": "error"}
    if AI_PROVIDER == "MISTRAL" and not MISTRAL_API_KEY:
        return {"insight": "Falta MISTRAL_API_KEY", "status": "error"}

    latest_date = db.query(func.max(HechoSeguridad.fecha_evento)).filter(
        HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL"
    ).scalar()
    period_end = end_date or latest_date or date.today()
    period_start = start_date or date(period_end.year, 1, 1)
    if period_start > period_end:
        raise HTTPException(status_code=400, detail="La fecha inicial no puede ser posterior a la fecha final.")

    total = db.query(hechos_unicos_expr()).filter(
        HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
        HechoSeguridad.fecha_evento >= period_start,
        HechoSeguridad.fecha_evento <= period_end,
    ).scalar() or 0
    if total == 0:
        return {
            "insight": "El sistema se encuentra a la espera de nuevos datos para generar la Perspectiva de Seguridad.",
            "status": "success",
            "provider": AI_PROVIDER
        }

    # Cache Check
    import time
    ahora = time.time()
    period_key = f"{period_start.isoformat()}:{period_end.isoformat()}"
    if ia_cache["insight"] and (ahora - ia_cache["timestamp"] < 1800) and (ia_cache["last_total"] == total) and (ia_cache["provider"] == AI_PROVIDER) and (ia_cache["period"] == period_key):
        return {
            "insight": ia_cache["insight"],
            "status": "success",
            "provider": ia_cache.get("effective_provider", AI_PROVIDER),
            "model": ia_cache.get("model"),
            "verified": ia_cache.get("verified"),
            "periodo": {"inicio": period_start.isoformat(), "fin": period_end.isoformat()},
            "cached": True
        }

    # EstadÃ­sticas para el INSIGHT (AÃ±o Actual 2026) - AGREGACIÃ“N DEDUPLICADA
    current_year = period_end.year

    # 1. Obtener conteos diarios de HOMICIDIOS de ambas fuentes para el aÃ±o actual
    hom_mod_daily = db.query(HechoSeguridad.fecha_evento, hechos_unicos_expr()).filter(
        HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
        HechoSeguridad.fecha_evento >= period_start,
        HechoSeguridad.fecha_evento <= period_end,
        HechoSeguridad.conducta_estandar.in_(HOMICIDE_ALIASES),
    ).group_by(HechoSeguridad.fecha_evento).all()

    hom_leg_daily = db.query(Event.occurrence_date, func.count(Event.id)).join(EventType).filter(
        Event.occurrence_date >= period_start,
        Event.occurrence_date <= period_end,
        EventType.category == "HOMICIDIO",
    ).group_by(Event.occurrence_date).all()

    # Unificar por fecha (DEDUPLICACIÃ“N POR DÃA)
    daily_hom = {}
    for d, c in hom_leg_daily: daily_hom[d] = c
    # Priorizar fuente Policial (Sobrescribe si hay dato el mismo dÃ­a)
    for d, c in hom_mod_daily: daily_hom[d] = c
    homicidios_periodo = sum(daily_hom.values())

    # 2. Conteo de Incidentes Totales (AproximaciÃ³n por mayor fuente)
    total_legacy = db.query(Event).filter(
        Event.occurrence_date >= period_start,
        Event.occurrence_date <= period_end,
    ).count()
    total_moderno = total
    total_real_periodo = total_moderno if total_moderno > 0 else total_legacy

    # 3. Barrios (Priorizar la base mÃ¡s poblada)
    if total_moderno > 0:
        top_barrio_2026 = db.query(HechoSeguridad.barrio_normalizado, hechos_unicos_expr()).filter(
            HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
            HechoSeguridad.fecha_evento >= period_start,
            HechoSeguridad.fecha_evento <= period_end,
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
            Event.occurrence_date >= period_start,
            Event.occurrence_date <= period_end,
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

    # Compatibilidad con la plantilla histórica; el contexto se reemplaza abajo.
    total_real_2026 = total_real_periodo
    homicidios_2026 = homicidios_periodo

    contexto = f"""
    Eres el analista experto del Sistema de InformaciÃ³n para la Seguridad y Convivencia (SISC) de JamundÃ­.
    Analiza estos datos del AÃ‘O ACTUAL {current_year} (Cifras Consolidadas y Sin Duplicados):
    - Incidentes registrados en {current_year}: {total_real_2026}
    - Homicidios totales unificados (PolicÃ­a + MinDefensa): {homicidios_2026}
    - Zona con mayor criticidad este aÃ±o: {top_barrio_2026[0] if top_barrio_2026 else 'N/A'} ({top_barrio_2026[1] if top_barrio_2026 else 0} casos).

    IMPORTANTE: Has detectado un traslape de fuentes y has priorizado la informaciÃ³n de la PolicÃ­a por su actualizaciÃ³n.
    Responde en espaÃ±ol, tono institucional firme. MÃ¡ximo 60 palabras.
    """
    contexto = f"""
    Eres analista del Sistema de Información para la Seguridad y Convivencia de Jamundí.
    Resume únicamente los datos consolidados entre {period_start.isoformat()} y {period_end.isoformat()}:
    - Registros únicos: {total_real_periodo}
    - Homicidios: {homicidios_periodo}
    - Mayor concentración territorial publicable: {top_barrio_2026[0] if top_barrio_2026 else 'sin dato clasificable'} ({top_barrio_2026[1] if top_barrio_2026 else 0} registros).
    No presentes predicciones ni causalidades. Indica que se trata de una lectura descriptiva.
    Responde en español, con tono institucional claro y máximo 60 palabras.
    """

    top_nombre = top_barrio_2026[0] if top_barrio_2026 else 'sin dato clasificable'
    top_total = top_barrio_2026[1] if top_barrio_2026 else 0
    datos = (
        f"Periodo: {period_start.isoformat()} a {period_end.isoformat()}. Registros unicos: {total_real_periodo}. "
        f"Homicidios: {homicidios_periodo}. Mayor concentracion: {top_nombre} ({top_total} registros)."
    )
    respaldo = (
        f"Lectura descriptiva del periodo {period_start.isoformat()} a {period_end.isoformat()}: "
        f"{total_real_periodo} registros únicos y {homicidios_periodo} homicidios. "
        f"Mayor concentración territorial publicable: {top_nombre} ({top_total} registros)."
    )
    resultado = await redactar_verificado(contexto, datos, respaldo)
    effective_provider = "SISC_AUTOMATICO" if resultado["fallback"] else AI_PROVIDER

    # Update Cache
    ia_cache["insight"] = resultado["text"]
    ia_cache["timestamp"] = ahora
    ia_cache["last_total"] = total
    ia_cache["provider"] = AI_PROVIDER
    ia_cache["effective_provider"] = effective_provider
    ia_cache["model"] = None if resultado["fallback"] else resultado["model"]
    ia_cache["verified"] = resultado["verified"]
    ia_cache["period"] = period_key

    return {
        "insight": resultado["text"],
        "status": "success",
        "provider": effective_provider,
        "model": ia_cache["model"],
        "verified": resultado["verified"],
        "verification_notes": resultado["problems"],
        "periodo": {"inicio": period_start.isoformat(), "fin": period_end.isoformat()},
        "cached": False
    }

from services.alert_engine import AlertEngine

@router.get("/alertas", dependencies=[Depends(institutional_access)], deprecated=True)
async def get_ai_alerts(db: Session = Depends(get_db)):
    """DEPRECATED: motor legado (ventanas desiguales, mezcla de unidades).

    Compatibilidad únicamente para tableros no migrados. Uso operativo:
    bandeja central /api/alerts-tray (evaluaciones persistidas y vigentes).
    """
    try:
        # LEGADO (ventanas desiguales, mezcla de unidades): se mantiene por compatibilidad.
        # Para alertas reproducibles usar GET /api/ia/alertas-semanales.
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


@router.get("/alertas-semanales", dependencies=[Depends(institutional_access)])
def get_weekly_alerts(
    indicator: str = "HOMICIDIO",
    ref_date: Optional[date] = None,
    source_version_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Consulta (solo lectura): evalúa la alerta semanal sin persistir.

    Determinista; la IA solo redacta a partir de la evidencia devuelta.
    Umbrales propuestos, pendientes de acuerdo con el Observatorio.
    """
    from services.alert_rules import evaluate_weekly
    try:
        return evaluate_weekly(db, indicator=indicator.upper(), ref_date=ref_date,
                               source_version_id=source_version_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as e:
        print(f"Error en alertas semanales: {e}")
        raise HTTPException(status_code=500, detail="Error al generar la alerta semanal.")


@router.post("/alertas-semanales", dependencies=[Depends(analyst_or_admin)])
def post_weekly_alerts(
    indicator: str = "HOMICIDIO",
    ref_date: Optional[date] = None,
    source_version_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Ejecución: evalúa y persiste idempotentemente la alerta semanal."""
    from services.alert_rules import emit_weekly
    try:
        return emit_weekly(db, indicator=indicator.upper(), ref_date=ref_date,
                           source_version_id=source_version_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as e:
        print(f"Error en alertas semanales: {e}")
        raise HTTPException(status_code=500, detail="Error al generar la alerta semanal.")
@router.post("/chat_ciudadano")
def citizen_chat(data: CitizenChatRequest, request: Request, db: Session = Depends(get_db)):
    """Asistente ciudadano del portal: cifras públicas verificadas (sin IA) y rutas de atención.

    Ver services/asistente_ciudadano.py. Tiene su propio límite de preguntas por persona.
    """
    from middleware.rate_limit import rate_limit_asistente
    from services import asistente_ciudadano

    rate_limit_asistente(request)
    mensaje = data.message.strip()
    if not mensaje:
        return {"response": "Hola, ¿en qué puedo ayudarle?"}
    resultado = asistente_ciudadano.responder(db, mensaje, [m.model_dump() for m in data.history])
    return {"response": resultado["respuesta"], "fuentes": resultado["fuentes"],
            "sugerencias": resultado["sugerencias"], "tipo": resultado["tipo"], "verified": True}
