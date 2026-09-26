from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.auth import institutional_access
from db.models import User
from db.models_medicina_legal import MedicinaLegalRecord, MedicinaLegalSnapshot
from db.session import get_db


router = APIRouter()

DATASET_NAMES = {
    "HOMICIDIOS_DEF": "Presuntos homicidios (definitivas)",
    "SUICIDIOS_DEF": "Presuntos suicidios (definitivas)",
    "FATALES_PRE": "Lesiones fatales (preliminar)",
    "NOFATALES_PRE": "Lesiones no fatales (preliminar)",
}


@router.get("/summary")
def medicina_legal_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(institutional_access),
):
    """Resumen de cortes, versiones y conteos de Medicina Legal para Jamundí."""
    result = []
    for key, name in DATASET_NAMES.items():
        snapshot = db.query(MedicinaLegalSnapshot).filter_by(
            dataset_key=key
        ).order_by(
            MedicinaLegalSnapshot.cutoff_date.desc(),
            MedicinaLegalSnapshot.created_at.desc(),
        ).first()
        if snapshot:
            result.append({
                "dataset_key": key,
                "dataset_id": snapshot.dataset_id,
                "name": name,
                "definitive": snapshot.definitive,
                "cutoff_date": snapshot.cutoff_date.isoformat() if snapshot.cutoff_date else None,
                "record_count": snapshot.filtered_count,
                "source_row_count": snapshot.source_row_count,
                "payload_sha256": snapshot.payload_sha256,
                "schema_version": snapshot.schema_version,
            })
    return {
        "generated_at": datetime.now(timezone.utc),
        "connector": "MEDICINA_LEGAL",
        "datasets": result,
    }