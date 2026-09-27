"""Revisión automática de MinDefensa para el PISCC, con respuestas simuladas de datos.gov.co."""
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from db.models_source_center import SourceConnectorState
from db.session import engine
from services import piscc_mindefensa_sync as sync
from services.source_center_service import SourceCenterService

JAMUNDI = {
    "d7zw-hpf4": [("2026-01-15", "2"), ("2026-01-15", "1"), ("2026-05-04", "1"), ("2025-05-03", "2"), ("2025-11-24", "1")],
    "q2ib-t9am": [("2026-08-23", "1"), ("2025-08-20", "1")],
    "gepp-dxcs": [("2026-08-31", "3"), ("2025-09-15", "4")],
}


def falsa_consulta(dataset, **parametros):
    if "$select" in parametros:
        return [{"corte": "2026-08-28T00:00:00.000"}]
    return [{"fecha_hecho": f + "T00:00:00.000", "cantidad": c} for f, c in JAMUNDI[dataset]]


@pytest.fixture
def archivo(tmp_path):
    ruta = tmp_path / "mindefensa.json"
    ruta.write_text(json.dumps({"mes_corte": "Junio", "indicadores": [
        {"delito": "Secuestro", "anterior": 2, "actual": 4, "ultimo_registro": "24/02/2026"},
        {"delito": "Homicidios", "anterior": 66, "actual": 68, "ultimo_registro": "30/06/2026"},
    ]}), encoding="utf-8")
    return ruta


def test_cuenta_el_anio_hasta_el_cierre_del_mes_y_el_mismo_periodo_anterior(archivo):
    resultado = sync.actualizar_archivo(falsa_consulta, archivo)
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    secuestro = next(f for f in datos["indicadores"] if f["delito"] == "Secuestro")
    assert (secuestro["actual"], secuestro["anterior"], secuestro["ultimo_registro"]) == (4, 2, "31/08/2026")
    assert secuestro["ultimo_caso_jamundi"] == "04/05/2026"
    vif = next(f for f in datos["indicadores"] if "intrafamiliar" in f["delito"].lower())
    assert (vif["actual"], vif["anterior"]) == (3, 0)  # el 15/09/2025 queda fuera del mismo periodo
    assert next(f for f in datos["indicadores"] if f["delito"] == "Homicidios")["actual"] == 68  # no se toca
    assert resultado["corte"].isoformat() == "2026-08-31" and resultado["cambios"]


def test_sin_novedades_no_reescribe(archivo):
    sync.actualizar_archivo(falsa_consulta, archivo)
    antes = archivo.read_text(encoding="utf-8")
    assert sync.actualizar_archivo(falsa_consulta, archivo)["cambios"] == []
    assert archivo.read_text(encoding="utf-8") == antes


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


def test_revisa_una_vez_por_semana_y_lo_anota_en_el_centro_de_fuentes(db, archivo):
    db.query(SourceConnectorState).filter_by(connector_code=sync.CONECTOR).delete()
    assert sync.sincronizar(db, falsa_consulta, archivo)["corte"].isoformat() == "2026-08-31"
    assert sync.sincronizar(db, falsa_consulta, archivo) is None  # ya revisó esta semana
    estado = db.get(SourceConnectorState, sync.CONECTOR)
    estado.last_checked_at = datetime.now(timezone.utc) - timedelta(days=8)
    assert sync.sincronizar(db, falsa_consulta, archivo) is not None
    tarjeta = next(c for c in SourceCenterService.summary(db)["connectors"] if c["code"] == sync.CONECTOR)
    assert tarjeta["source_cutoff_date"] == "2026-08-31" and tarjeta["indicator_count"] == 3


def test_si_falla_la_consulta_queda_el_aviso(db, archivo):
    db.query(SourceConnectorState).filter_by(connector_code=sync.CONECTOR).delete()

    def caida(dataset, **parametros):
        raise OSError("sin conexión")

    assert "error" in sync.sincronizar(db, caida, archivo)
    estado = db.get(SourceConnectorState, sync.CONECTOR)
    assert estado.status == "ERROR" and "sin conexión" in estado.warnings[0]
