"""Los meses que la sábana no trae (por ejemplo, diciembre de 2025) se avisan y no se muestran como una baja."""
from datetime import date

import pytest
from sqlalchemy.orm import Session

from api import analitica
from db.session import engine
from services import cobertura_sabana as cs
from services.asistente_periodos import fin_de_mes, meses_de


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


def _mes_vacio(db):
    """Un mes sin hechos entre el primero y el último cargados, si existe."""
    primero, corte = cs.limites(db)
    if not corte:
        return None
    for a, _b in meses_de(primero, corte):
        if cs.meses_incompletos(db, a.replace(day=1), fin_de_mes(a.year, a.month), corte) and \
                not db.execute(analitica.text(
                    "select 1 from hechos_seguridad where fuente_codigo='POLICIA_SEMANAL' and fecha_evento between :a and :b limit 1"),
                    {"a": a.replace(day=1), "b": fin_de_mes(a.year, a.month)}).first():
            return a.replace(day=1)
    return None


def test_mes_sin_datos_se_avisa_y_no_da_tasa(db):
    mes = _mes_vacio(db)
    if mes is None:
        pytest.skip("La sábana cargada no tiene meses vacíos")
    anio = mes.year
    kpis = analitica.get_dashboard_kpis(date(anio, 1, 1), date(anio, 12, 31), None, None, db)
    assert kpis["cobertura"]["completa"] is False
    assert cs.nombre_mes(mes) in kpis["cobertura"]["meses_incompletos"]
    assert kpis["tasa_homicidios"] is None


def test_la_tendencia_muestra_el_mes_vacio(db):
    mes = _mes_vacio(db)
    if mes is None:
        pytest.skip("La sábana cargada no tiene meses vacíos")
    filas = analitica.get_tendencia_delictiva(date(mes.year - 1, 1, 1), date(mes.year, 12, 31), None, db)
    vacias = [f for f in filas if f.get("sin_datos")]
    assert vacias and all(f["homicidios"] is None for f in vacias)


def test_ano_corrido_completo(db):
    primero, corte = cs.limites(db)
    if not corte:
        pytest.skip("Sin sábana")
    assert cs.cobertura(db, date(corte.year, 1, 1), corte)["completa"] is True


def test_portal_publico_avisa_meses_faltantes_y_no_publica_quien_cargo(db):
    from fastapi import Response
    mes = _mes_vacio(db)
    if mes is None:
        pytest.skip("La sábana cargada no tiene meses vacíos")
    datos = analitica.get_public_dashboard(Response(), year=mes.year, period_mode="year_to_date",
                                           comparison="same_period_previous_year", start_date=None, end_date=None,
                                           conducta=None, zona=None, territorio=None, include_map=False,
                                           min_location_count=3, db=db)
    meta = datos["metadata"]
    assert meta["cobertura"]["completa"] is False
    assert datos["kpis"]["tasa_homicidios"] is None
    assert "loaded_by" not in meta["last_ingestion"] and "id" not in meta["last_ingestion"]
