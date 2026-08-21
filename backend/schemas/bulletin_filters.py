"""
Pydantic models for SISC Bulletin Filters (v1).
Derived from contracts/bulletin-filters.schema.json ($id: sisc-bulletin-filters-v1).
This is the single source of truth for filter validation in the backend.
"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional, Literal
from datetime import date


class PeriodFilter(BaseModel):
    model_config = {"extra": "forbid"}

    start: date
    end: date
    timezone: str = "America/Bogota"
    closed_period_required: bool = True
    cutoff_policy: Literal["EXACT", "LATEST_CLOSED", "AUTO"] = "EXACT"

    @model_validator(mode="after")
    def _validate_dates(self) -> "PeriodFilter":
        if self.end < self.start:
            raise ValueError(
                f"period.end ({self.end}) no puede ser anterior a period.start ({self.start})"
            )
        return self


class ComparisonFilter(BaseModel):
    model_config = {"extra": "forbid"}

    mode: Literal["YEAR_OVER_YEAR", "PREVIOUS_PERIOD", "YEAR_TO_DATE", "NONE"]
    start: Optional[date] = None
    end: Optional[date] = None
    resolved_by_backend: bool = False


class TerritoryFilter(BaseModel):
    model_config = {"extra": "forbid"}

    scope: Literal[
        "TODO_JAMUNDI",
        "ZONA",
        "COMUNA",
        "CORREGIMIENTO",
        "BARRIO",
        "CAI",
        "DEPENDENCIA",
    ]
    zona: Optional[Literal["URBANA", "RURAL"]] = None
    selected_codes: list[str] = Field(default_factory=list)
    top_n: Optional[int] = Field(None, ge=1, le=20)

    @model_validator(mode="after")
    def _validate_scope(self) -> "TerritoryFilter":
        if self.scope == "ZONA" and self.zona is None:
            raise ValueError("territory.zona es requerido cuando scope = ZONA")
        if self.scope in ("COMUNA", "CORREGIMIENTO", "BARRIO", "CAI", "DEPENDENCIA"):
            if not self.selected_codes:
                raise ValueError(
                    f"territory.selected_codes no puede estar vacio cuando scope = {self.scope}"
                )
        return self


class ConductaFilter(BaseModel):
    model_config = {"extra": "forbid"}

    mode: Literal[
        "ALL_PRIORITIZED",
        "SPECIFIC",
        "TOP_INCREASE",
        "TOP_DECREASE",
        "HIGHEST_COUNT",
    ]
    selected_codes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_conductas(self) -> "ConductaFilter":
        if self.mode == "SPECIFIC" and not self.selected_codes:
            raise ValueError(
                "conductas.selected_codes no puede estar vacio cuando mode = SPECIFIC"
            )
        return self


class DimensionFilter(BaseModel):
    model_config = {"extra": "forbid"}

    franja_horaria: Optional[Literal["MADRUGADA", "MANANA", "TARDE", "NOCHE"]] = None
    dia_semana: Optional[
        Literal[
            "LUNES",
            "MARTES",
            "MIERCOLES",
            "JUEVES",
            "VIERNES",
            "SABADO",
            "DOMINGO",
        ]
    ] = None
    zona: Optional[Literal["URBANA", "RURAL"]] = None
    modalidad: Optional[str] = Field(None, max_length=100)
    arma_medio: Optional[str] = Field(None, max_length=100)
    clase_sitio: Optional[str] = Field(None, max_length=100)
    grupo_edad: Optional[Literal["<18", "18-30", "31-50", ">50"]] = None
    genero: Optional[Literal["M", "F"]] = None


class SectionFilter(BaseModel):
    model_config = {"extra": "forbid"}

    resumen_ejecutivo: bool = True
    total_hechos: bool = True
    comparacion_anual: bool = True
    comparativo_conducta: bool = True
    evolucion: bool = True
    distribucion_territorial: bool = True
    barrios_mayor_registro: bool = True
    horarios_franjas: bool = True
    modalidades_frecuentes: bool = False
    inspecciones_policia: bool = True
    comisarias_familia: bool = True
    fuentes_calidad: bool = True
    nota_metodologica: bool = True


class PresetRef(BaseModel):
    model_config = {"extra": "forbid"}

    id: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)


class BulletinFilters(BaseModel):
    model_config = {"extra": "forbid"}

    schema_version: Literal["1.0"] = "1.0"
    mode: Literal[
        "OFFICIAL_PUBLICATION", "PUBLIC_EXPLORATION", "INSTITUTIONAL_ANALYSIS"
    ]
    bulletin_type: Optional[
        Literal["WEEKLY", "MONTHLY", "SEMESTER", "ANNUAL", "TERRITORIAL_SPECIAL"]
    ] = None
    period: PeriodFilter
    comparison: ComparisonFilter
    sources: list[
        Literal["POLICIA_SEMANAL", "INSPECCIONES_RNMC", "COMISARIAS_FAMILIA"]
    ] = Field(..., min_length=1)
    territory: TerritoryFilter
    conductas: ConductaFilter
    dimensions: Optional[DimensionFilter] = None
    sections: Optional[SectionFilter] = None
    preset: Optional[PresetRef] = None

    @model_validator(mode="after")
    def _validate_mode_constraints(self) -> "BulletinFilters":
        if self.mode == "OFFICIAL_PUBLICATION":
            if self.bulletin_type is None:
                raise ValueError(
                    "bulletin_type es requerido cuando mode = OFFICIAL_PUBLICATION"
                )
            if self.sections is None:
                raise ValueError(
                    "sections es requerido cuando mode = OFFICIAL_PUBLICATION"
                )
            if self.preset is None:
                raise ValueError(
                    "preset es requerido cuando mode = OFFICIAL_PUBLICATION"
                )
            dims = self.dimensions or DimensionFilter()
            if any(vars(dims).values()):
                raise ValueError(
                    "dimensions debe estar vacio cuando mode = OFFICIAL_PUBLICATION"
                )
        if self.mode == "PUBLIC_EXPLORATION":
            if self.sections is not None:
                raise ValueError(
                    "sections no debe enviarse cuando mode = PUBLIC_EXPLORATION"
                )
            if self.dimensions is not None:
                raise ValueError(
                    "dimensions no debe enviarse cuando mode = PUBLIC_EXPLORATION"
                )
        if self.mode == "INSTITUTIONAL_ANALYSIS":
            if self.sections is not None:
                raise ValueError(
                    "sections no debe enviarse cuando mode = INSTITUTIONAL_ANALYSIS"
                )
        if self.bulletin_type == "TERRITORIAL_SPECIAL":
            if self.territory.scope == "TODO_JAMUNDI":
                raise ValueError(
                    "territory.scope no puede ser TODO_JAMUNDI cuando bulletin_type = TERRITORIAL_SPECIAL"
                )
        return self
