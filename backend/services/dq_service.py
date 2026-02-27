import pandas as pd
import numpy as np
from datetime import datetime
import io
from typing import List, Dict, Any, Tuple
import json
import unicodedata

# 1. Configuración de Esquema Requerido
# Columnas núcleo — siempre deben estar presentes
REQUIRED_COLUMNS = [
    "FECHA_HECHO",
    "COD_DEPTO",
    "DEPARTAMENTO",
    "COD_MUNI",
    "MUNICIPIO",
    "CANTIDAD"
]

# Columnas opcionales que enriquecen la validación si existen
OPTIONAL_COLUMNS = ["DESCRIPCION CONDUCTA", "ZONA", "SEXO", "ARMAS MEDIOS"]

# Aliases: si no existe CANTIDAD, buscar estas columnas (en orden) y renombrarlas
CANTIDAD_ALIASES = ["VICTIMAS", "CANTIDAD_VICTIMAS", "CASOS", "TOTAL"]
# Columnas que pueden ser inferidas si faltan
OPTIONAL_INFERRABLE = ["DESCRIPCION CONDUCTA"]

def make_serializable(obj: Any) -> Any:
    """Convierte tipos de numpy/pandas a tipos nativos de Python para JSON."""
    if isinstance(obj, dict):
        return {str(k): make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_serializable(i) for i in obj]
    elif isinstance(obj, (np.int64, np.int32, np.integer)):
        return int(obj)
    elif isinstance(obj, (np.float64, np.float32, np.floating)):
        return float(obj)
    elif pd.isna(obj):
        return None
    elif isinstance(obj, (datetime, pd.Timestamp)):
        return obj.isoformat()
    return obj

def clean_text(text: Any) -> str:
    """Normalización básica de texto: trim, espacios compactos y mayúsculas."""
    if pd.isna(text):
        return ""
    s = str(text).strip()
    return " ".join(s.split()).upper()

def create_key(text: str) -> str:
    """Crea una clave de búsqueda/matching sin acentos ni carácteres especiales."""
    if not text:
        return ""
    text = clean_text(text)
    # Quitar acentos
    text = "".join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    return text

def run_dq(file_bytes: bytes, filename: str, source_name: str = None) -> Dict[str, Any]:
    """
    Motor de Calidad de Datos (DQ).
    Ejecuta validación de esquema, normalización, reglas de negocio, consistencia y perfilamiento.
    """
    # 1. Lectura con detección de formato agresiva
    df = None
    last_error = ""
    
    # Intento 1: Excel Moderno (.xlsx)
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
    except Exception as e:
        last_error = str(e)
        
    # Intento 2: Excel Antiguo (.xls)
    if df is None:
        try:
            df = pd.read_excel(io.BytesIO(file_bytes), engine="xlrd")
        except:
            pass
            
    # Intento 3: CSV / Texto Plano (Forzado)
    if df is None:
        for enc in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
            try:
                # sep=None con engine='python' detecta automáticamente el separador (, ; \t |)
                df = pd.read_csv(io.BytesIO(file_bytes), encoding=enc, sep=None, engine='python')
                if df is not None and len(df.columns) > 1:
                    break
                df = None
            except:
                continue

    if df is None:
        return {
            "filename": filename,
            "error": f"Error crítico: El archivo no es un Excel válido ni un CSV legible. Detalles: {last_error}", 
            "schema_ok": False,
            "semaforo": "ROJO",
            "issues": [{"severity": "ERROR", "field": "FILE", "rule": f"Formato no reconocido: {last_error}", "count": 1}]
        }

    rows_count = len(df)
    # Normalizar nombres de columnas (strip de espacios)
    df.columns = [str(c).strip() for c in df.columns]
    cols_found = list(df.columns)

    # --- Resolución de alias para CANTIDAD ---
    if "CANTIDAD" not in cols_found:
        for alias in CANTIDAD_ALIASES:
            if alias in cols_found:
                df = df.rename(columns={alias: "CANTIDAD"})
                cols_found = list(df.columns)
                break

    # --- DESCRIPCION CONDUCTA es opcional: si no existe, se crea vacía ---
    if "DESCRIPCION CONDUCTA" not in cols_found:
        # Intentar derivarla del nombre del archivo / source
        conduct_value = source_name.replace("_MINDEFENSA", "").replace("_", " ") if source_name else filename
        df["DESCRIPCION CONDUCTA"] = conduct_value
        cols_found = list(df.columns)

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in cols_found]
    extra_cols = [c for c in cols_found if c not in REQUIRED_COLUMNS and c not in OPTIONAL_COLUMNS
                  and not c.endswith("_KEY")]
    
    if missing_cols:
        return {
            "filename": filename,
            "rows_total": rows_count,
            "schema_ok": False,
            "missing_cols": missing_cols,
            "extra_cols": extra_cols,
            "score_overall": 0.0,
            "semaforo": "ROJO",
            "issues": [{"severity": "ERROR", "field": "SCHEMA",
                        "rule": f"Faltan columnas requeridas: {', '.join(missing_cols)}", "count": 1}]
        }

    # 2. Normalización
    df_clean = df.copy()

    # Texto y Keys
    text_cols = ["DEPARTAMENTO", "MUNICIPIO", "DESCRIPCION CONDUCTA"]
    for col in text_cols:
        df_clean[col] = df_clean[col].apply(clean_text)
        df_clean[f"{col}_KEY"] = df_clean[col].apply(create_key)

    # Numéricos (Int64 permite NaNs)
    for col in ["COD_DEPTO", "COD_MUNI", "CANTIDAD"]:
        df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce").astype("Int64")
    
    # Fecha
    df_clean["FECHA_HECHO_DT"] = pd.to_datetime(df_clean["FECHA_HECHO"], errors="coerce")
    df_clean["ANIO"] = df_clean["FECHA_HECHO_DT"].dt.year.astype("Int64")
    
    # 3. Reglas de Validación (Hallazgos)
    issues = []
    samples = {}
    current_year = datetime.now().year

    def add_issue(severity, field, rule, mask, sample_key=None):
        count = int(mask.sum())
        if count > 0:
            issues.append({
                "severity": severity, "field": field, "rule": rule, "count": count,
                "example": df_clean[mask].head(5).to_dict(orient="records")
            })
            if sample_key:
                samples[sample_key] = df_clean[mask].head(100).to_dict(orient="records")
        return count

    # Errores Críticos (Validez)
    nat_count = add_issue("ERROR", "FECHA_HECHO", "Fecha no válida o formato incorrecto", df_clean["FECHA_HECHO_DT"].isna(), "nat_dates")
    future_count = add_issue("ERROR", "FECHA_HECHO", "Fechas futuras", df_clean["FECHA_HECHO_DT"] > datetime.now(), "future_dates")
    add_issue("ERROR", "ANIO", f"Año superior al actual ({current_year})", df_clean["ANIO"] > current_year)
    add_issue("ERROR", "CANTIDAD", "Cantidad menor o igual a cero", df_clean["CANTIDAD"] <= 0, "invalid_qty")

    # Advertencias (Heurísticas)
    add_issue("WARNING", "CANTIDAD", "Cantidades inusualmente altas (>100)", df_clean["CANTIDAD"] > 100)
    add_issue("WARNING", "ANIO", "Registros muy antiguos (previos a 1990)", df_clean["ANIO"] < 1990)

    # 4. Consistencia Cruzada
    # COD_DEPTO -> DEPARTAMENTO
    dept_conflicts = df_clean.groupby("COD_DEPTO")["DEPARTAMENTO_KEY"].nunique()
    if (dept_conflicts > 1).any():
        bad_codes = dept_conflicts[dept_conflicts > 1].index.tolist()
        mask = df_clean["COD_DEPTO"].isin(bad_codes)
        add_issue("WARNING", "COD_DEPTO", "Un código de departamento tiene múltiples nombres asociados", mask, "dept_consistency")

    # (COD_DEPTO, COD_MUNI) -> MUNICIPIO
    muni_conflicts = df_clean.groupby(["COD_DEPTO", "COD_MUNI"])["MUNICIPIO_KEY"].nunique()
    if (muni_conflicts > 1).any():
        bad_indices = muni_conflicts[muni_conflicts > 1].index
        mask = df_clean.set_index(["COD_DEPTO", "COD_MUNI"]).index.isin(bad_indices)
        add_issue("WARNING", "MUNICIPIO", "Un par (Dept, Muni) tiene múltiples nombres de municipio", mask, "muni_consistency")

    # 5. Duplicados
    # Exactos
    dup_exact_mask = df_clean[REQUIRED_COLUMNS].duplicated(keep=False)
    dup_exact_count = add_issue("WARNING", "MULTIPLE", "Filas exactamente duplicadas", dup_exact_mask, "exact_duplicates")

    # Lógicos
    logical_cols = ["FECHA_HECHO_DT", "COD_DEPTO", "COD_MUNI", "DESCRIPCION CONDUCTA_KEY"]
    dup_logic_mask = df_clean.duplicated(subset=logical_cols, keep=False) & ~dup_exact_mask
    dup_logic_count = add_issue("WARNING", "MULTIPLE", "Duplicados lógicos (misma fecha, lugar y conducta)", dup_logic_mask, "logical_duplicates")

    # 6. Profiling
    profiles = {
        "columns": {},
        "top_values": {},
        "anual_sum": {}
    }
    for col in REQUIRED_COLUMNS:
        profiles["columns"][col] = {
            "dtype": str(df_clean[col].dtype),
            "nulls": int(df_clean[col].isna().sum()),
            "null_pct": float(df_clean[col].isna().mean() * 100),
            "nunique": int(df_clean[col].nunique())
        }
    
    profiles["top_values"]["DEPARTAMENTO"] = df_clean["DEPARTAMENTO"].value_counts().head(10).to_dict()
    profiles["top_values"]["MUNICIPIO"] = df_clean["MUNICIPIO"].value_counts().head(10).to_dict()
    profiles["top_values"]["CONDUCTA"] = df_clean["DESCRIPCION CONDUCTA"].value_counts().head(10).to_dict()
    
    if not df_clean["ANIO"].isna().all():
        anual_sum_raw = df_clean.groupby("ANIO")["CANTIDAD"].sum().to_dict()
        profiles["anual_sum"] = {int(k): int(v) for k, v in anual_sum_raw.items()}

    # 7. Scoring y Semáforo
    # Fórmulas de scoring basadas en ratios de filas válidas
    completeness = 1.0 - (df_clean[REQUIRED_COLUMNS].isna().mean().mean())
    
    validity_errors = nat_count + future_count + int((df_clean["CANTIDAD"] <= 0).sum())
    validity_score = 1.0 - (validity_errors / rows_count if rows_count > 0 else 0)
    
    uniqueness_score = 1.0 - (df_clean.duplicated(subset=logical_cols).mean() if rows_count > 0 else 0)
    
    # Consistencia (simplificado: basado en conflictos de nombres)
    consistency_score = 1.0 - (mask.mean() if 'mask' in locals() else 0)

    score_overall = (completeness * 0.3) + (validity_score * 0.4) + (uniqueness_score * 0.2) + (consistency_score * 0.1)
    
    error_count = len([i for i in issues if i["severity"] == "ERROR"])
    warning_count = len([i for i in issues if i["severity"] == "WARNING"])
    
    semaforo = "VERDE"
    if error_count > 0: semaforo = "ROJO"
    elif warning_count > 0: semaforo = "AMARILLO"

    report_data = {
        "filename": filename,
        "source_name": source_name,
        "rows_total": rows_count,
        "schema_ok": True,
        "missing_cols": missing_cols,
        "extra_cols": extra_cols,
        "min_date": df_clean["FECHA_HECHO_DT"].min().isoformat() if not df_clean["FECHA_HECHO_DT"].isna().all() else None,
        "max_date": df_clean["FECHA_HECHO_DT"].max().isoformat() if not df_clean["FECHA_HECHO_DT"].isna().all() else None,
        "score_overall": float(score_overall),
        "score_completeness": float(completeness),
        "score_validity": float(validity_score),
        "score_consistency": float(consistency_score),
        "score_uniqueness": float(uniqueness_score),
        "semaforo": semaforo,
        "profiles": profiles,
        "issues": issues,
        "samples": samples, # Max 500 filas aprox según limitantes arriba
        "file_meta": {
            "rows": rows_count,
            "filename": filename,
            "created_at": datetime.now().isoformat()
        }
    }
    
    return make_serializable(report_data)

def build_excel_from_report(report_json: Dict[str, Any]) -> bytes:
    """Genera un reporte Excel on-demand con múltiples hojas de auditoría."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # 1. Resumen Ejecutivo
        resumen = [
            ["Métrica", "Valor"],
            ["Archivo", report_json.get("filename")],
            ["Total Filas", report_json.get("rows_total")],
            ["Score General", f"{round(report_json.get('score_overall', 0) * 100, 2)}%"],
            ["Semáforo", report_json.get("semaforo")],
            ["Fecha Inicial", report_json.get("min_date")],
            ["Fecha Final", report_json.get("max_date")]
        ]
        pd.DataFrame(resumen[1:], columns=resumen[0]).to_excel(writer, sheet_name="Resumen", index=False)
        
        # 2. Hallazgos (Issues)
        if report_json.get("issues"):
            pd.DataFrame(report_json["issues"]).to_excel(writer, sheet_name="Auditoria_Detallada", index=False)
            
        # 3. Muestras de Errores (Samples)
        samples = report_json.get("samples", {})
        for key, rows in samples.items():
            if rows:
                sheet_name = (key[:25]) # Limitar nombre hoja
                pd.DataFrame(rows).to_excel(writer, sheet_name=f"Sample_{sheet_name}", index=False)
                
        # 4. Perfil de Columnas
        if report_json.get("profiles", {}).get("columns"):
            cols_df = pd.DataFrame(report_json["profiles"]["columns"]).T
            cols_df.to_excel(writer, sheet_name="Perfil_Columnas")
            
    return output.getvalue()
