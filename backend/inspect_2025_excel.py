import pandas as pd
import sys

def inspect_local_excel(filename):
    print(f"Inspeccionando {filename}...")
    try:
        xl = pd.ExcelFile(filename)
        print("Pestañas encontradas:", xl.sheet_names)
        
        for sheet in xl.sheet_names[:10]:
            try:
                # El Ministerio suele poner 7-9 filas de encabezados corporativos
                df = pd.read_excel(xl, sheet_name=sheet, nrows=2)
                print(f"Pestaña: {sheet} | Columnas: {df.columns.tolist()}")
            except:
                pass
            
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    file = sys.argv[1] if len(sys.argv) > 1 else "backend/INDICADORES DE SEGUR Y RESULT OPER ENERO-DICIEMBRE 2025.xlsx"
    inspect_local_excel(file)
