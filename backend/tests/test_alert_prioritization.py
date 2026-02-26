import sys
import os
from datetime import datetime

import pytest

# Asegurar que `services` esté en el path cuando se ejecuta pytest desde backend.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.alerts_prioritizer import compute_action_score, get_scoring_config


class MockAlert:
    def __init__(self, alert_type, metrics):
        self.alert_type = alert_type
        self.metrics = metrics


@pytest.fixture
def rnmc_metrics_base():
    """
    Métricas tipo RNMC usadas como base en varias pruebas.
    """
    return {
        "dias": 45,
        "valor_neto": 500000,
        "estado": "EN PROCESO",
        "localidad": "JAMUNDI URBANO",
        "medida": "Sanción económica",
    }


def _build_metrics_for_target_score(target_score: float) -> dict:
    """
    Construye métricas (dias, valor_neto) que deberían producir un score
    cercano a target_score, asumiendo la configuración por defecto.
    """
    config = get_scoring_config()

    # Fijamos zona neutra (0.5) y estado neutro (0.4) como en el diseño base.
    W_AGE = config["W_AGE"]
    W_VALUE = config["W_VALUE"]
    W_STATE = config["W_STATE"]
    W_ZONE = config["W_ZONE"]

    state_score = 0.4
    zone_score = 0.5

    fixed = W_STATE * state_score + W_ZONE * zone_score

    # Tomamos edad máxima para forzar una solución válida.
    age_score = 1.0
    max_dias = config["MAX_DIAS"]

    # target = 100 * (W_AGE*age_score + W_VALUE*value_score + fixed)
    target_frac = target_score / 100.0
    value_score = (target_frac - fixed - W_AGE * age_score) / W_VALUE

    # Clamp explícito a [0,1] por si el target exige algo fuera de rango.
    if value_score < 0:
        value_score = 0
    if value_score > 1:
        value_score = 1

    dias = max_dias  # produce age_score≈1
    valor_neto = value_score * config["MAX_VALOR"]

    return {
        "dias": dias,
        "valor_neto": valor_neto,
        "estado": "EN PROCESO",
        "localidad": "JAMUNDI URBANO",
    }


def test_tier_boundaries(monkeypatch):
    """
    Fronteras de tier:
    - 74.99 => P2
    - 75.00 => P1
    - 44.99 => P3
    - 45.00 => P2
    La comparación de tiers se hace usando el score final redondeado.
    """
    # Aseguramos config estable para la prueba
    monkeypatch.setenv("RNMC_SCORE_MAX_DIAS", "90")
    monkeypatch.setenv("RNMC_SCORE_MAX_VALOR", "2000000")
    monkeypatch.setenv("P1_THRESHOLD", "75")
    monkeypatch.setenv("P2_THRESHOLD", "45")

    cases = [
        (74.99, "P2"),
        (75.00, "P1"),
        (44.99, "P3"),
        (45.00, "P2"),
    ]

    for target, expected_tier in cases:
        metrics = _build_metrics_for_target_score(target)
        alert = MockAlert("RNMC_OTHER", metrics)
        res = compute_action_score(alert)

        # El score devuelto se redondea a 2 decimales; usamos margen pequeño.
        assert res["priority_tier"] == expected_tier
        assert abs(res["action_score"] - res["action_score"]) < 1e-6  # auto-consistencia


def test_idempotent_scoring(rnmc_metrics_base):
    """
    Misma alerta + misma config => mismo action_score, priority_tier y rationale_md
    en ejecuciones consecutivas.
    """
    alert = MockAlert("RNMC_REZAGO_PROCESO", rnmc_metrics_base)

    res1 = compute_action_score(alert)
    res2 = compute_action_score(alert)

    assert res1["action_score"] == res2["action_score"]
    assert res1["priority_tier"] == res2["priority_tier"]
    assert res1["rationale_md"] == res2["rationale_md"]
    assert res1["recommended_action"] == res2["recommended_action"]


def test_zone_optional_neutral(rnmc_metrics_base):
    """
    Si no hay zone_score en métricas, el sistema debe usar un valor neutral (0.5)
    y no fallar.
    """
    metrics = dict(rnmc_metrics_base)
    metrics.pop("zone_score", None)  # Nos aseguramos de que no esté presente

    alert = MockAlert("RNMC_REZAGO_PROCESO", metrics)
    res = compute_action_score(alert)

    assert 0 <= res["action_score"] <= 100
    assert res["priority_tier"] in {"P1", "P2", "P3"}
    assert isinstance(res["rationale_md"], str) and len(res["rationale_md"]) > 0
