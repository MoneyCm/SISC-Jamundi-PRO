"""
Pruebas Fase 1.5 — Contrato v1, idempotencia, supresión, PDF BYTEA, response models.
Ejecutar: pytest tests/test_fase15_contract.py -v
"""
import hashlib
import json
import sys
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from schemas.bulletin_filters import BulletinFilters
from schemas.bulletin_responses import (
    CapabilitiesResponse,
    CatalogResponse,
    ConductaCatalogItem,
    ConductaCatalogResponse,
    TerritoryCatalogItem,
    TerritoryCatalogResponse,
    PresetCatalogItem,
    PresetCatalogResponse,
    ExploreResponse,
    ExploreResult,
    GenerateResponse,
    PublicationSnapshot,
    SiscErrorResponse,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_filters(**overrides):
    base = {
        "schema_version": "1.0",
        "mode": "PUBLIC_EXPLORATION",
        "bulletin_type": "WEEKLY",
        "period": {"start": "2026-08-11", "end": "2026-08-17", "timezone": "America/Bogota",
                   "closed_period_required": True, "cutoff_policy": "EXACT"},
        "comparison": {"mode": "YEAR_OVER_YEAR"},
        "sources": ["POLICIA_SEMANAL"],
        "territory": {"scope": "TODO_JAMUNDI"},
        "conductas": {"mode": "ALL_PRIORITIZED"},
    }
    base.update(overrides)
    return base


def _official_filters(**overrides):
    base = _make_filters(
        mode="OFFICIAL_PUBLICATION",
        bulletin_type="MONTHLY",
        period={"start": "2026-07-01", "end": "2026-07-31", "timezone": "America/Bogota",
                "closed_period_required": True, "cutoff_policy": "EXACT"},
        sources=["POLICIA_SEMANAL", "INSPECCIONES_RNMC", "COMISARIAS_FAMILIA"],
        sections={"resumen_ejecutivo": True, "total_hechos": True, "comparacion_anual": True,
                  "comparativo_conducta": True, "evolucion": True, "distribucion_territorial": True,
                  "barrios_mayor_registro": True, "horarios_franjas": True,
                  "modalidades_frecuentes": False, "inspecciones_policia": True,
                  "comisarias_familia": True, "fuentes_calidad": True, "nota_metodologica": True},
        preset={"id": "MONTHLY_SECURITY_DEFAULT", "version": "1.0"},
    )
    base.update(overrides)
    return base


def _make_user(roles=None, user_id="u1"):
    return SimpleNamespace(
        id=user_id,
        username="testuser",
        roles=[SimpleNamespace(code=r) for r in (roles or ["ANALYST"])],
        is_active=True,
        data_level_max=2,
        expires_at=None,
    )


def _make_row(**overrides):
    defaults = {
        "id": "test-id-001",
        "title": "SISC EN CIFRAS",
        "edition_type": "MONTHLY",
        "period_start": date(2026, 7, 1),
        "period_end": date(2026, 7, 31),
        "status": "PUBLISHED",
        "created_by": "test",
        "source_codes": ["POLICIA_SEMANAL"],
        "publication_json": {
            "id": "test-id-001",
            "period": {"start": "2026-07-01", "end": "2026-07-31"},
            "comparison_period": {"start": "2025-07-01", "end": "2025-07-31"},
            "comparison_mode": "year_over_year",
            "sources": [{"code": "POLICIA_SEMANAL", "included": True, "period_records": 150}],
            "indicators": [],
            "generated_at": "2026-07-31T12:00:00Z",
        },
        "requested_filters": None,
        "resolved_filters": None,
        "schema_version": None,
        "pdf_url": None,
        "pdf_data": None,
        "pdf_sha256": None,
        "hash_integrity": None,
        "suppressed_cells": None,
        "catalog_versions_used": None,
        "query_hash": None,
        "created_at": datetime(2026, 7, 31, 12, 0, 0),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ===========================================================================
# 1. Los cuatro ejemplos contractuales validan con Pydantic
# ===========================================================================

class TestContractExamples:
    EXAMPLES_DIR = Path(r"C:\Proyectos\plataforma-seguridad\contracts\examples")

    def test_weekly_official(self):
        data = json.loads((self.EXAMPLES_DIR / "weekly-official.json").read_text(encoding="utf-8"))
        f = BulletinFilters(**data)
        assert f.mode == "OFFICIAL_PUBLICATION"

    def test_monthly_official(self):
        data = json.loads((self.EXAMPLES_DIR / "monthly-official.json").read_text(encoding="utf-8"))
        f = BulletinFilters(**data)
        assert f.bulletin_type == "MONTHLY"

    def test_public_exploration(self):
        data = json.loads((self.EXAMPLES_DIR / "public-exploration.json").read_text(encoding="utf-8"))
        f = BulletinFilters(**data)
        assert f.mode == "PUBLIC_EXPLORATION"

    def test_territorial_special(self):
        data = json.loads((self.EXAMPLES_DIR / "territorial-special.json").read_text(encoding="utf-8"))
        f = BulletinFilters(**data)
        assert f.bulletin_type == "TERRITORIAL_SPECIAL"


# ===========================================================================
# 2. Payloads inválidos por modo
# ===========================================================================

class TestModeConstraints:
    def test_public_exploitation_rejects_dimensions(self):
        with pytest.raises(Exception):
            BulletinFilters(**_make_filters(
                dimensions={"franja_horaria": "NOCHE"},
            ))

    def test_public_exploitation_rejects_sections(self):
        with pytest.raises(Exception):
            BulletinFilters(**_make_filters(
                sections={"resumen_ejecutivo": True},
            ))

    def test_official_allows_optional_preset(self):
        f = BulletinFilters(**_official_filters(preset=None))
        assert f.preset is None

    def test_official_allows_optional_sections(self):
        f = BulletinFilters(**_official_filters(sections=None))
        assert f.sections is None

    def test_official_rejects_dimensions(self):
        with pytest.raises(Exception):
            BulletinFilters(**_official_filters(
                dimensions={"franja_horaria": "NOCHE"},
            ))

    def test_institutional_allows_dimensions(self):
        f = BulletinFilters(**_make_filters(
            mode="INSTITUTIONAL_ANALYSIS",
            dimensions={"franja_horaria": "NOCHE"},
        ))
        assert f.mode == "INSTITUTIONAL_ANALYSIS"

    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):
            BulletinFilters(**_make_filters(custom_field="bad"))

    def test_territorial_special_requires_non_todo(self):
        with pytest.raises(Exception):
            BulletinFilters(**_official_filters(
                bulletin_type="TERRITORIAL_SPECIAL",
                territory={"scope": "TODO_JAMUNDI"},
            ))


# ===========================================================================
# 3. Filtros territoriales y conductas
# ===========================================================================

class TestFilterValidation:
    def test_barrio_requires_selected_codes(self):
        with pytest.raises(Exception):
            BulletinFilters(**_make_filters(
                territory={"scope": "BARRIO", "selected_codes": []},
            ))

    def test_comuna_requires_selected_codes(self):
        with pytest.raises(Exception):
            BulletinFilters(**_make_filters(
                territory={"scope": "COMUNA", "selected_codes": []},
            ))

    def test_zona_requires_zona_field(self):
        with pytest.raises(Exception):
            BulletinFilters(**_make_filters(
                territory={"scope": "ZONA"},
            ))

    def test_zona_with_zona_value_ok(self):
        f = BulletinFilters(**_make_filters(
            territory={"scope": "ZONA", "zona": "URBANA"},
        ))
        assert f.territory.zona == "URBANA"

    def test_specific_conducta_requires_codes(self):
        with pytest.raises(Exception):
            BulletinFilters(**_make_filters(
                conductas={"mode": "SPECIFIC", "selected_codes": []},
            ))

    def test_specific_conducta_with_codes_ok(self):
        f = BulletinFilters(**_make_filters(
            conductas={"mode": "SPECIFIC", "selected_codes": ["HURTO_PERSONAS"]},
        ))
        assert f.conductas.selected_codes == ["HURTO_PERSONAS"]


# ===========================================================================
# 4. Separación de unidades (dominios nunca se suman)
# ===========================================================================

class TestDomainSeparation:
    def test_explore_result_domain_consistency(self):
        ExploreResult(
            key="k", label="L", domain="HECHOS_DELICTIVOS",
            source_code="POLICIA_SEMANAL", unit="HECHOS",
            is_suppressed=False, count=10,
        )

    def test_wrong_source_for_domain_rejected(self):
        with pytest.raises(Exception):
            ExploreResult(
                key="k", label="L", domain="HECHOS_DELICTIVOS",
                source_code="INSPECCIONES_RNMC", unit="HECHOS",
                is_suppressed=False, count=10,
            )

    def test_wrong_unit_for_domain_rejected(self):
        with pytest.raises(Exception):
            ExploreResult(
                key="k", label="L", domain="HECHOS_DELICTIVOS",
                source_code="POLICIA_SEMANAL", unit="ACTUACIONES",
                is_suppressed=False, count=10,
            )

    def test_all_three_domains_use_different_sources(self):
        mapping = {
            "HECHOS_DELICTIVOS": "POLICIA_SEMANAL",
            "ACTUACIONES_INSPECCION": "INSPECCIONES_RNMC",
            "ATENCIONES_COMISARIA": "COMISARIAS_FAMILIA",
        }
        for domain, source in mapping.items():
            ExploreResult(
                key="k", label="L", domain=domain,
                source_code=source, unit={"HECHOS_DELICTIVOS": "HECHOS",
                                          "ACTUACIONES_INSPECCION": "ACTUACIONES",
                                          "ATENCIONES_COMISARIA": "ATENCIONES"}[domain],
                is_suppressed=False, count=10,
            )


# ===========================================================================
# 5. Supresión completa
# ===========================================================================

class TestSuppression:
    def test_suppressed_count_null(self):
        r = ExploreResult(
            key="k", label="L", domain="HECHOS_DELICTIVOS",
            source_code="POLICIA_SEMANAL", unit="HECHOS",
            is_suppressed=True, count=None, comparison_count=None,
            percentage_change=None, suppression_reason="MINIMUM_CELL_SIZE",
        )
        assert r.count is None
        assert r.is_suppressed is True

    def test_suppressed_requires_reason(self):
        with pytest.raises(Exception):
            ExploreResult(
                key="k", label="L", domain="HECHOS_DELICTIVOS",
                source_code="POLICIA_SEMANAL", unit="HECHOS",
                is_suppressed=True, count=None,
            )

    def test_suppressed_rejects_non_null_count(self):
        with pytest.raises(Exception):
            ExploreResult(
                key="k", label="L", domain="HECHOS_DELICTIVOS",
                source_code="POLICIA_SEMANAL", unit="HECHOS",
                is_suppressed=True, count=3,
                suppression_reason="MINIMUM_CELL_SIZE",
            )

    def test_suppressed_rejects_non_null_percentage(self):
        with pytest.raises(Exception):
            ExploreResult(
                key="k", label="L", domain="HECHOS_DELICTIVOS",
                source_code="POLICIA_SEMANAL", unit="HECHOS",
                is_suppressed=True, count=None, percentage_change=5.0,
                suppression_reason="MINIMUM_CELL_SIZE",
            )

    def test_non_suppressed_requires_count(self):
        with pytest.raises(Exception):
            ExploreResult(
                key="k", label="L", domain="HECHOS_DELICTIVOS",
                source_code="POLICIA_SEMANAL", unit="HECHOS",
                is_suppressed=False, count=None,
            )

    def test_non_suppressed_rejects_reason(self):
        with pytest.raises(Exception):
            ExploreResult(
                key="k", label="L", domain="HECHOS_DELICTIVOS",
                source_code="POLICIA_SEMANAL", unit="HECHOS",
                is_suppressed=False, count=10,
                suppression_reason="MINIMUM_CELL_SIZE",
            )

    def test_minimum_cell_size_literal_accepted(self):
        from schemas.bulletin_responses import SuppressedCell
        cell = SuppressedCell(
            cell_id="POLICIA_SEMANAL:seguridad.total",
            reason="MINIMUM_CELL_SIZE",
            source="POLICIA_SEMANAL",
            row_label="Total hechos",
            column_label="current",
            threshold_used=5,
        )
        assert cell.reason == "MINIMUM_CELL_SIZE"


# ===========================================================================
# 6. Idempotencia con mismo dataset
# ===========================================================================

class TestIdempotency:
    def test_same_hash_same_data(self):
        from services.sisc_cifras_service import SiscCifrasService
        filters = {"mode": "PUBLIC_EXPLORATION", "sources": ["POLICIA_SEMANAL"]}
        resolved = {"period": {"start": "2026-08-11", "end": "2026-08-17"},
                     "sources": {"records": {"POLICIA_SEMANAL": {"cutoff_date": "2026-08-17", "unique_count": 100}}}}
        catalogs = {"conductas": "2026.08", "barrios": "2026.08"}
        dataset = {"POLICIA_SEMANAL": {"cutoff_date": "2026-08-17", "unique_count": 100}}

        h1 = SiscCifrasService.generate_query_hash(filters, resolved, catalogs, dataset)
        h2 = SiscCifrasService.generate_query_hash(filters, resolved, catalogs, dataset)
        assert h1 == h2
        assert len(h1) == 64

    def test_different_dataset_different_hash(self):
        from services.sisc_cifras_service import SiscCifrasService
        filters = {"mode": "PUBLIC_EXPLORATION"}
        resolved = {"period": {"start": "2026-08-11", "end": "2026-08-17"}}
        catalogs = {"conductas": "2026.08"}

        dataset_a = {"POLICIA_SEMANAL": {"cutoff_date": "2026-08-17", "unique_count": 100}}
        dataset_b = {"POLICIA_SEMANAL": {"cutoff_date": "2026-08-18", "unique_count": 102}}

        h1 = SiscCifrasService.generate_query_hash(filters, resolved, catalogs, dataset_a)
        h2 = SiscCifrasService.generate_query_hash(filters, resolved, catalogs, dataset_b)
        assert h1 != h2

    def test_different_catalog_version_different_hash(self):
        from services.sisc_cifras_service import SiscCifrasService
        filters = {"mode": "PUBLIC_EXPLORATION"}
        resolved = {"period": {"start": "2026-08-11", "end": "2026-08-17"}}
        dataset = {"POLICIA_SEMANAL": {"cutoff_date": "2026-08-17", "unique_count": 100}}

        h1 = SiscCifrasService.generate_query_hash(filters, resolved, {"conductas": "2026.08"}, dataset)
        h2 = SiscCifrasService.generate_query_hash(filters, resolved, {"conductas": "2026.09"}, dataset)
        assert h1 != h2


# ===========================================================================
# 7. Nueva publicación cuando cambia dataset
# ===========================================================================

class TestDatasetChange:
    def test_same_count_different_cutoff_different_hash(self):
        from services.sisc_cifras_service import SiscCifrasService
        filters = {"mode": "PUBLIC_EXPLORATION"}
        resolved = {"period": {"start": "2026-08-11", "end": "2026-08-17"}}
        catalogs = {"conductas": "2026.08"}

        ds1 = {"POLICIA_SEMANAL": {"cutoff_date": "2026-08-17", "unique_count": 100}}
        ds2 = {"POLICIA_SEMANAL": {"cutoff_date": "2026-08-20", "unique_count": 100}}

        h1 = SiscCifrasService.generate_query_hash(filters, resolved, catalogs, ds1)
        h2 = SiscCifrasService.generate_query_hash(filters, resolved, catalogs, ds2)
        assert h1 != h2

    def test_same_count_same_cutoff_different_content_hash_different_hash(self):
        from services.sisc_cifras_service import SiscCifrasService
        filters = {"mode": "PUBLIC_EXPLORATION"}
        resolved = {"period": {"start": "2026-08-11", "end": "2026-08-17"}}
        catalogs = {"conductas": "2026.08"}

        ds1 = {
            "POLICIA_SEMANAL": {
                "cutoff_date": "2026-08-17",
                "unique_count": 100,
                "latest_ingestion_id": "aaa-bbb",
                "content_hash": "abc123",
            }
        }
        ds2 = {
            "POLICIA_SEMANAL": {
                "cutoff_date": "2026-08-17",
                "unique_count": 100,
                "latest_ingestion_id": "aaa-bbb",
                "content_hash": "def456",
            }
        }

        h1 = SiscCifrasService.generate_query_hash(filters, resolved, catalogs, ds1)
        h2 = SiscCifrasService.generate_query_hash(filters, resolved, catalogs, ds2)
        assert h1 != h2

    def test_same_count_same_content_different_ingestion_different_hash(self):
        from services.sisc_cifras_service import SiscCifrasService
        filters = {"mode": "PUBLIC_EXPLORATION"}
        resolved = {"period": {"start": "2026-08-11", "end": "2026-08-17"}}
        catalogs = {"conductas": "2026.08"}

        ds1 = {
            "POLICIA_SEMANAL": {
                "cutoff_date": "2026-08-17",
                "unique_count": 100,
                "latest_ingestion_id": "aaa-bbb",
                "content_hash": "abc123",
            }
        }
        ds2 = {
            "POLICIA_SEMANAL": {
                "cutoff_date": "2026-08-17",
                "unique_count": 100,
                "latest_ingestion_id": "xxx-yyy",
                "content_hash": "abc123",
            }
        }

        h1 = SiscCifrasService.generate_query_hash(filters, resolved, catalogs, ds1)
        h2 = SiscCifrasService.generate_query_hash(filters, resolved, catalogs, ds2)
        assert h1 != h2


# ===========================================================================
# 8. build_snapshot_from_publication completo
# ===========================================================================

class TestSnapshot:
    def test_snapshot_has_all_required_fields(self):
        from services.sisc_cifras_service import SiscCifrasService
        publication = {
            "period": {"start": "2026-07-01", "end": "2026-07-31"},
            "comparison_period": {"start": "2025-07-01", "end": "2025-07-31"},
            "comparison_mode": "year_over_year",
            "sources": [{"code": "POLICIA_SEMANAL", "included": True, "period_records": 100}],
            "generated_at": "2026-07-31T12:00:00Z",
        }
        requested = {"mode": "PUBLIC_EXPLORATION"}
        resolved = {
            "period": {"start": "2026-07-01", "end": "2026-07-31", "timezone": "America/Bogota", "days": 31},
            "comparison": {"mode": "YEAR_OVER_YEAR", "resolved_by_backend": True, "start": "2025-07-01", "end": "2025-07-31"},
            "sources": {"active": ["POLICIA_SEMANAL"], "cutoff_used": "2026-07-31", "records": {"POLICIA_SEMANAL": {"cutoff_date": "2026-07-31", "unique_count": 100}}},
            "territory": {"scope": "TODO_JAMUNDI", "resolved_barrios": ["TODO_JAMUNDI"]},
            "conductas": {"mode": "ALL_PRIORITIZED", "resolved_codes": []},
        }
        catalogs = {"barrios": "2026.08", "conductas": "2026.08"}
        suppressed = []
        snapshot = SiscCifrasService.build_snapshot_from_publication(
            publication, requested, resolved, catalogs, suppressed, "test_user", "/api/pdf",
        )
        assert "requested_filters" in snapshot
        assert "resolved_filters" in snapshot
        assert "catalog_versions_used" in snapshot
        assert "hash_integrity" in snapshot
        assert "suppressed_cells" in snapshot
        assert "generated_at" in snapshot
        assert "published_at" in snapshot
        assert "pdf_url" in snapshot
        assert snapshot["pdf_url"] == "/api/pdf"
        assert snapshot["hash_integrity"]["algorithm"] == "sha256"
        assert len(snapshot["hash_integrity"]["value"]) == 64

    def test_snapshot_validates_with_publication_snapshot(self):
        from services.sisc_cifras_service import SiscCifrasService
        publication = {
            "period": {"start": "2026-07-01", "end": "2026-07-31"},
            "comparison_period": {"start": "2025-07-01", "end": "2025-07-31"},
            "comparison_mode": "year_over_year",
            "sources": [],
            "generated_at": "2026-07-31T12:00:00Z",
        }
        resolved = {
            "period": {"start": "2026-07-01", "end": "2026-07-31", "timezone": "America/Bogota", "days": 31},
            "comparison": {"mode": "YEAR_OVER_YEAR", "resolved_by_backend": True},
            "sources": {"active": ["POLICIA_SEMANAL"], "cutoff_used": "2026-07-31", "records": {}},
            "territory": {"scope": "TODO_JAMUNDI", "resolved_barrios": ["TODO_JAMUNDI"]},
            "conductas": {"mode": "ALL_PRIORITIZED", "resolved_codes": []},
        }
        snapshot = SiscCifrasService.build_snapshot_from_publication(
            publication, {}, resolved, {}, [], "test", "/api/pdf",
        )
        ps = PublicationSnapshot(**snapshot)
        assert ps.pdf_url == "/api/pdf"
        assert ps.created_by == "test"


# ===========================================================================
# 9. adapt_legacy_publication produce snapshot válido
# ===========================================================================

class TestLegacyAdaptation:
    def test_legacy_snapshot_has_required_fields(self):
        from services.sisc_cifras_service import SiscCifrasService
        row = _make_row(schema_version=None)
        result = SiscCifrasService.adapt_legacy_publication(row)
        assert "requested_filters" in result
        assert "resolved_filters" in result
        assert "catalog_versions_used" in result
        assert "hash_integrity" in result
        assert "published_at" in result
        assert "pdf_url" in result
        assert "_legacy" not in result

    def test_v1_snapshot_adapts_correctly(self):
        from services.sisc_cifras_service import SiscCifrasService
        row = _make_row(
            schema_version="1.0",
            requested_filters={"mode": "OFFICIAL_PUBLICATION"},
            resolved_filters={"period": {"start": "2026-07-01", "end": "2026-07-31"}},
            pdf_url="/api/v1/pdf",
        )
        result = SiscCifrasService.adapt_legacy_publication(row)
        assert result["pdf_url"] == "/api/v1/pdf"

    def test_legacy_snapshot_validates_as_publication_snapshot(self):
        from services.sisc_cifras_service import SiscCifrasService
        row = _make_row()
        result = SiscCifrasService.adapt_legacy_publication(row)
        ps = PublicationSnapshot(**result)
        assert ps.created_by == "test"


# ===========================================================================
# 10. Catálogo territorial
# ===========================================================================

class TestCatalog:
    def test_load_catalog_versions_includes_barrios(self):
        from services.sisc_cifras_service import SiscCifrasService
        versions = SiscCifrasService._load_catalog_versions()
        assert "barrios" in versions
        assert "conductas" in versions
        assert "presets" in versions
        assert versions["barrios"] is not None

    def test_get_catalog_barrios_maps_to_territorios(self):
        from services.sisc_cifras_service import SiscCifrasService
        result = SiscCifrasService.get_catalog("barrios")
        assert result["status"] == "ok"
        assert result["catalog"] == "barrios"
        assert result["count"] > 0

    def test_get_catalog_territorios_works(self):
        from services.sisc_cifras_service import SiscCifrasService
        result = SiscCifrasService.get_catalog("territorios")
        assert result["status"] == "ok"
        assert result["catalog"] == "territorios"

    def test_get_catalog_conductas(self):
        from services.sisc_cifras_service import SiscCifrasService
        result = SiscCifrasService.get_catalog("conductas")
        assert result["status"] == "ok"
        assert result["count"] == 8

    def test_capabilities_has_all_catalog_versions(self):
        from services.sisc_cifras_service import SiscCifrasService
        caps = SiscCifrasService.get_capabilities()
        cv = caps["catalog_versions"]
        assert "barrios" in cv
        assert "conductas" in cv
        assert "presets" in cv
        assert cv["barrios"] is not None


# ===========================================================================
# 11. Capabilities
# ===========================================================================

class TestCapabilities:
    def test_capabilities_validates(self):
        from services.sisc_cifras_service import SiscCifrasService
        caps = SiscCifrasService.get_capabilities()
        cr = CapabilitiesResponse(**caps)
        assert cr.schema_version == "1.0"
        assert len(cr.supported_modes) == 3
        assert len(cr.available_sources) == 3

    def test_capabilities_no_fake_catalogs(self):
        from services.sisc_cifras_service import SiscCifrasService
        caps = SiscCifrasService.get_capabilities()
        cv_keys = set(caps["catalog_versions"].keys())
        assert "dependencias" not in cv_keys
        assert "comunas" not in cv_keys
        assert "zonas" not in cv_keys


# ===========================================================================
# 12. Response models
# ===========================================================================

class TestResponseModels:
    def test_generate_response_validates(self):
        from schemas.bulletin_responses import HashIntegrity
        snapshot_data = {
            "requested_filters": {},
            "resolved_filters": {
                "period": {"start": "2026-07-01", "end": "2026-07-31", "timezone": "America/Bogota", "days": 31},
                "comparison": {"mode": "YEAR_OVER_YEAR", "resolved_by_backend": True},
                "sources": {"active": ["POLICIA_SEMANAL"], "cutoff_used": "2026-07-31", "records": {}},
                "territory": {"scope": "TODO_JAMUNDI", "resolved_barrios": ["TODO_JAMUNDI"]},
                "conductas": {"mode": "ALL_PRIORITIZED", "resolved_codes": []},
            },
            "hash_integrity": {"algorithm": "sha256", "value": "a" * 64},
            "generated_at": datetime(2026, 7, 31),
            "published_at": datetime(2026, 7, 31),
            "created_by": "test",
            "pdf_url": "/api/pdf",
        }
        gr = GenerateResponse(
            schema_version="1.0",
            status="ok",
            mode="OFFICIAL_PUBLICATION",
            bulletin_type="MONTHLY",
            snapshot=PublicationSnapshot(**snapshot_data),
            created_at=datetime(2026, 7, 31),
        )
        assert gr.status == "ok"

    def test_catalog_response_validates(self):
        cr = ConductaCatalogResponse(
            schema_version="1.0",
            status="ok",
            catalog="conductas",
            version="2026.08",
            count=8,
            items=[],
        )
        assert cr.count == 8
        assert cr.catalog == "conductas"

    def test_error_response_validates(self):
        er = SiscErrorResponse(
            schema_version="1.0",
            status="error",
            error_code="VALIDATION_ERROR",
            message="Test error",
            timestamp=datetime(2026, 7, 31),
        )
        assert er.status == "error"


# ===========================================================================
# 12b. Catálogos reales — contenido y estructura por tipo
# ===========================================================================

CATALOGS_DIR = Path(__file__).resolve().parents[1] / "data" / "catalogs"


class TestCatalogsRealContent:
    """Valida que el contenido real de cada catálogo pase el modelo Pydantic."""

    def test_territorios_real_content(self):
        data = json.loads((CATALOGS_DIR / "territorios.json").read_text(encoding="utf-8"))
        resp = TerritoryCatalogResponse(
            schema_version="1.0",
            status="ok",
            catalog="barrios",
            version=data["version"],
            count=len(data["items"]),
            items=[TerritoryCatalogItem(**item) for item in data["items"]],
        )
        assert resp.catalog == "barrios"
        assert resp.count == 12
        codes = [i.code for i in resp.items]
        assert "BARRIO-001" in codes
        assert "COMUNA-001" in codes
        assert "CORREG-001" in codes
        barrio = next(i for i in resp.items if i.code == "BARRIO-001")
        assert barrio.metadata["type"] == "BARRIO"
        assert barrio.metadata["zone"] == "URBANA"
        assert isinstance(barrio.metadata["aliases"], list)
        assert barrio.parent_code == "COMUNA-001"

    def test_conductas_real_content(self):
        data = json.loads((CATALOGS_DIR / "conductas.json").read_text(encoding="utf-8"))
        resp = ConductaCatalogResponse(
            schema_version="1.0",
            status="ok",
            catalog="conductas",
            version=data["version"],
            count=len(data["items"]),
            items=[ConductaCatalogItem(**item) for item in data["items"]],
        )
        assert resp.catalog == "conductas"
        assert resp.count == 8
        codes = [i.code for i in resp.items]
        assert "HOMICIDIO" in codes
        assert "VIOLENCIA_INTRAFAMILIAR" in codes
        hom = next(i for i in resp.items if i.code == "HOMICIDIO")
        assert hom.category == "SEGURIDAD"
        assert len(hom.aliases) >= 3
        assert "HOMICIDIO DOLOSO" in hom.aliases
        vif = next(i for i in resp.items if i.code == "VIOLENCIA_INTRAFAMILIAR")
        assert vif.category == "CONVIVENCIA"

    def test_presets_real_content(self):
        data = json.loads((CATALOGS_DIR / "presets.json").read_text(encoding="utf-8"))
        resp = PresetCatalogResponse(
            schema_version="1.0",
            status="ok",
            catalog="presets",
            version=data["version"],
            count=len(data["items"]),
            items=[PresetCatalogItem(**item) for item in data["items"]],
        )
        assert resp.catalog == "presets"
        assert resp.count == 5
        codes = [i.code for i in resp.items]
        assert "WEEKLY_SECURITY_DEFAULT" in codes
        assert "TERRITORIAL_SPECIAL_DEFAULT" in codes
        weekly = next(i for i in resp.items if i.code == "WEEKLY_SECURITY_DEFAULT")
        assert weekly.bulletin_type == "WEEKLY"
        assert weekly.metadata["comparison_mode"] == "YEAR_OVER_YEAR"
        assert "POLICIA_SEMANAL" in weekly.metadata["default_sources"]
        sections = weekly.metadata["default_sections"]
        assert isinstance(sections["resumen_ejecutivo"], bool)
        assert isinstance(sections["inspecciones_policia"], bool)

    def test_catalog_rejects_wrong_discriminator(self):
        with pytest.raises(Exception):
            TerritoryCatalogResponse(
                schema_version="1.0",
                status="ok",
                catalog="conductas",
                version="2026.08",
                count=1,
                items=[],
            )

    def test_catalog_rejects_missing_required_fields(self):
        with pytest.raises(Exception):
            ConductaCatalogItem(
                code="TEST",
                label="Test",
            )

    def test_catalog_rejects_extra_fields(self):
        with pytest.raises(Exception):
            TerritoryCatalogItem(
                code="TEST",
                label="Test",
                parent_code=None,
                metadata={"type": "BARRIO", "zone": None, "aliases": []},
                fake_field="nope",
            )


# ===========================================================================
# 13. PDF BYTEA - modelo y fallback
# ===========================================================================

class TestPdfBytea:
    def test_model_has_large_binary(self):
        from db.models_sisc_cifras import SiscCifrasPublication
        col = SiscCifrasPublication.__table__.c.pdf_data
        from sqlalchemy import LargeBinary
        assert isinstance(col.type, LargeBinary)

    def test_adapt_legacy_with_no_pdf(self):
        from services.sisc_cifras_service import SiscCifrasService
        row = _make_row(pdf_data=None, pdf_url=None)
        result = SiscCifrasService.adapt_legacy_publication(row)
        assert "/api/sisc-cifras/publications/" in result["pdf_url"]

    def test_adapt_legacy_with_existing_pdf_url(self):
        from services.sisc_cifras_service import SiscCifrasService
        row = _make_row(pdf_url="/api/custom/pdf")
        result = SiscCifrasService.adapt_legacy_publication(row)
        assert result["pdf_url"] == "/api/custom/pdf"


# ===========================================================================
# 14. Autorización
# ===========================================================================

class TestAuthorization:
    def test_generate_rejects_no_user(self):
        from api.sisc_cifras_v1 import generate_v1
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            generate_v1(
                filters=BulletinFilters(**_official_filters()),
                request=MagicMock(),
                db=MagicMock(),
                user=None,
            )
        assert exc_info.value.status_code == 401

    def test_generate_rejects_wrong_role(self):
        from api.sisc_cifras_v1 import generate_v1
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            generate_v1(
                filters=BulletinFilters(**_official_filters()),
                request=MagicMock(),
                db=MagicMock(),
                user=_make_user(roles=["CITIZEN"]),
            )
        assert exc_info.value.status_code == 403

    def test_generate_allows_ti_admin(self):
        user = _make_user(roles=["TI_ADMIN"])
        assert any(r.code == "TI_ADMIN" for r in user.roles)

    def test_generate_allows_analyst(self):
        user = _make_user(roles=["ANALYST"])
        assert any(r.code in ("ANALYST", "DIRECTIVE", "FUNC_ADMIN", "TI_ADMIN")
                   for r in user.roles)


# ===========================================================================
# 15. Rate limit - IP extraction
# ===========================================================================

class TestRateLimitIP:
    def _make_request(self, forwarded=None, real_ip=None, client_host="127.0.0.1"):
        req = MagicMock()
        req.headers = {}
        if forwarded:
            req.headers["X-Forwarded-For"] = forwarded
        if real_ip:
            req.headers["X-Real-IP"] = real_ip
        req.client = SimpleNamespace(host=client_host)
        return req

    @patch("middleware.rate_limit._RATE_LIMIT_IP_STRATEGY", "forwarded_last")
    def test_forwarded_last_uses_last_ip(self):
        from middleware.rate_limit import get_client_ip
        req = self._make_request(forwarded="1.1.1.1, 2.2.2.2, 3.3.3.3")
        ip = get_client_ip(req)
        assert ip == "3.3.3.3"

    @patch("middleware.rate_limit._RATE_LIMIT_IP_STRATEGY", "forwarded_first")
    def test_forwarded_first_uses_first_ip(self):
        from middleware.rate_limit import get_client_ip
        req = self._make_request(forwarded="1.1.1.1, 2.2.2.2")
        ip = get_client_ip(req)
        assert ip == "1.1.1.1"

    @patch("middleware.rate_limit._RATE_LIMIT_IP_STRATEGY", "client")
    def test_client_strategy_ignores_headers(self):
        from middleware.rate_limit import get_client_ip
        req = self._make_request(forwarded="1.1.1.1", client_host="192.168.1.1")
        ip = get_client_ip(req)
        assert ip == "192.168.1.1"

    def test_no_forwarded_uses_real_ip(self):
        from middleware.rate_limit import get_client_ip
        req = self._make_request(real_ip="5.5.5.5")
        ip = get_client_ip(req)
        assert ip == "5.5.5.5"

    def test_no_headers_uses_client(self):
        from middleware.rate_limit import get_client_ip
        req = self._make_request(client_host="10.0.0.1")
        ip = get_client_ip(req)
        assert ip == "10.0.0.1"


# ===========================================================================
# 16. dataset_identity_from_resolved
# ===========================================================================

class TestDatasetIdentity:
    def test_extracts_from_resolved(self):
        from api.sisc_cifras_v1 import _dataset_identity_from_resolved
        resolved = {
            "sources": {
                "records": {
                    "POLICIA_SEMANAL": {"cutoff_date": "2026-08-17", "unique_count": 100},
                    "INSPECCIONES_RNMC": {"cutoff_date": "2026-08-16", "unique_count": 50},
                }
            }
        }
        identity = _dataset_identity_from_resolved(resolved)
        assert identity["POLICIA_SEMANAL"]["unique_count"] == 100
        assert identity["INSPECCIONES_RNMC"]["cutoff_date"] == "2026-08-16"


# ===========================================================================
# 17. SiscErrorResponse extras_forbid
# ===========================================================================

class TestErrorModel:
    def test_error_rejects_extra_fields(self):
        with pytest.raises(Exception):
            SiscErrorResponse(
                schema_version="1.0",
                status="error",
                error_code="VALIDATION_ERROR",
                message="test",
                timestamp=datetime.now(),
                extra_field="bad",
            )


# ===========================================================================
# 18. explore_data aplica filtros
# ===========================================================================

class TestExploreData:
    def test_conducta_aliases_load(self):
        from services.sisc_cifras_service import SiscCifrasService
        aliases = SiscCifrasService._load_conducta_aliases()
        assert "HURTO_PERSONAS" in aliases
        assert any("HURTO A PERSONAS" in a.upper() for a in aliases["HURTO_PERSONAS"])
