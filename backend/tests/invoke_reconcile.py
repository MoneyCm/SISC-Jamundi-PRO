"""Invoca la conciliación tri-fuente contra la BD real del contenedor."""
import sys
sys.path.insert(0, "/app")

from db.session import SessionLocal
from services.reconciliation_tri_fuente_service import reconcile_homicidios_tri_fuente

db = SessionLocal()
try:
    result = reconcile_homicidios_tri_fuente(
        db,
        period_start="2024-01-01",
        period_end="2024-12-31",
        source_version_ids={
            "POLICIA_SEMANAL": "438e1090-7e2a-497c-ae89-a67f8c4bbb0b",
            "FISCALIA_SPOA_V3": "3102458a-52e2-4cf4-9b54-6d9836691dfe",
            "MEDICINA_LEGAL": "7389ace6-11c0-41f2-9383-7859c0834975",
        },
    )
    import json
    print("=== CONCILIACION TRI-FUENTE (OBSERVATORIO) ===")
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
finally:
    db.close()
