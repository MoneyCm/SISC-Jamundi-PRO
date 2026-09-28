"""Capa judicial de la Fiscalía desde datos.gov.co, con respuestas simuladas."""
import pytest
from sqlalchemy.orm import Session

from db.models_source_center import SourceConnectorState
from db.session import engine
from services import fiscalia_datos_sync as fis
from services.source_center_service import SourceCenterService


def falsa_consulta(dataset, **p):
    where = p.get("$where", "")
    if p.get("$select") == "fecha_corte_datos":
        return [{"fecha_corte_datos": "31/08/2026"}]
    assert "mes_hecho" in where and "<='08'" in where  # mismo periodo: enero a agosto
    anio = "2026" if "'2026'" in where else "2025"
    if p.get("$group") == "capitulo_delito":
        return [{"capitulo_delito": "Del Hurto", "n": "10" if anio == "2026" else "12"},
                {"capitulo_delito": "De La Violencia Intrafamiliar", "n": "4" if anio == "2026" else "3"}]
    if p.get("$group") == "estado, etapa":
        return [{"estado": "Activo", "etapa": "Indagación", "n": "12"}, {"estado": "Activo", "etapa": "Juicio", "n": "2"}]
    return [{"n": "7" if dataset == fis.VICTIMAS else "3"}]


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


def test_nombres_legibles():
    assert fis.nombre_capitulo("De La Violencia Intrafamiliar") == "Violencia intrafamiliar"
    assert fis.nombre_capitulo("Del Homicidio") == "Homicidio (incluye culposos)"


def test_resumen_del_anio_contra_el_mismo_periodo():
    r = fis.resumen(falsa_consulta)
    assert r["corte"].isoformat() == "2026-08-31"
    assert r["procesos"][0] == {"delito": "Hurto", "actual": 10, "anterior": 12}
    assert r["procesos"][-1] == {"delito": "Total de procesos", "actual": 14, "anterior": 15}
    assert r["respuesta_judicial"] == {"Indagación (activo)": 12, "Juicio (activo)": 2}
    assert r["personas"][0]["actual"] == 7 and r["personas"][1]["actual"] == 3


def test_tarjeta_con_tabla_judicial(db):
    db.query(SourceConnectorState).filter_by(connector_code=fis.CONECTOR).delete()
    assert fis.sincronizar(db, falsa_consulta) is not None
    assert fis.sincronizar(db, falsa_consulta) is None
    tarjeta = next(c for c in SourceCenterService.summary(db)["connectors"] if c["code"] == fis.CONECTOR)
    assert tarjeta["contrast_kind"] == "judicial" and tarjeta["record_count"] == 14
    assert tarjeta["judicial_stages"]["Juicio (activo)"] == 2
