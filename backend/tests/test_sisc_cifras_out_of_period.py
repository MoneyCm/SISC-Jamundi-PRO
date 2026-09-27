"""SISC en cifras: un boletín no mezcla en sus cifras informes de otro periodo."""
from services.sisc_cifras_service import Indicator, SiscCifrasService as S


def indicator(code, source_code, context=False, entity=None, label=None):
    metadata = {"coverage_type": "CONTEXT", "reporting_entity": entity, "period_label": label} if context else {}
    return Indicator(id=code, source="Fuente", source_code=source_code, domain="FAMILIA Y PROTECCION", category="x",
                     indicator_code=code, indicator_name=code, value=69.0, unit="casos", period_start="2026-01-01",
                     period_end="2026-03-26", geography="JAMUNDI", comparison_value=None, variation_absolute=None,
                     variation_percentage=None, quality_status="VALIDADO", publication_level="PUBLICO",
                     cutoff_date="2026-03-26", metadata=metadata)


def test_los_informes_de_otro_periodo_salen_de_las_cifras():
    items = [
        indicator("hechos", "POLICIA_SEMANAL"),
        indicator("medidas", "COMISARIAS_FAMILIA", True, "Comisaría Segunda de Familia", "enero a marzo de 2026"),
        indicator("pard", "COMISARIAS_FAMILIA", True, "Comisaría Segunda de Familia", "enero a marzo de 2026"),
        indicator("pard", "COMISARIAS_FAMILIA", True, "Comisaría Primera de Familia", "enero a septiembre de 2025"),
    ]
    in_period, out_of_period = S.split_out_of_period(items)
    assert [i.indicator_code for i in in_period] == ["hechos"]
    assert len(out_of_period) == 3
    notes = S.out_of_period_notes(out_of_period)
    assert [n["entity"] for n in notes] == ["Comisaría Segunda de Familia", "Comisaría Primera de Familia"]  # una por dependencia
    assert notes[0]["note"] == ("Último informe disponible de Comisaría Segunda de Familia: enero a marzo de 2026. "
                                "No corresponde al periodo del boletín y no se incluye en sus cifras.")
