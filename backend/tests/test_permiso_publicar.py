"""Publicar boletines: solo el permiso "Publica boletines" (la Secretaria) y la administración; un directivo sin ese permiso no."""
from api import sisc_cifras, sisc_cifras_v1


def test_quien_publica():
    for roles in (sisc_cifras.PUBLISHER_ROLES, sisc_cifras_v1.PUBLISHER_ROLES):
        assert set(roles) == {"PUBLICATION_APPROVER", "FUNC_ADMIN", "TI_ADMIN"}
        assert "DIRECTIVE" not in roles and "ANALYST" not in roles


def test_aprobar_exige_el_permiso():
    ruta = next(r for r in sisc_cifras.router.routes if r.path == "/publications/{publication_id}/approve")
    guardias = [d.call for d in ruta.dependant.dependencies if hasattr(d.call, "allowed_roles")]
    assert guardias and set(guardias[0].allowed_roles) == set(sisc_cifras.PUBLISHER_ROLES)


def test_no_se_aprueba_un_borrador_de_una_sabana_reemplazada(monkeypatch):
    """Caso real: borrador de agosto armado con SEM 37 (100 hechos) cuando la vigente es SEM 39 (105)."""
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from uuid import uuid4

    import pytest
    from fastapi import HTTPException

    from api import sisc_cifras
    from services import indicator_calculation

    row = SimpleNamespace(status="DRAFT", source_version_ids={"POLICIA_SEMANAL": "sem-37"}, publication_json={})
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = row
    monkeypatch.setattr(indicator_calculation, "_latest_completed_run", lambda db: SimpleNamespace(id="sem-39"))
    with pytest.raises(HTTPException) as error:
        asyncio.run(sisc_cifras.approve_sisc_cifras_publication(uuid4(), MagicMock(), None, db, MagicMock()))
    assert error.value.status_code == 409 and "sábana anterior" in error.value.detail
