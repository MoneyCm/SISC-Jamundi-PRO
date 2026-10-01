"""Portal ciudadano: metas del PISCC y comparación con otros municipios."""
import pytest
from fastapi import Response
from sqlalchemy.orm import Session

from api import analitica
from db.session import engine
from services import comparacion_publica


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


def test_metas_publicas_sin_identificadores_internos(monkeypatch):
    from services import piscc_goals
    monkeypatch.setattr(piscc_goals, "build_goals", lambda db: {
        "as_of": "2026-09-30", "source": "PISCC", "note": "n", "closed_years_source": "MinDefensa", "closed_years_legend": {},
        "indicators": [{"id": "homicidios", "label": "Homicidios", "count": 79, "status": "DESVIACION",
                        "source_version_id": "interno", "goal_2027": 105, "baseline_2023": 115}]})
    datos = analitica.get_public_piscc(Response(), db=None)
    meta = datos["indicators"][0]
    assert meta["count"] == 79 and meta["goal_2027"] == 105
    assert "source_version_id" not in meta


def test_comparacion_incluye_jamundi_valle_y_colombia(db):
    if not comparacion_publica.anios_disponibles(db):
        pytest.skip("Sin cifras municipales de MinDefensa en esta base")
    datos = comparacion_publica.comparar(db, "homicidio")
    assert datos["available"] and datos["delito_nombre"] == "Homicidio"
    jamundi = [m for m in datos["municipios"] if m["es_jamundi"]]
    assert jamundi and jamundi[0]["municipio"] == "Jamundí" and jamundi[0]["tasa"] is not None
    assert datos["valle"]["tasa"] and datos["colombia"]["tasa"]
    assert 1 <= datos["puesto_valle"]["puesto"] <= datos["puesto_valle"]["de"] == 42
    tasas = [m["tasa"] for m in datos["municipios"]]
    assert tasas == sorted(tasas, reverse=True)


def test_delito_desconocido_usa_homicidio(db):
    if not comparacion_publica.anios_disponibles(db):
        pytest.skip("Sin cifras municipales de MinDefensa en esta base")
    assert comparacion_publica.comparar(db, "inventado")["delito"] == "homicidio"
    assert comparacion_publica._nombre("VALLE DEL CAUCA") == "Valle del Cauca"


def _tablero(db, **filtros):
    base = dict(year=None, period_mode="year_to_date", comparison="same_period_previous_year", start_date=None,
                end_date=None, conducta=None, zona=None, territorio=None, include_map=False, min_location_count=3)
    return analitica.get_public_dashboard(Response(), db=db, **{**base, **filtros})


def test_barrio_con_pocos_casos_no_publica_cifras(db):
    """Caso real: Libertadores en los últimos 7 días mostraba "1 homicidio"."""
    todos = _tablero(db)
    barrios = [t["name"] for t in todos["filters"]["available"]["territories"]]
    if not barrios:
        pytest.skip("Sin sábana en esta base")
    for barrio in barrios:
        datos = _tablero(db, period_mode="last_7_days", territorio=barrio)
        if datos.get("suppressed"):
            assert datos["kpis"]["total_hechos"] is None and datos["conductas"] == [] and datos["weekday"] == []
            assert "privacidad" in datos["suppressed"]["message"]
            break
    else:
        pytest.skip("Ningún barrio con menos de 3 casos en 7 días")


def test_la_lista_de_barrios_no_depende_del_periodo(db):
    anual = _tablero(db)["filters"]["available"]["territories"]
    semana = _tablero(db, period_mode="last_7_days")["filters"]["available"]["territories"]
    if not anual:
        pytest.skip("Sin sábana en esta base")
    assert [t["name"] for t in anual] == [t["name"] for t in semana]
