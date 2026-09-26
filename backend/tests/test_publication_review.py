"""Revisión editorial de SISC en cifras, con los casos encontrados en boletines reales."""

from services.publication_review import review_publication, summarize


def _indicator(**overrides):
    base = {
        "id": "POLICIA_SEMANAL:total:TOTAL", "source": "Policia Nacional", "source_code": "POLICIA_SEMANAL",
        "indicator_name": "Total de hechos registrados", "value": 18.0, "comparison_value": 26.0,
        "period_start": "2026-09-06", "period_end": "2026-09-12", "cutoff_date": "2026-09-12",
        "metadata": {"small_base": True},
    }
    base.update(overrides)
    return base


def _publication(indicators, blockers=()):
    return {
        "period": {"start": "2026-09-06", "end": "2026-09-12"},
        "indicators": indicators,
        "insights": [{"evidence_indicator_ids": [indicators[0]["id"]]}] if indicators else [],
        "sources": [],
        "governance": {"public_only": True, "review_blockers": list(blockers)},
    }


def _codes(checks, level):
    return {check["code"] for check in checks if check["level"] == level}


def test_weekly_bulletin_with_real_problems_is_flagged():
    comisaria = {
        "source_code": "COMISARIAS_FAMILIA", "source": "Comisarias de Familia", "cutoff_date": "2025-09-30",
        "metadata": {"coverage_type": "CONTEXT", "reporting_entity": "Comisaría Segunda de Familia",
                     "period_label": "enero a septiembre de 2025"},
    }
    publication = _publication([
        _indicator(),
        _indicator(id="c1", indicator_name="Casos de violencia intrafamiliar atendidos", value=212.0, **comisaria),
        _indicator(id="c2", indicator_name="Medidas de proteccion definitivas", value=212.0, **comisaria),
    ])
    checks = review_publication(publication)
    assert {"TITULAR_PRELIMINAR", "TITULAR_BASE_PEQUENA", "CIFRAS_DE_OTRO_PERIODO", "VALORES_IDENTICOS"} <= _codes(checks, "REVISAR")
    detail = next(check["detail"] for check in checks if check["code"] == "CIFRAS_DE_OTRO_PERIODO")
    assert "enero a septiembre de 2025" in detail
    summary = summarize(checks)
    assert summary["can_publish"] and summary["warnings"] >= 4


def test_source_without_coverage_blocks_publication():
    checks = review_publication(_publication([_indicator()], blockers=["No hay cortes aprobados de Comisarias."]))
    assert "FUENTE_SIN_COBERTURA" in _codes(checks, "BLOQUEA")
    assert not summarize(checks)["can_publish"]


def test_clean_complete_period_only_has_ok_checks():
    clean = _indicator(value=939.0, comparison_value=958.0, period_start="2026-01-01",
                       period_end="2026-08-31", metadata={"small_base": False})
    checks = review_publication(_publication([clean]))
    assert not _codes(checks, "BLOQUEA") and not _codes(checks, "REVISAR")
    assert {"COBERTURA", "PRIVACIDAD", "FECHAS"} <= _codes(checks, "OK")


def test_empty_bulletin_is_blocked():
    assert "SIN_INDICADORES" in _codes(review_publication(_publication([])), "BLOQUEA")
