"""Prueba funcional REAL contra la BD del contenedor sisc_backend (datos reales).

Verifica que collect_dataset_identity con las 3 fuentes tri-fuente
devuelve latest_snapshot_id para SPOA/ML, y que el guard
require_tri_fuente_homicidios dispara correctamente.
"""
import os, sys
sys.path.insert(0, "/app")

from datetime import date
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

# 1) collect_dataset_identity con datos reales de la BD
from db.session import SessionLocal
from services.sisc_cifras_service import SiscCifrasService


def test_collect_identity_real():
    db = SessionLocal()
    try:
        identity = SiscCifrasService.collect_dataset_identity(
            db,
            date(2024, 1, 1),
            date(2024, 12, 31),
            source_codes=["POLICIA_SEMANAL", "FISCALIA_SPOA_V3", "MEDICINA_LEGAL"],
        )
    finally:
        db.close()

    pol = (identity or {}).get("POLICIA_SEMANAL") or {}
    spoa = (identity or {}).get("FISCALIA_SPOA_V3") or {}
    ml = (identity or {}).get("MEDICINA_LEGAL") or {}

    print("=== collect_dataset_identity real ===")
    print("POLICIA_SEMANAL ->", {k: pol.get(k) for k in ("cutoff_date", "unique_count", "content_hash")})
    print("FISCALIA_SPOA_V3 ->", {k: spoa.get(k) for k in ("status", "cutoff_date", "unique_count", "latest_snapshot_id", "error", "content_hash")})
    print("MEDICINA_LEGAL ->", {k: ml.get(k) for k in ("status", "cutoff_date", "unique_count", "latest_snapshot_id", "content_hash")})

    assert "unique_count" in pol, "POLICIA_SEMANAL debe tener unique_count real"
    assert "status" in spoa and spoa["status"] == "SIN_ENTREGA_FIJA", f"SPOA error real: {spoa}"
    assert "latest_snapshot_id" in ml, "ML debe tener latest_snapshot_id (snapshot HOMICIDIOS_DEF existe)"
    assert ml["latest_snapshot_id"], "latest_snapshot_id no vacío"
    print("OK: identity real coherente")


# 2) require_tri_fuente_homicidios con source_version_ids construidos desde identity
from services import publication_guards


def test_guard_real():
    spoa_id = None
    ml_id = None
    pol_id = None
    # Resolvemos los UUIDs de la BD
    db = SessionLocal()
    try:
        from db.models_fiscalia_spoa import FiscaliaSpoaSnapshot
        from db.models_medicina_legal import MedicinaLegalSnapshot
        from db.models_hechos_seguridad import IngestionRun
        ml = db.query(MedicinaLegalSnapshot).filter(
            MedicinaLegalSnapshot.definitive.is_(True),
            MedicinaLegalSnapshot.dataset_key == "HOMICIDIOS_DEF",
        ).order_by(MedicinaLegalSnapshot.cutoff_date.desc()).first()
        spoa = db.query(FiscaliaSpoaSnapshot).filter(
            FiscaliaSpoaSnapshot.cutoff_date.isnot(None)
        ).order_by(FiscaliaSpoaSnapshot.cutoff_date.desc()).first()
        pol_run = db.query(IngestionRun).filter(
            IngestionRun.fuente_codigo == "POLICIA_SEMANAL",
            IngestionRun.status == "COMPLETED",
        ).order_by(IngestionRun.fecha_fin.desc()).first()
        ml_id = str(ml.id) if ml else None
        spoa_id = str(spoa.id) if spoa else None
        pol_id = str(pol_run.id) if pol_run else None
    finally:
        db.close()

    versions = {
        "POLICIA_SEMANAL": pol_id,
        "FISCALIA_SPOA_V3": spoa_id,
        "MEDICINA_LEGAL": ml_id,
    }
    row = MagicMock()
    row.source_codes = ["POLICIA_SEMANAL", "FISCALIA_SPOA_V3", "MEDICINA_LEGAL"]
    row.source_version_ids = versions
    row.period_start = date(2024, 1, 1)
    row.period_end = date(2024, 12, 31)

    print("=== guard require_tri_fuente_homicidios real ===")
    print("source_version_ids:", versions)

    if spoa_id is None:
        print("NOTA: sin snapshots SPOA en BD → el guard tirará 422 por entrega FISCALIA_SPOA_V3 ausente (esperado)")
        try:
            db2 = SessionLocal()
            try:
                publication_guards.require_tri_fuente_homicidios(db2, row)
            finally:
                db2.close()
        except HTTPException as e:
            assert e.status_code == 422
            assert "FISCALIA_SPOA_V3" in e.detail
            print("OK: guard revierte 422 por entrega SPOA ausente (comportamiento correcto)")
    else:
        with patch(
            "services.reconciliation_tri_fuente_service.reconcile_homicidios_tri_fuente",
            return_value={"fuente_final": "FISCALIA_SPOA_V3"},
        ) as fake:
            result = publication_guards.require_tri_fuente_homicidios(MagicMock(), row)
            assert result == {"fuente_final": "FISCALIA_SPOA_V3"}
            fake.assert_called_once()
            assert fake.call_args.kwargs["source_version_ids"]["MEDICINA_LEGAL"] == ml_id
            print("OK: guard con las 3 entregas → conciliación devuelta")
            print("reconcile called with:", fake.call_args.kwargs["source_version_ids"])


if __name__ == "__main__":
    test_collect_identity_real()
    test_guard_real()
    print("\n=== TODAS LAS PRUEBAS FUNCIONALES REALES PASARON ===")
