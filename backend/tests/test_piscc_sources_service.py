from datetime import date

from services.piscc_sources_service import load_mindefensa


def test_mindefensa_preserves_independent_cutoffs(tmp_path, monkeypatch):
    # Archivo de ejemplo: cada indicador trae su propio corte y no se mezclan.
    import json
    from services import piscc_sources_service
    snapshot = tmp_path / "mindefensa.json"
    snapshot.write_text(json.dumps({"indicadores": [
        {"delito": "Secuestro", "anterior": 2, "actual": 4, "ultimo_registro": "24/02/2026"},
        {"delito": "Extorsión", "anterior": 15, "actual": 16, "ultimo_registro": "14/05/2026"},
        {"delito": "Violencia Intrafamiliar", "anterior": 92, "actual": 152, "ultimo_registro": "25/06/2026"},
    ]}), encoding="utf-8")
    monkeypatch.setattr(piscc_sources_service, "SNAPSHOT", snapshot)
    sources, notices = load_mindefensa(date(2026, 8, 31))
    assert sources["secuestro"]["countBase"] == 4
    assert sources["secuestro"]["fechaCorte"] == "2026-02-24"
    assert sources["extorsion"]["countBase"] == 16
    assert sources["vif"]["countBase"] == 152
    assert not notices
    parcial, avisos = load_mindefensa(date(2026, 3, 31))
    assert set(parcial) == {"secuestro"} and len(avisos) == 2


def test_el_archivo_real_trae_los_tres_indicadores_con_corte():
    sources, notices = load_mindefensa(date.today())
    assert set(sources) == {"secuestro", "extorsion", "vif"} and not notices


def test_mindefensa_does_not_use_future_values():
    sources, notices = load_mindefensa(date(2026, 1, 31))
    assert sources == {}
    assert len(notices) == 3
