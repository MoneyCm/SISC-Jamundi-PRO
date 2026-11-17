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


# Homicidio se cuenta por VICTIMA (una fila de la sabana = una persona), como lo publica la
# Policia; el resto de conductas se cuenta por HECHO unico. Metodologia v2 (Observatorio, nov 2026).
CONDUCTAS_POR_VICTIMA = ("HOMICIDIO", "HOMICIDIO INTENCIONAL", "HOMICIDIO DOLOSO")


def es_conteo_por_victima(conducta) -> bool:
    return str(conducta or "").strip().upper() in CONDUCTAS_POR_VICTIMA


def _ultima_entrega_del_hecho(model):
    """Entrega más reciente que trae el hecho (mismo id_fuente) en la tabla maestra."""
    from sqlalchemy import select
    from sqlalchemy.orm import aliased

    from db.models_hechos_seguridad import IngestionRun

    otra = aliased(model)
    return (select(otra.ingestion_id)
            .join(IngestionRun, IngestionRun.id == otra.ingestion_id)
            .where(otra.id_fuente == model.id_fuente)
            .order_by(IngestionRun.fecha_inicio.desc())
            .limit(1)
            .correlate(model)
            .scalar_subquery())


def conteo_key_expr(model=HechoSeguridad):
    """Clave de conteo oficial: victima (fila) para homicidio; hecho unico para lo demas.

    En la tabla maestra un hecho puede conservar filas de entregas viejas cuando la Policía corrige
    un dato (edad, barrio): se cuentan solo las víctimas de la entrega más reciente que trae el hecho.
    Las demás filas dan NULL y COUNT(DISTINCT ...) no las cuenta. La foto de una entrega
    (sabana_snapshot_rows, con hecho_key) ya es una sola entrega y no necesita ese filtro.
    """
    conducta = func.upper(func.trim(func.coalesce(model.conducta_estandar, "")))
    victima = literal("V:") + cast(model.id, String)
    if hasattr(model, "hecho_key"):
        return case((conducta.in_(CONDUCTAS_POR_VICTIMA), victima), else_=model.hecho_key)
    sin_id = func.nullif(func.btrim(model.id_fuente), "").is_(None)
    es_homicidio = conducta.in_(CONDUCTAS_POR_VICTIMA)
    return case(
        (and_(es_homicidio, or_(sin_id, model.ingestion_id == _ultima_entrega_del_hecho(model))), victima),
        (es_homicidio, literal(None, String)),
        else_=hecho_key_expr(model),
    )


def hechos_unicos_expr(model=HechoSeguridad):
    """Conteo oficial: hechos unicos, salvo homicidio, que suma victimas."""
    return func.count(func.distinct(conteo_key_expr(model)))


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