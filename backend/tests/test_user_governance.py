from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api import reportes, users
from api.auth import SecurityChecker, user_session_version


def _guard(router, path):
    route = next(route for route in router.routes if route.path == path)
    return next(
        dependency.call
        for dependency in route.dependant.dependencies
        if isinstance(dependency.call, SecurityChecker)
    )


def _user(password="hash-a", active=True, level=2, roles=("ANALYST",)):
    return SimpleNamespace(
        password_hash=password,
        is_active=active,
        data_level_max=level,
        expires_at=None,
        roles=[SimpleNamespace(code=role) for role in roles],
    )


def test_security_sensitive_user_changes_invalidate_session_fingerprint():
    baseline = user_session_version(_user())
    assert baseline != user_session_version(_user(password="hash-b"))
    assert baseline != user_session_version(_user(active=False))
    assert baseline != user_session_version(_user(level=3))
    assert baseline != user_session_version(_user(roles=("DIRECTIVE",)))


def test_privileged_roles_cannot_be_requested_by_self_service():
    assert {"TI_ADMIN", "FUNC_ADMIN", "DATA_OWNER", "PORTAL_ADMIN"}.isdisjoint(
        users.REQUESTABLE_ROLE_CODES
    )


def test_password_policy_rejects_weak_and_username_based_passwords():
    with pytest.raises(HTTPException):
        users._validate_password_strength("short")
    with pytest.raises(HTTPException):
        users._validate_password_strength("Analista.2026!", "analista")
    users._validate_password_strength("Lluvia!Cali2026")


def test_user_mutations_and_reports_require_ti_or_operational_roles():
    assert _guard(users.router, "/{user_id}").allowed_roles == ["TI_ADMIN"]
    assert _guard(users.router, "/{user_id}/status").allowed_roles == ["TI_ADMIN"]
    assert _guard(users.router, "/{user_id}/reset-password").allowed_roles == ["TI_ADMIN"]

    expected = {"ANALYST", "DIRECTIVE", "FUNC_ADMIN"}
    assert set(_guard(reportes.router, "/generar-boletin").allowed_roles) == expected
    assert set(_guard(reportes.router, "/generar-boletin-ejecutivo").allowed_roles) == expected


def test_bootstrap_never_resets_an_existing_admin_password():
    source = (Path(__file__).parents[1] / "create_roles_v2.py").read_text(encoding="utf-8")
    assert 'os.getenv("ADMIN_PASSWORD", "admin_password")' not in source
    existing_branch = source.split("else:", 1)[1]
    assert "admin_user.password_hash =" not in existing_branch
    assert "admin_user.is_active = True" not in existing_branch
