import pandas as pd
import numpy as np
import sys
import os
import json
import unicodedata
from datetime import datetime

def normalize_text(text):
    if pd.isna(text):
        return "N/D"
    text = str(text).upper()
    # Normalize unicode to avoid accents
    text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8')
    # Use join and split to collapse multiple spaces
    text = " ".join(text.split())
    return text.strip()

def detect_sem_policial(df):
    cols = [str(c).upper() for c in df.columns]
    # Key requirements
    has_year = any(x in cols for x in ["AÑO", "ANO", "AO"])
    has_week = any(x in cols for x in ["NOSEMANA", "SEMANA", "NUM_SEMANA"])
    has_conducta = any(x in cols for x in ["DESCRIPCION_CONDUCTA", "CONDUCTA", "HECHO"])
    
    return has_year and has_week and has_conducta

def get_col_mapping(df):
    cols = {str(c).upper(): c for c in df.columns}
    mapping = {}
    
    # Required
    mapping['year'] = next((cols[x] for x in ["AO", "AÑO", "ANO"] if x in cols), None)
    mapping['week'] = next((cols[x] for x in ["NOSEMANA", "SEMANA", "NUM_SEMANA"] if x in cols), None)
    mapping['date'] = next((cols[x] for x in ["FECHA_HECHO", "FECHA"] if x in cols), None)
    mapping['conducta'] = next((cols[x] for x in ["DESCRIPCION_CONDUCTA", "CONDUCTA", "HECHO"] if x in cols), None)
    mapping['barrio'] = next((cols[x] for x in ["BARRIOS_HECHO", "BARRIO", "VEREDA"] if x in cols), None)
    
    # Optional
    mapping['zona'] = next((cols[x] for x in ["ZONA"] if x in cols), None)
    mapping['dia'] = next((cols[x] for x in ["DIA_SEMANA"] if x in cols), None)
    mapping['hora_agrupada'] = next((cols[x] for x in ["INTERVALOS_HORA", "HORA24"] if x in cols), None)
    mapping['modalidad'] = next((cols[x] for x in ["MODALIDAD"] if x in cols), None)
    mapping['armas'] = next((cols[x] for x in ["ARMAS_MEDIOS"] if x in cols), None)
    mapping['sitio'] = next((cols[x] for x in ["CLASE_SITIO"] if x in cols), None)
    mapping['cantidad'] = next((cols[x] for x in ["CANTIDAD"] if x in cols), None)
    
    return mapping

def apply_privacy(df, col, value_col='total'):
    """Groups categories with n < 5 into 'OTROS'"""
    # Create a copy to avoid warnings
    res = df.copy()
    mask = res[value_col] < 5
    if mask.any():
        otros_sum = res.loc[mask, value_col].sum()
        res = res[~mask]
        # Use concat instead of append
        new_row = pd.DataFrame([{col: 'OTROS', value_col: otros_sum}])
        res = pd.concat([res, new_row], ignore_index=True)
    return res

def analyze_sem(file_path):
    print(f"--- ANALIZANDO: {os.path.basename(file_path)} ---")
    
    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        print(f"Error cargando archivo: {e}")
        return

    if not detect_sem_policial(df):
        print("ERROR: El archivo no cumple con los criterios de un SEM Policial.")
        return

    m = get_col_mapping(df)
    
    # Quality Check: Report missing columns
    required = ['year', 'week', 'date', 'conducta', 'barrio']
    missing = [k for k in required if m[k] is None]
    if missing:
        print(f"ADVERTENCIA: Faltan columnas clave: {missing}. El análisis será parcial.")

    # 1. Normalization
    if m['conducta']:
        df[m['conducta']] = df[m['conducta']].apply(normalize_text)
    if m['barrio']:
        df[m['barrio']] = df[m['barrio']].apply(normalize_text)

    # 2. Week Selection
    year_col = m['year']
    week_col = m['week']
    
    max_year = df[year_col].max()
    max_week = df[df[year_col] == max_year][week_col].max()
    
    # Filter current and previous week
    df_curr = df[(df[year_col] == max_year) & (df[week_col] == max_week)].copy()
    df_prev = df[(df[year_col] == max_year) & (df[week_col] == (max_week - 1))].copy()

    # Rule of counting
    def calculate_total(subset):
        if subset.empty: return 0
        if m['cantidad']:
            return subset[m['cantidad']].sum()
        return len(subset)

    total_curr = calculate_total(df_curr)
    total_prev = calculate_total(df_prev)
    variation = total_curr - total_prev
    var_pct = (variation / total_prev * 100) if total_prev > 0 else 0

    # Date Range
    date_col = m['date']
    if date_col:
        # Check for nulls
        null_dates = df_curr[date_col].isna().sum()
        if null_dates > 0:
            print(f"ADVERTENCIA: Se encontraron {null_dates} registros con fecha nula. Excluidos del rango temporal.")
        
        df_curr[date_col] = pd.to_datetime(df_curr[date_col], errors='coerce')
        valid_dates = df_curr.dropna(subset=[date_col])
        if not valid_dates.empty:
            date_min = valid_dates[date_col].min().strftime('%Y-%m-%d')
            date_max = valid_dates[date_col].max().strftime('%Y-%m-%d')
        else:
            date_min = date_max = "N/D"
    else:
        date_min = date_max = "N/D"

    print(f"\nREPORTE: SEMANA POLICIAL {max_week} - {max_year}")
    print(f"RANGO: {date_min} al {date_max}")
    print("-" * 40)
    print(f"Total hechos esta semana: {total_curr}")
    print(f"Variación vs semana anterior: {variation} ({var_pct:+.1f}%)")
    print("-" * 40)

    # OUTPUTS
    # Helper to aggregate
    def agg_col(df_sub, col_name, label, top=None):
        if not col_name: return None
        if m['cantidad']:
            res = df_sub.groupby(col_name)[m['cantidad']].sum().reset_index(name='total')
        else:
            res = df_sub.groupby(col_name).size().reset_index(name='total')
        
        res = res.sort_values('total', ascending=False)
        total_sum = res['total'].sum()
        res['pct'] = (res['total'] / total_sum * 100).round(1)
        
        # Privacy
        res = apply_privacy(res, col_name)
        
        if top:
            return res.head(top)
        return res

    # 1. Top Conductas
    top_conductas = agg_col(df_curr, m['conducta'], "CONDUCTA")
    print("\nTOP CONDUCTAS:")
    print(top_conductas.to_string(index=False))

    # 2. Top 10 Barrios
    top_barrios = agg_col(df_curr, m['barrio'], "BARRIO", top=10)
    print("\nTOP 10 BARRIOS/VEREDAS:")
    print(top_barrios.to_string(index=False))

    # 3. Cruce Barrio x Conducta (Top combinaciones)
    if m['barrio'] and m['conducta']:
        if m['cantidad']:
            cruce = df_curr.groupby([m['barrio'], m['conducta']])[m['cantidad']].sum().reset_index(name='total')
        else:
            cruce = df_curr.groupby([m['barrio'], m['conducta']]).size().reset_index(name='total')
        print("\nTOP 10 CRUCES BARRIO X CONDUCTA:")
        print(cruce.sort_values('total', ascending=False).head(10).to_string(index=False))

    # 4. Heatmap: Dia x Hora
    if m['dia'] and m['hora_agrupada']:
        if m['cantidad']:
            heat = df_curr.groupby([m['dia'], m['hora_agrupada']])[m['cantidad']].sum().unstack(fill_value=0)
        else:
            heat = df_curr.groupby([m['dia'], m['hora_agrupada']]).size().unstack(fill_value=0)
        print("\nDISTRIBUCIÓN DÍA X HORA:")
        print(heat.to_string())

    # 5. Extras (Zona, Sitio)
    if m['zona']:
        print("\nDISTRIBUCIÓN POR ZONA:")
        print(agg_col(df_curr, m['zona'], "ZONA").to_string(index=False))
    
    if m['sitio']:
        print("\nDISTRIBUCIÓN POR CLASE SITIO (TOP 5):")
        print(agg_col(df_curr, m['sitio'], "SITIO", top=5).to_string(index=False))

    # 6. Contexto Conducta Prioritaria
    if m['conducta']:
        # Most frequent behavior
        main_c = top_conductas.iloc[0][m['conducta']]
        if main_c != "OTROS":
            print(f"\nCONTEXTO PARA CONDUCTA PRIORITARIA: {main_c}")
            df_main = df_curr[df_curr[m['conducta']] == main_c]
            if m['modalidad']:
                print("\nMODALIDAD:")
                print(agg_col(df_main, m['modalidad'], "MODALIDAD", top=5).to_string(index=False))
            if m['armas']:
                print("\nARMAS/MEDIOS:")
                print(agg_col(df_main, m['armas'], "ARMAS", top=5).to_string(index=False))

if __name__ == "__main__":
    path = r'c:\Users\USER\Downloads\SEM 08. 2026.xlsx'
    if len(sys.argv) > 1:
        path = sys.argv[1]
    analyze_sem(path)
