from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from math import log10
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from uuid import uuid4

from sqlalchemy import desc, func, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from db.models_hechos_seguridad import HechoSeguridad
from db.models_institutional import InstitutionalDataBatch, InstitutionalIndicator, InstitutionalAgentRun
from db.models_inspecciones import InspeccionActuacion, InspeccionExpediente, InspeccionMedida
from db.models_sisc_cifras import SiscCifrasPublication
from services.hechos_metrics import hechos_unicos_expr


MIN_PUBLIC_TERRITORIAL_COUNT = 3
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
NON_PUBLIC_TERRITORY_PATTERNS = (
    "PENDIENTE",
    "POR ASIGNAR",
    "NO APLICA",
    "NO DEFINIDO",
    "SIN LOCALIDAD",
    "SIN COMUNA",
)


@dataclass
class Indicator:
    id: str
    source: str
    source_code: str
    domain: str
    category: str
    indicator_code: str
    indicator_name: str
    value: float
    unit: str
    period_start: str
    period_end: str
    geography: Optional[str]
    comparison_value: Optional[float]
    variation_absolute: Optional[float]
    variation_percentage: Optional[float]
    quality_status: str
    publication_level: str
    cutoff_date: Optional[str]
    metadata: Dict[str, Any]


@dataclass
class Insight:
    id: str
    domain: str
    source: str
    indicator_code: str
    title: str
    value_text: str
    detail: str
    relevance_score: float
    quality_status: str
    cutoff_date: Optional[str]
    chart_type: str
    evidence_indicator_ids: List[str]


def pct_change(current: float, previous: Optional[float]) -> Optional[float]:
    if previous is None or previous == 0:
        return None
    return ((current - previous) / previous) * 100


def variation_text(value: Optional[float]) -> str:
    if value is None:
        return "sin base comparable"
    if abs(value) < 0.05:
        return "sin variacion"
    prefix = "+" if value > 0 else ""
    return f"{prefix}{value:.1f}%"


def calculate_relevance(
    *,
    value: float,
    variation_percentage: Optional[float],
    priority: float,
    quality_status: str,
    territorial_share: Optional[float] = None,
    trend_weeks: int = 0,
) -> float:
    change_component = min(abs(variation_percentage or 0), 100) * 0.35
    volume_component = min(log10(max(value, 0) + 1) * 18, 28)
    priority_component = priority * 18
    territory_component = min((territorial_share or 0) * 40, 12)
    trend_component = min(trend_weeks * 4, 12)
    quality_factor = {
        "VALIDADO": 1.0,
        "PRELIMINAR": 0.75,
        "INCOMPLETO": 0.35,
        "NO PUBLICABLE": 0.0,
    }.get(quality_status, 0.5)
    return round(
        (change_component + volume_component + priority_component + territory_component + trend_component)
        * quality_factor,
        2,
    )


def is_public_territory_name(value: Optional[str]) -> bool:
    if not value:
        return False
    clean = " ".join(str(value).strip().upper().split())
    if not clean or clean in NON_PUBLIC_TERRITORY_VALUES:
        return False
    return not any(pattern in clean for pattern in NON_PUBLIC_TERRITORY_PATTERNS)


def public_measure_label(value: Optional[str]) -> Tuple[str, Optional[str]]:
    technical = " ".join(str(value or "").strip().split())
    clean = technical.upper()
    if not clean or clean in {"SIN ESPECIFICAR", "NAN", "NONE", "NULL"}:
        return "", technical or None
    if "PROHIBICION DE INGRESO" in clean or "PROHIBICIÓN DE INGRESO" in clean:
        return "Restricciones de ingreso a eventos publicos", technical
    if "MULTA" in clean and "GENERAL" in clean and "TIPO 4" in clean:
        return "Comparendos con multa de mayor cuantia", technical
    if "MULTA" in clean and "GENERAL" in clean and "TIPO 3" in clean:
        return "Comparendos con multa de cuantia alta", technical
    if "MULTA" in clean and "GENERAL" in clean and "TIPO 2" in clean:
        return "Comparendos con multa de cuantia media", technical
    if "MULTA" in clean and "GENERAL" in clean and "TIPO 1" in clean:
        return "Comparendos con multa de menor cuantia", technical
    if "MULTA" in clean and "GENERAL" in clean:
        return "Comparendos por convivencia ciudadana", technical
    if "AMONEST" in clean:
        return "Amonestaciones por convivencia ciudadana", technical
    if "PARTICIP" in clean and ("PROGRAMA" in clean or "COMUNIT" in clean):
        return "Participacion en programas comunitarios", technical
    if "REPAR" in clean or "DANO" in clean or "DAÑO" in clean:
        return "Reparacion por danos a la convivencia", technical
    if "DESTRU" in clean or "BIEN" in clean:
        return "Medidas sobre bienes relacionados con convivencia", technical
    return technical.title(), technical


def public_measure_detail(value: Optional[str]) -> Optional[str]:
    clean = " ".join(str(value or "").strip().split()).upper()
    if not clean or clean in {"SIN ESPECIFICAR", "NAN", "NONE", "NULL"}:
        return None
    if "PROHIBICION DE INGRESO" in clean or "PROHIBICIÓN DE INGRESO" in clean:
        return "Medida aplicada para limitar el ingreso a actividades o eventos con publico."
    if "MULTA" in clean and "GENERAL" in clean and "TIPO 4" in clean:
        return "La fuente informa la categoria de la multa, no el comportamiento especifico."
    if "MULTA" in clean and "GENERAL" in clean and "TIPO 3" in clean:
        return "La fuente informa la categoria de la multa, no el comportamiento especifico."
    if "MULTA" in clean and "GENERAL" in clean and "TIPO 2" in clean:
        return "La fuente informa la categoria de la multa, no el comportamiento especifico."
    if "MULTA" in clean and "GENERAL" in clean and "TIPO 1" in clean:
        return "La fuente informa la categoria de la multa, no el comportamiento especifico."
    if "MULTA" in clean and "GENERAL" in clean:
        return "La fuente reporta el tipo de multa; para saber el comportamiento se requiere articulo o numeral."
    return None


class SiscCifrasService:
    SOURCE_CATALOG = {
        "POLICIA_SEMANAL": {
            "name": "Policia Nacional",
            "domain": "SEGURIDAD",
            "dependency": "Policia Nacional / SISC",
            "periodicity": "Semanal",
            "coverage": "Jamundi",
            "unit": "hechos registrados",
        },
        "INSPECCIONES_RNMC": {
            "name": "Inspecciones de Policia / RNMC",
            "domain": "CONVIVENCIA",
            "dependency": "Inspecciones de Policia",
            "periodicity": "Mensual",
            "coverage": "Jamundi",
            "unit": "actuaciones registradas",
        },
        "COMISARIAS_FAMILIA": {
            "name": "Comisarias de Familia",
            "domain": "FAMILIA Y PROTECCION",
            "dependency": "Comisarias de Familia",
            "periodicity": "Mensual",
            "coverage": "Agregado municipal",
            "unit": "casos agregados",
        },
    }

    @staticmethod
    def period_bounds(mode: Optional[str], period_start: Optional[date], period_end: Optional[date]) -> Tuple[date, date]:
        if period_start and period_end:
            return period_start, period_end

        today = date.today()
        if mode == "monthly":
            start = today.replace(day=1)
            return start, today
        if mode == "semester":
            start_month = 1 if today.month <= 6 else 7
            return date(today.year, start_month, 1), today
        if mode == "annual":
            return date(today.year, 1, 1), today

        start = today - timedelta(days=today.weekday())
        return start, today

    @staticmethod
    def previous_bounds(start: date, end: date) -> Tuple[date, date]:
        duration = end - start
        previous_end = start - timedelta(days=1)
        previous_start = previous_end - duration
        return previous_start, previous_end

    @staticmethod
    def previous_month_bounds(start: date, end: date) -> Tuple[date, date]:
        previous_month_end = start - timedelta(days=1)
        previous_month_start = previous_month_end.replace(day=1)
        current_period_is_full_month = (end + timedelta(days=1)).month != end.month
        if current_period_is_full_month:
            return previous_month_start, previous_month_end

        comparison_day = min(end.day, previous_month_end.day)
        return previous_month_start, previous_month_end.replace(day=comparison_day)

    @staticmethod
    def year_over_year_bounds(start: date, end: date) -> Tuple[date, date]:
        try:
            return start.replace(year=start.year - 1), end.replace(year=end.year - 1)
        except ValueError:
            duration = end - start
            comparison_start = start - timedelta(days=365)
            return comparison_start, comparison_start + duration

    @classmethod
    def comparison_bounds(cls, edition_type: Optional[str], mode: str, start: date, end: date) -> Tuple[date, date, str, str]:
        selected = (mode or "auto").lower()
        if selected == "auto":
            selected = "previous_period" if edition_type == "monthly" else "year_over_year"

        if selected in ("previous_period", "previous", "periodo_anterior"):
            if edition_type == "monthly" and start.day == 1:
                compare_start, compare_end = cls.previous_month_bounds(start, end)
            else:
                compare_start, compare_end = cls.previous_bounds(start, end)
            return compare_start, compare_end, "periodo anterior comparable", "previous_period"

        compare_start, compare_end = cls.year_over_year_bounds(start, end)
        return compare_start, compare_end, "mismo periodo del ano anterior", "year_over_year"

    @classmethod
    def database_available(cls, db: Session) -> bool:
        try:
            db.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError:
            try:
                db.rollback()
            except Exception:
                pass
            return False

    @classmethod
    def fallback_source_registry(cls) -> List[Dict[str, Any]]:
        return [
            {
                **meta,
                "code": code,
                "last_cutoff_date": None,
                "reported_cutoff_date": None,
                "available_records": 0,
                "future_records": 0,
                "excluded_test_records": 0,
                "exclusion_note": None,
                "quality_status": "INCOMPLETO",
                "publication_level": "PUBLICO",
                "available_indicators": cls.available_indicator_codes(code),
                "status_note": "Base de datos no disponible. Inicie PostgreSQL/PostGIS para calcular cifras reales.",
            }
            for code, meta in cls.SOURCE_CATALOG.items()
        ]

    @classmethod
    def source_registry(cls, db: Session) -> List[Dict[str, Any]]:
        if not cls.database_available(db):
            return cls.fallback_source_registry()

        today = date.today()
        tomorrow = datetime.combine(today + timedelta(days=1), datetime.min.time())
        registry = []
        for code, meta in cls.SOURCE_CATALOG.items():
            row = {**meta, "code": code}
            reported_cutoff = None
            future_records = 0
            excluded_test_records = 0
            if code == "POLICIA_SEMANAL":
                reported_cutoff = db.query(func.max(HechoSeguridad.fecha_evento)).filter(
                    HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL"
                ).scalar()
                cutoff = db.query(func.max(HechoSeguridad.fecha_evento)).filter(
                    HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
                    HechoSeguridad.fecha_evento <= today,
                ).scalar()
                total = db.query(HechoSeguridad.id).filter(
                    HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
                    HechoSeguridad.fecha_evento <= today,
                ).count()
                future_records = db.query(HechoSeguridad.id).filter(
                    HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
                    HechoSeguridad.fecha_evento > today,
                ).count()
            elif code == "INSPECCIONES_RNMC":
                public_filters = cls.inspection_public_filters()
                reported_cutoff = db.query(func.max(InspeccionActuacion.fecha_actuacion)).filter(
                    *public_filters,
                ).scalar()
                cutoff = db.query(func.max(InspeccionActuacion.fecha_actuacion)).filter(
                    *public_filters,
                    InspeccionActuacion.fecha_actuacion < tomorrow,
                ).scalar()
                total = db.query(InspeccionActuacion.id).filter(
                    *public_filters,
                    InspeccionActuacion.fecha_actuacion < tomorrow,
                ).count()
                future_records = db.query(InspeccionActuacion.id).filter(
                    *public_filters,
                    InspeccionActuacion.fecha_actuacion >= tomorrow,
                ).count()
                excluded_test_records = db.query(InspeccionActuacion.id).filter(
                    ~public_filters[0] | ~public_filters[1],
                ).count()
            elif code == "COMISARIAS_FAMILIA":
                cutoff = db.query(func.max(InstitutionalDataBatch.cutoff_date)).filter(
                    InstitutionalDataBatch.program == "COMISARIAS",
                    InstitutionalDataBatch.validation_status == "APPROVED",
                ).scalar()
                total = db.query(InstitutionalIndicator.id).join(
                    InstitutionalDataBatch,
                    InstitutionalIndicator.batch_id == InstitutionalDataBatch.id,
                ).filter(
                    InstitutionalDataBatch.program == "COMISARIAS",
                    InstitutionalDataBatch.validation_status == "APPROVED",
                    InstitutionalIndicator.is_public.is_(True),
                    InstitutionalIndicator.value >= InstitutionalIndicator.privacy_threshold,
                ).count()
                reported_cutoff = cutoff
            else:
                cutoff = None
                total = 0

            quality = "VALIDADO" if total > 0 and cutoff else "INCOMPLETO"
            status_note = None
            exclusion_note = None
            if future_records:
                quality = "PRELIMINAR"
                status_note = (
                    f"Se excluyeron {future_records} registros con fecha futura. "
                    "La fuente requiere correccion antes de publicar."
                )
            elif excluded_test_records:
                exclusion_note = f"Se excluyeron {excluded_test_records} registros identificados como prueba."
            row.update(
                {
                    "last_cutoff_date": cls.iso_date(cutoff),
                    "reported_cutoff_date": cls.iso_date(reported_cutoff),
                    "available_records": total,
                    "future_records": future_records,
                    "excluded_test_records": excluded_test_records,
                    "quality_status": quality,
                    "publication_level": "PUBLICO",
                    "available_indicators": cls.available_indicator_codes(code),
                    "status_note": status_note,
                    "exclusion_note": exclusion_note,
                }
            )
            registry.append(row)
        return registry

    @staticmethod
    def iso_date(value: Optional[Any]) -> Optional[str]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)

    @staticmethod
    def inspection_public_filters() -> List[Any]:
        source_filename = func.lower(func.coalesce(InspeccionActuacion.fuente_archivo, ""))
        return [
            ~source_filename.like("%test%"),
            ~source_filename.like("%prueba%"),
        ]

    @staticmethod
    def coverage_status(period_records: int, cutoff: Optional[date], start: date, end: date) -> str:
        if period_records <= 0:
            if cutoff and cutoff < start:
                return "stale"
            return "missing"
        if not cutoff or cutoff < end:
            return "partial"
        return "aligned"

    @staticmethod
    def latest_batches_by_entity(
        batches: Sequence[InstitutionalDataBatch],
    ) -> List[InstitutionalDataBatch]:
        latest: Dict[str, InstitutionalDataBatch] = {}
        for batch in batches:
            entity_key = (batch.reporting_entity or "").strip().upper()
            current = latest.get(entity_key)
            if current is None or batch.version > current.version:
                latest[entity_key] = batch
        return [latest[key] for key in sorted(latest)]

    @staticmethod
    def _enumerate_months(start: date, end: date) -> List[str]:
        months: List[str] = []
        current = start.replace(day=1)
        while current <= end:
            months.append(current.strftime("%Y-%m"))
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        return months

    @classmethod
    def _resolve_institutional_batches(
        cls,
        db: Session,
        program: str,
        start: date,
        end: date,
    ) -> Tuple[List[InstitutionalDataBatch], List[str]]:
        months = cls._enumerate_months(start, end)
        all_batches: List[InstitutionalDataBatch] = []
        for period_str in months:
            batches = cls.latest_batches_by_entity(
                db.query(InstitutionalDataBatch).filter(
                    InstitutionalDataBatch.program == program,
                    InstitutionalDataBatch.validation_status == "APPROVED",
                    InstitutionalDataBatch.period == period_str,
                ).order_by(
                    InstitutionalDataBatch.reporting_entity.asc(),
                    InstitutionalDataBatch.version.desc(),
                ).all()
            )
            all_batches.extend(batches)
        return all_batches, months

    @classmethod
    def publication_sources(
        cls,
        db: Session,
        *,
        edition_type: Optional[str] = None,
        start: date,
        end: date,
        prev_start: date,
        prev_end: date,
        source_codes: Sequence[str],
    ) -> List[Dict[str, Any]]:
        registry = {item["code"]: item for item in cls.source_registry(db)}
        today = date.today()
        tomorrow = datetime.combine(today + timedelta(days=1), datetime.min.time())
        result: List[Dict[str, Any]] = []

        for code in source_codes:
            source = dict(registry.get(code, {**cls.SOURCE_CATALOG.get(code, {}), "code": code}))
            source.update(
                {
                    "requested_period": {"start": start.isoformat(), "end": end.isoformat()},
                    "period_records": 0,
                    "comparison_records": 0,
                    "coverage_status": "missing",
                    "included": False,
                    "comparable": False,
                    "publishable": False,
                }
            )

            if code == "COMISARIAS_FAMILIA":
                batches, covered_months = cls._resolve_institutional_batches(
                    db, "COMISARIAS", start, end,
                )
                prev_batches, prev_covered_months = cls._resolve_institutional_batches(
                    db, "COMISARIAS", prev_start, prev_end,
                )

                if batches:
                    public_items = [
                        item for batch in batches for item in batch.indicators
                        if item.is_public and float(item.value) >= item.privacy_threshold
                    ]
                    previous_public_items = [
                        item for batch in prev_batches for item in batch.indicators
                        if item.is_public and float(item.value) >= item.privacy_threshold
                    ]
                    source.update(
                        {
                            "period_records": len(public_items),
                            "comparison_records": len(previous_public_items),
                            "coverage_status": "aligned" if public_items else "missing",
                            "included": bool(public_items),
                            "comparable": bool(previous_public_items),
                            "publishable": bool(public_items) and source.get("quality_status") == "VALIDADO",
                            "covered_periods": covered_months,
                            "period_label": ",".join(covered_months),
                            "reporting_basis": sorted({batch.reporting_basis for batch in batches}),
                            "reporting_entities": sorted({batch.reporting_entity for batch in batches}),
                            "status_note": None if public_items else "Los cortes existen, pero no contienen indicadores publicables.",
                        }
                    )
                else:
                    cutoff_text = source.get("last_cutoff_date")
                    cutoff = date.fromisoformat(cutoff_text) if cutoff_text else None
                    source["coverage_status"] = "stale" if cutoff and cutoff < start else "missing"
                    periods_str = ",".join(covered_months)
                    source["status_note"] = (
                        f"No hay cortes aprobados de Comisarias para los periodos [{periods_str}]."
                        + (f" Ultimo corte disponible: {cutoff.isoformat()}." if cutoff else "")
                    )
                result.append(source)
                continue

            if code == "POLICIA_SEMANAL":
                period_records = db.query(hechos_unicos_expr()).filter(
                    HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
                    HechoSeguridad.fecha_evento >= start,
                    HechoSeguridad.fecha_evento <= min(end, today),
                ).scalar() or 0
                comparison_records = db.query(hechos_unicos_expr()).filter(
                    HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
                    HechoSeguridad.fecha_evento >= prev_start,
                    HechoSeguridad.fecha_evento <= prev_end,
                ).scalar() or 0
            elif code == "INSPECCIONES_RNMC":
                period_records = db.query(InspeccionActuacion.id).filter(
                    *cls.inspection_public_filters(),
                    InspeccionActuacion.fecha_actuacion >= datetime.combine(start, datetime.min.time()),
                    InspeccionActuacion.fecha_actuacion < min(
                        datetime.combine(end + timedelta(days=1), datetime.min.time()),
                        tomorrow,
                    ),
                ).count()
                comparison_records = db.query(InspeccionActuacion.id).filter(
                    *cls.inspection_public_filters(),
                    InspeccionActuacion.fecha_actuacion >= datetime.combine(prev_start, datetime.min.time()),
                    InspeccionActuacion.fecha_actuacion < datetime.combine(prev_end + timedelta(days=1), datetime.min.time()),
                ).count()
            else:
                result.append(source)
                continue

            cutoff_text = source.get("last_cutoff_date")
            cutoff = date.fromisoformat(cutoff_text) if cutoff_text else None
            status = cls.coverage_status(int(period_records), cutoff, start, end)
            quality = source.get("quality_status", "INCOMPLETO")
            note = source.get("status_note")
            if not note:
                if status == "partial":
                    note = f"Cobertura disponible hasta {cutoff.isoformat() if cutoff else 'un corte no informado'}."
                elif status == "stale":
                    note = f"El ultimo corte disponible es anterior al periodo solicitado ({cutoff.isoformat()})."
                elif status == "missing":
                    note = "No hay registros para el periodo solicitado."

            source.update(
                {
                    "period_records": int(period_records),
                    "comparison_records": int(comparison_records),
                    "coverage_status": status,
                    "included": int(period_records) > 0,
                    "comparable": int(comparison_records) > 0,
                    "publishable": int(period_records) > 0 and status == "aligned" and quality == "VALIDADO",
                    "status_note": note,
                }
            )
            result.append(source)
        return result

    @staticmethod
    def available_indicator_codes(source_code: str) -> List[str]:
        if source_code == "POLICIA_SEMANAL":
            return ["seguridad.total", "seguridad.conductas", "seguridad.barrios", "seguridad.tendencia"]
        if source_code == "INSPECCIONES_RNMC":
            return ["convivencia.actuaciones", "convivencia.medidas", "convivencia.estados", "convivencia.territorios"]
        return ["familia.atenciones", "familia.proteccion", "familia.tipologias"]

    @classmethod
    def generate_publication(
        cls,
        db: Session,
        *,
        edition_type: str,
        period_start: Optional[date],
        period_end: Optional[date],
        comparison_mode: str,
        source_codes: Optional[Sequence[str]],
        max_insights: int,
        created_by: Optional[str],
        save_history: bool = False,
    ) -> Dict[str, Any]:
        start, end = cls.period_bounds(edition_type, period_start, period_end)
        prev_start, prev_end, comparison_label, resolved_comparison_mode = cls.comparison_bounds(
            edition_type, comparison_mode, start, end
        )
        selected_sources = list(source_codes or ["POLICIA_SEMANAL", "INSPECCIONES_RNMC", "COMISARIAS_FAMILIA"])
        if not cls.database_available(db):
            return cls.fallback_publication(
                edition_type=edition_type,
                start=start,
                end=end,
                prev_start=prev_start,
                prev_end=prev_end,
                comparison_label=comparison_label,
                comparison_mode=resolved_comparison_mode,
                selected_sources=selected_sources,
                created_by=created_by,
            )

        sources = cls.publication_sources(
            db,
            edition_type=edition_type,
            start=start,
            end=end,
            prev_start=prev_start,
            prev_end=prev_end,
            source_codes=selected_sources,
        )
        included_sources = [source["code"] for source in sources if source.get("included")]
        indicators = cls.collect_indicators(
            db,
            start,
            end,
            prev_start,
            prev_end,
            included_sources,
            edition_type=edition_type,
        )
        insights = cls.select_insights(indicators, max_insights=max_insights, comparison_label=comparison_label)
        slides = cls.build_slides(indicators, insights, start, end)
        applicable_sources = [source for source in sources if source.get("coverage_status") != "not_applicable"]
        review_blockers = [
            source.get("status_note") or f"{source.get('name', source['code'])} requiere revision."
            for source in applicable_sources
            if not source.get("publishable")
        ]

        publication = {
            "id": str(uuid4()),
            "title": "SISC EN CIFRAS",
            "edition_type": edition_type,
            "period": {"start": start.isoformat(), "end": end.isoformat()},
            "comparison_period": {"start": prev_start.isoformat(), "end": prev_end.isoformat()},
            "comparison_label": comparison_label,
            "comparison_mode": resolved_comparison_mode,
            "format": "CAROUSEL_1080x1350",
            "template_code": "SISC_CIFRAS_1080x1350",
            "status": "DRAFT",
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "sources": sources,
            "indicators": [asdict(i) for i in indicators],
            "insights": [asdict(i) for i in insights],
            "slides": slides,
            "governance": {
                "public_only": True,
                "human_review_required": True,
                "publication_ready": bool(indicators) and not review_blockers,
                "history_saved": False,
                "review_blockers": review_blockers,
                "privacy_note": "Solo se usan indicadores agregados y clasificados como PUBLICO.",
                "aggregation_note": "Los dominios se presentan por separado y sus valores no se suman entre si.",
            },
        }

        if save_history:
            publication_id = uuid4()
            publication["id"] = str(publication_id)
            publication["governance"]["history_saved"] = True
            row = SiscCifrasPublication(
                id=publication_id,
                title=publication["title"],
                edition_type=edition_type,
                period_start=start,
                period_end=end,
                created_by=created_by,
                source_codes=selected_sources,
                publication_json=publication,
            )
            db.add(row)
            db.commit()
            db.refresh(row)

        return publication

    @classmethod
    def operational_summary(
        cls,
        db: Session,
        *,
        period_start: date,
        period_end: date,
        comparison_mode: str,
    ) -> Dict[str, Any]:
        """Return the public multi-source contract without building publication assets."""
        start, end = cls.period_bounds("monthly", period_start, period_end)
        prev_start, prev_end, comparison_label, resolved_comparison_mode = cls.comparison_bounds(
            "monthly", comparison_mode, start, end
        )
        selected_sources = ["INSPECCIONES_RNMC", "COMISARIAS_FAMILIA"]

        if not cls.database_available(db):
            fallback = cls.fallback_publication(
                edition_type="monthly",
                start=start,
                end=end,
                prev_start=prev_start,
                prev_end=prev_end,
                comparison_label=comparison_label,
                comparison_mode=resolved_comparison_mode,
                selected_sources=selected_sources,
                created_by=None,
            )
            return {
                "period": fallback["period"],
                "comparison_period": fallback["comparison_period"],
                "comparison_label": fallback["comparison_label"],
                "comparison_mode": fallback["comparison_mode"],
                "generated_at": fallback["generated_at"],
                "sources": fallback["sources"],
                "indicators": [],
                "governance": fallback["governance"],
            }

        sources = cls.publication_sources(
            db,
            edition_type="monthly",
            start=start,
            end=end,
            prev_start=prev_start,
            prev_end=prev_end,
            source_codes=selected_sources,
        )
        included_sources = [source["code"] for source in sources if source.get("included")]
        indicators = cls.collect_indicators(
            db,
            start,
            end,
            prev_start,
            prev_end,
            included_sources,
            edition_type="monthly",
        )

        return {
            "period": {"start": start.isoformat(), "end": end.isoformat()},
            "comparison_period": {"start": prev_start.isoformat(), "end": prev_end.isoformat()},
            "comparison_label": comparison_label,
            "comparison_mode": resolved_comparison_mode,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "sources": sources,
            "indicators": [asdict(indicator) for indicator in indicators],
            "governance": {
                "public_only": True,
                "aggregation_note": (
                    "Inspecciones y Comisarias conservan cortes independientes. "
                    "Sus valores no se suman entre si ni con los hechos de seguridad."
                ),
            },
        }

    @classmethod
    def fallback_publication(
        cls,
        *,
        edition_type: str,
        start: date,
        end: date,
        prev_start: date,
        prev_end: date,
        comparison_label: str,
        comparison_mode: str,
        selected_sources: Sequence[str],
        created_by: Optional[str],
    ) -> Dict[str, Any]:
        sources = []
        for registry_source in cls.fallback_source_registry():
            if registry_source["code"] not in selected_sources:
                continue
            source = dict(registry_source)
            source.update(
                {
                    "requested_period": {"start": start.isoformat(), "end": end.isoformat()},
                    "period_records": 0,
                    "comparison_records": 0,
                    "coverage_status": "missing",
                    "included": False,
                    "comparable": False,
                    "publishable": False,
                    "status_note": "La base de datos no esta disponible para validar esta fuente.",
                }
            )
            sources.append(source)
        return {
            "id": str(uuid4()),
            "title": "SISC EN CIFRAS",
            "edition_type": edition_type,
            "period": {"start": start.isoformat(), "end": end.isoformat()},
            "comparison_period": {"start": prev_start.isoformat(), "end": prev_end.isoformat()},
            "comparison_label": comparison_label,
            "comparison_mode": comparison_mode,
            "format": "CAROUSEL_1080x1350",
            "template_code": "SISC_CIFRAS_1080x1350",
            "status": "DRAFT",
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "created_by": created_by,
            "sources": sources,
            "indicators": [],
            "insights": [],
            "slides": [
                {
                    "type": "cover",
                    "title": "SISC EN CIFRAS",
                    "subtitle": f"Jamundi | {start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}",
                    "blocks": [],
                    "featured": "Base de datos no disponible. Inicie PostgreSQL/PostGIS para calcular indicadores reales.",
                }
            ],
            "governance": {
                "public_only": True,
                "human_review_required": True,
                "publication_ready": False,
                "history_saved": False,
                "review_blockers": ["La base de datos no esta disponible."],
                "privacy_note": "Modo degradado sin datos. No publicar esta pieza.",
                "aggregation_note": "Los dominios se presentan por separado y sus valores no se suman entre si.",
            },
        }

    @classmethod
    def collect_indicators(
        cls,
        db: Session,
        start: date,
        end: date,
        prev_start: date,
        prev_end: date,
        source_codes: Sequence[str],
        edition_type: Optional[str] = None,
    ) -> List[Indicator]:
        indicators: List[Indicator] = []
        if "POLICIA_SEMANAL" in source_codes:
            indicators.extend(cls.police_indicators(db, start, end, prev_start, prev_end))
        if "INSPECCIONES_RNMC" in source_codes:
            indicators.extend(cls.inspection_indicators(db, start, end, prev_start, prev_end))
        if "COMISARIAS_FAMILIA" in source_codes:
            indicators.extend(cls.family_indicators(db, start, end, prev_start, prev_end, edition_type=edition_type))
        return indicators

    @staticmethod
    def quality_status(value: float, cutoff: Optional[Any], min_value: int = 1) -> str:
        if value < min_value or not cutoff:
            return "INCOMPLETO"
        return "VALIDADO"

    @classmethod
    def police_indicators(cls, db: Session, start: date, end: date, prev_start: date, prev_end: date) -> List[Indicator]:
        base_filter = [
            HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
            HechoSeguridad.fecha_evento >= start,
            HechoSeguridad.fecha_evento <= end,
        ]
        prev_filter = [
            HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
            HechoSeguridad.fecha_evento >= prev_start,
            HechoSeguridad.fecha_evento <= prev_end,
        ]
        cutoff = db.query(func.max(HechoSeguridad.fecha_evento)).filter(HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL").scalar()
        total = db.query(hechos_unicos_expr()).filter(*base_filter).scalar() or 0
        prev_total = db.query(hechos_unicos_expr()).filter(*prev_filter).scalar() or 0

        indicators = [
            cls.indicator(
                source="Policia Nacional",
                source_code="POLICIA_SEMANAL",
                domain="SEGURIDAD",
                category="Hechos registrados",
                code="seguridad.total",
                name="Total de hechos registrados",
                value=total,
                unit="hechos registrados",
                start=start,
                end=end,
                comparison_value=prev_total,
                cutoff=cutoff,
                priority=1.0,
            )
        ]

        top_conductas = db.query(
            HechoSeguridad.conducta_estandar,
            hechos_unicos_expr().label("total"),
        ).filter(*base_filter).group_by(HechoSeguridad.conducta_estandar).order_by(desc("total")).limit(6).all()

        prev_by_conducta = dict(
            db.query(HechoSeguridad.conducta_estandar, hechos_unicos_expr().label("total"))
            .filter(*prev_filter)
            .group_by(HechoSeguridad.conducta_estandar)
            .all()
        )

        for name, value in top_conductas:
            clean_name = name or "SIN ESPECIFICAR"
            indicators.append(
                cls.indicator(
                    source="Policia Nacional",
                    source_code="POLICIA_SEMANAL",
                    domain="SEGURIDAD",
                    category="Conducta",
                    code=f"seguridad.conducta.{clean_name[:48]}",
                    name=clean_name,
                    value=value,
                    unit="hechos registrados",
                    start=start,
                    end=end,
                    comparison_value=prev_by_conducta.get(name, 0),
                    cutoff=cutoff,
                    priority=0.8,
                )
            )

        top_barrios = db.query(
            HechoSeguridad.barrio_normalizado,
            hechos_unicos_expr().label("total"),
        ).filter(
            *base_filter,
            HechoSeguridad.barrio_normalizado.isnot(None),
            HechoSeguridad.barrio_normalizado != "",
            func.upper(func.trim(HechoSeguridad.barrio_normalizado)).notin_(NON_PUBLIC_TERRITORY_VALUES),
            ~func.upper(HechoSeguridad.barrio_normalizado).like("%PENDIENTE%"),
            ~func.upper(HechoSeguridad.barrio_normalizado).like("%POR ASIGNAR%"),
            ~func.upper(HechoSeguridad.barrio_normalizado).like("%NO APLICA%"),
            ~func.upper(HechoSeguridad.barrio_normalizado).like("%NO DEFINIDO%"),
        ).group_by(HechoSeguridad.barrio_normalizado).having(hechos_unicos_expr() >= MIN_PUBLIC_TERRITORIAL_COUNT).order_by(desc("total")).limit(5).all()

        for barrio, value in top_barrios:
            if not is_public_territory_name(barrio):
                continue
            share = (value / total) if total else 0
            indicators.append(
                cls.indicator(
                    source="Policia Nacional",
                    source_code="POLICIA_SEMANAL",
                    domain="TERRITORIO",
                    category="Concentracion territorial",
                    code=f"territorio.seguridad.{barrio[:48]}",
                    name=f"{barrio}",
                    value=value,
                    unit="hechos registrados",
                    start=start,
                    end=end,
                    comparison_value=None,
                    cutoff=cutoff,
                    priority=0.65,
                    geography=barrio,
                    metadata={"territorial_share": round(share, 4)},
                )
            )
        return indicators

    @classmethod
    def inspection_indicators(cls, db: Session, start: date, end: date, prev_start: date, prev_end: date) -> List[Indicator]:
        tomorrow = datetime.combine(date.today() + timedelta(days=1), datetime.min.time())
        start_dt = datetime.combine(start, datetime.min.time())
        end_dt = min(datetime.combine(end + timedelta(days=1), datetime.min.time()), tomorrow)
        prev_start_dt = datetime.combine(prev_start, datetime.min.time())
        prev_end_dt = datetime.combine(prev_end + timedelta(days=1), datetime.min.time())

        base_filter = [
            *cls.inspection_public_filters(),
            InspeccionActuacion.fecha_actuacion >= start_dt,
            InspeccionActuacion.fecha_actuacion < end_dt,
            InspeccionActuacion.fecha_actuacion < tomorrow,
        ]
        prev_filter = [
            *cls.inspection_public_filters(),
            InspeccionActuacion.fecha_actuacion >= prev_start_dt,
            InspeccionActuacion.fecha_actuacion < prev_end_dt,
            InspeccionActuacion.fecha_actuacion < tomorrow,
        ]
        cutoff = db.query(func.max(InspeccionActuacion.fecha_actuacion)).filter(*base_filter).scalar()
        total = db.query(InspeccionActuacion.id).filter(*base_filter).count()
        prev_total = db.query(InspeccionActuacion.id).filter(*prev_filter).count()

        indicators = [
            cls.indicator(
                source="Inspecciones de Policia / RNMC",
                source_code="INSPECCIONES_RNMC",
                domain="CONVIVENCIA",
                category="Actuaciones",
                code="convivencia.actuaciones",
                name="Actuaciones registradas",
                value=total,
                unit="actuaciones registradas",
                start=start,
                end=end,
                comparison_value=prev_total,
                cutoff=cutoff,
                priority=0.85,
            )
        ]

        top_medidas = db.query(
            InspeccionMedida.nombre_medida,
            func.count(InspeccionActuacion.id).label("total"),
        ).join(InspeccionActuacion).filter(*base_filter).group_by(InspeccionMedida.nombre_medida).order_by(desc("total")).limit(10).all()
        previous_measures = {
            name or "SIN ESPECIFICAR": value
            for name, value in db.query(
                InspeccionMedida.nombre_medida,
                func.count(InspeccionActuacion.id).label("total"),
            ).join(InspeccionActuacion).filter(*prev_filter).group_by(InspeccionMedida.nombre_medida).all()
        }

        for name, value in top_medidas:
            clean_name = name or "SIN ESPECIFICAR"
            public_name, technical_name = public_measure_label(clean_name)
            # A missing measure is a data-quality issue, not citizen-facing content.
            if not public_name:
                continue
            public_detail = public_measure_detail(clean_name)
            metadata = {}
            if technical_name:
                metadata["technical_name"] = technical_name
            if public_detail:
                metadata["public_detail"] = public_detail
            indicators.append(
                cls.indicator(
                    source="Inspecciones de Policia / RNMC",
                    source_code="INSPECCIONES_RNMC",
                    domain="CONVIVENCIA",
                    category="Medida",
                    code=f"convivencia.medida.{clean_name[:48]}",
                    name=public_name,
                    value=value,
                    unit="actuaciones registradas",
                    start=start,
                    end=end,
                    comparison_value=previous_measures.get(clean_name),
                    cutoff=cutoff,
                    priority=0.65,
                    metadata=metadata or None,
                )
            )
            if len([item for item in indicators if item.category == "Medida"]) >= 4:
                break

        top_localidades = db.query(
            InspeccionExpediente.localidad,
            func.count(InspeccionActuacion.id).label("total"),
        ).join(InspeccionMedida, InspeccionExpediente.id == InspeccionMedida.expediente_id).join(
            InspeccionActuacion, InspeccionMedida.id == InspeccionActuacion.medida_id
        ).filter(
            *base_filter,
            InspeccionExpediente.localidad.isnot(None),
            InspeccionExpediente.localidad != "",
            func.upper(func.trim(InspeccionExpediente.localidad)).notin_(NON_PUBLIC_TERRITORY_VALUES),
            ~func.upper(InspeccionExpediente.localidad).like("%PENDIENTE%"),
            ~func.upper(InspeccionExpediente.localidad).like("%POR ASIGNAR%"),
            ~func.upper(InspeccionExpediente.localidad).like("%NO APLICA%"),
            ~func.upper(InspeccionExpediente.localidad).like("%NO DEFINIDO%"),
            ~func.upper(InspeccionExpediente.localidad).like("%SIN LOCALIDAD%"),
            ~func.upper(InspeccionExpediente.localidad).like("%SIN COMUNA%"),
        ).group_by(
            InspeccionExpediente.localidad
        ).having(func.count(InspeccionActuacion.id) >= MIN_PUBLIC_TERRITORIAL_COUNT).order_by(desc("total")).limit(5).all()

        for localidad, value in top_localidades:
            if not is_public_territory_name(localidad):
                continue
            share = (value / total) if total else 0
            indicators.append(
                cls.indicator(
                    source="Inspecciones de Policia / RNMC",
                    source_code="INSPECCIONES_RNMC",
                    domain="TERRITORIO",
                    category="Concentracion territorial",
                    code=f"territorio.convivencia.{localidad[:48]}",
                    name=localidad,
                    value=value,
                    unit="actuaciones registradas",
                    start=start,
                    end=end,
                    comparison_value=None,
                    cutoff=cutoff,
                    priority=0.6,
                    geography=localidad,
                    metadata={"territorial_share": round(share, 4)},
                )
            )
        return indicators

    @classmethod
    def family_indicators(
        cls,
        db: Session,
        start: date,
        end: date,
        prev_start: date,
        prev_end: date,
        *,
        edition_type: Optional[str] = None,
    ) -> List[Indicator]:
        latest_batches, _ = cls._resolve_institutional_batches(
            db, "COMISARIAS", start, end,
        )
        if not latest_batches:
            return []

        prev_batches, _ = cls._resolve_institutional_batches(
            db, "COMISARIAS", prev_start, prev_end,
        )

        previous_values: Dict[Tuple[str, str], float] = {}
        for previous_batch in prev_batches:
            previous_values.update({
                (previous_batch.reporting_entity, item.indicator): float(item.value)
                for item in previous_batch.indicators
                if item.is_public and float(item.value) >= item.privacy_threshold
            })

        public_items = [
            (batch, item)
            for batch in latest_batches
            for item in batch.indicators
            if item.is_public and float(item.value) >= item.privacy_threshold
        ]
        if not public_items:
            return []

        def family_priority(item: InstitutionalIndicator) -> float:
            name = item.indicator.upper()
            if "VIOLENCIA INTRAFAMILIAR" in name:
                return 0.95
            if "MEDIDAS DE PROTECCION URGENTES" in name:
                return 0.9
            if "RESTABLECIMIENTO DE DERECHOS" in name:
                return 0.86
            if "VIOLENCIA" in name or "PROTECCION" in name:
                return 0.82
            return 0.7

        indicators: List[Indicator] = []
        ordered_items = sorted(
            public_items,
            key=lambda pair: (family_priority(pair[1]), float(pair[1].value)),
            reverse=True,
        )[:6]
        for batch, item in ordered_items:
            priority = family_priority(item)
            indicators.append(
                cls.indicator(
                    source="Comisarias de Familia",
                    source_code="COMISARIAS_FAMILIA",
                    domain="FAMILIA Y PROTECCION",
                    category=item.category or "Indicador agregado",
                    code=f"familia.indicador.{batch.reporting_entity[:20]}.{item.indicator[:32]}",
                    name=item.indicator,
                    value=float(item.value),
                    unit=item.unit,
                    start=start,
                    end=end,
                    comparison_value=previous_values.get((batch.reporting_entity, item.indicator)),
                    cutoff=batch.cutoff_date,
                    priority=priority,
                    metadata={
                        "period": batch.period,
                        "reporting_entity": batch.reporting_entity,
                        "reporting_basis": batch.reporting_basis,
                        "privacy_threshold": item.privacy_threshold,
                        "privacy_threshold_applied": True,
                    },
                )
            )
        return indicators

    @classmethod
    def indicator(
        cls,
        *,
        source: str,
        source_code: str,
        domain: str,
        category: str,
        code: str,
        name: str,
        value: float,
        unit: str,
        start: date,
        end: date,
        comparison_value: Optional[float],
        cutoff: Optional[Any],
        priority: float,
        geography: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Indicator:
        variation_abs = value - comparison_value if comparison_value is not None else None
        variation_pct = pct_change(value, comparison_value)
        quality = cls.quality_status(value, cutoff)
        cutoff_date = cutoff.date().isoformat() if hasattr(cutoff, "date") else cutoff.isoformat() if cutoff else None
        meta = metadata or {}
        meta["priority"] = priority
        meta["relevance_score"] = calculate_relevance(
            value=value,
            variation_percentage=variation_pct,
            priority=priority,
            quality_status=quality,
            territorial_share=meta.get("territorial_share"),
        )
        return Indicator(
            id=f"{source_code}:{code}:{geography or 'TOTAL'}",
            source=source,
            source_code=source_code,
            domain=domain,
            category=category,
            indicator_code=code,
            indicator_name=name,
            value=float(value or 0),
            unit=unit,
            period_start=start.isoformat(),
            period_end=end.isoformat(),
            geography=geography,
            comparison_value=float(comparison_value) if comparison_value is not None else None,
            variation_absolute=float(variation_abs) if variation_abs is not None else None,
            variation_percentage=round(variation_pct, 2) if variation_pct is not None else None,
            quality_status=quality,
            publication_level="PUBLICO",
            cutoff_date=cutoff_date,
            metadata=meta,
        )

    @classmethod
    def select_insights(
        cls,
        indicators: Iterable[Indicator],
        max_insights: int = 5,
        comparison_label: str = "mismo periodo del ano anterior",
    ) -> List[Insight]:
        candidates = [
            i for i in indicators
            if i.publication_level == "PUBLICO" and i.quality_status in ("VALIDADO", "PRELIMINAR")
        ]
        candidates.sort(key=lambda item: item.metadata.get("relevance_score", 0), reverse=True)
        # The public "Que cambio" story must lead with a real comparison. Volume-only
        # rows remain available in their domain slide, but do not displace a trend.
        comparable = [item for item in candidates if item.variation_percentage is not None]
        if comparable:
            candidates = comparable + [item for item in candidates if item.variation_percentage is None]

        insights: List[Insight] = []
        used_domains = set()
        for indicator in candidates:
            if len(insights) >= max_insights:
                break
            if indicator.domain in used_domains and len(insights) < 2:
                continue
            used_domains.add(indicator.domain)
            insights.append(cls.insight_from_indicator(indicator, comparison_label=comparison_label))
        return insights

    @staticmethod
    def insight_from_indicator(indicator: Indicator, comparison_label: str = "mismo periodo del ano anterior") -> Insight:
        value = int(indicator.value) if float(indicator.value).is_integer() else indicator.value
        delta = variation_text(indicator.variation_percentage)
        if indicator.variation_percentage is None:
            detail = f"{indicator.indicator_name}: {value} {indicator.unit} en el periodo."
        else:
            verb = "aumento" if indicator.variation_percentage > 0 else "disminuyo" if indicator.variation_percentage < 0 else "se mantuvo"
            detail = f"{indicator.indicator_name} {verb} {abs(indicator.variation_percentage):.1f}% frente al {comparison_label}."

        return Insight(
            id=f"insight:{indicator.id}",
            domain=indicator.domain,
            source=indicator.source,
            indicator_code=indicator.indicator_code,
            title=indicator.indicator_name,
            value_text=f"{value} {indicator.unit}",
            detail=detail,
            relevance_score=indicator.metadata.get("relevance_score", 0),
            quality_status=indicator.quality_status,
            cutoff_date=indicator.cutoff_date,
            chart_type="bar" if indicator.geography else "kpi",
            evidence_indicator_ids=[indicator.id],
        )

    @classmethod
    def build_slides(cls, indicators: List[Indicator], insights: List[Insight], start: date, end: date) -> List[Dict[str, Any]]:
        by_domain: Dict[str, List[Indicator]] = {}
        for indicator in indicators:
            by_domain.setdefault(indicator.domain, []).append(indicator)

        slides = [
            {
                "type": "cover",
                "title": "SISC EN CIFRAS",
                "subtitle": f"Jamundi | {start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}",
                "blocks": [
                    cls.domain_block(domain, values)
                    for domain, values in by_domain.items()
                    if domain != "TERRITORIO"
                ],
                "featured": insights[0].detail if insights else "No hay hallazgos publicables para el periodo seleccionado.",
            }
        ]

        for domain in ("SEGURIDAD", "CONVIVENCIA", "TERRITORIO"):
            domain_indicators = by_domain.get(domain, [])
            if domain == "CONVIVENCIA":
                domain_indicators = domain_indicators + by_domain.get("FAMILIA Y PROTECCION", [])
            domain_insights = [i for i in insights if i.domain == domain]
            if domain == "CONVIVENCIA":
                domain_insights = domain_insights + [i for i in insights if i.domain == "FAMILIA Y PROTECCION"]
            if not domain_indicators and not domain_insights:
                continue
            slides.append(
                {
                    "type": "domain",
                    "title": domain,
                    "subtitle": cls.domain_subtitle(domain),
                    "indicators": [asdict(i) for i in domain_indicators[:6]],
                    "insights": [asdict(i) for i in domain_insights[:3]],
                    "featured": cls.domain_featured(domain, domain_indicators, domain_insights),
                    "chart": cls.chart_payload(domain_indicators),
                }
            )

        comparable_codes = {
            indicator.indicator_code
            for indicator in indicators
            if indicator.variation_percentage is not None
        }
        comparison_insights = [insight for insight in insights if insight.indicator_code in comparable_codes]
        if insights:
            slides.append(
                {
                    "type": "changes",
                    "title": "QUE CAMBIO",
                    "subtitle": "Principales comparaciones del periodo",
                    "insights": [asdict(i) for i in comparison_insights[:4]],
                }
            )
        return slides

    @staticmethod
    def domain_block(domain: str, indicators: List[Indicator]) -> Dict[str, Any]:
        total = next((i for i in indicators if i.indicator_code.endswith("total") or i.indicator_code.endswith("actuaciones")), indicators[0])
        return {
            "domain": domain,
            "value": int(total.value),
            "unit": total.unit,
            "variation": total.variation_percentage,
            "cutoff_date": total.cutoff_date,
            "quality_status": total.quality_status,
        }

    @staticmethod
    def domain_subtitle(domain: str) -> str:
        return {
            "SEGURIDAD": "Hechos registrados, conductas y variaciones.",
            "CONVIVENCIA": "Medidas de convivencia y atencion a familias.",
            "FAMILIA Y PROTECCION": "Informacion agregada y anonimizada.",
            "TERRITORIO": "Zonas con mayor numero de hechos registrados en el periodo.",
        }.get(domain, "Indicadores agregados del periodo.")

    @staticmethod
    def domain_featured(domain: str, indicators: List[Indicator], insights: List[Insight]) -> str:
        if insights:
            return insights[0].detail
        if domain == "TERRITORIO":
            top = next((item for item in indicators if item.geography), None)
            if top:
                return f"{top.geography} registro {int(top.value)} {top.unit} en el periodo."
            return "No hay zonas con datos territoriales publicables para destacar en este periodo."
        return "Indicadores agregados disponibles para el periodo seleccionado."

    @staticmethod
    def chart_payload(indicators: List[Indicator]) -> Dict[str, Any]:
        rows = [
            {"name": i.geography or i.indicator_name, "value": i.value, "unit": i.unit}
            for i in indicators
            if not i.indicator_code.endswith("total") and not i.indicator_code.endswith("actuaciones")
        ][:6]
        return {"type": "bar", "data": rows}

    @staticmethod
    def list_publications(db: Session, limit: int = 20) -> List[Dict[str, Any]]:
        rows = db.query(SiscCifrasPublication).order_by(SiscCifrasPublication.created_at.desc()).limit(limit).all()
        return [
            {
                "id": str(row.id),
                "title": row.title,
                "edition_type": row.edition_type,
                "period_start": row.period_start.isoformat(),
                "period_end": row.period_end.isoformat(),
                "status": row.status,
                "created_by": row.created_by,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "source_codes": row.source_codes,
            }
            for row in rows
        ]

    # --- Fase 1.5: métodos nuevos para contrato v1 ---

    @staticmethod
    def get_capabilities() -> Dict[str, Any]:
        from middleware.rate_limit import get_rate_limit_info
        catalog_versions = SiscCifrasService._load_catalog_versions()
        return {
            "schema_version": "1.0",
            "status": "ok",
            "supported_modes": [
                "OFFICIAL_PUBLICATION",
                "PUBLIC_EXPLORATION",
                "INSTITUTIONAL_ANALYSIS",
            ],
            "supported_bulletin_types": [
                "WEEKLY", "MONTHLY", "SEMESTER", "ANNUAL", "TERRITORIAL_SPECIAL",
            ],
            "available_sources": [
                "POLICIA_SEMANAL", "INSPECCIONES_RNMC", "COMISARIAS_FAMILIA",
            ],
            "territory_scopes": [
                "TODO_JAMUNDI", "ZONA", "COMUNA", "CORREGIMIENTO",
                "BARRIO", "CAI", "DEPENDENCIA",
            ],
            "conducta_modes": [
                "ALL_PRIORITIZED", "SPECIFIC", "TOP_INCREASE",
                "TOP_DECREASE", "HIGHEST_COUNT",
            ],
            "dimensions": [
                "franja_horaria", "dia_semana", "zona", "modalidad",
                "arma_medio", "clase_sitio", "grupo_edad", "genero",
            ],
            "max_period_days": 366,
            "catalog_versions": catalog_versions,
            "rate_limit": get_rate_limit_info(),
        }

    @staticmethod
    def get_catalog(catalog_name: str) -> Dict[str, Any]:
        import json
        from pathlib import Path
        catalogs_dir = Path(__file__).resolve().parents[1] / "data" / "catalogs"
        actual_name = "territorios" if catalog_name == "barrios" else catalog_name
        cat_file = catalogs_dir / f"{actual_name}.json"
        if not cat_file.exists():
            return {"status": "error", "error_code": "CATALOG_VERSION_MISMATCH", "message": f"Catálogo '{catalog_name}' no encontrado."}
        with open(cat_file, encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("items", [])
        return {
            "schema_version": "1.0",
            "status": "ok",
            "catalog": catalog_name,
            "version": data.get("version", "unknown"),
            "count": len(items),
            "items": items,
        }

    @staticmethod
    def _load_catalog_versions() -> Dict[str, Any]:
        import json
        from pathlib import Path
        catalogs_dir = Path(__file__).resolve().parents[1] / "data" / "catalogs"
        mapping = {"conductas": "conductas", "presets": "presets", "territorios": "barrios"}
        versions: Dict[str, Any] = {}
        for file_key, response_key in mapping.items():
            cat_file = catalogs_dir / f"{file_key}.json"
            if cat_file.exists():
                with open(cat_file, encoding="utf-8") as f:
                    data = json.load(f)
                versions[response_key] = data.get("version", "unknown")
        return versions

    @staticmethod
    def build_snapshot_from_publication(
        publication: Dict[str, Any],
        requested_filters: Dict[str, Any],
        resolved_filters: Dict[str, Any],
        catalog_versions: Dict[str, Any],
        suppressed_cells: List[Dict[str, Any]],
        created_by: str,
        pdf_url: str,
    ) -> Dict[str, Any]:
        import hashlib, json as _json
        period = publication.get("period", {})
        comp = publication.get("comparison_period", {})
        sources_data = publication.get("sources", [])

        active_sources = [s.get("code") for s in sources_data if s.get("included")]
        cutoff_str = period.get("end", date.today().isoformat())
        records: Dict[str, Any] = {}
        for s in sources_data:
            code = s.get("code", "")
            if code in ("POLICIA_SEMANAL", "INSPECCIONES_RNMC", "COMISARIAS_FAMILIA"):
                records[code] = s.get("period_records", 0)

        snapshot = {
            "requested_filters": requested_filters,
            "resolved_filters": resolved_filters,
            "catalog_versions_used": catalog_versions,
            "warnings": [],
            "suppressed_cells": suppressed_cells,
            "generated_at": publication.get("generated_at", datetime.utcnow().isoformat() + "Z"),
            "published_at": datetime.utcnow().isoformat() + "Z",
            "created_by": created_by,
            "pdf_url": pdf_url,
            "previous_version_id": None,
        }

        payload = _json.dumps(
            {k: v for k, v in snapshot.items() if k != "hash_integrity"},
            sort_keys=True, default=str,
        )
        h = hashlib.sha256(payload.encode()).hexdigest()
        snapshot["hash_integrity"] = {"algorithm": "sha256", "value": h}
        return snapshot

    @staticmethod
    def generate_query_hash(
        filters: Dict[str, Any],
        resolved: Dict[str, Any],
        catalog_versions: Dict[str, Any],
        dataset_identity: Optional[Dict[str, Any]] = None,
    ) -> str:
        import hashlib, json
        identity = {
            "requested": filters,
            "resolved": resolved,
            "catalogs": catalog_versions,
            "dataset": dataset_identity or {},
        }
        payload = json.dumps(identity, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def adapt_legacy_publication(row: SiscCifrasPublication) -> Dict[str, Any]:
        import hashlib as _hashlib, json as _json
        pub = dict(row.publication_json) if row.publication_json else {}
        period = pub.get("period", {})
        comp = pub.get("comparison_period", {})
        sources_data = pub.get("sources", [])
        active_sources = [s.get("code") for s in sources_data if s.get("included")]
        records: Dict[str, Any] = {}
        for s in sources_data:
            code = s.get("code", "")
            if code in ("POLICIA_SEMANAL", "INSPECCIONES_RNMC", "COMISARIAS_FAMILIA"):
                records[code] = s.get("period_records", 0)

        raw_mode = pub.get("comparison_mode", "YEAR_OVER_YEAR")
        comparison_mode = raw_mode.upper() if raw_mode else "YEAR_OVER_YEAR"

        resolved_filters = {
            "period": {
                "start": period.get("start", ""),
                "end": period.get("end", ""),
                "timezone": "America/Bogota",
                "days": 7,
            },
            "comparison": {
                "mode": comparison_mode,
                "resolved_by_backend": True,
                "start": comp.get("start"),
                "end": comp.get("end"),
            },
            "sources": {
                "active": active_sources,
                "cutoff_used": period.get("end", ""),
                "records": records,
            },
            "territory": {
                "scope": "TODO_JAMUNDI",
                "resolved_barrios": ["TODO_JAMUNDI"],
            },
            "conductas": {
                "mode": "ALL_PRIORITIZED",
                "resolved_codes": [],
            },
        }
        pdf_url = row.pdf_url or f"/api/sisc-cifras/publications/{row.id}/pdf"
        hash_val = row.hash_integrity.get("value", "") if row.hash_integrity else ""
        if len(hash_val) != 64:
            hash_val = _hashlib.sha256(_json.dumps(pub, sort_keys=True, default=str).encode()).hexdigest()
        return {
            "requested_filters": row.requested_filters or {},
            "resolved_filters": resolved_filters,
            "catalog_versions_used": row.catalog_versions_used or {},
            "warnings": [],
            "suppressed_cells": row.suppressed_cells or [],
            "hash_integrity": {"algorithm": "sha256", "value": hash_val},
            "generated_at": pub.get("generated_at", ""),
            "published_at": row.created_at.isoformat() if row.created_at else "",
            "created_by": row.created_by or "legacy",
            "pdf_url": pdf_url,
            "previous_version_id": None,
        }

    @staticmethod
    def find_existing_by_query_hash(db: Session, query_hash: str) -> Optional[SiscCifrasPublication]:
        return (
            db.query(SiscCifrasPublication)
            .filter(
                SiscCifrasPublication.query_hash == query_hash,
                SiscCifrasPublication.status != "SUPERSEDED",
            )
            .first()
        )

    @classmethod
    def collect_dataset_identity(cls, db: Session, start: date, end: date) -> Dict[str, Any]:
        identity: Dict[str, Any] = {}
        today = date.today()
        tomorrow = datetime.combine(today + timedelta(days=1), datetime.min.time())

        if not cls.database_available(db):
            return {"POLICIA_SEMANAL": {}, "INSPECCIONES_RNMC": {}, "COMISARIAS_FAMILIA": {}}

        from sqlalchemy import text as sql_text

        cutoff_policia = db.query(func.max(HechoSeguridad.fecha_evento)).filter(
            HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL"
        ).scalar()
        unique_policia = int(db.query(hechos_unicos_expr()).filter(
            HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
            HechoSeguridad.fecha_evento >= start,
            HechoSeguridad.fecha_evento <= min(end, today),
        ).scalar() or 0)

        content_hash_policia = db.query(
            func.md5(func.string_agg(HechoSeguridad.fingerprint, sql_text("'|' ORDER BY fingerprint")))
        ).filter(
            HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
            HechoSeguridad.fecha_evento >= start,
            HechoSeguridad.fecha_evento <= min(end, today),
            HechoSeguridad.fingerprint.isnot(None),
        ).scalar()

        identity["POLICIA_SEMANAL"] = {
            "cutoff_date": cls.iso_date(cutoff_policia),
            "unique_count": unique_policia,
            "content_hash": content_hash_policia,
        }

        cutoff_insp = db.query(func.max(InspeccionActuacion.fecha_actuacion)).filter(
            *cls.inspection_public_filters(),
        ).scalar()
        unique_insp = db.query(InspeccionActuacion.id).filter(
            *cls.inspection_public_filters(),
            InspeccionActuacion.fecha_actuacion >= datetime.combine(start, datetime.min.time()),
            InspeccionActuacion.fecha_actuacion < min(
                datetime.combine(end + timedelta(days=1), datetime.min.time()), tomorrow
            ),
        ).count()

        content_hash_insp = db.query(
            func.md5(func.string_agg(InspeccionActuacion.fingerprint_hash, sql_text("'|' ORDER BY fingerprint_hash")))
        ).filter(
            *cls.inspection_public_filters(),
            InspeccionActuacion.fecha_actuacion >= datetime.combine(start, datetime.min.time()),
            InspeccionActuacion.fecha_actuacion < min(
                datetime.combine(end + timedelta(days=1), datetime.min.time()), tomorrow
            ),
            InspeccionActuacion.fingerprint_hash.isnot(None),
        ).scalar()

        identity["INSPECCIONES_RNMC"] = {
            "cutoff_date": cls.iso_date(cutoff_insp),
            "unique_count": unique_insp,
            "content_hash": content_hash_insp,
        }

        cutoff_comis = db.query(func.max(InstitutionalDataBatch.cutoff_date)).filter(
            InstitutionalDataBatch.program == "COMISARIAS",
            InstitutionalDataBatch.validation_status == "APPROVED",
        ).scalar()
        unique_comis = db.query(InstitutionalIndicator.id).join(
            InstitutionalDataBatch,
            InstitutionalIndicator.batch_id == InstitutionalDataBatch.id,
        ).filter(
            InstitutionalDataBatch.program == "COMISARIAS",
            InstitutionalDataBatch.validation_status == "APPROVED",
            InstitutionalIndicator.is_public.is_(True),
        ).count()

        latest_batch = db.query(InstitutionalDataBatch).filter(
            InstitutionalDataBatch.program == "COMISARIAS",
            InstitutionalDataBatch.validation_status == "APPROVED",
        ).order_by(
            InstitutionalDataBatch.version.desc(),
            InstitutionalDataBatch.created_at.desc(),
        ).first()

        source_hash_comis = None
        latest_batch_id = None
        if latest_batch:
            latest_batch_id = str(latest_batch.id)
            agent_run = db.query(InstitutionalAgentRun).filter(
                InstitutionalAgentRun.batch_id == latest_batch.id,
            ).order_by(InstitutionalAgentRun.started_at.desc()).first()
            if agent_run:
                source_hash_comis = agent_run.source_sha256

        identity["COMISARIAS_FAMILIA"] = {
            "cutoff_date": cls.iso_date(cutoff_comis),
            "unique_count": unique_comis,
            "latest_batch_id": latest_batch_id,
            "content_hash": source_hash_comis,
        }
        return identity

    @classmethod
    def query_explore_data(
        cls,
        db: Session,
        *,
        edition_type: Optional[str] = None,
        period_start: date,
        period_end: date,
        comparison_mode: str,
        source_codes: List[str],
        territory_scope: str,
        territory_codes: List[str],
        conducta_mode: str,
        conducta_codes: List[str],
    ) -> Dict[str, Any]:
        start, end = cls.period_bounds(edition_type, period_start, period_end)
        prev_start, prev_end, comparison_label, resolved_comparison_mode = cls.comparison_bounds(
            edition_type, comparison_mode, start, end
        )

        if not cls.database_available(db):
            return {"indicators": [], "sources": [], "resolved_comparison_mode": resolved_comparison_mode,
                    "comparison_label": comparison_label, "start": start, "end": end}

        indicators = cls.collect_indicators(
            db, start, end, prev_start, prev_end, source_codes, edition_type=edition_type,
        )

        if conducta_mode == "SPECIFIC" and conducta_codes:
            allowed = set(c.upper() for c in conducta_codes)
            aliases = cls._load_conducta_aliases()
            code_to_aliases = {}
            for code, alias_list in aliases.items():
                code_to_aliases[code.upper()] = {a.upper() for a in alias_list}
                code_to_aliases[code.upper()].add(code.upper())
            matched_names: set = set()
            for code in allowed:
                matched_names.update(code_to_aliases.get(code, {code}))
            indicators = [
                i for i in indicators
                if i.indicator_name.upper() in matched_names
                or i.indicator_code.upper() in matched_names
                or i.category == "Conducta"
            ]

        sources = cls.publication_sources(
            db, edition_type=edition_type, start=start, end=end,
            prev_start=prev_start, prev_end=prev_end, source_codes=source_codes,
        )
        return {
            "indicators": indicators,
            "sources": sources,
            "resolved_comparison_mode": resolved_comparison_mode,
            "comparison_label": comparison_label,
            "start": start,
            "end": end,
        }

    @staticmethod
    def _load_conducta_aliases() -> Dict[str, List[str]]:
        import json
        from pathlib import Path
        catalogs_dir = Path(__file__).resolve().parents[1] / "data" / "catalogs"
        cat_file = catalogs_dir / "conductas.json"
        if not cat_file.exists():
            return {}
        with open(cat_file, encoding="utf-8") as f:
            data = json.load(f)
        return {item["code"]: item.get("aliases", []) for item in data.get("items", [])}
