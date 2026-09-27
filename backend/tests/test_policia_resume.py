from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock
import uuid

import pandas as pd
from db.models_hechos_seguridad import IngestionRun, SabanaSnapshotRow
from services import excel_policia_processor as module


def test_resume_counts_saved_rows_as_approved_without_inserting_them(monkeypatch):
    run = SimpleNamespace(id=uuid.uuid4(), resumen={})
    saved = SimpleNamespace(record_key='saved-key', fecha_evento=date(2026, 9, 1), semana_num=35)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = run
    db.query.return_value.filter.return_value.all.return_value = [saved]
    monkeypatch.setattr(module.PoliciaJamundiProcessor, '_load_catalogo', lambda self: {})
    monkeypatch.setattr(module.PoliciaJamundiProcessor, '_generate_narrative_alerts', lambda self: None)
    monkeypatch.setattr(module.PoliciaJamundiProcessor, '_homologar_conducta', lambda *a: ('HURTO', 'HURTO'))
    monkeypatch.setattr(module.GeocodingService, 'get_coords_for_localidad', lambda *a: None)
    monkeypatch.setattr(module, 'build_snapshot_record_key', lambda *a: 'saved-key')
    frame = pd.DataFrame([{'HECHOS_ID':'test-1', 'FECHA_HECHO':'2026-09-01', 'DESCRIPCION_CONDUCTA':'HURTO', 'MUNICIPIO':'JAMUNDI'}] * 2)
    monkeypatch.setattr(module, 'select_sheet_frame', lambda *a: ('Sheet1', frame))
    processor = module.PoliciaJamundiProcessor(db)
    result = processor._process_locked(b'test-content', 'test.csv', run_id=str(run.id))
    assert run.status == 'COMPLETED'
    assert run.aprobadas == 1
    assert run.rechazadas == 0
    assert result['stats']['filas_snapshot'] == 1
    assert result['stats']['repetidas_en_archivo'] == 1
    assert run.cobertura_inicio == date(2026, 9, 1)
    assert not any(isinstance(call.args[0], SabanaSnapshotRow) for call in db.add.call_args_list)
