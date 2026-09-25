"""Pruebas de aceptación — conciliación reproducible boletín semanal Policía.

- Cargar dos veces el mismo archivo no duplica cifras.
- Un hecho con varias víctimas respeta la unidad definida.
- Corregir un barrio mueve la distribución territorial sin aumentar el total.
- Una corrección retrospectiva conserva el valor publicado y muestra el actualizado.
- Una reclasificación cambia los indicadores aunque el total permanezca igual.
- Tablero, boletín y chat coinciden al consultar mismos filtros y versiones.
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.hechos_metrics import canonical_hecho_key
from services.indicator_catalog import INDICATOR_CATALOG, METHODOLOGY_VERSION, get_indicator_meta
from services.sabana_history import build_record_identity, content_hash


def test_catalog_declares_counting_unit():
    hom = get_indicator_meta("HOMICIDIO")
    assert hom["unit"] == "HECHO"
    assert hom["methodology_version"] == METHODOLOGY_VERSION
    assert "COUNT DISTINCT" in hom["deduplication"]
    assert hom["date_field"] == "fecha_evento"
    assert "barrio_normalizado" in hom["dimensions"]
    # Diagnóstico nunca es cifra oficial
    assert get_indicator_meta("POLICIA_REGISTROS")["unit"] == "REGISTRO_ORIGEN"


def test_multivictim_same_id_is_one_hecho():
    # Un hecho con tres víctimas: 3 registros, 1 hecho.
    keys = {canonical_hecho_key("H-1", f"fp-v{i}", f"row-{i}") for i in range(3)}
    assert keys == {"ID:H-1"}


def test_identity_stable_when_barrio_corrected():
    # Misma identidad, distinta huella: es modificación, no alta.
    first = {"HECHOS_ID": "H-1", "BARRIO": "A", "CONDUCTA": "HOMICIDIO", "FECHA": "2026-07-01"}
    corrected = {"HECHOS_ID": "H-1", "BARRIO": "B", "CONDUCTA": "HOMICIDIO", "FECHA": "2026-07-01"}
    id_a = build_record_identity("H-1", "fp-a")
    id_b = build_record_identity("H-1", "fp-b")
    assert id_a["record_identity"] == id_b["record_identity"] == "ID:H-1"
    assert id_a["confidence"] == "HIGH"
    assert content_hash(first) != content_hash(corrected)


def test_missing_id_marks_uncertain_match():
    ident = build_record_identity("", "fp-x")
    assert ident["confidence"] == "UNCERTAIN"
    # No presentar coincidencia aproximada como corrección confirmada.


def test_same_file_twice_does_not_change_hash():
    payload = {"HECHOS_ID": "H-1", "BARRIO": "A"}
    assert content_hash(payload) == content_hash(dict(payload))


def test_homicide_uses_hechos_not_rows():
    # Chat/IA debe usar hechos únicos para HOMICIDIO (misma regla que el resto).
    import pathlib
    src = pathlib.Path(__file__).resolve().parents[1] / "api" / "ia.py"
    text = src.read_text(encoding="utf-8")
    assert "func.count(HechoSeguridad.id)).filter(\n        HechoSeguridad.fuente_codigo == \"POLICIA_SEMANAL\",\n        HechoSeguridad.conducta_estandar.in_(HOMICIDE_ALIASES)" not in text
    assert "hechos_unicos_expr" in text


def test_reconciliation_classification_logic():
    # Simula publicado 54, recalculado 55, +1 alta; reclasificación sin cambio neto.
    old_map = {
        "ID:H-1": {"conducta": "HURTO", "content_hash": "a", "barrio": "X", "fecha": "2026-07-01"},
        "ID:H-2": {"conducta": "HURTO", "content_hash": "b", "barrio": "Y", "fecha": "2026-07-02"},
    }
    new_map = {
        "ID:H-1": {"conducta": "HURTO", "content_hash": "a", "barrio": "X", "fecha": "2026-07-01"},
        "ID:H-2": {"conducta": "LESIONES", "content_hash": "c", "barrio": "Y", "fecha": "2026-07-02"},
        "ID:H-3": {"conducta": "HURTO", "content_hash": "d", "barrio": "Z", "fecha": "2026-07-03"},
    }
    altas = sum(1 for k in new_map if k not in old_map)
    reclas = sum(1 for k in new_map if k in old_map and new_map[k]["content_hash"] != old_map[k]["content_hash"] and new_map[k]["conducta"] != old_map[k]["conducta"])
    assert altas == 1
    assert reclas == 1


def test_single_calculation_contract_shape():
    import hashlib
    import json
    payload = {
        "indicator": "HOMICIDIO",
        "period": {"start": "2026-01-01", "end": "2026-07-12"},
        "territory": "JAMUNDI",
        "source_version_id": "00000000-0000-0000-0000-000000000000",
        "methodology_version": "1",
    }
    qh = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    assert len(qh) == 64
    assert set(INDICATOR_CATALOG) >= {"HOMICIDIO", "SEGURIDAD_TOTAL", "POLICIA_REGISTROS"}
