import pandas as pd
import sys
import json

def analyze_afectacion(file_path):
    try:
        # Load the excel file
        # The user says "Sheet 1", but usually pandas reads the first sheet or we specify "Sheet1"
        # Since I saw "Sheet1" in my previous test with another file, I'll try "Sheet 1" first then fallback
        try:
            df = pd.read_excel(file_path, sheet_name='Sheet 1')
        except ValueError:
            df = pd.read_excel(file_path, sheet_name=0) # Read first sheet as fallback

        # Print columns for debug
        print(f"Columns found: {df.columns.tolist()}")

        # Normalize column names to match requirements
        required_cols = [
            'FECHA HECHO', 'COD_DEPTO', 'DEPARTAMENTO', 'COD_MUNI', 
            'MUNICIPIO', 'NOMBRE_FUERZA', 'ACCION', 'CATEGORIA', 'CANTIDAD'
        ]
        
        # MAPPING if names are slightly different (e.g. spaces or case)
        # But user says "tal cual" (as is), so I'll trust them.
        
        # 1. Filter Jamundí
        # Jamundí (use one of these and prioritize the code):
        # COD_MUNI = 76364 OR (MUNICIPIO = "JAMUNDI" and DEPARTAMENTO = "VALLE DEL CAUCA")
        
        jamundi_mask = (df['COD_MUNI'] == 76364) | \
                      ((df['MUNICIPIO'].astype(str).str.upper().str.strip() == 'JAMUNDI') & \
                       (df['DEPARTAMENTO'].astype(str).str.upper().str.strip() == 'VALLE DEL CAUCA'))
        
        df_jamundi = df[jamundi_mask].copy()
        
        if df_jamundi.empty:
            print("No data found for Jamundí with the given filters.")
            return

        # 2. Quality & Normalization
        text_cols = ['DEPARTAMENTO', 'MUNICIPIO', 'NOMBRE_FUERZA', 'ACCION', 'CATEGORIA']
        for col in text_cols:
            if col in df_jamundi.columns:
                df_jamundi[col] = df_jamundi[col].astype(str).str.upper().str.strip()

        # 3. Handle Null Dates
        null_dates_count = df_jamundi['FECHA HECHO'].isna().sum()
        if null_dates_count > 0:
            print(f"REPORT: Found {null_dates_count} rows with null dates. Excluding from temporal analysis.")
            df_temporal = df_jamundi.dropna(subset=['FECHA HECHO']).copy()
        else:
            df_temporal = df_jamundi.copy()

        df_temporal['FECHA HECHO'] = pd.to_datetime(df_temporal['FECHA HECHO'], errors='coerce')
        df_temporal = df_temporal.dropna(subset=['FECHA HECHO']) # Drop any parsing errors

        # 4. Temporal Analysis (sum(CANTIDAD))
        df_temporal['year'] = df_temporal['FECHA HECHO'].dt.year
        df_temporal['month'] = df_temporal['FECHA HECHO'].dt.month
        
        temporal_year = df_temporal.groupby('year')['CANTIDAD'].sum().to_dict()
        temporal_month = df_temporal.groupby(['year', 'month'])['CANTIDAD'].sum().reset_index()
        temporal_month_list = temporal_month.to_dict('records')

        # 5. Distribution by ACCION (Top and %)
        total_cantidad = df_jamundi['CANTIDAD'].sum()
        dist_accion = df_jamundi.groupby('ACCION')['CANTIDAD'].sum().sort_values(ascending=False)
        dist_accion_pct = (dist_accion / total_cantidad * 100).round(2)
        
        accion_table = pd.DataFrame({
            'Total': dist_accion,
            'Percentage': dist_accion_pct
        }).reset_index().to_dict('records')

        # 6. Distribution by NOMBRE_FUERZA
        dist_fuerza = df_jamundi.groupby('NOMBRE_FUERZA')['CANTIDAD'].sum().sort_values(ascending=False)
        fuerza_table = dist_fuerza.reset_index().to_dict('records')

        # 7. Cross: ACCION x NOMBRE_FUERZA
        cross_accion_fuerza = df_jamundi.groupby(['ACCION', 'NOMBRE_FUERZA'])['CANTIDAD'].sum().unstack(fill_value=0)
        cross_accion_fuerza_dict = cross_accion_fuerza.to_dict('index')

        # 8. Cross: ACCION x CATEGORIA
        cross_accion_cat = df_jamundi.groupby(['ACCION', 'CATEGORIA'])['CANTIDAD'].sum().unstack(fill_value=0)
        cross_accion_cat_dict = cross_accion_cat.to_dict('index')

        # 9. Top 10 combinations: NOMBRE_FUERZA + CATEGORIA
        df_jamundi['FUERZA_CAT'] = df_jamundi['NOMBRE_FUERZA'] + " - " + df_jamundi['CATEGORIA']
        top10_comb = df_jamundi.groupby('FUERZA_CAT')['CANTIDAD'].sum().sort_values(ascending=False).head(10).to_dict()

        # Output Results
        results = {
            "temporal_year": temporal_year,
            "temporal_month": temporal_month_list,
            "distribution_accion": accion_table,
            "distribution_fuerza": fuerza_table,
            "cross_accion_fuerza": cross_accion_fuerza_dict,
            "cross_accion_cat": cross_accion_cat_dict,
            "top10_combinations": top10_comb,
            "total_incidents": total_cantidad
        }

        # Custom JSON Encoder helper
        def convert_types(obj):
            if isinstance(obj, dict):
                return {k: convert_types(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_types(i) for i in obj]
            elif hasattr(obj, 'item'): # handles numpy/pandas scalars
                return obj.item()
            return obj

        results = convert_types(results)
        print("\n=== RESULTS ANALYSIS ===")
        print(json.dumps(results, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"Error during analysis: {e}")

if __name__ == "__main__":
    file_path = r'c:\Users\USER\Downloads\AFECTACIÓN A LA FUERZA PÚBLICA.xlsx'
    analyze_afectacion(file_path)
