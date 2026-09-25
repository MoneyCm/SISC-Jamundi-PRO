"""DEPRECATED — consolidado en `services.reconciliation_tri_fuente_service`.

Este módulo era un duplicado huérfano de la conciliación tri-fuente de
HOMICIDIOS (nunca estuvo cableado a ningún endpoint). El servicio canónico es
`services.reconciliation_tri_fuente_service.reconcile_homicidios_tri_fuente`,
que valida las 3 entregas fijas contra sus tablas reales
(IngestionRun / FiscaliaSpoaSnapshot / MedicinaLegalSnapshot).

Se conserva este shim solo por compatibilidad de imports: re-exporta los
símbolos canónicos. No añadir lógica aquí.
"""

from __future__ import annotations

from services.reconciliation_tri_fuente_service import (  # noqa: F401
    FUENTES,
    HOMICIDIO_CONDUCTAS,
    HOMICIDIO_UMBRAL_DELTA,
    ML_DATASET_HOMICIDIOS_DEF,
    PAIR_LABELS,
    SPOA_HOMICIDIO_TOKEN,
    reconcile_homicidios_tri_fuente,
)

__all__ = [
    "FUENTES",
    "HOMICIDIO_CONDUCTAS",
    "HOMICIDIO_UMBRAL_DELTA",
    "ML_DATASET_HOMICIDIOS_DEF",
    "PAIR_LABELS",
    "SPOA_HOMICIDIO_TOKEN",
    "reconcile_homicidios_tri_fuente",
]
