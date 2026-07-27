"""Metricas consistentes para registros de la SABANA SIEDCO/PONAL."""

from sqlalchemy import String, and_, case, cast, func, literal, or_

from db.models_hechos_seguridad import HechoSeguridad


INVALID_PERSON_VALUES = ("", "NO REPORTA", "SIN INFORMACION", "SIN INFORMACIÓN", "N/A", "NA")


def canonical_hecho_key(id_fuente, fingerprint, record_id):
    """Identidad estable: primero el ID oficial; luego la huella y finalmente la fila."""
    source_id = str(id_fuente).strip() if id_fuente is not None else ""
    if source_id:
        return f"ID:{source_id}"
    row_fingerprint = str(fingerprint).strip() if fingerprint is not None else ""
    if row_fingerprint:
        return f"FP:{row_fingerprint}"
    return f"ROW:{record_id}"


def hecho_key_expr(model=HechoSeguridad):
    """Expresion SQL equivalente a canonical_hecho_key para COUNT DISTINCT."""
    source_id = func.nullif(func.btrim(model.id_fuente), "")
    fingerprint = func.nullif(func.btrim(model.fingerprint), "")
    return case(
        (source_id.is_not(None), literal("ID:") + source_id),
        (fingerprint.is_not(None), literal("FP:") + fingerprint),
        else_=literal("ROW:") + cast(model.id, String),
    )


def hechos_unicos_expr(model=HechoSeguridad):
    return func.count(func.distinct(hecho_key_expr(model)))


def registros_expr(model=HechoSeguridad):
    return func.count(model.id)


def persona_identificable_filter(model=HechoSeguridad):
    sexo = func.upper(func.btrim(func.coalesce(model.sexo, "")))
    grupo = func.upper(func.btrim(func.coalesce(model.grupo_edad, "")))
    return or_(
        and_(sexo != "", ~sexo.in_(INVALID_PERSON_VALUES)),
        model.edad > 0,
        and_(grupo != "", ~grupo.in_(INVALID_PERSON_VALUES)),
    )


def victimas_identificables_expr(model=HechoSeguridad):
    return func.count(model.id).filter(persona_identificable_filter(model))


def hechos_sin_id_expr(model=HechoSeguridad):
    return func.count(model.id).filter(
        or_(model.id_fuente.is_(None), func.btrim(model.id_fuente) == "")
    )