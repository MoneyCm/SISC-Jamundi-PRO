import pandas as pd
import io
import os
import hashlib
from datetime import datetime

def analyze_sem_file(file_path):
    print(f"ANÁLISIS DE ARCHIVO: {os.path.basename(file_path)}")
    
    # 1. Encontrar header
    df_raw = pd.read_excel(file_path, header=None, nrows=20)
    header_idx = -1
    for idx, row in df_raw.iterrows():
        row_str = [str(v).upper().strip() for v in row.values if pd.notna(v)]
        if any("MUNICIPIO" in v for v in row_str):
            header_idx = idx
            break
            
    if header_idx == -1:
        print("Error: No se encontró fila de encabezado.")
        return

    df = pd.read_excel(file_path, header=header_idx)
    
    # Normalizar columnas
    df.columns = [str(c).upper().replace(" ", "_").strip() for c in df.columns]
    
    # 2. Selección de periodo (Max Año, Max Semana)
    col_anio = next((c for c in df.columns if "AÑO" in c or "ANIO" in c), None)
    col_semana = next((c for c in df.columns if "NOSEMANA" in c), None)
    col_fecha = next((c for c in df.columns if "FECHA" in c), None)
    col_muni = "HECHOS.MUNICIPIO"
    
    # Filtrar solo Jamundí
    df_jamundi = df[df[col_muni].astype(str).str.upper().str.contains("JAMUND")].copy()
    
    if df_jamundi.empty:
        print("Error: No hay datos de Jamundí en el archivo.")
        print(f"Municipios encontrados: {df[col_muni].unique()}")
        return

    max_anio = df_jamundi[col_anio].max()
    max_semana = df_jamundi[df_jamundi[col_anio] == max_anio][col_semana].max()
    
    df_periodo = df_jamundi[(df_jamundi[col_anio] == max_anio) & (df_jamundi[col_semana] == max_semana)].copy()
    
    min_fecha = df_periodo[col_fecha].min()
    max_fecha = df_periodo[col_fecha].max()
    
    print("\n1) SELECCIÓN DE PERIODO")
    print(f"- AÑO: {max_anio}")
    print(f"- SEMANA: {max_semana}")
    print(f"- RANGO FECHAS: {min_fecha} a {max_fecha}")
    
    # 3. Pre-check de colisiones en STAGING
    col_conducta = "DESCRIPCION_CONDUCTA"
    col_barrio = "BARRIOS_HECHO"
    col_hora = "HORA_HECHO"
    col_modo = "MODALIDAD"
    col_arma = "ARMAS_MEDIOS"
    
    def gen_fp(row):
        f = str(row.get(col_fecha, ''))
        c = str(row.get(col_conducta, ''))
        b = str(row.get(col_barrio, ''))
        h = str(row.get(col_hora, ''))
        m = str(row.get(col_modo, ''))
        a = str(row.get(col_arma, ''))
        raw = f"{f}|JAMUNDI|{c}|{b}|{h}|{m}|{a}"
        return hashlib.sha256(raw.encode()).hexdigest()

    df_periodo['fp'] = df_periodo.apply(gen_fp, axis=1)
    
    rows_total = len(df_periodo)
    fp_unicos = df_periodo['fp'].nunique()
    colisiones = rows_total - fp_unicos
    
    print("\n2) PRE-CHECK DE COLISIONES EN STAGING")
    print(f"- ROWS TOTAL (Periodo): {rows_total}")
    print(f"- FINGERPRINTS UNICOS: {fp_unicos}")
    print(f"- COLISIONES: {colisiones}")
    
    if colisiones > 0:
        print("\nDETALLE DE COLISIONES:")
        dups = df_periodo[df_periodo.duplicated(['fp'], keep=False)]
        summary = dups.groupby(col_conducta).size().reset_index(name='count')
        print(summary.to_string(index=False))
        print("\nPOSIBLE CAUSA:")
        print("- Registros con la misma hora, barrio y conducta. Si CANTIDAD > 1, es probable que el archivo venga pre-agregado y no por micro-eventos.")
    else:
        print("\nSITUACIÓN: 0 COLISIONES. Los micro-eventos son únicos por (Fecha, Hora, Barrio, Conducta, Modalidad, Arma).")

if __name__ == "__main__":
    analyze_sem_file(r'c:\Users\USER\Downloads\SEM 08. 2026.xlsx')
