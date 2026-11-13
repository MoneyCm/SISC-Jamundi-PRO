import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.hechos_metrics import canonical_hecho_key


def test_same_source_id_is_one_hecho_for_multiple_victims():
    first = canonical_hecho_key("ABC-42", "victim-a", "row-a")
    second = canonical_hecho_key(" ABC-42 ", "victim-b", "row-b")
    assert first == second == "ID:ABC-42"


def test_fingerprint_is_fallback_when_source_id_is_missing():
    assert canonical_hecho_key(None, "fingerprint-1", "row-a") == "FP:fingerprint-1"
    assert canonical_hecho_key("", "fingerprint-2", "row-b") == "FP:fingerprint-2"


def test_record_id_is_last_resort():
    assert canonical_hecho_key(None, None, "row-a") == "ROW:row-a"

def test_sql_expression_counts_distinct_canonical_keys():
    from sqlalchemy.dialects import postgresql
    from services.hechos_metrics import hechos_unicos_expr

    sql = str(hechos_unicos_expr().compile(dialect=postgresql.dialect()))
    assert "count(distinct" in sql.lower()
    assert "hechos_seguridad.id_fuente" in sql
    assert "hechos_seguridad.fingerprint" in sql

def test_homicidio_se_cuenta_por_victima_y_lo_demas_por_hecho():
    from sqlalchemy.dialects import postgresql
    from db.models_hechos_seguridad import SabanaSnapshotRow
    from services.hechos_metrics import es_conteo_por_victima, hechos_unicos_expr

    assert es_conteo_por_victima("Homicidio") and es_conteo_por_victima(" HOMICIDIO DOLOSO ")
    assert not es_conteo_por_victima("Lesiones personales")
    assert not es_conteo_por_victima("Homicidio (Tránsito)")
    for model in (None, SabanaSnapshotRow):
        expr = hechos_unicos_expr() if model is None else hechos_unicos_expr(model)
        sql = str(expr.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        assert "count(distinct(case" in sql.lower()
        assert "'HOMICIDIO'" in sql and "'V:'" in sql


def test_conteo_oficial_en_sqlite_cuadra_con_la_policia():
    """Doble homicidio (mismo HECHOS_ID) = 2 víctimas; lesiones con 2 filas del mismo hecho = 1."""
    import uuid
    from datetime import date
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from db.models_hechos_seguridad import SabanaSnapshotRow
    from services.hechos_metrics import hechos_unicos_expr

    engine = create_engine("sqlite://")
    SabanaSnapshotRow.__table__.create(engine)
    run = uuid.uuid4()

    def fila(hecho, conducta):
        return SabanaSnapshotRow(id=uuid.uuid4(), ingestion_id=run, record_key=uuid.uuid4().hex,
                                 hecho_key=hecho, anio=2026, fecha_evento=date(2026, 11, 2),
                                 conducta_estandar=conducta)

    with Session(engine) as db:
        db.add_all([fila("ID:1", "Homicidio"), fila("ID:1", "Homicidio"), fila("ID:2", "Homicidio"),
                    fila("ID:3", "Lesiones personales"), fila("ID:3", "Lesiones personales")])
        db.commit()
        homicidios = db.scalar(select(hechos_unicos_expr(SabanaSnapshotRow)).where(
            SabanaSnapshotRow.conducta_estandar == "Homicidio"))
        lesiones = db.scalar(select(hechos_unicos_expr(SabanaSnapshotRow)).where(
            SabanaSnapshotRow.conducta_estandar == "Lesiones personales"))
    assert homicidios == 3
    assert lesiones == 1
