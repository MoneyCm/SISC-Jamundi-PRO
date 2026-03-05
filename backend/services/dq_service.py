import pandas as pd
import numpy as np
from datetime import datetime
import io
from typing import List, Dict, Any, Tuple
import json
import unicodedata

# 1. Configuración de Esquema Requerido
# 1. Configuración de Esquema Requerido
REQUIRED_COLUMNS = [
    "FECHA_HECHO",
    "MUNICIPIO"
]

OPTIONAL_COLUMNS = ["DESCRIPCION CONDUCTA", "ZONA", "SEXO", "ARMAS MEDIOS"]
CANTIDAD_ALIASES = ["VICTIMAS", "CANTIDAD_VICTIMAS", "CASOS", "TOTAL"]
OPTIONAL_INFERRABLE = ["DESCRIPCION CONDUCTA"]

def make_serializable(obj: Any) -> Any:
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
    if pd.isna(text): return ""
    s = str(text).strip()
    return " ".join(s.split()).upper()

def create_key(text: str) -> str:
    if not text: return ""
    text = clean_text(text)
    text = "".join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    return text

def run_dq(file_bytes: bytes, filename: str, source_name: str = None) -> Dict[str, Any]:
    from services.file_reader import smart_read_file
    try:
        df = smart_read_file(file_bytes)
    except Exception as e:
        return {
            "filename": filename,
            "error": str(e), 
            "schema_ok": False,
            "semaforo": "ROJO",
            "issues": [{"severity": "ERROR", "field": "FILE", "rule": f"Error de lectura: {str(e)}", "count": 1}]
        }

    rows_count = len(df)
    df.columns = [str(c).strip().upper() for c in df.columns]
    
    # Mapeo Inteligente de Alias de Columnas
    aliases_map = {
        "FECHA": "FECHA_HECHO", "DATE": "FECHA_HECHO", "FECHA DEL HECHO": "FECHA_HECHO",
        "BARRIO": "MUNICIPIO", "SECTOR": "MUNICIPIO", "CIUDAD": "MUNICIPIO", "BARRIOS_HECHO": "MUNICIPIO", "BARRIOS HECHO": "MUNICIPIO",
        "DELITO": "DESCRIPCION CONDUCTA", "CONDUCTA": "DESCRIPCION CONDUCTA", "TIPO": "DESCRIPCION CONDUCTA",
        "VICTIMAS": "CANTIDAD", "CANTIDAD_VICTIMAS": "CANTIDAD", "CASOS": "CANTIDAD", "TOTAL": "CANTIDAD"
    }
    
    for col in list(df.columns):
        if col in aliases_map and aliases_map[col] not in df.columns:
            df.rename(columns={col: aliases_map[col]}, inplace=True)
            
    cols_found = list(df.columns)

    if "CANTIDAD" not in cols_found:
        df["CANTIDAD"] = 1
        cols_found.append("CANTIDAD")

    if "DESCRIPCION CONDUCTA" not in cols_found:
        fallback = source_name.replace("_MINDEFENSA", "").replace("_", " ") if source_name else "CONDUCTA_NO_ESPECIFICADA"
        df["DESCRIPCION CONDUCTA"] = fallback
        cols_found.append("DESCRIPCION CONDUCTA")
        
    for opt_col in ["COD_DEPTO", "DEPARTAMENTO", "COD_MUNI"]:
        if opt_col not in cols_found:
            df[opt_col] = None

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in cols_found]
    extra_cols = [c for c in cols_found if c not in REQUIRED_COLUMNS and c not in OPTIONAL_COLUMNS]
    
    if missing_cols:
        return {
            "filename": filename,
            "rows_total": rows_count,
            "schema_ok": False,
            "missing_cols": missing_cols,
            "semaforo": "ROJO",
            "issues": [{"severity": "ERROR", "field": "SCHEMA", "rule": f"Faltan columnas: {', '.join(missing_cols)}", "count": 1}]
        }

    df_clean = df.copy()
    text_cols = ["DEPARTAMENTO", "MUNICIPIO", "DESCRIPCION CONDUCTA"]
    for col in text_cols:
        df_clean[col] = df_clean[col].apply(clean_text)
        df_clean[f"{col}_KEY"] = df_clean[col].apply(create_key)

    for col in ["COD_DEPTO", "COD_MUNI", "CANTIDAD"]:
        df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce").astype("Int64")
    
    df_clean["FECHA_HECHO_DT"] = pd.to_datetime(df_clean["FECHA_HECHO"], errors="coerce")
    df_clean["ANIO"] = df_clean["FECHA_HECHO_DT"].dt.year.astype("Int64")
    
    issues = []
    samples = {}
    current_year = datetime.now().year

    def add_issue(severity, field, rule, mask, sample_key=None):
        count = int(mask.sum())
        if count > 0:
            issues.append({"severity": severity, "field": field, "rule": rule, "count": count})
            if sample_key: samples[sample_key] = df_clean[mask].head(10).to_dict(orient="records")
        return count

    nat_count = add_issue("ERROR", "FECHA_HECHO", "Fecha inválida", df_clean["FECHA_HECHO_DT"].isna(), "nat_dates")
    future_count = add_issue("ERROR", "FECHA_HECHO", "Fechas futuras", df_clean["FECHA_HECHO_DT"] > datetime.now(), "future_dates")
    add_issue("ERROR", "CANTIDAD", "Cantidad <= 0", df_clean["CANTIDAD"] <= 0, "invalid_qty")

    # Profiling
    profiles = {
        "columns": {col: {"dtype": str(df_clean[col].dtype), "nulls": int(df_clean[col].isna().sum()), "nunique": int(df_clean[col].nunique())} for col in REQUIRED_COLUMNS},
        "top_values": {"MUNICIPIO": df_clean["MUNICIPIO"].value_counts().head(10).to_dict()},
        "anual_sum": df_clean.groupby("ANIO")["CANTIDAD"].sum().to_dict() if not df_clean["ANIO"].isna().all() else {}
    }

    completeness = 1.0 - (df_clean[REQUIRED_COLUMNS].isna().mean().mean())
    score_overall = completeness # Simplificado para estabilidad
    
    semaforo = "ROJO" if any(i["severity"] == "ERROR" for i in issues) else "VERDE"

    report_data = {
        "filename": filename,
        "source_name": source_name,
        "rows_total": rows_count,
        "schema_ok": True,
        "score_overall": float(score_overall),
        "semaforo": semaforo,
        "profiles": profiles,
        "issues": issues,
        "samples": samples,
        "min_date": df_clean["FECHA_HECHO_DT"].min().isoformat() if not df_clean["FECHA_HECHO_DT"].isna().all() else None,
        "max_date": df_clean["FECHA_HECHO_DT"].max().isoformat() if not df_clean["FECHA_HECHO_DT"].isna().all() else None
    }
    
    return make_serializable(report_data)

def build_excel_from_report(report_json: Dict[str, Any]) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame([["Métrica", "Valor"], ["Archivo", report_json.get("filename")], ["Filas", report_json.get("rows_total")]]).to_excel(writer, sheet_name="Resumen", index=False)
    return output.getvalue()
