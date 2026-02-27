"""Inspect the homicidio_intencional.xlsx which follows the same MinDefensa format"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd

# Usar el de homicidio intencional que ya existe localmente como referencia del formato
paths_to_check = [
    "homicidio_intencional.xlsx",
    "hurto_personas.xlsx",
    "test_policia_2025.xlsx",
]

for fname in paths_to_check:
    fpath = os.path.join(os.path.dirname(__file__), fname)
    if not os.path.exists(fpath):
        continue
    print(f"\n{'='*60}")
    print(f"ARCHIVO: {fname}")
    xl = pd.ExcelFile(fpath, engine="openpyxl")
    print(f"Hojas: {xl.sheet_names}")
    for sheet in xl.sheet_names[:3]:
        try:
            df = pd.read_excel(fpath, sheet_name=sheet, engine="openpyxl", nrows=5)
            print(f"\n  HOJA '{sheet}': {df.shape[0]} filas x {df.shape[1]} cols")
            print(f"  Columnas: {list(df.columns)}")
        except Exception as e:
            print(f"  HOJA '{sheet}': ERROR {e}")
