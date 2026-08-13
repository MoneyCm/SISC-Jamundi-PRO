import io
import re
import unicodedata
from datetime import date, datetime, time
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd


NULL_TEXT_VALUES = {
    "",
    "NAN",
    "NONE",
    "NULL",
    "N/A",
    "NA",
    "SIN INFORMACION",
    "NO REPORTA",
}


PROFILE_CONFIG = {
    "SEGURIDAD": {
        "required": ["FECHA_HECHO", "MUNICIPIO"],
        "recommended": ["DESCRIPCION_CONDUCTA"],
        "aliases": {
            "FECHA_HECHO": ["FECHA_HECHO", "FECHA", "DATE", "FECHA_DEL_HECHO", "FECHA_DANE"],
            "MUNICIPIO": ["MUNICIPIO", "MUNICIPIO_HECHO", "HECHOS_MUNICIPIO", "MPIO", "CIUDAD"],
            "DESCRIPCION_CONDUCTA": ["DESCRIPCION_CONDUCTA", "DELITO", "CONDUCTA", "TIPO"],
            "CANTIDAD": ["CANTIDAD", "VICTIMAS", "CANTIDAD_VICTIMAS", "CASOS", "TOTAL", "NUMERO_CASOS"],
        },
        "date_field": "FECHA_HECHO",
        "quantity_field": "CANTIDAD",
        "territory_field": "MUNICIPIO",
        "duplicate_fields": ["FECHA_HECHO", "MUNICIPIO", "DESCRIPCION_CONDUCTA", "CANTIDAD"],
    },
    "POLICIA_SEMANAL": {
        "required": ["ID_FUENTE", "CONDUCTA", "FECHA_HECHO", "SEMANA", "BARRIO", "ZONA"],
        "recommended": ["MUNICIPIO", "HORA", "MODALIDAD", "ARMA_MEDIO"],
        "aliases": {
            "ID_FUENTE": ["HECHOS_ID", "ID_HECHO", "HECHO_ID", "COD_HECHO", "ID"],
            "CONDUCTA": ["DESCRIPCION_CONDUCTA", "CONDUCTA", "DELITO"],
            "FECHA_HECHO": ["FECHA_HECHO", "FECHA", "FECHA_DEL_HECHO", "FECHA_INCIDENTE"],
            "SEMANA": ["NOSEMANA", "SEMANA", "NUM_SEMANA", "SEMANA_DEL"],
            "BARRIO": ["BARRIOS_HECHO", "BARRIO", "BARRIO_HECHO", "DESCRIPCION_BARRIO"],
            "ZONA": ["ZONA", "ZONA_HECHO"],
            "MUNICIPIO": ["MUNICIPIO_HECHO", "HECHOS_MUNICIPIO", "MUNICIPIO", "MPIO"],
            "HORA": ["HORA24", "HORA_HECHO", "HORA", "FRANJA_HORA", "FRANJA_HORARIA"],
            "MODALIDAD": ["MODALIDAD", "MODALIDAD_HECHO"],
            "ARMA_MEDIO": ["ARMAS_MEDIOS", "ARMA_MEDIO", "ARMA", "MEDIO"],
            "CANTIDAD": ["CANTIDAD", "VICTIMAS", "CANTIDAD_VICTIMAS", "TOTAL"],
        },
        "date_field": "FECHA_HECHO",
        "quantity_field": "CANTIDAD",
        "territory_field": "MUNICIPIO",
        "duplicate_fields": ["ID_FUENTE", "CONDUCTA", "FECHA_HECHO", "BARRIO", "HORA"],
    },
    "INSPECCIONES": {
        "required": ["EXPEDIENTE", "MEDIDA", "FECHA_ACTUACION", "MUNICIPIO"],
        "recommended": ["LOCALIDAD", "ESTADO"],
        "aliases": {
            "EXPEDIENTE": ["EXPEDIENTE", "NUMERO_EXPEDIENTE", "NRO_EXPEDIENTE", "RADICADO"],
            "MEDIDA": ["MEDIDA", "MEDIDA_CORRECTIVA", "TIPO_MEDIDA"],
            "FECHA_ACTUACION": ["FECHA_ACTUACION", "FECHA_DE_ACTUACION", "FECHA"],
            "MUNICIPIO": ["MUNICIPIO", "MPIO", "CIUDAD"],
            "LOCALIDAD": ["LOCALIDAD", "BARRIO", "SECTOR", "COMUNA"],
            "ESTADO": ["ESTADO", "ESTADO_ACTUAL"],
            "FECHA_INICIO": ["FECHA_INICIO", "INICIO"],
            "FECHA_FIN": ["FECHA_FIN", "FIN"],
        },
        "date_field": "FECHA_ACTUACION",
        "territory_field": "MUNICIPIO",
        "duplicate_fields": ["EXPEDIENTE", "MEDIDA", "FECHA_ACTUACION", "ANOTACION"],
    },
    "EVENTOS_GEO": {
        "required": ["FECHA", "HORA", "DELITO", "LATITUD", "LONGITUD"],
        "recommended": ["BARRIO", "DESCRIPCION"],
        "aliases": {
            "FECHA": ["FECHA", "FECHA_HECHO", "FECHA_DEL_HECHO"],
            "HORA": ["HORA", "HORA_HECHO", "HORA24"],
            "DELITO": ["DELITO", "CONDUCTA", "DESCRIPCION_CONDUCTA", "TIPO"],
            "LATITUD": ["LATITUD", "LAT", "Y"],
            "LONGITUD": ["LONGITUD", "LON", "LNG", "X"],
            "BARRIO": ["BARRIO", "BARRIOS_HECHO", "LOCALIDAD"],
            "DESCRIPCION": ["DESCRIPCION", "DETALLE", "OBSERVACION"],
        },
        "date_field": "FECHA",
        "duplicate_fields": ["FECHA", "HORA", "DELITO", "LATITUD", "LONGITUD"],
    },
    "REGISTROS_NORMALIZADOS": {
        "required": ["SOURCE_ID", "FECHA_HECHO", "MUNICIPIO", "CANTIDAD"],
        "recommended": ["EVENT_FINGERPRINT"],
        "aliases": {
            "SOURCE_ID": ["SOURCE_ID", "FUENTE_ID"],
            "FECHA_HECHO": ["FECHA_HECHO", "FECHA"],
            "MUNICIPIO": ["MUNICIPIO", "MUNICIPIO_HECHO", "MPIO"],
            "CANTIDAD": ["CANTIDAD", "TOTAL", "CASOS"],
            "EVENT_FINGERPRINT": ["EVENT_FINGERPRINT", "HASH_REGISTRO"],
        },
        "date_field": "FECHA_HECHO",
        "quantity_field": "CANTIDAD",
        "territory_field": "MUNICIPIO",
        "duplicate_fields": ["SOURCE_ID", "EVENT_FINGERPRINT"],
    },
}


def make_serializable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(key): make_serializable(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [make_serializable(value) for value in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (datetime, date, time, pd.Timestamp)):
        return obj.isoformat()
    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass
    return obj


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return " ".join(str(value).strip().split()).upper()


def create_key(value: Any) -> str:
    text = clean_text(value)
    return "".join(
        char
        for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    )


def normalize_column_name(value: Any) -> str:
    text = create_key(value)
    return re.sub(r"[^A-Z0-9]+", "_", text).strip("_")


def _profile_for(source_name: Optional[str], profile: Optional[str]) -> str:
    if profile:
        candidate = normalize_column_name(profile)
        if candidate in PROFILE_CONFIG:
            return candidate

    source = normalize_column_name(source_name or "")
    if "POLICIA_SEMANAL" in source or source == "SEM_POLICIA":
        return "POLICIA_SEMANAL"
    if "INSPECCION" in source and "RNMC" not in source:
        return "INSPECCIONES"
    if "EVENTOS_GEO" in source:
        return "EVENTOS_GEO"
    return "SEGURIDAD"


def _blank_mask(series: pd.Series) -> pd.Series:
    normalized = series.fillna("").astype(str).map(clean_text)
    return normalized.isin(NULL_TEXT_VALUES)


def _prepare_frame(frame: pd.DataFrame, profile: str) -> pd.DataFrame:
    prepared = frame.copy()
    prepared.columns = [normalize_column_name(column) for column in prepared.columns]
    aliases = PROFILE_CONFIG[profile]["aliases"]

    for canonical, candidates in aliases.items():
        if canonical in prepared.columns:
            continue
        match = next(
            (normalize_column_name(candidate) for candidate in candidates if normalize_column_name(candidate) in prepared.columns),
            None,
        )
        if match:
            prepared.rename(columns={match: canonical}, inplace=True)

    return prepared


def _failed_report(
    filename: str,
    source_name: Optional[str],
    profile: str,
    rule: str,
    field: str = "FILE",
    rows_total: int = 0,
    missing_cols: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "filename": filename,
        "source_name": source_name,
        "profile": profile,
        "rows_total": rows_total,
        "schema_ok": False,
        "missing_cols": missing_cols or [],
        "extra_cols": [],
        "score_overall": 0.0,
        "score_completeness": 0.0,
        "score_validity": 0.0,
        "score_consistency": 0.0,
        "score_uniqueness": 0.0,
        "semaforo": "ROJO",
        "status": "BLOCKED",
        "profiles": {"columns": {}, "top_values": {}, "anual_sum": {}},
        "issues": [{"severity": "ERROR", "field": field, "rule": rule, "count": 1}],
        "samples": {},
        "min_date": None,
        "max_date": None,
    }


def _append_issue(
    issues: List[Dict[str, Any]],
    samples: Dict[str, Any],
    severity: str,
    field: str,
    rule: str,
    mask: Optional[pd.Series] = None,
    count: Optional[int] = None,
    frame: Optional[pd.DataFrame] = None,
    sample_key: Optional[str] = None,
) -> int:
    issue_count = int(mask.sum()) if mask is not None else int(count or 0)
    if issue_count <= 0:
        return 0
    issues.append({"severity": severity, "field": field, "rule": rule, "count": issue_count})
    if sample_key and frame is not None and mask is not None:
        samples[sample_key] = frame.loc[mask].head(10).to_dict(orient="records")
    return issue_count


def _run_frame(
    frame: pd.DataFrame,
    filename: str,
    source_name: Optional[str],
    profile: str,
) -> Dict[str, Any]:
    rows_total = int(len(frame))
    if rows_total == 0:
        return _failed_report(filename, source_name, profile, "El archivo no contiene registros.")

    config = PROFILE_CONFIG[profile]
    prepared = _prepare_frame(frame, profile)
    cols_found = list(prepared.columns)
    required = config["required"]
    missing_cols = [column for column in required if column not in cols_found]
    known_columns = set(config["aliases"].keys())
    extra_cols = [column for column in cols_found if column not in known_columns]

    if missing_cols:
        return _failed_report(
            filename,
            source_name,
            profile,
            "Faltan columnas obligatorias: " + ", ".join(missing_cols),
            field="SCHEMA",
            rows_total=rows_total,
            missing_cols=missing_cols,
        )

    issues: List[Dict[str, Any]] = []
    samples: Dict[str, Any] = {}
    blank_required = pd.DataFrame({column: _blank_mask(prepared[column]) for column in required})
    blank_occurrences = int(blank_required.sum().sum())

    for column in required:
        _append_issue(
            issues,
            samples,
            "ERROR",
            column,
            "Valor obligatorio vacio",
            mask=blank_required[column],
            frame=prepared,
            sample_key=f"missing_{column.lower()}",
        )

    missing_recommended = [column for column in config.get("recommended", []) if column not in cols_found]
    if missing_recommended:
        _append_issue(
            issues,
            samples,
            "WARNING",
            "SCHEMA",
            "No se encontraron columnas recomendadas: " + ", ".join(missing_recommended),
            count=len(missing_recommended),
        )

    date_field = config.get("date_field")
    parsed_dates = None
    if date_field and date_field in prepared.columns:
        parsed_dates = pd.to_datetime(prepared[date_field], errors="coerce")
        invalid_dates = parsed_dates.isna() & ~_blank_mask(prepared[date_field])
        _append_issue(
            issues,
            samples,
            "ERROR",
            date_field,
            "Fecha invalida",
            mask=invalid_dates,
            frame=prepared,
            sample_key="invalid_dates",
        )
        future_dates = parsed_dates > pd.Timestamp.now()
        _append_issue(
            issues,
            samples,
            "ERROR",
            date_field,
            "Fecha futura",
            mask=future_dates.fillna(False),
            frame=prepared,
            sample_key="future_dates",
        )

    quantity_field = config.get("quantity_field")
    if quantity_field:
        if quantity_field not in prepared.columns:
            prepared[quantity_field] = 1
        quantities = pd.to_numeric(prepared[quantity_field], errors="coerce")
        invalid_quantities = quantities.isna() | (quantities <= 0)
        _append_issue(
            issues,
            samples,
            "ERROR",
            quantity_field,
            "Cantidad invalida o menor o igual a cero",
            mask=invalid_quantities,
            frame=prepared,
            sample_key="invalid_quantities",
        )

    territory_outside = 0
    territory_field = config.get("territory_field")
    source_key = normalize_column_name(source_name or "")
    if profile == "REGISTROS_NORMALIZADOS" and any(
        token in source_key for token in ("ASPERSION", "VALLE", "TERRITORIAL")
    ):
        territory_field = None
    if territory_field and territory_field in prepared.columns:
        territory_keys = prepared[territory_field].map(create_key)
        nonblank_territory = ~_blank_mask(prepared[territory_field])
        outside_mask = nonblank_territory & ~territory_keys.str.contains("JAMUNDI", na=False)
        territory_outside = int(outside_mask.sum())
        if territory_outside:
            severity = "ERROR" if territory_outside == rows_total else "WARNING"
            _append_issue(
                issues,
                samples,
                severity,
                territory_field,
                "Registros fuera de Jamundi",
                mask=outside_mask,
                frame=prepared,
                sample_key="outside_jamundi",
            )

    if profile == "POLICIA_SEMANAL":
        weeks = pd.to_numeric(prepared["SEMANA"], errors="coerce")
        invalid_weeks = weeks.isna() | (weeks < 1) | (weeks > 53)
        _append_issue(
            issues,
            samples,
            "ERROR",
            "SEMANA",
            "Semana fuera del rango 1 a 53",
            mask=invalid_weeks,
            frame=prepared,
            sample_key="invalid_weeks",
        )

    if profile == "EVENTOS_GEO":
        latitudes = pd.to_numeric(prepared["LATITUD"], errors="coerce")
        longitudes = pd.to_numeric(prepared["LONGITUD"], errors="coerce")
        invalid_coordinates = latitudes.isna() | longitudes.isna() | ~latitudes.between(-90, 90) | ~longitudes.between(-180, 180)
        _append_issue(
            issues,
            samples,
            "ERROR",
            "COORDENADAS",
            "Coordenadas invalidas o fuera de rango",
            mask=invalid_coordinates,
            frame=prepared,
            sample_key="invalid_coordinates",
        )

    if profile == "INSPECCIONES" and {"FECHA_INICIO", "FECHA_FIN"}.issubset(prepared.columns):
        start_dates = pd.to_datetime(prepared["FECHA_INICIO"], errors="coerce")
        end_dates = pd.to_datetime(prepared["FECHA_FIN"], errors="coerce")
        inverted_dates = start_dates.notna() & end_dates.notna() & (end_dates < start_dates)
        _append_issue(
            issues,
            samples,
            "WARNING",
            "FECHA_FIN",
            "La fecha final es anterior a la fecha inicial",
            mask=inverted_dates,
            frame=prepared,
            sample_key="inverted_date_ranges",
        )

    duplicate_fields = [column for column in config.get("duplicate_fields", []) if column in prepared.columns]
    if duplicate_fields:
        duplicate_mask = prepared.duplicated(subset=duplicate_fields, keep="first")
    else:
        duplicate_mask = prepared.duplicated(keep="first")
    duplicate_count = _append_issue(
        issues,
        samples,
        "WARNING",
        "DUPLICADOS",
        "Filas potencialmente duplicadas",
        mask=duplicate_mask,
        frame=prepared,
        sample_key="exact_duplicates",
    )

    completeness = max(0.0, 1.0 - (blank_occurrences / max(rows_total * len(required), 1)))
    error_count = sum(item["count"] for item in issues if item["severity"] == "ERROR")
    warning_count = sum(item["count"] for item in issues if item["severity"] == "WARNING")
    validity = max(0.0, 1.0 - (error_count / max(rows_total * len(required), 1)))
    uniqueness = max(0.0, 1.0 - (duplicate_count / max(rows_total, 1)))
    consistency = max(0.0, 1.0 - (territory_outside / max(rows_total, 1)))
    overall = (completeness * 0.35) + (validity * 0.35) + (uniqueness * 0.15) + (consistency * 0.15)
    overall = max(0.0, overall - min(0.15, warning_count / max(rows_total * 20, 1)))

    has_errors = any(item["severity"] == "ERROR" for item in issues)
    has_warnings = any(item["severity"] == "WARNING" for item in issues)
    semaforo = "ROJO" if has_errors else ("AMARILLO" if has_warnings else "VERDE")
    status = "BLOCKED" if has_errors else ("REVIEW" if has_warnings else "READY")

    profiles = {
        "columns": {
            column: {
                "dtype": str(prepared[column].dtype),
                "nulls": int(_blank_mask(prepared[column]).sum()),
                "nunique": int(prepared[column].nunique(dropna=True)),
            }
            for column in prepared.columns
        },
        "top_values": {},
        "anual_sum": {},
    }
    for candidate in ("MUNICIPIO", "LOCALIDAD", "BARRIO", "CONDUCTA", "DESCRIPCION_CONDUCTA"):
        if candidate in prepared.columns:
            values = prepared[candidate].map(clean_text)
            profiles["top_values"][candidate] = values[~values.isin(NULL_TEXT_VALUES)].value_counts().head(10).to_dict()

    if parsed_dates is not None and parsed_dates.notna().any():
        years = parsed_dates.dt.year
        if quantity_field and quantity_field in prepared.columns:
            weights = pd.to_numeric(prepared[quantity_field], errors="coerce").fillna(0)
        else:
            weights = pd.Series(1, index=prepared.index)
        annual_frame = pd.DataFrame({"year": years, "value": weights}).dropna(subset=["year"])
        profiles["anual_sum"] = annual_frame.groupby("year")["value"].sum().to_dict()

    report = {
        "filename": filename,
        "source_name": source_name,
        "profile": profile,
        "rows_total": rows_total,
        "schema_ok": True,
        "missing_cols": [],
        "extra_cols": extra_cols,
        "score_overall": float(overall),
        "score_completeness": float(completeness),
        "score_validity": float(validity),
        "score_consistency": float(consistency),
        "score_uniqueness": float(uniqueness),
        "semaforo": semaforo,
        "status": status,
        "profiles": profiles,
        "issues": issues,
        "samples": samples,
        "min_date": parsed_dates.min().isoformat() if parsed_dates is not None and parsed_dates.notna().any() else None,
        "max_date": parsed_dates.max().isoformat() if parsed_dates is not None and parsed_dates.notna().any() else None,
    }
    return make_serializable(report)


def run_dq(
    file_bytes: bytes,
    filename: str,
    source_name: Optional[str] = None,
    profile: Optional[str] = None,
) -> Dict[str, Any]:
    selected_profile = _profile_for(source_name, profile)
    try:
        from services.file_reader import smart_read_file

        frame = smart_read_file(file_bytes)
    except Exception as exc:
        report = _failed_report(
            filename,
            source_name,
            selected_profile,
            f"No fue posible leer el archivo: {exc}",
        )
        report["error"] = str(exc)
        return report
    return _run_frame(frame, filename, source_name, selected_profile)


def run_records_dq(
    records: Iterable[Dict[str, Any]],
    filename: str,
    source_name: Optional[str] = None,
) -> Dict[str, Any]:
    frame = pd.DataFrame(list(records))
    return _run_frame(frame, filename, source_name, "REGISTROS_NORMALIZADOS")


def report_from_findings(
    filename: str,
    source_name: str,
    findings: Iterable[Any],
    rows_total: int,
) -> Dict[str, Any]:
    issues = []
    for finding in findings:
        value = finding if isinstance(finding, dict) else finding.__dict__
        blocks = bool(value.get("blocks_publication"))
        raw_severity = str(value.get("severity") or "LOW").upper()
        severity = "ERROR" if blocks else ("WARNING" if raw_severity in {"HIGH", "MEDIUM"} else "INFO")
        issues.append({
            "severity": severity,
            "field": str(value.get("agent_name") or "AGENTE").upper(),
            "rule": str(value.get("message") or value.get("code") or "Hallazgo automatico")[:255],
            "count": 1,
        })

    error_count = sum(item["count"] for item in issues if item["severity"] == "ERROR")
    warning_count = sum(item["count"] for item in issues if item["severity"] == "WARNING")
    semaforo = "ROJO" if error_count else ("AMARILLO" if warning_count else "VERDE")
    validity = max(0.0, 1.0 - (error_count / max(rows_total, 1)))
    overall = validity if rows_total else (0.0 if error_count else 1.0)
    return {
        "filename": filename,
        "source_name": source_name,
        "profile": "AGENTES_INSTITUCIONALES",
        "rows_total": rows_total,
        "schema_ok": not bool(error_count),
        "missing_cols": [],
        "extra_cols": [],
        "score_overall": overall,
        "score_completeness": 1.0 if rows_total else 0.0,
        "score_validity": validity,
        "score_consistency": 1.0,
        "score_uniqueness": 1.0,
        "semaforo": semaforo,
        "status": "BLOCKED" if error_count else ("REVIEW" if warning_count else "READY"),
        "profiles": {"columns": {}, "top_values": {}, "anual_sum": {}},
        "issues": issues,
        "samples": {},
        "min_date": None,
        "max_date": None,
    }


def build_excel_from_report(report_json: Dict[str, Any]) -> bytes:
    output = io.BytesIO()
    summary = [
        {"Metrica": "Archivo", "Valor": report_json.get("filename")},
        {"Metrica": "Fuente", "Valor": report_json.get("source_name")},
        {"Metrica": "Perfil", "Valor": report_json.get("profile")},
        {"Metrica": "Filas", "Valor": report_json.get("rows_total")},
        {"Metrica": "Semaforo", "Valor": report_json.get("semaforo")},
        {"Metrica": "Calidad general", "Valor": report_json.get("score_overall")},
        {"Metrica": "Completitud", "Valor": report_json.get("score_completeness")},
        {"Metrica": "Validez", "Valor": report_json.get("score_validity")},
        {"Metrica": "Unicidad", "Valor": report_json.get("score_uniqueness")},
        {"Metrica": "Consistencia", "Valor": report_json.get("score_consistency")},
    ]
    issues = report_json.get("issues") or []
    columns = [
        {"Columna": name, **details}
        for name, details in (report_json.get("profiles", {}).get("columns", {}) or {}).items()
    ]
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(summary).to_excel(writer, sheet_name="Resumen", index=False)
        pd.DataFrame(issues or [{"severity": "INFO", "rule": "Sin hallazgos", "count": 0}]).to_excel(
            writer, sheet_name="Hallazgos", index=False
        )
        pd.DataFrame(columns).to_excel(writer, sheet_name="Columnas", index=False)
    return output.getvalue()
