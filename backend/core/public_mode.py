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
import json
import logging
import os
import re
from pathlib import Path
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


# --- Archivos del PISCC -------------------------------------------------------------------------
# Las metas del PISCC se calculan con data/piscc/historico.json y mindefensa.json, que la oficina
# actualiza cada semana desde datos.gov.co. scripts/actualizar_portal.ps1 los sube a la tabla
# portal_archivos de Neon; el backend publico los baja aqui (no tiene permiso de escribir en la base).
PORTAL_FILES = {"historico.json", "mindefensa.json"}
PORTAL_FILES_DIR = Path(__file__).resolve().parents[1] / "data" / "piscc"


def sync_portal_files(session_factory=None) -> List[str]:
    """Escribe en data/piscc los archivos guardados en portal_archivos. Devuelve los que cambiaron."""
    from sqlalchemy import text

    if session_factory is None:
        from db.session import SessionLocal as session_factory
    db = session_factory()
    try:
        exists = db.execute(text("SELECT to_regclass('public.portal_archivos')")).scalar()
        if not exists:
            return []
        rows = db.execute(text("SELECT nombre, contenido FROM portal_archivos")).fetchall()
    finally:
        db.close()

    changed = []
    for name, content in rows:
        if name not in PORTAL_FILES or not content:
            continue
        try:
            json.loads(content)  # nunca se escribe un archivo dañado
        except ValueError:
            logger.warning("[Modo publico] %s en portal_archivos no es JSON valido; se ignora.", name)
            continue
        target = PORTAL_FILES_DIR / name
        current = target.read_text(encoding="utf-8-sig") if target.exists() else None
        if current != content:
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(".tmp")
            tmp.write_text(content, encoding="utf-8")
            tmp.replace(target)
            changed.append(name)
    if changed:
        logger.info("[Modo publico] Archivos del PISCC actualizados desde Neon: %s", ", ".join(changed))
    return changed


def start_portal_files_sync(interval_seconds: int = 900) -> None:
    import threading
    import time

    def loop():
        while True:
            try:
                sync_portal_files()
            except Exception as exc:  # la base puede estar en plena copia; se reintenta luego
                logger.warning("[Modo publico] No se pudieron bajar los archivos del PISCC: %s", exc)
            time.sleep(interval_seconds)

    threading.Thread(target=loop, daemon=True, name="portal-files-sync").start()
