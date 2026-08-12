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
from db.models_institutional import InstitutionalDataBatch, InstitutionalIndicator
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
            "periodicity": "Segun disponibilidad",
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
    def period_bounds(mode: str, period_start: Optional[date], period_end: Optional[date]) -> Tuple[date, date]:
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
    def year_over_year_bounds(start: date, end: date) -> Tuple[date, date]:
        try:
            return start.replace(year=start.year - 1), end.replace(year=end.year - 1)
        except ValueError:
            duration = end - start
            comparison_start = start - timedelta(days=365)
            return comparison_start, comparison_start + duration

    @classmethod
    def comparison_bounds(cls, edition_type: str, mode: str, start: date, end: date) -> Tuple[date, date, str, str]:
        selected = (mode or "auto").lower()
        if selected == "auto":
            selected = "previous_period" if edition_type == "monthly" else "year_over_year"

        if selected in ("previous_period", "previous", "periodo_anterior"):
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
                "available_records": 0,
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

        registry = []
        for code, meta in cls.SOURCE_CATALOG.items():
            row = {**meta, "code": code}
            if code == "POLICIA_SEMANAL":
                cutoff = db.query(func.max(HechoSeguridad.fecha_evento)).filter(
                    HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL"
                ).scalar()
                total = db.query(HechoSeguridad.id).filter(
                    HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL"
                ).count()
            elif code == "INSPECCIONES_RNMC":
                cutoff = db.query(func.max(InspeccionActuacion.fecha_actuacion)).scalar()
                total = db.query(InspeccionActuacion.id).count()
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
            else:
                cutoff = None
                total = 0

            quality = "VALIDADO" if total > 0 and cutoff else "INCOMPLETO"
            row.update(
                {
                    "last_cutoff_date": cutoff.date().isoformat() if hasattr(cutoff, "date") else cutoff.isoformat() if cutoff else None,
                    "available_records": total,
                    "quality_status": quality,
                    "publication_level": "PUBLICO",
                    "available_indicators": cls.available_indicator_codes(code),
                }
            )
            registry.append(row)
        return registry

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
        save_history: bool = True,
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

        indicators = cls.collect_indicators(db, start, end, prev_start, prev_end, selected_sources)
        insights = cls.select_insights(indicators, max_insights=max_insights, comparison_label=comparison_label)
        slides = cls.build_slides(indicators, insights, start, end)
        sources = [s for s in cls.source_registry(db) if s["code"] in selected_sources]

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
                "privacy_note": "Solo se usan indicadores agregados y clasificados como PUBLICO.",
            },
        }

        if save_history:
            row = SiscCifrasPublication(
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
            publication["id"] = str(row.id)

        return publication

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
        sources = [s for s in cls.fallback_source_registry() if s["code"] in selected_sources]
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
                "privacy_note": "Modo degradado sin datos. No publicar esta pieza.",
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
    ) -> List[Indicator]:
        indicators: List[Indicator] = []
        if "POLICIA_SEMANAL" in source_codes:
            indicators.extend(cls.police_indicators(db, start, end, prev_start, prev_end))
        if "INSPECCIONES_RNMC" in source_codes:
            indicators.extend(cls.inspection_indicators(db, start, end, prev_start, prev_end))
        if "COMISARIAS_FAMILIA" in source_codes:
            indicators.extend(cls.family_indicators(db, start, end, prev_start, prev_end))
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
        start_dt = datetime.combine(start, datetime.min.time())
        end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time())
        prev_start_dt = datetime.combine(prev_start, datetime.min.time())
        prev_end_dt = datetime.combine(prev_end + timedelta(days=1), datetime.min.time())

        base_filter = [InspeccionActuacion.fecha_actuacion >= start_dt, InspeccionActuacion.fecha_actuacion < end_dt]
        prev_filter = [InspeccionActuacion.fecha_actuacion >= prev_start_dt, InspeccionActuacion.fecha_actuacion < prev_end_dt]
        cutoff = db.query(func.max(InspeccionActuacion.fecha_actuacion)).scalar()
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
                    comparison_value=None,
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
    def family_indicators(cls, db: Session, start: date, end: date, prev_start: date, prev_end: date) -> List[Indicator]:
        latest_batch = db.query(InstitutionalDataBatch).filter(
            InstitutionalDataBatch.program == "COMISARIAS",
            InstitutionalDataBatch.validation_status == "APPROVED",
            InstitutionalDataBatch.cutoff_date <= end,
        ).order_by(InstitutionalDataBatch.cutoff_date.desc(), InstitutionalDataBatch.version.desc()).first()
        if not latest_batch:
            return []

        previous_batch = db.query(InstitutionalDataBatch).filter(
            InstitutionalDataBatch.program == "COMISARIAS",
            InstitutionalDataBatch.validation_status == "APPROVED",
            InstitutionalDataBatch.cutoff_date <= prev_end,
        ).order_by(InstitutionalDataBatch.cutoff_date.desc(), InstitutionalDataBatch.version.desc()).first()

        previous_values = {}
        if previous_batch:
            previous_values = {
                item.indicator: float(item.value)
                for item in previous_batch.indicators
                if item.is_public and float(item.value) >= item.privacy_threshold
            }

        public_items = [
            item for item in latest_batch.indicators
            if item.is_public and float(item.value) >= item.privacy_threshold
        ]
        if not public_items:
            return []

        total_value = sum(float(item.value) for item in public_items)
        previous_total = sum(previous_values.values()) if previous_values else None
        indicators = [
            cls.indicator(
                source="Comisarias de Familia",
                source_code="COMISARIAS_FAMILIA",
                domain="FAMILIA Y PROTECCION",
                category="Atencion institucional",
                code="familia.total_publicable",
                name="Registros agregados publicables",
                value=total_value,
                unit="registros agregados",
                start=start,
                end=end,
                comparison_value=previous_total,
                cutoff=latest_batch.cutoff_date,
                priority=0.9,
                metadata={
                    "period": latest_batch.period,
                    "reporting_entity": latest_batch.reporting_entity,
                    "privacy_threshold_applied": True,
                },
            )
        ]

        for item in sorted(public_items, key=lambda value: float(value.value), reverse=True)[:5]:
            indicators.append(
                cls.indicator(
                    source="Comisarias de Familia",
                    source_code="COMISARIAS_FAMILIA",
                    domain="FAMILIA Y PROTECCION",
                    category=item.category or "Indicador agregado",
                    code=f"familia.indicador.{item.indicator[:48]}",
                    name=item.indicator,
                    value=float(item.value),
                    unit=item.unit,
                    start=start,
                    end=end,
                    comparison_value=previous_values.get(item.indicator),
                    cutoff=latest_batch.cutoff_date,
                    priority=0.72,
                    metadata={
                        "period": latest_batch.period,
                        "reporting_entity": latest_batch.reporting_entity,
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
