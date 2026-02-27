import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
import urllib3
urllib3.disable_warnings()
from services.dq_service import run_dq, REQUIRED_COLUMNS

FILE_URL = "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/CONT93A3E06E0C134EF197783385D56AABBF/native/VIOLENCIA%20INTRAFAMILIAR.xlsx"
FILENAME = "VIOLENCIA_INTRAFAMILIAR.xlsx"
SOURCE   = "VIOLENCIA_INTRAFAMILIAR_MINDEFENSA"

print("Descargando archivo desde MinDefensa...")
try:
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(FILE_URL, headers=headers, timeout=60, verify=False)
    r.raise_for_status()
    file_bytes = r.content
    print(f"OK - {len(file_bytes):,} bytes\n")
except Exception as e:
    print(f"ERROR descargando: {e}")
    local = os.path.join(os.path.dirname(__file__), "test_copy.xlsx")
    if os.path.exists(local):
        print(f"Usando archivo local: {local}")
        with open(local, "rb") as f:
            file_bytes = f.read()
        FILENAME = "test_copy.xlsx"
    else:
        sys.exit(1)

print("Ejecutando analisis DQ...\n")
report = run_dq(file_bytes, FILENAME, SOURCE)

print("=" * 65)
print(f"SEMAFORO   : {report.get('semaforo', '?')}")
print(f"SCHEMA OK  : {report.get('schema_ok', '?')}")
print(f"FILAS TOTAL: {report.get('rows_total', '?')}")
score = report.get('score_overall') or 0
print(f"SCORE      : {round(score * 100, 1)}%")

missing = report.get("missing_cols", [])
extra   = report.get("extra_cols", [])
if missing:
    print(f"\nCOLUMNAS FALTANTES: {missing}")
    print("Columnas que REQUIERE el sistema:")
    for c in REQUIRED_COLUMNS:
        mark = "OK " if c not in missing else "---"
        print(f"  [{mark}] {c}")
    print(f"\nColumnas que TIENE el archivo ({len(extra)} cols):")
    for c in extra[:20]:
        print(f"  {c}")

issues = report.get("issues", [])
errors = [i for i in issues if i.get("severity") == "ERROR"]
warns  = [i for i in issues if i.get("severity") == "WARNING"]

print(f"\nErrores criticos : {len(errors)}")
print(f"Advertencias     : {len(warns)}")

if errors:
    print("\n--- ERRORES CRITICOS ---\n")
    for idx, issue in enumerate(errors, 1):
        print(f"  {idx}. Campo: {issue.get('field')}")
        print(f"     Regla : {issue.get('rule')}")
        print(f"     Filas : {issue.get('count')}")
        examples = issue.get("example", [])
        if examples:
            print("     Ejemplos:")
            for ex in examples[:2]:
                print(f"       {json.dumps(ex, ensure_ascii=False, default=str)[:200]}")
        print()

if warns:
    print("--- ADVERTENCIAS ---\n")
    for idx, issue in enumerate(warns, 1):
        print(f"  {idx}. [{issue.get('field')}] {issue.get('rule')} - {issue.get('count')} filas")

print("=" * 65)
