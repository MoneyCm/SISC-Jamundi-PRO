import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingest_medicina_legal import (
    MESES,
    _extract,
    _month_number,
    _payload_sha256,
    _record_key,
    DATASETS,
)
from db.models_medicina_legal import MedicinaLegalRecord, MedicinaLegalSnapshot


def test_medicina_legal_dataset_contract_is_stable():
    assert {item["id"] for item in DATASETS.values()} == {
        "vtub-3de2", "f75u-mirk", "2kpj-cktv", "79dd-d24f"
    }
    assert DATASETS["HOMICIDIOS_DEF"]["definitive"] is True
    assert DATASETS["FATALES_PRE"]["definitive"] is False
    assert any(item.name == "uq_ml_snapshot_record" for item in MedicinaLegalRecord.__table__.constraints)
    assert any(item.name == "uq_ml_snapshot_version" for item in MedicinaLegalSnapshot.__table__.constraints)


def test_medicina_legal_extract_and_record_key_are_stable():
    row = {
        "a_o_del_hecho": "2025",
        "mes_del_hecho": "diciembre",
        "sexo_de_la_victima": "Hombre",
        "grupo_de_edad_de_la_victima": "(20 a 24)",
        "codigo_dane_departamento": "76",
        "codigo_dane_municipio": "76364",
        "departamento_del_hecho_dane": "Valle del Cauca",
        "municipio_del_hecho_dane": "Jamundí",
        "zona_del_hecho": "Cabecera municipal",
        "escenario_del_hecho": "Vía pública",
        "manera_de_muerte": "1 Presuntos Homicidios",
        "mecanismo_causal": "Arma de fuego",
        "circunstancia_del_hecho": "Riña",
    }
    canon = _extract(row, DATASETS["FATALES_PRE"])
    assert canon["year"] == 2025
    assert canon["month"] == 12
    assert canon["contexto"] == "1 Presuntos Homicidios"
    assert canon["muni"] == "Jamundí"
    assert _record_key(canon) == _record_key(dict(canon))
    assert len(_record_key(canon)) == 64
    assert _payload_sha256([canon], "2kpj-cktv") != _payload_sha256(
        [{**canon, "contexto": "2 Presuntos Suicidios"}], "2kpj-cktv"
    )


def test_medicina_legal_month_mapping():
    assert _month_number("enero") == 1
    assert _month_number("Marzo") == 3
    assert _month_number("no aplica") is None
    assert MESES["diciembre"] == 12