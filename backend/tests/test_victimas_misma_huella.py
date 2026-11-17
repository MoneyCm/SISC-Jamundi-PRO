"""Dos víctimas del mismo hecho con igual sexo y edad no se funden en la tabla maestra."""
import pandas as pd
import pytest
from sqlalchemy.orm import Session

from db.models_hechos_seguridad import HechoSeguridad, SabanaSnapshotRow
import db.models_dq  # noqa: F401  (registra dq_reports, que usa events)
from db.session import engine
from services import excel_policia_processor as module

HECHO = "TEST-VICTIMAS-9001"


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    session.commit = session.flush  # todo se deshace al final
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def _fila(nombre):
    return {"HECHOS_ID": HECHO, "FECHA_HECHO": "2025-09-27", "DESCRIPCION_CONDUCTA": "HOMICIDIO",
            "MUNICIPIO": "JAMUNDI", "GENERO": "MASCULINO", "EDAD": 18, "BARRIO": "JUAN DE AMPUDIA",
            "ARMA_MEDIO": "ARMA DE FUEGO", "MODALIDAD": nombre}


def _cargar(db, monkeypatch, filas):
    monkeypatch.setattr(module.PoliciaJamundiProcessor, "_generate_narrative_alerts", lambda self: None)
    monkeypatch.setattr(module.GeocodingService, "get_coords_for_localidad", lambda *a: None)
    monkeypatch.setattr(module, "select_sheet_frame", lambda *a: ("Hoja1", pd.DataFrame(filas)))
    contenido = repr(filas).encode()
    return module.PoliciaJamundiProcessor(db)._process_locked(contenido, "prueba.xlsx", force=True)


def _maestra(db):
    return db.query(HechoSeguridad).filter(HechoSeguridad.id_fuente == HECHO).all()


def test_dos_victimas_iguales_quedan_como_dos_filas(db, monkeypatch):
    _cargar(db, monkeypatch, [_fila("SICARIATO A"), _fila("SICARIATO B")])
    assert len(_maestra(db)) == 2
    assert db.query(SabanaSnapshotRow).filter(SabanaSnapshotRow.id_fuente == HECHO).count() == 2


def test_la_entrega_siguiente_actualiza_sin_duplicar(db, monkeypatch):
    _cargar(db, monkeypatch, [_fila("SICARIATO A"), _fila("SICARIATO B")])
    _cargar(db, monkeypatch, [_fila("SICARIATO A"), _fila("SICARIATO B"), {**_fila("X"), "HECHOS_ID": "TEST-OTRO-9002"}])
    filas = _maestra(db)
    assert len(filas) == 2
    assert len({f.ingestion_id for f in filas}) == 1  # las dos quedaron en la entrega más reciente


def test_la_copia_exacta_de_una_fila_sigue_siendo_una_sola(db, monkeypatch):
    _cargar(db, monkeypatch, [_fila("SICARIATO A"), _fila("SICARIATO A")])
    assert len(_maestra(db)) == 1


def test_la_huella_de_la_primera_victima_no_cambia():
    assert module.PoliciaJamundiProcessor.huella_de_victima("abc", 1) == "abc"
    assert module.PoliciaJamundiProcessor.huella_de_victima("abc", 2) != "abc"
