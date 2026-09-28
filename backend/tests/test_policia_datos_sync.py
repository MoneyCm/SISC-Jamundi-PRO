"""Contraste de la Policía Nacional desde datos.gov.co, con respuestas simuladas."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from db.models_source_center import SourceConnectorState
from db.session import engine
from services import policia_datos_sync as pol
from services.source_center_service import SourceCenterService


def falsa_consulta(dataset, **parametros):
    if "$select" in parametros:
        return [{"corte": "2026-08-30T00:00:00.000"}]
    return [{"fecha_hecho": "2026-03-10T00:00:00.000", "cantidad": "2"},
            {"fecha_hecho": "2026-09-05T00:00:00.000", "cantidad": "1"},   # después del corte
            {"fecha_hecho": "2025-04-01T00:00:00.000", "cantidad": "1"},
            {"fecha_hecho": "2025-10-01T00:00:00.000", "cantidad": "1"}]   # fuera del mismo periodo


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    session.commit = session.flush
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def test_suma_hasta_el_cierre_del_mes_y_contrasta_con_la_sabana(db):
    resultado = pol.contraste(db, falsa_consulta)
    assert resultado["corte"].isoformat() == "2026-08-31" and len(resultado["filas"]) == 8
    homicidio = next(f for f in resultado["filas"] if f["delito"] == "Homicidio")
    assert (homicidio["oficial_actual"], homicidio["oficial_anterior"]) == (2, 1)
    if homicidio["sabana_actual"] is not None:
        assert homicidio["diferencia"] == homicidio["sabana_actual"] - 2
    extorsion = next(f for f in resultado["filas"] if f["delito"] == "Extorsión")
    assert extorsion["sabana_actual"] is None and extorsion["diferencia"] is None


def test_revisa_cada_semana_y_llena_la_tarjeta(db):
    db.query(SourceConnectorState).filter_by(connector_code=pol.CONECTOR).delete()
    assert pol.sincronizar(db, falsa_consulta) is not None
    assert pol.sincronizar(db, falsa_consulta) is None
    db.get(SourceConnectorState, pol.CONECTOR).last_checked_at = datetime.now(timezone.utc) - timedelta(days=8)
    assert pol.sincronizar(db, falsa_consulta) is not None
    tarjeta = next(c for c in SourceCenterService.summary(db)["connectors"] if c["code"] == pol.CONECTOR)
    assert tarjeta["source_cutoff_date"] == "2026-08-31" and tarjeta["indicator_count"] == 8
    assert len(tarjeta["contrast"]) == 8


def test_si_falla_queda_el_aviso(db):
    db.query(SourceConnectorState).filter_by(connector_code=pol.CONECTOR).delete()

    def caida(dataset, **parametros):
        raise OSError("sin conexión")

    assert "error" in pol.sincronizar(db, caida)
    assert db.get(SourceConnectorState, pol.CONECTOR).status == "ERROR"
