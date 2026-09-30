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
    # Hecho, conducta y fecha de la entrega vigente (una fecha corregida no se cuenta dos veces).
    assert "h.conducta_estandar, h.fecha_evento) IN (SELECT hecho_key, conducta_estandar, fecha_evento FROM sabana_snapshot_rows" in sql
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


def test_cada_mes_cuenta_lo_mismo_que_la_foto(db):
    """Si la Policía corrige la fecha de un hecho, la versión vieja no se cuenta en otro mes (caso real: 40234501)."""
    entrega = ev.entrega_vigente(db)
    if entrega is None:
        pytest.skip("Sin entrega vigente en la base")
    inicio, fin = entrega.ventanas[-1]
    for mes in range(inicio.month, fin.month + 1):
        desde = date(inicio.year, mes, 1)
        hasta = min(fin, date(inicio.year + (mes == 12), mes % 12 + 1, 1).replace(day=1) - (date(2000, 1, 2) - date(2000, 1, 1)))
        foto = db.query(func.count(func.distinct(SabanaSnapshotRow.hecho_key))).filter(
            SabanaSnapshotRow.ingestion_id == entrega.run_id, SabanaSnapshotRow.fecha_evento.between(desde, hasta)).scalar()
        sisc = db.query(hechos_unicos_expr()).filter(
            HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL", ev.filtro_hechos(db, entrega=entrega),
            HechoSeguridad.fecha_evento.between(desde, hasta)).scalar()
        assert sisc == foto, (desde, hasta, sisc, foto)


def test_consulta_mensual_por_barrio_cuenta_solo_ese_barrio(db, monkeypatch):
    from services import asistente_secretaria as svc
    entrega = ev.entrega_vigente(db)
    if entrega is None:
        pytest.skip("Sin entrega vigente en la base")
    inicio = entrega.ventanas[-1][1].replace(day=1)
    fin = entrega.ventanas[-1][1]
    fila = db.query(HechoSeguridad.barrio_normalizado, hechos_unicos_expr().label("n")).filter(
        HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL", ev.filtro_hechos(db, entrega=entrega),
        HechoSeguridad.barrio_normalizado.isnot(None), HechoSeguridad.fecha_evento.between(inicio, fin)
    ).group_by(HechoSeguridad.barrio_normalizado).order_by(hechos_unicos_expr().desc()).first()
    if fila is None:
        pytest.skip("Sin barrios en el mes")
    barrio, esperado = fila
    monkeypatch.setattr(svc, "detectar_temas", lambda db, q: {"delitos": [], "entidades": [], "barrios": [barrio], "piscc": []})
    texto = svc.responder_mes(db, "¿Qué pasó en el barrio este mes?", inicio, date(inicio.year, inicio.month, 28) if inicio.month == 2 else fin, fin)["respuesta"]
    assert f"Total de delitos: {esperado}" in texto
    assert svc.nombre_barrio(barrio) in texto
