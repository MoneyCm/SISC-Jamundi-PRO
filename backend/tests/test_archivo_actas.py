"""Archivo de actas: el original se guarda, solo se adjunta el mismo archivo y el listado trae todas las actas."""
import hashlib
from datetime import date

import pytest
from sqlalchemy.orm import Session

from db.models_council import CouncilActFile, CouncilActRead
from db.session import engine
from services import council_commitments_service as svc


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def _acta(db, contenido=b"%PDF-1.4 acta de prueba", estado="CONFIRMADA"):
    fila = CouncilActRead(filename="Acta 99.pdf", sha256=hashlib.sha256(contenido).hexdigest(), instance="CONSEJO_SEGURIDAD",
                          act_number="99", act_date=date(2026, 9, 30), reading={"proposals": [{}, {}]}, status=estado,
                          result={"created": ["CS-2026-900"], "linked": ["CS-2026-001"], "skipped": []}, created_by="prueba")
    db.add(fila)
    db.commit()
    return fila


def test_solo_se_adjunta_el_mismo_archivo(db):
    fila = _acta(db)
    with pytest.raises(ValueError, match="no es el mismo"):
        svc.attach_act_file(db, str(fila.id), b"otro archivo", "otro.pdf", "mospina")
    assert svc.attach_act_file(db, str(fila.id), b"%PDF-1.4 acta de prueba", "Acta 99.pdf", "mospina")["has_file"]
    record, archivo = svc.get_act_file(db, str(fila.id))
    assert archivo.content == b"%PDF-1.4 acta de prueba" and archivo.content_type == "application/pdf"
    assert archivo.uploaded_by == "mospina"


def test_el_archivo_trae_todas_las_actas_con_su_estado(db):
    fila = _acta(db)
    pendiente = _acta(db, b"otra acta", estado="PENDIENTE")
    todas = {a["read_id"]: a for a in svc.act_archive(db)}
    assert todas[str(fila.id)]["commitments"] == 2 and todas[str(fila.id)]["has_file"] is False
    assert todas[str(pendiente.id)]["commitments"] == 2 and todas[str(pendiente.id)]["status"] == "PENDIENTE"


def test_sin_original_avisa(db):
    fila = _acta(db)
    with pytest.raises(LookupError):
        svc.get_act_file(db, str(fila.id))


def test_al_descartar_una_lectura_se_va_su_archivo(db):
    fila = _acta(db, b"lectura pendiente", estado="PENDIENTE")
    svc.save_act_file(db, fila, b"lectura pendiente", "pendiente.pdf", "mospina")
    svc.discard_act_read(db, str(fila.id))
    db.expire_all()
    assert db.query(CouncilActFile).filter(CouncilActFile.read_id == fila.id).count() == 0
