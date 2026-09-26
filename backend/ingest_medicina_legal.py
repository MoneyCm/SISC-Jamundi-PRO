"""
Ingesta de Medicina Legal (INMLCF) para Jamundí vía datos.gov.co (Socrata SODA).

La Medicina Legal es la capa forense que arbitra el delito: clasifica el hecho
desde la práctica necropsia/valoración (carácter forense, en presunción), no
tipifica. Por eso se conserva como fuente separada, sin fusionarla ni con
SIEDCO ni con SPOA.

Fuentes consumidas (catálogo oficial "Instituto Nacional de Medicina Legal y
Ciencias Forenses", https://www.datos.gov.co):
  - HOMICIDIOS_DEF   vtub-3de2  Presuntos Homicidios 2015-2024 (definitivas)
  - SUICIDIOS_DEF    f75u-mirk  Presuntos Suicidios 2015-2024 (definitivas)
  - FATALES_PRE      2kpj-cktv  Lesiones fatales de causa externa preliminar
  - NOFATALES_PRE    79dd-d24f  Lesiones no fatales de causa externa preliminar

El script descarga solo Valle del Cauca (codigo_dane_departamento=76) y conserva
los registros cuyo municipio es Jamundí (codigo_dane_municipio=76364). Los
cortes se marcan con el último periodo presente (mes vencido), preserves la
metodología oficial y entrega la fuente lista para reconciliar contra SIEDCO y
SPOA en SISC en Cifras.

Uso:
  python backend/ingest_medicina_legal.py
  python backend/ingest_medicina_legal.py --dataset HOMICIDIOS_DEF
"""
import argparse
import hashlib
import json
import logging
import os
import sys
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.dialects.postgresql import insert

sys.path.append(os.path.join(os.getcwd(), "backend"))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.models_medicina_legal import MedicinaLegalRecord, MedicinaLegalRun, MedicinaLegalSnapshot
from db.models_source_center import SourceConnectorState
from db.session import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ingesta_medicina_legal")

HOST = "https://www.datos.gov.co/resource"
MUNICIPIO_DANE_JAMUNDI = "76364"
DEPARTAMENTO_DANE_VALLE = "76"
SCHEMA_VERSION = "ML-V1-2026"
CONNECTOR_CODE = "MEDICINA_LEGAL"

BASIC_FIELDS = {
    "year": "a_o_del_hecho",
    "month": "mes_del_hecho",
    "sexo": "sexo_de_la_victima",
    "cod_depto": "codigo_dane_departamento",
    "cod_muni": "codigo_dane_municipio",
    "depto": "departamento_del_hecho_dane",
    "muni": "municipio_del_hecho_dane",
    "zona": "zona_del_hecho",
    "escenario": "escenario_del_hecho",
}

DATASETS: Dict[str, Dict[str, Any]] = {
    "HOMICIDIOS_DEF": {
        "id": "vtub-3de2",
        "name": "Presuntos homicidios 2015-2024 (definitivas)",
        "definitive": True,
        "contexto": "manera_de_muerte",
        "mecanismo": "mecanismo_causal_de_la_lesion_fatal",
        "circunstancia": "circunstancia_del_hecho_detallada",
        "grupo_edad": "grupo_de_edad_quinquenal",
    },
    "SUICIDIOS_DEF": {
        "id": "f75u-mirk",
        "name": "Presuntos suicidios 2015-2024 (definitivas)",
        "definitive": True,
        "contexto": "manera_de_muerte",
        "mecanismo": "mecanismo_causal_de_la_lesion_fatal",
        "circunstancia": "circunstancia_del_hecho_detallada",
        "grupo_edad": "grupo_de_edad_quinquenal",
    },
    "FATALES_PRE": {
        "id": "2kpj-cktv",
        "name": "Lesiones fatales de causa externa - preliminar mensual",
        "definitive": False,
        "contexto": "manera_de_muerte",
        "mecanismo": "mecanismo_causal",
        "circunstancia": "circunstancia_del_hecho",
        "grupo_edad": "grupo_de_edad_de_la_victima",
    },
    "NOFATALES_PRE": {
        "id": "79dd-d24f",
        "name": "Lesiones no fatales de causa externa - preliminar mensual",
        "definitive": False,
        "contexto": "contexto_de_violencia",
        "mecanismo": "mecanismo_causal",
        "circunstancia": "circunstancia_del_hecho",
        "grupo_edad": "grupo_de_edad_de_la_victima",
    },
}

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11,
    "diciembre": 12,
}


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean(value: Any) -> Optional[str]:
    text = _text(value)
    if text and text.lower() in {"sin información", "sin informacion", "no aplica"}:
        return None
    return text


def _int(value: Any) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _month_number(value: Any) -> Optional[int]:
    return MESES.get(str(value).strip().lower())


def _extract(row: Dict[str, Any], config: Dict[str, str]) -> Dict[str, Any]:
    """Proyecta una fila Socrata a un dict canónico estable."""
    fields = dict(BASIC_FIELDS)
    fields.update({
        "contexto": config["contexto"],
        "mecanismo": config["mecanismo"],
        "circunstancia": config["circunstancia"],
        "grupo_edad": config["grupo_edad"],
    })
    canon = {}
    for key, source in fields.items():
        canon[key] = _clean(row.get(source))
    canon["year"] = _int(row.get(fields["year"]) or canon.get("year"))
    canon["month"] = _month_number(_text(row.get(fields["month"])))
    return canon


def _record_key(canon: Dict[str, Any]) -> str:
    serialized = json.dumps(canon, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _payload_sha256(rows: List[Dict[str, Any]], dataset_id: str) -> str:
    serialized = json.dumps(rows, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return hashlib.sha256(f"{dataset_id}:{digest}".encode("utf-8")).hexdigest()


def _fetch_dataset(client: httpx.Client, dataset: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Descarga Valle del Cauca paginado de un dataset de datos.gov.co."""
    dataset_id = dataset["id"]
    url = f"{HOST}/{dataset_id}.json"
    where = f"codigo_dane_departamento='{DEPARTAMENTO_DANE_VALLE}'"
    rows: List[Dict[str, Any]] = []
    offset = 0
    page_size = 50000
    while True:
        response = client.get(
            url,
            params={
                "$where": where,
                "$limit": page_size,
                "$offset": offset,
                "$order": ":id",
            },
            timeout=120,
        )
        response.raise_for_status()
        page = response.json()
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def _ingest_dataset(
    db,
    run: MedicinaLegalRun,
    client: httpx.Client,
    dataset_key: str,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    logger.info("Descargando %s (%s)...", config["name"], config["id"])
    source_rows = _fetch_dataset(client, config)

    filtered: List[Dict[str, Any]] = []
    discarded = {"no_jamundi": 0, "sin_periodo": 0}
    for row in source_rows:
        cod_muni = _text(row.get("codigo_dane_municipio"))
        if cod_muni != MUNICIPIO_DANE_JAMUNDI:
            discarded["no_jamundi"] += 1
            continue
        canon = _extract(row, config)
        if not canon["year"] or not canon["month"]:
            discarded["sin_periodo"] += 1
            continue
        filtered.append(canon)

    if not filtered:
        return {"accepted": False, "reason": "sin_registros_jamundi"}

    max_year = max(canon["year"] for canon in filtered)
    max_month = max(
        canon["month"]
        for canon in filtered
        if canon["year"] == max_year
    )
    cutoff_date = date(max_year, max_month, 1)
    payload_sha256 = _payload_sha256(filtered, config["id"])

    existing = (
        db.query(MedicinaLegalSnapshot)
        .filter_by(
            dataset_id=config["id"],
            cutoff_date=cutoff_date,
            payload_sha256=payload_sha256,
        )
        .first()
    )
    if existing:
        logger.info(
            "Snapshot idéntico ya registrado (corte %s), se omite.", cutoff_date
        )
        return {"accepted": False, "reason": "ya_ingestado", "cutoff_date": cutoff_date}

    snapshot = MedicinaLegalSnapshot(
        run_id=run.id,
        dataset_key=dataset_key,
        dataset_id=config["id"],
        cutoff_date=cutoff_date,
        payload_sha256=payload_sha256,
        schema_version=SCHEMA_VERSION,
        source_row_count=len(source_rows),
        filtered_count=len(filtered),
        valid_count=len(filtered),
        discarded_count=sum(discarded.values()),
        discard_reasons=discarded,
        definitive=bool(config["definitive"]),
    )
    db.add(snapshot)
    db.flush()

    values = []
    for canon in filtered:
        values.append({
            "snapshot_id": snapshot.id,
            "dataset_key": dataset_key,
            "record_key": _record_key(canon),
            "year_hecho": canon["year"],
            "month_hecho": canon["month"],
            "codigo_dane_departamento": canon["cod_depto"],
            "codigo_dane_municipio": canon["cod_muni"],
            "departamento": canon["depto"],
            "municipio": canon["muni"],
            "contexto": canon["contexto"],
            "sexo": canon["sexo"],
            "grupo_edad": canon["grupo_edad"],
            "zona": canon["zona"],
            "escenario": canon["escenario"],
            "mecanismo_causal": canon["mecanismo"],
            "circunstancia": canon["circunstancia"],
            "payload": canon,
        })
    inserted = 0
    if values:
        statement = insert(MedicinaLegalRecord).values(values).on_conflict_do_nothing(
            constraint="uq_ml_snapshot_record"
        )
        result = db.execute(statement)
        inserted = max(int(result.rowcount or 0), 0)
    db.commit()
    logger.info(
        "Registros Jamundí en %s (%s): %s inserción %s filas (fuente %s).",
        config["name"],
        cutoff_date,
        len(values),
        inserted,
        len(source_rows),
    )
    return {"accepted": True, "count": inserted, "cutoff_date": cutoff_date}


def _record_connector_state(db, datasets_summary: Dict[str, Any]) -> None:
    """Refleja el resultado de la ingesta en el Centro de fuentes."""
    from sqlalchemy import func

    from db.models_medicina_legal import MedicinaLegalRecord, MedicinaLegalSnapshot

    cutoff = (
        db.query(func.max(MedicinaLegalSnapshot.cutoff_date)).scalar() or date.today()
    )
    record_count = db.query(func.count(MedicinaLegalRecord.id)).scalar()
    has_preliminar = any(item.get("preliminar", False) for item in datasets_summary.values())
    updated = any(item.get("accepted", False) for item in datasets_summary.values())

    state = db.query(SourceConnectorState).filter_by(connector_code=CONNECTOR_CODE).first()
    if state is None:
        state = SourceConnectorState(connector_code=CONNECTOR_CODE)
        db.add(state)
    state.status = "UPDATED" if updated else "CURRENT"
    state.quality_status = "WARNING" if has_preliminar else "VALIDATED"
    state.period_label = f"Corte al {cutoff.isoformat()}"
    state.source_cutoff_date = cutoff
    state.record_count = record_count
    state.last_checked_at = datetime.now(timezone.utc)
    if updated:
        state.last_success_at = datetime.now(timezone.utc)
    state.warnings = (
        ["Incluye cifras preliminares de mes vencido (definitiva pendiente)."]
        if has_preliminar
        else []
    )
    state.details = {
        "via": "datos.gov.co SODA",
        "municipio_dane": MUNICIPIO_DANE_JAMUNDI,
        "datasets": {k: v["id"] for k, v in DATASETS.items()},
    }
    db.commit()


def run_full_ingestion(only_dataset: Optional[str] = None) -> int:
    db = SessionLocal()
    datasets_summary: Dict[str, Dict[str, Any]] = {}
    run = None
    try:
        run_id = f"ml-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8]}"
        run = MedicinaLegalRun(id=run_id, status="COMPLETED", details={"via": "datos.gov.co SODA"})
        db.add(run)
        db.commit()

        with httpx.Client(base_url=HOST, follow_redirects=True) as client:
            for dataset_key, config in DATASETS.items():
                if only_dataset and dataset_key != only_dataset:
                    continue
                try:
                    outcome = _ingest_dataset(db, run, client, dataset_key, config)
                except httpx.HTTPError as error:
                    logger.error("Fallo al ingestar %s: %s", dataset_key, error)
                    outcome = {"accepted": False, "reason": f"http_error: {error}"}
                datasets_summary[dataset_key] = {
                    **outcome,
                    "preliminar": not config["definitive"],
                }

        run.datasets = {
            k: {"id": DATASETS[k]["id"], **{kk: vv.isoformat() if isinstance(vv, date) else vv for kk, vv in v.items()}}
            for k, v in datasets_summary.items()
            if v.get("cutoff_date") is not None
        }
        alloc = {k: v for k, v in datasets_summary.items() if not v.get("accepted")}
        if alloc:
            run.status = "PARTIAL"
            run.details["rejected"] = alloc
        run.finished_at = datetime.now(timezone.utc)
        db.commit()

        _record_connector_state(db, datasets_summary)

        logger.info(
            "[RESULTADO] %s datasets: %s aceptados, %s omitidos.",
            len(datasets_summary),
            sum(1 for v in datasets_summary.values() if v.get("accepted")),
            sum(1 for v in datasets_summary.values() if not v.get("accepted")),
        )
        return sum(1 for v in datasets_summary.values() if v.get("accepted"))
    except Exception as error:  # pragma: no cover
        logger.exception("Error general en la ingesta de Medicina Legal: %s", error)
        if run is not None:
            run.status = "ERROR"
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingesta INMLCF para Jamundí")
    parser.add_argument(
        "--dataset",
        choices=list(DATASETS.keys()),
        default=None,
        help="Ingesta de un único dataset (por defecto todos).",
    )
    args = parser.parse_args()
    accepted = run_full_ingestion(only_dataset=args.dataset)
    sys.exit(0 if accepted or args.dataset else 1)