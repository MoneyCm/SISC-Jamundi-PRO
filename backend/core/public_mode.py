"""Modo publico del backend: solo lo que necesita el portal ciudadano.

Con SISC_PUBLIC_ONLY=true el servidor deja montadas unicamente las rutas de la
lista de abajo. Todo lo institucional (login, carga de sabanas, usuarios,
monitores, alertas, actas...) desaparece: responde 404 como si no existiera.

Ademas, cualquier ruta permitida que pida usuario autenticado se descarta, para
que un cambio futuro en un endpoint no lo deje expuesto por accidente.

Los formularios ciudadanos (reporte seguro, propuestas, frentes de seguridad)
escriben en la base. Quedan apagados salvo que SISC_PUBLIC_ALLOW_WRITES=true,
para poder desplegar contra una base de solo lectura.
"""
import logging
import os
import re
from typing import Iterable, List, Tuple

from fastapi import FastAPI
from fastapi.routing import APIRoute

logger = logging.getLogger("sisc_api.public_mode")

_TRUE = {"1", "true", "si", "sí", "yes"}

# (metodo, patron de ruta). El patron es una expresion regular sobre route.path.
PUBLIC_READ_ROUTES: List[Tuple[str, str]] = [
    ("GET", r"/"),
    ("GET", r"/api/analitica/public/.+"),
    ("GET", r"/api/analitica/estadisticas/(kpis|distribucion|ultima-actualizacion)"),
    ("GET", r"/api/intelligence/public/.+"),
    ("GET", r"/api/institutional-indicators/public"),
    ("GET", r"/api/participacion/(propuestas|frentes)"),
    # Asistente ciudadano (solo responde, no escribe en la base).
    # "SISC en cifras" y los boletines no van aqui: se generan y revisan en la oficina.
    ("POST", r"/api/ia/chat_ciudadano"),
]

PUBLIC_WRITE_ROUTES: List[Tuple[str, str]] = [
    ("POST", r"/api/participacion/reportes-seguros"),
    ("POST", r"/api/participacion/propuestas"),
    ("POST", r"/api/participacion/frentes"),
]

_AUTH_DEPENDENCIES = {"get_current_user", "require_role", "require_data_level", "role_checker", "checker"}


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in _TRUE


def is_public_only() -> bool:
    return _flag("SISC_PUBLIC_ONLY")


def _requires_auth(route: APIRoute) -> bool:
    pending = [route.dependant]
    while pending:
        dependant = pending.pop()
        call = getattr(dependant, "call", None)
        name = getattr(call, "__name__", "") or ""
        qualname = getattr(call, "__qualname__", "") or ""
        if type(call).__name__ == "SecurityChecker" or name in _AUTH_DEPENDENCIES or "require_role" in qualname or "require_data_level" in qualname:
            return True
        if dependant.security_requirements:
            return True
        pending.extend(dependant.dependencies)
    return False


def _allowed(route: APIRoute, rules: Iterable[Tuple[str, str]]) -> bool:
    methods = route.methods or set()
    return any(method in methods and re.fullmatch(pattern, route.path) for method, pattern in rules)


def restrict_to_public(app: FastAPI) -> List[str]:
    """Quita del app todas las rutas que no son del portal ciudadano. Devuelve las que quedan."""
    rules = list(PUBLIC_READ_ROUTES)
    if _flag("SISC_PUBLIC_ALLOW_WRITES"):
        rules += PUBLIC_WRITE_ROUTES

    kept, dropped_auth = [], []
    new_routes = []
    for route in app.router.routes:
        if not isinstance(route, APIRoute):
            # /docs, /openapi.json y similares: fuera en produccion publica.
            continue
        if not _allowed(route, rules):
            continue
        if _requires_auth(route):
            dropped_auth.append(route.path)
            continue
        # En modo publico solo se responde al metodo permitido (p. ej. GET), no a los demas.
        allowed_methods = {m for m, p in rules if re.fullmatch(p, route.path)}
        route.methods = (route.methods or set()) & allowed_methods
        new_routes.append(route)
        kept.append(f"{','.join(sorted(route.methods))} {route.path}")

    app.router.routes[:] = new_routes
    app.openapi_schema = None
    for path in dropped_auth:
        logger.warning("[Modo publico] Ruta descartada porque exige usuario: %s", path)
    logger.info("[Modo publico] %d rutas publicas activas.", len(kept))
    return kept
