"""Pull monitor evidence from trusted GitHub workflows into the LOCAL database.

Run from the host with authenticated gh: python backend/scripts/sync_source_monitors.py
Use --watch for periodic synchronization. Never executes monitors or sends mail.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def gh_api(path, *, binary=False):
    for attempt in range(3):
        try:
            result = subprocess.run(
                ["gh", "api", path], capture_output=True, timeout=120, check=True,
            )
            return result.stdout if binary else json.loads(result.stdout)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            if attempt == 2:
                raise
            time.sleep(2 ** (attempt + 1))


def artifact_payload(archive, code):
    # Read only the expected JSON in memory; never extract arbitrary archive paths.
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        entries = [item for item in bundle.infolist() if item.filename == "sisc-heartbeat.json"]
        if len(entries) != 1 or entries[0].file_size > 100_000:
            raise ValueError("Invalid heartbeat artifact")
        payload = json.loads(bundle.read(entries[0]))
    from api.source_center import SourceHeartbeat, HEARTBEAT_STATUSES, HEARTBEAT_QUALITY
    parsed = SourceHeartbeat.model_validate(payload)
    if parsed.connector_code != code:
        raise ValueError("Artifact connector does not match trusted repository")
    if parsed.status not in HEARTBEAT_STATUSES or parsed.quality_status not in HEARTBEAT_QUALITY:
        raise ValueError("Invalid monitor status")
    if parsed.last_checked_at.tzinfo is None:
        raise ValueError("Heartbeat timestamp must include timezone")
    if parsed.last_checked_at > datetime.now(timezone.utc):
        raise ValueError("Heartbeat timestamp is in the future")
    return parsed.model_dump(exclude_none=True)


def evidence_for_run(repo, code, run):
    artifacts = gh_api(f"repos/{repo}/actions/runs/{run['id']}/artifacts?per_page=100")
    matches = [a for a in artifacts['artifacts']
               if a['name'] == 'sisc-heartbeat' and not a['expired']]
    if matches:
        if matches[0].get('size_in_bytes', 0) > 1_000_000:
            raise ValueError('Heartbeat artifact exceeds size limit')
        archive = gh_api(f"repos/{repo}/actions/artifacts/{matches[0]['id']}/zip", binary=True)
        payload = artifact_payload(archive, code)
        mode = 'heartbeat_artifact'
    else:
        # A green workflow does not establish source coverage or successful delivery.
        # Do not manufacture a cutoff, source review time, success time or counts.
        payload = {
            'status': 'NEEDS_REVIEW', 'quality_status': 'INCOMPLETE',
            'warnings': [
                f"Monitor localizado en GitHub; ejecucion {run['id']} "
                f"finalizada {run['updated_at']} ({run['conclusion']}).",
                'Esta ejecucion no conserva el reporte estructurado SISC. '
                'Su resultado no acredita corte, cifras ni entrega al servidor.',
            ],
        }
        mode = 'workflow_only'
    payload['details'] = {
        **payload.get('details', {}),
        'sync_mode': mode, 'github_run_id': run['id'],
        'github_run_attempt': run.get('run_attempt', 1),
        'github_run_url': run['html_url'], 'repository': repo,
        'synced_at': datetime.now(timezone.utc).isoformat(),
    }
    return payload


def should_apply(existing, payload):
    if existing is None:
        return True
    details = existing.details or {}
    incoming = payload['details']
    if (details.get('github_run_id') == incoming['github_run_id']
            and details.get('github_run_attempt') == incoming['github_run_attempt']
            and details.get('sync_mode') == incoming['sync_mode']):
        return False
    checked = payload.get('last_checked_at')
    if checked and existing.last_checked_at:
        return checked > existing.last_checked_at.replace(tzinfo=timezone.utc)
    # Incomplete workflow evidence must never replace a real report.
    return checked is not None or existing.last_checked_at is None


def sync_once():
    from api.source_center import TRUSTED_GITHUB_WORKFLOWS
    from db.session import SessionLocal, engine
    from db.models_source_center import SourceConnectorState
    from services.source_center_service import SourceCenterService
    if engine.url.host not in {'localhost', '127.0.0.1', '::1', 'db'}:
        raise RuntimeError('Synchronization is restricted to the local database')
    failures = 0
    for code, config in TRUSTED_GITHUB_WORKFLOWS.items():
        try:
            repo = config['repository']
            workflow = config['workflow_ref'].split('/.github/workflows/')[1].split('@')[0]
            runs = gh_api(f'repos/{repo}/actions/workflows/{workflow}/runs?branch=main&status=completed&per_page=10')
            run = next((r for r in runs['workflow_runs']
                        if r['event'] in {'schedule', 'workflow_dispatch'}
                        and r['head_repository']['full_name'] == repo), None)
            if run is None:
                raise ValueError('No trusted completed execution found')
            payload = evidence_for_run(repo, code, run)
            with SessionLocal() as db:
                existing = db.get(SourceConnectorState, code)
                if should_apply(existing, payload):
                    SourceCenterService.record_heartbeat(db, code, payload)
                    print(f'{code}: {payload["status"]} ({payload["details"]["sync_mode"]})', flush=True)
                else:
                    print(f'{code}: sin cambios', flush=True)
        except Exception as error:
            failures += 1
            # Never print subprocess output, which could contain credentials.
            print(f'{code}: sincronizacion fallida ({type(error).__name__})', flush=True)
    return 1 if failures else 0


MONITOR_MINDEFENSA_DIR = Path(r"C:\Proyectos\monitor-mindefensa")
REFERENCE_STATE_FILE = BACKEND.parent / "mindefensa_reference_sync_state.json"


def _load_reference_exporter(monitor_dir):
    """Importa el exportador del monitor sin exigir sus dependencias de registro."""
    import importlib
    import logging
    import types
    try:
        import loguru  # noqa: F401
    except ImportError:
        shim = types.ModuleType("logger")
        shim.log = logging.getLogger("monitor-mindefensa")
        sys.modules.setdefault("logger", shim)
    if str(monitor_dir) not in sys.path:
        sys.path.append(str(monitor_dir))
    return importlib.import_module("reference_exporter").ReferenceExporter


def sync_mindefensa_reference():
    """Carga en la base local los libros nacionales de MinDefensa que haya descargado el monitor.

    Solo procesa archivos nuevos o modificados desde la última carga. No usa
    usuario ni contraseña: escribe directamente en la base local.
    """
    import os
    from datetime import date
    monitor_dir = Path(os.getenv("MINDEFENSA_MONITOR_DIR", str(MONITOR_MINDEFENSA_DIR)))
    books_dir = monitor_dir / "mindefensa_xlsx"
    if not books_dir.is_dir():
        print(f"MINDEFENSA_REFERENCIA: carpeta no encontrada ({books_dir})", flush=True)
        return 0

    from db.session import SessionLocal, engine
    from services.mindefensa_reference_service import persist_reference_payload
    if engine.url.host not in {"localhost", "127.0.0.1", "::1", "db"}:
        raise RuntimeError("Synchronization is restricted to the local database")

    ReferenceExporter = _load_reference_exporter(monitor_dir)
    try:
        state = json.loads(REFERENCE_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}

    exporter = ReferenceExporter()
    failures = 0
    for book in sorted(books_dir.glob("*.xlsx")):
        if "_SL" in book.stem.upper() or not ReferenceExporter.is_priority_file(book):
            continue
        stamp = f"{book.stat().st_mtime_ns}:{book.stat().st_size}"
        if state.get(book.name) == stamp:
            continue
        cutoff = date.fromtimestamp(book.stat().st_mtime).isoformat()
        try:
            payload = exporter._build_payload(book, cutoff)
            with SessionLocal() as db:
                result = persist_reference_payload(db, payload)
                db.commit()
            state[book.name] = stamp
            REFERENCE_STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"MINDEFENSA_REFERENCIA: {book.name} cargado ({result['records']} agregados, "
                  f"años {result['coverage_years']})", flush=True)
        except Exception as error:
            failures += 1
            detail = str(error).strip().splitlines()[0][:300] if str(error).strip() else ""
            print(f"MINDEFENSA_REFERENCIA: {book.name} fallido ({type(error).__name__}: {detail})", flush=True)
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--interval', type=int, default=900)
    args = parser.parse_args()
    if args.interval < 60:
        parser.error('--interval must be at least 60 seconds')
    from dotenv import load_dotenv
    load_dotenv(BACKEND / '.env')
    while True:
        result = sync_once()
        try:
            result = max(result, sync_mindefensa_reference())
        except Exception as error:
            print(f"MINDEFENSA_REFERENCIA: sincronizacion fallida ({type(error).__name__})", flush=True)
            result = 1
        if not args.watch:
            return result
        time.sleep(args.interval)


if __name__ == '__main__':
    raise SystemExit(main())
