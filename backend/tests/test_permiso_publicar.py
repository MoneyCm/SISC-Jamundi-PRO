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
