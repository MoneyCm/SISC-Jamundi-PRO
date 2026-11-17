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
    if "a_o_hecho in" in where:
        return seguimiento_falso(p)
    assert "mes_hecho" in where and "<='08'" in where  # mismo periodo: enero a agosto
    anio = "2026" if "'2026'" in where else "2025"
    if p.get("$group") == "capitulo_delito":
        return [{"capitulo_delito": "Del Hurto", "n": "10" if anio == "2026" else "12"},
                {"capitulo_delito": "De La Violencia Intrafamiliar", "n": "4" if anio == "2026" else "3"}]
    if p.get("$group") == "estado, etapa":
        return [{"estado": "Activo", "etapa": "Indagación", "n": "12"}, {"estado": "Activo", "etapa": "Juicio", "n": "2"}]
    return [{"n": "7" if dataset == fis.VICTIMAS else "3"}]


def seguimiento_falso(p):
    """Etapas de los procesos de 2024, 2025 y 2026 (sin filtro de mes: años completos)."""
    grupo = p["$group"]
    if grupo == "a_o_hecho, etapa, estado":
        return [{"a_o_hecho": "2024", "etapa": "Indagación", "estado": "Inactivo", "n": "60"},
                {"a_o_hecho": "2024", "etapa": "Indagación", "estado": "Activo", "n": "30"},
                {"a_o_hecho": "2024", "etapa": "Juicio", "estado": "Activo", "n": "4"},
                {"a_o_hecho": "2024", "etapa": "Ejecución De Penas", "estado": "Inactivo", "n": "6"},
                {"a_o_hecho": "2026", "etapa": "Indagación", "estado": "Activo", "n": "20"}]
    if grupo == "a_o_hecho, delito, etapa, estado":
        assert "capitulo_delito='Del Homicidio'" in p["$where"]
        return [{"a_o_hecho": "2024", "delito": "Homicidio Art. 103 C.P.", "etapa": "Juicio", "estado": "Activo", "n": "2"},
                {"a_o_hecho": "2024", "delito": "Homicidio Art. 103 C.P. Agravado", "etapa": "Indagación", "estado": "Activo", "n": "8"},
                {"a_o_hecho": "2024", "delito": "Homicidio Culposo Art. 109 C.P.", "etapa": "Indagación", "estado": "Activo", "n": "3"}]
    assert "'2026'" not in p["$where"]  # por delito solo los dos años completos
    return [{"a_o_hecho": "2025", "capitulo_delito": "Del Hurto", "etapa": "Indagación", "estado": "Inactivo", "n": "40"},
            {"a_o_hecho": "2025", "capitulo_delito": "Del Hurto", "etapa": "Juicio", "estado": "Activo", "n": "1"},
            {"a_o_hecho": "2025", "capitulo_delito": "De La Violencia Intrafamiliar", "etapa": "Juicio", "estado": "Activo", "n": "5"},
            {"a_o_hecho": "2024", "capitulo_delito": "Del Hurto", "etapa": "Ejecución De Penas", "estado": "Inactivo", "n": "2"}]


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


def test_seguimiento_de_los_tres_anios():
    s = fis.resumen(falsa_consulta)["seguimiento"]
    assert s["anios"] == [2024, 2025, 2026] and s["anio_en_curso"] == 2026
    t2024 = s["todos"]["2024"]
    assert (t2024["total"], t2024["indagacion_inactiva"], t2024["juicio_o_condena"]) == (100, 60, 10)
    assert s["todos"]["2025"]["total"] == 0 and s["todos"]["2026"]["indagacion_activa"] == 20
    assert s["homicidio_doloso"]["2024"]["total"] == 10 and s["homicidio_doloso"]["2024"]["juicio_o_condena"] == 2
    assert s["homicidio_culposo"]["2024"]["total"] == 3
    hurto = s["por_delito"][0]
    assert hurto["delito"] == "Hurto" and hurto["2025"]["total"] == 41 and hurto["2024"]["condena"] == 2
    assert "2026" not in hurto


def test_el_seguimiento_queda_en_los_detalles(db):
    db.query(SourceConnectorState).filter_by(connector_code=fis.CONECTOR).delete()
    fis.sincronizar(db, falsa_consulta)
    estado = db.get(SourceConnectorState, fis.CONECTOR)
    assert estado.details["seguimiento"]["todos"]["2024"]["juicio_o_condena"] == 10


def test_la_pestana_interna_lee_el_seguimiento(db):
    from types import SimpleNamespace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api import source_center
    from api.auth import institutional_access
    from db.session import get_db

    app = FastAPI()
    app.include_router(source_center.router, prefix="/api/source-center")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[institutional_access] = lambda: SimpleNamespace(username="prueba")
    cliente = TestClient(app)

    db.query(SourceConnectorState).filter_by(connector_code=fis.CONECTOR).delete()
    assert cliente.get("/api/source-center/fiscalia/respuesta-judicial").json()["available"] is False
    fis.sincronizar(db, falsa_consulta)
    datos = cliente.get("/api/source-center/fiscalia/respuesta-judicial").json()
    assert datos["available"] and datos["corte"] == "2026-08-31"
    assert datos["seguimiento"]["todos"]["2024"]["juicio_o_condena"] == 10
