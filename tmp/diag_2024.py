import pandas as pd
import io

f = 'C:/Users/USER/Downloads/2024.xlsx'
df_raw = pd.read_excel(f, header=None, nrows=20)
indicators = ['MUNICIPIO', 'MPIO', 'LUGAR', 'CONDUCTA', 'FECHA_HECHO']
h_idx = -1
for idx, row in df_raw.head(20).iterrows():
    row_str = [str(x).upper().strip() for x in row.values if pd.notna(x)]
    # print(f"Row {idx}: {row_str}")
    if any(any(ind in v for ind in indicators) for v in row_str):
        h_idx = idx
        break
print(f'Header Idx: {h_idx}')
if h_idx != -1:
    df = pd.read_excel(f, header=h_idx)
    df.columns = [str(c).upper().strip().replace(' ', '_') for c in df.columns]
    print(f'Columns: {df.columns.tolist()[:10]}...')
    # Check if JAMUNDI is there
    col_muni = next((c for c in df.columns if any(x in c for x in ["MUNICIPIO", "LUGAR", "MPIO"])), None)
    if col_muni:
        print(f"Col muni found: {col_muni}")
        jam_rows = df[df[col_muni].astype(str).str.contains('JAMUNDI', case=False, na=False)]
        print(f"Jamundi rows: {len(jam_rows)}")
