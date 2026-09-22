"""Conciliación tri-fuente de HOMICIDIOS — arbitraje forense, jamás suma capas.

SERVICIO CANÓNICO tri-fuente (consolida `tri_source_reconciliation.py`, que queda
marcado DEPRECATED). `services/reconciliation_service.py` sigue siendo el servicio
vivo de 2 entregas (misma fuente, versión vieja vs nueva) y NO se toca.

Tres capas independientes describen el mismo hecho (arrastre del Observatorio
para Jamundí, DANE 76364):

- POLICIA_SEMANAL : sábana SIEDCO policial, unidad HECHO (COUNT DISTINCT hecho_key).
- FISCALIA_SPOA_V3: procesos SPOA de la Fiscalía; un proceso con HOMICIDIO = 1
  (COUNT DISTINCT entidad|proceso con token HOMICI en delito_id/delito).
- MEDICINA_LEGAL   : INMLCF homicidios definitivos (dataset HOMICIDIOS_DEF,
  municipio DANE 76364, COUNT DISTINCT record_key).

Reglas metodológicas (no negociables en publicación):
1. NUNCA se suman las capas: el mismo hecho consta hasta en las tres. Sumar
   contaría el mismo homicidio hasta tres veces.
2. Ninguna capa "corrige" a otra en la cifra oficial: la cifra del boletín
   sale de POLICIA_SEMANAL (capa de entrega fija de la metodología). La capa
   forense INMLCF se usa como árbitro de explicación, no de sustitución.
3. UMBRAL de conciliación: Δ absoluto (hechos), por defecto Δ<=1. Con cifras
   mensuales pequeñas de homicidio, un Δ absoluto es más estable que un
   porcentaje. Si |Δ|>1 se marca WARNING (evidencia), NUNCA se bloquea:
   el desfase puede deberse a fechas de corte distintas entre fuentes.
4. ENTREGA FIJA OBLIGATORIA: faltar una de las 3 entregas (ausente o
   irresoluble) lanza ValueError → el endpoint responde 422 y la publicación
   se bloquea. El backend jamás "arregla" una fuente ausente.

Retorno (mismo contrato que en el boletín `SISC EN CIFRAS`):
{
  "period": {"start": ..., "end": ...},
  "hechos_por_fuente": {
      "POLICIA_SEMANAL": {"hechos": N, "source_version_id": ..., "estado": "FIXED"},
      "FISCALIA_SPOA_V3": {"hechos": M, "source_version_id": ..., "estado": "FIXED"},
      "MEDICINA_LEGAL":   {"hechos": K, "source_version_id": ..., "estado": "FIXED"},
  },
  "pares": [
      {"par": "POLICIA-SPOA", "delta": ..., "dentro_umbral": ...},
      ...
  ],
  "estado": "CONCILIADO" | "WARNING",
  "arbitraje_forense": {...},
  "evidencias": [...],
  "nota_metodologica": "...",
  "methodology_version": "...",
}
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional, Union
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models_fiscalia_spoa import FiscaliaSpoaRecord, FiscaliaSpoaSnapshot
from db.models_hechos_seguridad import IngestionRun, SabanaSnapshotRow
from db.models_medicina_legal import MedicinaLegalRecord, MedicinaLegalSnapshot
from services.indicator_catalog import METHODOLOGY_VERSION, get_indicator_meta

# Umbral absoluto: la aritmética homicidial es de números pequeños.
HOMICIDIO_UMBRAL_DELTA = 1

# Discriminante canónico HOMICIDIO en la sábana policial (mismo que el motor).
try:
    HOMICIDIO_CONDUCTAS = get_indicator_meta("HOMICIDIO")["conducta_filter"]
except (ValueError, KeyError, TypeError):
    HOMICIDIO_CONDUCTAS = ["Homicidio", "HOMICIDIO", "HOMICIDIO INTENCIONAL", "HOMICIDIO DOLOSO"]

# SPOA: homicidio se identifica por token en delito_id / delito (la ingesta
# fiscalia_spoa ya homologa 'HOMICI' → HOMICIDIO; ver api/ingesta.py:174).
SPOA_HOMICIDIO_TOKEN = "HOMICI"

# INMLCF: solo el conjunto definitivo de homicidios, ya filtrado a Jamundí
# (codigo_dane_municipio=76364) durante la ingesta.
ML_DATASET_HOMICIDIOS_DEF = "HOMICIDIOS_DEF"
DANE_JAMUNDI = "76364"

FUENTES = ("POLICIA_SEMANAL", "FISCALIA_SPOA_V3", "MEDICINA_LEGAL")


def _coerce_date(value: Union[date, str]) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _resolve_policia_delivery(db: Session, source_version_id: str) -> IngestionRun:
    """Entrega fija policial: existe y COMPLETED. Si no, ValueError (bloquea)."""
    try:
        run_id = UUID(str(source_version_id))
    except ValueError:
        raise ValueError(f"Entrega POLICIA_SEMANAL inválida (no es UUID): {source_version_id}")
    run = db.query(IngestionRun).filter(
        IngestionRun.id == run_id,
        IngestionRun.fuente_codigo == "POLICIA_SEMANAL",
    ).first()
    if run is None:
        raise ValueError(f"No existe entrega fija POLICIA_SEMANAL {source_version_id} en el servidor.")
    if run.status != "COMPLETED":
        raise ValueError(f"La entrega POLICIA_SEMANAL {source_version_id} no es utilizable (estado {run.status}).")
    return run


def _resolve_spoa_delivery(db: Session, source_version_id: str) -> FiscaliaSpoaSnapshot:
    """Snapshot SPOA fijo: existe. Si no, ValueError (bloquea)."""
    try:
        snap_id = UUID(str(source_version_id))
    except ValueError:
        raise ValueError(f"Entrega FISCALIA_SPOA_V3 inválida (no es UUID): {source_version_id}")
    snap = db.query(FiscaliaSpoaSnapshot).filter_by(id=snap_id).first()
    if snap is None:
        raise ValueError(f"No existe entrega fija FISCALIA_SPOA_V3 {source_version_id} en el servidor.")
    return snap


def _resolve_ml_delivery(db: Session, source_version_id: str) -> MedicinaLegalSnapshot:
    """Snapshot INMLCF fijo: existe. Si no, ValueError (bloquea)."""
    try:
        snap_id = UUID(str(source_version_id))
    except ValueError:
        raise ValueError(f"Entrega MEDICINA_LEGAL inválida (no es UUID): {source_version_id}")
    snap = db.query(MedicinaLegalSnapshot).filter_by(id=snap_id).first()
    if snap is None:
        raise ValueError(f"No existe entrega fija MEDICINA_LEGAL {source_version_id} en el servidor.")
    return snap


_RESOLVERS = {
    "POLICIA_SEMANAL": _resolve_policia_delivery,
    "FISCALIA_SPOA_V3": _resolve_spoa_delivery,
    "MEDICINA_LEGAL": _resolve_ml_delivery,
}


def _count_policia_homicidio(
    db: Session,
    *,
    start: date,
    end: date,
    source_version_id: str,
) -> int:
    """HECHOS únicos de HOMICIDIO en la sábana policial para la entrega fija."""
    value = db.query(func.count(func.distinct(SabanaSnapshotRow.hecho_key))).filter(
        SabanaSnapshotRow.ingestion_id == UUID(str(source_version_id)),
        SabanaSnapshotRow.conducta_estandar.in_(HOMICIDIO_CONDUCTAS),
        SabanaSnapshotRow.fecha_evento >= start,
        SabanaSnapshotRow.fecha_evento <= end,
    ).scalar()
    return int(value or 0)


def _count_spoa_homicidio(
    db: Session,
    *,
    start: date,
    end: date,
    source_version_id: str,
) -> int:
    """Procesos SPOA con HOMICIDIO en el periodo para la entrega fija.

    Unidad: proceso (entidad|proceso anonimizado) con token HOMICI en
    delito_id o delito. Cada proceso con homicidio cuenta como 1 hecho.
    """
    homicidio = (
        (FiscaliaSpoaRecord.delito_id.is_(None))
        & (FiscaliaSpoaRecord.delito.ilike(f"%{SPOA_HOMICIDIO_TOKEN}%"))
    ) | (FiscaliaSpoaRecord.delito_id.ilike(f"%{SPOA_HOMICIDIO_TOKEN}%"))
    proceso = func.concat(
        FiscaliaSpoaRecord.entity_anonimizado,
        "|",
        func.coalesce(FiscaliaSpoaRecord.proceso_anonimizado, ""),
    )
    value = db.query(func.count(func.distinct(proceso))).filter(
        FiscaliaSpoaRecord.snapshot_id == UUID(str(source_version_id)),
        homicidio,
        FiscaliaSpoaRecord.year_hecho.isnot(None),
        FiscaliaSpoaRecord.month_hecho.isnot(None),
        (
            (FiscaliaSpoaRecord.year_hecho > start.year)
            | ((FiscaliaSpoaRecord.year_hecho == start.year)
               & (FiscaliaSpoaRecord.month_hecho >= start.month))
        )
        & (
            (FiscaliaSpoaRecord.year_hecho < end.year)
            | ((FiscaliaSpoaRecord.year_hecho == end.year)
               & (FiscaliaSpoaRecord.month_hecho <= end.month))
        ),
    ).scalar()
    return int(value or 0)


def _count_ml_homicidio(
    db: Session,
    *,
    start: date,
    end: date,
    source_version_id: str,
) -> int:
    """HECHOS únicos de homicidio INMLCF (definitivas, Jamundí) en el periodo."""
    value = db.query(func.count(func.distinct(MedicinaLegalRecord.record_key))).filter(
        MedicinaLegalRecord.snapshot_id == UUID(str(source_version_id)),
        MedicinaLegalRecord.dataset_key == ML_DATASET_HOMICIDIOS_DEF,
        MedicinaLegalRecord.year_hecho.isnot(None),
        MedicinaLegalRecord.month_hecho.isnot(None),
        MedicinaLegalRecord.codigo_dane_municipio == DANE_JAMUNDI,
        (
            (MedicinaLegalRecord.year_hecho > start.year)
            | ((MedicinaLegalRecord.year_hecho == start.year)
               & (MedicinaLegalRecord.month_hecho >= start.month))
        )
        & (
            (MedicinaLegalRecord.year_hecho < end.year)
            | ((MedicinaLegalRecord.year_hecho == end.year)
               & (MedicinaLegalRecord.month_hecho <= end.month))
        ),
    ).scalar()
    return int(value or 0)


_COUNTERS = {
    "POLICIA_SEMANAL": _count_policia_homicidio,
    "FISCALIA_SPOA_V3": _count_spoa_homicidio,
    "MEDICINA_LEGAL": _count_ml_homicidio,
}

PAIR_LABELS = {
    ("POLICIA_SEMANAL", "FISCALIA_SPOA_V3"): "POLICIA-SPOA",
    ("POLICIA_SEMANAL", "MEDICINA_LEGAL"): "POLICIA-INMLCF",
    ("FISCALIA_SPOA_V3", "MEDICINA_LEGAL"): "SPOA-INMLCF",
}


def reconcile_homicidios_tri_fuente(
    db: Session,
    *,
    period_start: Union[date, str],
    period_end: Union[date, str],
    source_version_ids: Dict[str, str],
) -> Dict[str, Any]:
    """Cruza las tres capas para el mismo periodo y devuelve la conciliación.

    Lanza ValueError si falta una entrega fija (ausente o irresoluble): las
    tres fuentes son obligatorias para arbitrar homicidio; el backend jamás
    "arregla" una fuente ausente. `source_version_ids`: {FUENTE: UUID}.
    """
    start = _coerce_date(period_start)
    end = _coerce_date(period_end)
    if start > end:
        raise ValueError("La fecha inicial no puede ser posterior al corte.")

    missing = [code for code in FUENTES if not source_version_ids.get(code)]
    if missing:
        raise ValueError(f"Conciliar homicidios exige entrega fija de: {', '.join(missing)}.")

    # Resolver las 3 entregas ANTES de contar: si una no existe, se bloquea aquí.
    deliveries: Dict[str, Any] = {}
    for code in FUENTES:
        deliveries[code] = _RESOLVERS[code](db, source_version_ids[code])

    counts: Dict[str, Dict[str, Any]] = {}
    for code in FUENTES:
        value = _COUNTERS[code](
            db, start=start, end=end, source_version_id=source_version_ids[code]
        )
        counts[code] = {
            "hechos": value,
            "source_version_id": str(source_version_ids[code]),
            "estado": "FIXED",
        }

    pares = []
    discrepancias = []
    for (a, b), label in PAIR_LABELS.items():
        va = int(counts[a]["hechos"])
        vb = int(counts[b]["hechos"])
        diferencia = abs(va - vb)
        dentro = diferencia <= HOMICIDIO_UMBRAL_DELTA
        pares.append({
            "par": label,
            "fuente_a": a,
            "fuente_b": b,
            "hechos_a": va,
            "hechos_b": vb,
            "diferencia": diferencia,
            "dentro_umbral": dentro,
        })
        if not dentro:
            discrepancias.append(label)

    # Arbitraje forense: INMLCF definitivo es la capa de referencia cuando hay
    # desacuerdo, pero NUNCA reemplaza la fuente declarada en source_codes.
    arbitraje: Dict[str, Any] = {"usado_inmlcf": True, "desempate": None}
    if discrepancias:
        ml = int(counts["MEDICINA_LEGAL"]["hechos"])
        pol = int(counts["POLICIA_SEMANAL"]["hechos"])
        spoa = int(counts["FISCALIA_SPOA_V3"]["hechos"])
        if abs(ml - pol) <= HOMICIDIO_UMBRAL_DELTA and spoa != pol:
            arbitraje["desempate"] = {
                "fuente_final": "POLICIA_SEMANAL",
                "razon": "INMLCF y Policía coinciden dentro del umbral; SPOA se desvía.",
            }
        elif abs(ml - spoa) <= HOMICIDIO_UMBRAL_DELTA and pol != spoa:
            arbitraje["desempate"] = {
                "fuente_final": "FISCALIA_SPOA_V3",
                "razon": "INMLCF y Fiscalía coinciden dentro del umbral; Policía se desvía.",
            }
        else:
            arbitraje["desempate"] = {
                "fuente_final": "MEDICINA_LEGAL",
                "razon": "Las tres capas divergen; INMLCF definitivo es la referencia forense.",
            }

    estado = "WARNING" if discrepancias else "CONCILIADO"
    if estado == "CONCILIADO":
        evidencias = [
            "Las tres fuentes concuerdan dentro del umbral absoluto "
            f"(±{HOMICIDIO_UMBRAL_DELTA} hecho) para el periodo."
        ]
    else:
        evidencias = [
            f"{p['par']}: {p['hechos_a']} vs {p['hechos_b']} "
            f"(diferencia {p['diferencia']} > ±{HOMICIDIO_UMBRAL_DELTA})."
            for p in pares if not p["dentro_umbral"]
        ]

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "hechos_por_fuente": counts,
        "pares": pares,
        "estado": estado,
        "arbitraje_forense": arbitraje,
        "evidencias": evidencias,
        "nota_metodologica": (
            "Las capas no se suman: un mismo homicidio puede constar en Policía, "
            "Fiscalía e INMLCF. Todas cuentan HECHOS únicos. INMLCF (definitivas) "
            "arbitra el desempate forense sin sustituir la fuente declarada."
        ),
        "methodology_version": METHODOLOGY_VERSION,
    }
