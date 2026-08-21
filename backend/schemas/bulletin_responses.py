"""
Pydantic models for SISC Bulletin Responses (v1).
Derived from contracts/bulletin-responses.schema.json ($id: sisc-bulletin-responses-v1).
"""

from pydantic import BaseModel, Field, model_validator
from typing import Annotated, Optional, Literal, Any, Union
from datetime import date, datetime


class HashIntegrity(BaseModel):
    model_config = {"extra": "forbid"}

    algorithm: Literal["sha256"] = "sha256"
    value: str = Field(..., pattern=r"^[a-f0-9]{64}$")


class CatalogMeta(BaseModel):
    model_config = {"extra": "forbid"}

    schema_version: Literal["1.0"] = "1.0"
    status: Literal["ok"] = "ok"
    version: str = Field(..., min_length=1)
    count: int = Field(..., ge=0)


class TerritoryCatalogItem(BaseModel):
    model_config = {"extra": "forbid"}

    code: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    parent_code: Optional[str] = None
    metadata: dict[str, Any] = Field(...)


class TerritoryCatalogResponse(CatalogMeta):
    model_config = {"extra": "forbid"}

    catalog: Literal["barrios"] = "barrios"
    items: list[TerritoryCatalogItem] = Field(default_factory=list)


class ConductaCatalogItem(BaseModel):
    model_config = {"extra": "forbid"}

    code: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    aliases: list[str] = Field(..., min_length=1)
    category: Literal["SEGURIDAD", "CONVIVENCIA"]
    metadata: Optional[dict[str, Any]] = None


class ConductaCatalogResponse(CatalogMeta):
    model_config = {"extra": "forbid"}

    catalog: Literal["conductas"] = "conductas"
    items: list[ConductaCatalogItem] = Field(default_factory=list)


class PresetCatalogItem(BaseModel):
    model_config = {"extra": "forbid"}

    code: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    bulletin_type: Literal["WEEKLY", "MONTHLY", "SEMESTER", "ANNUAL", "TERRITORIAL_SPECIAL"]
    description: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(...)


class PresetCatalogResponse(CatalogMeta):
    model_config = {"extra": "forbid"}

    catalog: Literal["presets"] = "presets"
    items: list[PresetCatalogItem] = Field(default_factory=list)


CatalogResponse = Annotated[
    Union[TerritoryCatalogResponse, ConductaCatalogResponse, PresetCatalogResponse],
    Field(discriminator="catalog"),
]


class CatalogVersions(BaseModel):
    model_config = {"extra": "forbid"}

    barrios: Optional[str] = None
    conductas: Optional[str] = None
    presets: Optional[str] = None


class RateLimitInfo(BaseModel):
    model_config = {"extra": "forbid"}

    requests_per_minute: int = Field(..., ge=1)
    burst: Optional[int] = Field(None, ge=1)


class CapabilitiesResponse(BaseModel):
    model_config = {"extra": "forbid"}

    schema_version: Literal["1.0"] = "1.0"
    status: Literal["ok"] = "ok"
    supported_modes: list[
        Literal["OFFICIAL_PUBLICATION", "PUBLIC_EXPLORATION", "INSTITUTIONAL_ANALYSIS"]
    ] = Field(..., min_length=1)
    supported_bulletin_types: list[
        Literal["WEEKLY", "MONTHLY", "SEMESTER", "ANNUAL", "TERRITORIAL_SPECIAL"]
    ] = Field(..., min_length=1)
    available_sources: list[
        Literal["POLICIA_SEMANAL", "INSPECCIONES_RNMC", "COMISARIAS_FAMILIA"]
    ] = Field(..., min_length=1)
    territory_scopes: list[
        Literal[
            "TODO_JAMUNDI", "ZONA", "COMUNA", "CORREGIMIENTO",
            "BARRIO", "CAI", "DEPENDENCIA",
        ]
    ] = Field(..., min_length=1)
    conducta_modes: list[
        Literal[
            "ALL_PRIORITIZED", "SPECIFIC", "TOP_INCREASE",
            "TOP_DECREASE", "HIGHEST_COUNT",
        ]
    ] = Field(..., min_length=1)
    dimensions: list[str] = Field(default_factory=list)
    max_period_days: int = Field(..., ge=1)
    catalog_versions: CatalogVersions = Field(default_factory=CatalogVersions)
    rate_limit: RateLimitInfo = Field(default_factory=lambda: RateLimitInfo(requests_per_minute=60))


class BulletinWarning(BaseModel):
    model_config = {"extra": "forbid"}

    code: Literal[
        "SOURCE_PARTIAL_DATA",
        "CUTOFF_ADJUSTED",
        "TERRITORY_TRUNCATED",
        "CONDUCTA_LIMIT_EXCEEDED",
        "CATALOG_VERSION_OLD",
        "PERIOD_TOO_LONG",
        "DIMENSION_NOT_SUPPORTED",
        "COMPARISON_FALLBACK",
        "SMALL_SAMPLE_SIZE",
        "DATA_QUALITY_ISSUE",
    ]
    message: str = Field(..., min_length=1)
    severity: Literal["info", "warning", "error"]
    context: Optional[dict[str, Any]] = None


class SuppressedCell(BaseModel):
    model_config = {"extra": "forbid"}

    cell_id: str = Field(..., min_length=1)
    reason: Literal[
        "BELOW_MINIMUM_COUNT",
        "MINIMUM_CELL_SIZE",
        "IDENTIFIABLE_VICTIM",
        "SMALL_GROUP_SIZE",
        "COMPLIANCE_POLICY",
        "SOURCE_REDACTION",
    ]
    source: Literal["POLICIA_SEMANAL", "INSPECCIONES_RNMC", "COMISARIAS_FAMILIA"]
    row_label: str = Field(..., min_length=1)
    column_label: str = Field(..., min_length=1)
    threshold_used: Optional[int] = Field(None, ge=1)


class ResolvedPeriod(BaseModel):
    model_config = {"extra": "forbid"}

    start: date
    end: date
    timezone: str
    days: int = Field(..., ge=1)
    closed_period_confirmed: Optional[bool] = None


class ResolvedComparison(BaseModel):
    model_config = {"extra": "forbid"}

    mode: Literal["YEAR_OVER_YEAR", "PREVIOUS_PERIOD", "YEAR_TO_DATE", "NONE"]
    resolved_by_backend: bool
    start: Optional[date] = None
    end: Optional[date] = None


class ResolvedSourceRecords(BaseModel):
    model_config = {"extra": "forbid"}

    POLICIA_SEMANAL: Optional[int] = Field(None, ge=0)
    INSPECCIONES_RNMC: Optional[int] = Field(None, ge=0)
    COMISARIAS_FAMILIA: Optional[int] = Field(None, ge=0)


class ResolvedSources(BaseModel):
    model_config = {"extra": "forbid"}

    active: list[
        Literal["POLICIA_SEMANAL", "INSPECCIONES_RNMC", "COMISARIAS_FAMILIA"]
    ] = Field(..., min_length=1)
    cutoff_used: date
    records: ResolvedSourceRecords = Field(default_factory=ResolvedSourceRecords)


class ResolvedTerritory(BaseModel):
    model_config = {"extra": "forbid"}

    scope: Literal[
        "TODO_JAMUNDI", "ZONA", "COMUNA", "CORREGIMIENTO",
        "BARRIO", "CAI", "DEPENDENCIA",
    ]
    zona: Optional[Literal["URBANA", "RURAL"]] = None
    resolved_barrios: list[str] = Field(..., min_length=1)
    total_barrios_in_scope: Optional[int] = Field(None, ge=0)


class ResolvedConductas(BaseModel):
    model_config = {"extra": "forbid"}

    mode: Literal[
        "ALL_PRIORITIZED", "SPECIFIC", "TOP_INCREASE",
        "TOP_DECREASE", "HIGHEST_COUNT",
    ]
    resolved_codes: list[str] = Field(default_factory=list)
    total_in_catalog: Optional[int] = Field(None, ge=0)


class ResolvedFilters(BaseModel):
    model_config = {"extra": "forbid"}

    period: ResolvedPeriod
    comparison: ResolvedComparison
    sources: ResolvedSources
    territory: ResolvedTerritory
    conductas: ResolvedConductas


class PublicationSnapshot(BaseModel):
    model_config = {"extra": "forbid"}

    requested_filters: dict[str, Any]
    resolved_filters: ResolvedFilters
    catalog_versions_used: CatalogVersions = Field(default_factory=CatalogVersions)
    warnings: list[BulletinWarning] = Field(default_factory=list)
    suppressed_cells: list[SuppressedCell] = Field(default_factory=list)
    hash_integrity: HashIntegrity
    generated_at: datetime
    published_at: datetime
    created_by: str = Field(..., min_length=1)
    pdf_url: str = Field(..., min_length=1)
    previous_version_id: Optional[str] = None


class GenerateResponse(BaseModel):
    model_config = {"extra": "forbid"}

    schema_version: Literal["1.0"] = "1.0"
    status: Literal["ok", "partial"]
    mode: Literal[
        "OFFICIAL_PUBLICATION", "PUBLIC_EXPLORATION", "INSTITUTIONAL_ANALYSIS"
    ]
    bulletin_type: Literal[
        "WEEKLY", "MONTHLY", "SEMESTER", "ANNUAL", "TERRITORIAL_SPECIAL"
    ]
    snapshot: PublicationSnapshot
    created_at: datetime


class ExploreResult(BaseModel):
    model_config = {"extra": "forbid"}

    key: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    domain: Literal["HECHOS_DELICTIVOS", "ACTUACIONES_INSPECCION", "ATENCIONES_COMISARIA"]
    source_code: Literal["POLICIA_SEMANAL", "INSPECCIONES_RNMC", "COMISARIAS_FAMILIA"]
    unit: Literal["HECHOS", "ACTUACIONES", "ATENCIONES"]
    is_suppressed: bool
    count: Optional[int] = Field(None, ge=0)
    comparison_count: Optional[int] = Field(None, ge=0)
    percentage_change: Optional[float] = None
    suppression_reason: Optional[
        Literal[
            "BELOW_MINIMUM_COUNT",
            "MINIMUM_CELL_SIZE",
            "IDENTIFIABLE_VICTIM",
            "SMALL_GROUP_SIZE",
            "COMPLIANCE_POLICY",
            "SOURCE_REDACTION",
        ]
    ] = None
    coverage_type: Literal["EXACT", "CONTEXT"] = "EXACT"
    source_period: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}$")
    cutoff_date: Optional[date] = None
    context_label: Optional[str] = None
    reporting_entity: Optional[str] = None
    reporting_basis: Optional[Literal["CUMULATIVE", "MONTHLY"]] = None

    @model_validator(mode="after")
    def _validate_domain_consistency(self) -> "ExploreResult":
        mapping = {
            "HECHOS_DELICTIVOS": ("POLICIA_SEMANAL", "HECHOS"),
            "ACTUACIONES_INSPECCION": ("INSPECCIONES_RNMC", "ACTUACIONES"),
            "ATENCIONES_COMISARIA": ("COMISARIAS_FAMILIA", "ATENCIONES"),
        }
        expected_source, expected_unit = mapping[self.domain]
        if self.source_code != expected_source:
            raise ValueError(
                f"domain={self.domain} requiere source_code={expected_source}, "
                f"recibido {self.source_code}"
            )
        if self.unit != expected_unit:
            raise ValueError(
                f"domain={self.domain} requiere unit={expected_unit}, "
                f"recibido {self.unit}"
            )
        if self.is_suppressed:
            if self.suppression_reason is None:
                raise ValueError(
                    "suppression_reason es requerido cuando is_suppressed=true"
                )
            if self.count is not None:
                raise ValueError("count debe ser null cuando is_suppressed=true")
            if self.comparison_count is not None:
                raise ValueError(
                    "comparison_count debe ser null cuando is_suppressed=true"
                )
            if self.percentage_change is not None:
                raise ValueError(
                    "percentage_change debe ser null cuando is_suppressed=true"
                )
        else:
            if self.count is None:
                raise ValueError("count es requerido cuando is_suppressed=false")
            if self.suppression_reason is not None:
                raise ValueError(
                    "suppression_reason no debe enviarse cuando is_suppressed=false"
                )
        if self.coverage_type == "CONTEXT":
            if not self.source_period:
                raise ValueError(
                    "source_period es requerido cuando coverage_type=CONTEXT"
                )
            if self.cutoff_date is None:
                raise ValueError(
                    "cutoff_date es requerido cuando coverage_type=CONTEXT"
                )
            if not self.context_label:
                raise ValueError(
                    "context_label es requerido cuando coverage_type=CONTEXT"
                )
            if not self.reporting_entity:
                raise ValueError(
                    "reporting_entity es requerido cuando coverage_type=CONTEXT"
                )
            if not self.reporting_basis:
                raise ValueError(
                    "reporting_basis es requerido cuando coverage_type=CONTEXT"
                )
            if self.comparison_count is not None:
                raise ValueError(
                    "comparison_count debe ser null cuando coverage_type=CONTEXT"
                )
            if self.percentage_change is not None:
                raise ValueError(
                    "percentage_change debe ser null cuando coverage_type=CONTEXT"
                )
        return self


class ExploreMetadata(BaseModel):
    model_config = {"extra": "forbid"}

    query_time_ms: Optional[int] = Field(None, ge=0)
    data_sources_queried: list[
        Literal["POLICIA_SEMANAL", "INSPECCIONES_RNMC", "COMISARIAS_FAMILIA"]
    ] = Field(default_factory=list)
    filters_applied: int = Field(0, ge=0)


class ExploreResponse(BaseModel):
    model_config = {"extra": "forbid"}

    schema_version: Literal["1.0"] = "1.0"
    status: Literal["ok", "partial"]
    results: list[ExploreResult] = Field(default_factory=list)
    total_results: int = Field(..., ge=0)
    resolved_filters: ResolvedFilters
    warnings: list[BulletinWarning] = Field(default_factory=list)
    suppressed_cells: list[SuppressedCell] = Field(default_factory=list)
    metadata: ExploreMetadata = Field(default_factory=ExploreMetadata)


class SiscErrorResponse(BaseModel):
    model_config = {"extra": "forbid"}

    schema_version: Literal["1.0"] = "1.0"
    status: Literal["error"] = "error"
    error_code: Literal[
        "VALIDATION_ERROR",
        "PERIOD_NOT_CLOSED",
        "COMPARISON_NOT_VALID",
        "SOURCE_UNAVAILABLE",
        "INSUFFICIENT_DATA",
        "RATE_LIMIT_EXCEEDED",
        "FORBIDDEN_DIMENSION",
        "CATALOG_VERSION_MISMATCH",
    ]
    message: str = Field(..., min_length=1)
    details: Optional[dict[str, Any]] = None
    timestamp: datetime
    request_id: Optional[str] = None
