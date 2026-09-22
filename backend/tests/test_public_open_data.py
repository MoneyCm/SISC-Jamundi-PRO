"""Dataset ciudadano versionado: constructores puros del paquete abierto."""
from api.analitica import (
    OPEN_DATA_CSV_HEADERS,
    OPEN_DATA_DICTIONARY,
    OPEN_DATA_LICENSE,
    build_open_data_package,
    build_open_data_records,
    open_data_csv_text,
    open_data_filename,
    open_data_version,
)

PAYLOAD = {
    "metadata": {
        "period_start": "2026-01-01",
        "period_end": "2026-09-12",
        "latest_event_date": "2026-09-12",
        "source": "SABANA SIEDCO/PONAL - Policia Nacional",
        "comparison_label": "Mismo periodo del ano anterior",
        "privacy": "Agregado.",
        "methodology": "Base consolidada.",
    },
    "kpis": {"total_hechos": 904, "previous_total": 932, "homicidios": 77},
    "conductas": [{"name": "Hurto a personas", "value": 324, "previous_value": 300}],
    "zones": [{"name": "URBANA", "value": 800}],
    "territories": [{"name": "TERRANOVA", "total": 69, "previous_value": 60}],
    "filters": {"selected": {"period_mode": "year_to_date"}},
}


def test_records_mirror_the_citizen_download_schema():
    rows = build_open_data_records(PAYLOAD)
    assert [row["dataset"] for row in rows] == [
        "indicadores", "indicadores", "conductas", "zonas", "territorios",
    ]
    assert rows[0]["current_value"] == 904
    assert rows[0]["comparison_value"] == 932
    assert rows[2]["category"] == "Hurto a personas"
    assert rows[4]["current_value"] == 69
    assert set(rows[0].keys()) == set(OPEN_DATA_CSV_HEADERS)


def test_missing_sections_default_to_empty():
    rows = build_open_data_records({})
    assert [row["dataset"] for row in rows] == ["indicadores", "indicadores"]
    assert all(row["current_value"] == "" for row in rows)


def test_version_hash_is_deterministic_and_sensitive():
    package = build_open_data_package(PAYLOAD)
    assert len(package["metadata"]["version"]) == 64
    assert package["metadata"]["version"] == build_open_data_package(PAYLOAD)["metadata"]["version"]
    altered = dict(PAYLOAD, kpis=dict(PAYLOAD["kpis"], total_hechos=905))
    assert build_open_data_package(altered)["metadata"]["version"] != package["metadata"]["version"]


def test_package_carries_license_dictionary_and_citation_fields():
    package = build_open_data_package(PAYLOAD)
    assert package["metadata"]["license"] == OPEN_DATA_LICENSE
    assert OPEN_DATA_LICENSE["short"] == "CC BY 4.0"
    assert "creativecommons.org/licenses/by/4.0" in OPEN_DATA_LICENSE["url"]
    assert package["data_dictionary"] == OPEN_DATA_DICTIONARY
    assert {entry["field"] for entry in OPEN_DATA_DICTIONARY} == set(OPEN_DATA_CSV_HEADERS)
    assert package["metadata"]["cutoff_date"] == "2026-09-12"


def test_csv_renders_header_rows_and_quotes_commas():
    package = build_open_data_package(PAYLOAD)
    text = open_data_csv_text(package)
    assert text.startswith("﻿")
    lines = text.lstrip("﻿").strip().splitlines()
    assert lines[0] == ",".join(OPEN_DATA_CSV_HEADERS)
    assert len(lines) == len(package["records"]) + 1
    quoted = build_open_data_package(
        dict(PAYLOAD, conductas=[{"name": "Hurto, atraco y robo", "value": 1}])
    )
    csv_lines = open_data_csv_text(quoted).strip().splitlines()
    assert '"Hurto, atraco y robo"' in csv_lines[3]


def test_filename_is_stable_and_citable():
    package = build_open_data_package(PAYLOAD)
    name = open_data_filename(package, "csv")
    assert name.startswith("sisc-jamundi-datos-abiertos-2026-09-12-")
    assert name.endswith(".csv")
    assert package["metadata"]["version"][:8] in name
