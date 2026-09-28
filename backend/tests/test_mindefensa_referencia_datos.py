"""Referencia nacional de MinDefensa desde datos.gov.co: mismo paquete que armaba el monitor."""
from datetime import date

import pytest
from sqlalchemy.orm import Session

from db.models_intelligence import NationalCrimeStats
from db.session import engine
from services import mindefensa_referencia_datos as ref
from services.mindefensa_reference_service import COMPACT_REFERENCE_SOURCE, MUNICIPAL_REFERENCE_SOURCE

FILAS = [
    {"cod_depto": "76", "departamento": "VALLE DEL CAUCA", "cod_muni": "76364", "municipio": "JAMUNDI", "anio": "2026", "mes": "1", "cantidad": "12"},
    {"cod_depto": "76", "departamento": "VALLE DEL CAUCA", "cod_muni": "76364", "municipio": "JAMUNDI", "anio": "2026", "mes": "8", "cantidad": "5"},
    {"cod_depto": "05", "departamento": "ANTIOQUIA", "cod_muni": "05001", "municipio": "MEDELLIN", "anio": "2026", "mes": "8", "cantidad": "30"},
    {"cod_depto": "19", "departamento": "CAUCA", "cod_muni": "19001", "municipio": "POPAYAN", "anio": "2025", "mes": "3", "cantidad": "7"},
]


def falsa_consulta(dataset, **p):
    if p.get("$select", "").startswith("max("):
        return [{"corte": "2026-08-28T00:00:00.000"}]
    assert "fecha_hecho >= '2024-01-01'" in p["$where"]
    return FILAS


def test_paquete_con_pais_region_totales_y_cobertura():
    paquete = ref.armar_paquete("m8fd-ahd9", "Homicidio Intencional", falsa_consulta, hoy=date(2026, 9, 27))
    assert paquete["source_cutoff"] == "2026-08-31" and paquete["tipo_delito"] == "Homicidio Intencional"
    nacional = {(r["anio"], r["mes"]): r["cantidad"] for r in paquete["records"] if r["codigo_dane"] == "NACIONAL"}
    assert nacional[(2026, 8)] == 35  # Jamundí 5 + Medellín 30
    regionales = {r["codigo_dane"] for r in paquete["records"] if r["codigo_dane"] != "NACIONAL"}
    assert regionales == {"76364", "19001"}  # Medellín no es de Valle ni Cauca
    jamundi_2026 = next(t for t in paquete["municipal_totals"] if t["codigo_dane"] == "76364" and t["anio"] == 2026)
    assert jamundi_2026["cantidad"] == 17 and jamundi_2026["period_end_month"] == 8
    assert {c["anio"] for c in paquete["coverage"]} == {2025, 2026}


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


def test_se_guarda_con_las_llaves_de_contexto_comparado(db):
    paquete = ref.armar_paquete("m8fd-ahd9", "Homicidio Intencional", falsa_consulta, hoy=date(2026, 9, 27))
    from services.mindefensa_reference_service import persist_reference_payload
    persist_reference_payload(db, paquete)
    agosto = db.query(NationalCrimeStats).filter_by(source_id=COMPACT_REFERENCE_SOURCE, tipo_delito="Homicidio Intencional",
                                                    codigo_dane="76364", anio=2026, mes=8).one()
    assert agosto.cantidad == 5 and agosto.fuente_archivo == "datos.gov.co/m8fd-ahd9"
    assert db.query(NationalCrimeStats).filter_by(source_id=MUNICIPAL_REFERENCE_SOURCE, tipo_delito="Homicidio Intencional",
                                                  codigo_dane="05001", anio=2026).one().cantidad == 30
