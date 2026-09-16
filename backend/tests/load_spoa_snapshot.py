"""Carga un snapshot SPOA de prueba en la BD del contenedor sisc_backend.

Objetivo: que el guard tri-fuente dispare con las 3 entregas (Policía + SPOA + ML)
y se genere la conciliación tri-fuente visible en el boletín del observatorio.

Uso: docker exec sisc_backend python tests/load_spoa_snapshot.py
"""
import sys
sys.path.insert(0, "/app")

from datetime import date
from db.session import SessionLocal
from db.models_fiscalia_spoa import FiscaliaSpoaRun, FiscaliaSpoaSnapshot, FiscaliaSpoaRecord

RUN_ID = "spoa-run-2024-12"
SNAPSHOT_DATASET_KEY = "HOMICIDIOS"
SNAPSHOT_DATASET_ID = "jamundi-2024"


def load():
    db = SessionLocal()
    try:
        # 1) Run SPOA COMPLETED
        run = FiscaliaSpoaRun(
            id=RUN_ID,
            status="COMPLETED",
            source_cutoff_date=date(2024, 12, 1),
            datasets={},
            details={},
        )
        db.add(run)

        # 2) Snapshot asociado al run (cutoff dentro del período)
        snap = FiscaliaSpoaSnapshot(
            run_id=RUN_ID,
            dataset_key=SNAPSHOT_DATASET_KEY,
            dataset_id=SNAPSHOT_DATASET_ID,
            cutoff_date=date(2024, 12, 1),
            metadata_sha256="0" * 64,
            payload_sha256="1" * 64,
            schema_version="1",
        )
        db.add(snap)
        db.flush()  # obtener snap.id sin commit

        # 3) Record asociado al snapshot (año/mes en rango)
        rec = FiscaliaSpoaRecord(
            snapshot_id=snap.id,
            dataset_key=SNAPSHOT_DATASET_KEY,
            record_key="test-record-spoa-2024-12",
            entity_anonimizado="entidad-test",
            proceso_anonimizado="proceso-test",
            delito_id="HOMICIDIO",
            delito="HOMICIDIO",
            year_hecho=2024,
            month_hecho=12,
            estado="PROCESANDO",
            payload={},
        )
        db.add(rec)
        db.commit()
        print("OK snapshot SPOA cargado:")
        print("  run_id:", RUN_ID)
        print("  snapshot_id:", snap.id)
        print("  record_key:", rec.record_key)
    except Exception as e:
        db.rollback()
        print("ERROR:", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    load()
