"""Apply the additive migration and run tests only against explicitly local sisc_staging.

Usage: python scripts/verify_interventions_staging.py --uri-file PATH
The URI is never printed. No production access; test data rolls back.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

parser = argparse.ArgumentParser()
parser.add_argument("--uri-file", required=True)
parser.add_argument("--regression", action="store_true")
args = parser.parse_args()
url = make_url(Path(args.uri_file).read_text().strip()).set(database="sisc_staging")
if url.host not in {"127.0.0.1", "localhost"}:
    raise SystemExit("Only localhost staging is allowed")
root = Path(__file__).resolve().parents[1]
engine = create_engine(url, connect_args={"connect_timeout": 5})
with engine.connect() as conn:
    conn.exec_driver_sql((root / "db/migrations/20260908_interventions.sql").read_text())
    conn.commit()
engine.dispose()
print("Additive intervention migration applied to local sisc_staging.")
env = dict(os.environ, INTERVENTIONS_TEST_DATABASE_URL=url.render_as_string(hide_password=False))
tests = ["tests/test_interventions.py"]
if args.regression:
    tests += [f"tests/test_{name}.py" for name in ["alert_rules", "alerts_tray", "publication_guards", "cierre_validacion",
        "conciliacion_unificada", "e2e_dos_entregas", "hechos_metrics", "sabana_history", "fase15_contract"]]
raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", *tests, "-q", "-p", "no:cacheprovider"], cwd=root, env=env))
