"""Tablero y estadísticas cuentan como el cálculo oficial: última entrega en las fechas que cubre."""
from datetime import date
from uuid import UUID

import pytest
from sqlalchemy import func
from sqlalchemy.orm import Session

from api import analitica
from db.models_hechos_seguridad import HechoSeguridad, SabanaSnapshotRow
from db.session import engine
from services import entrega_vigente as ev
from services.hechos_metrics import hechos_unicos_expr


def test_filtro_sql_con_ventanas_y_pares():
    entrega = ev.EntregaVigente(UUID("44021d06-766a-47bd-9069-16a239477b17"), "SEM 37.xlsx",
                                ((date(2025, 1, 1), date(2025, 9, 12)), (date(2026, 1, 1), date(2026, 9, 12))))
    sql = ev.filtro_sql(None, prefijo="h", entrega=entrega)
    assert "h.fecha_evento BETWEEN DATE '2025-01-01' AND DATE '2025-09-12'" in sql
    assert "h.conducta_estandar) IN (SELECT hecho_key, conducta_estandar FROM sabana_snapshot_rows" in sql
    assert "ingestion_id = '44021d06-766a-47bd-9069-16a239477b17'" in sql


def test_sin_entrega_no_filtra():
    assert ev.filtro_sql(None, entrega=ev.EntregaVigente(UUID(int=1), None, ())) == ""


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


def test_dentro_de_la_entrega_cuenta_lo_mismo_que_la_foto(db):
    entrega = ev.entrega_vigente(db)
    if entrega is None:
        pytest.skip("Sin entregas cargadas en esta base")
    inicio, fin = entrega.ventanas[-1]
    foto = db.query(func.count(func.distinct(SabanaSnapshotRow.hecho_key))).filter(
        SabanaSnapshotRow.ingestion_id == entrega.run_id,
        SabanaSnapshotRow.fecha_evento.between(inicio, fin)).scalar()
    assert analitica._hechos_total(db, inicio, fin) == foto
    homicidios_foto = db.query(func.count(func.distinct(SabanaSnapshotRow.hecho_key))).filter(
        SabanaSnapshotRow.ingestion_id == entrega.run_id,
        SabanaSnapshotRow.fecha_evento.between(inicio, fin),
        SabanaSnapshotRow.conducta_estandar.in_(analitica.CONDUCTA_KEYS["HOMICIDIO"])).scalar()
    assert analitica._hechos_count(db, analitica.CONDUCTA_KEYS["HOMICIDIO"], inicio, fin) == homicidios_foto


def test_fuera_de_la_entrega_se_usa_el_historico(db):
    entrega = ev.entrega_vigente(db)
    if entrega is None:
        pytest.skip("Sin entregas cargadas en esta base")
    anterior = entrega.ventanas[0][0].year - 1
    inicio, fin = date(anterior, 1, 1), date(anterior, 12, 31)
    historico = db.query(hechos_unicos_expr()).filter(
        HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
        HechoSeguridad.fecha_evento.between(inicio, fin)).scalar()
    assert analitica._hechos_total(db, inicio, fin) == historico
