"""Inspect all sheets and columns in test_copy.xlsx"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd

path = os.path.join(os.path.dirname(__file__), "test_copy.xlsx")
print(f"Archivo: {path}")

# Listar todas las hojas
xl = pd.ExcelFile(path, engine="openpyxl")
print(f"Hojas disponibles: {xl.sheet_names}\n")

for sheet in xl.sheet_names[:5]:  # max 5 hojas
    try:
        df = pd.read_excel(path, sheet_name=sheet, engine="openpyxl", nrows=3)
        print(f"HOJA: '{sheet}' - {len(df.columns)} columnas")
        print(f"  Columnas: {list(df.columns)}")
        print()
    except Exception as e:
        print(f"HOJA: '{sheet}' - ERROR: {e}\n")
