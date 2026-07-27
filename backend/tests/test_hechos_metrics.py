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