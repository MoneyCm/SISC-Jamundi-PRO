"""Verifica que el DQ ajustado pase el archivo real de homicidio_intencional.xlsx"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from services.dq_service import run_dq

tests = [
    ("homicidio_intencional.xlsx", "HOMICIDIO_INTENCIONAL_MINDEFENSA"),
    ("hurto_personas.xlsx",        "HURTO_PERSONAS_MINDEFENSA"),
]

for fname, source in tests:
    fpath = os.path.join(os.path.dirname(__file__), fname)
    if not os.path.exists(fpath):
        print(f"[SKIP] {fname} - no encontrado")
        continue
    with open(fpath, "rb") as f:
        file_bytes = f.read()
    report = run_dq(file_bytes, fname, source)
    sem = report.get("semaforo", "?")
    rows = report.get("rows_total", "?")
    score = round((report.get("score_overall") or 0) * 100, 1)
    missing = report.get("missing_cols", [])
    errors = [i for i in report.get("issues", []) if i.get("severity") == "ERROR"]
    print(f"\n{fname}")
    print(f"  Semaforo : {sem}")
    print(f"  Filas    : {rows}")
    print(f"  Score    : {score}%")
    print(f"  Missing  : {missing}")
    print(f"  Errores  : {len(errors)}")
    for e in errors:
        print(f"    [{e.get('field')}] {e.get('rule')} - {e.get('count')} filas")
