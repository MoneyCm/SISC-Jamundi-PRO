"""Radar Defensoría × SISC.

Contrasta las Alertas Tempranas de la Defensoría del Pueblo (advertencia cualitativa,
registro curado en data/defensoria_sat_jamundi.json) con los hechos registrados por la
Policía en la sábana SIEDCO semanal.

Reglas:
- Un hecho = una identidad (id_fuente/fingerprint). Si varias entregas lo ubican o
  clasifican distinto, gana la entrega más reciente y se prefiere una ubicación asignada
  sobre "PENDIENTE POR ASIGNAR". Los conflictos se reportan como calidad de datos.
- Solo se comparan ventanas equivalentes: 1 de enero al día/mes del corte, en cada año
  con cobertura hasta ese día. Nunca un año en curso contra un año completo.
- El radar no genera alertas operativas ni califica el riesgo: describe si lo advertido
  por la Defensoría aparece en los hechos registrados, y qué no puede medirse.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.geocoding_service import GeocodingService

REGISTRY_PATH = Path(__file__).resolve().parents[1] / "data" / "defensoria_sat_jamundi.json"
RURAL_LAYER = "veredas_jamundi_oficial.geojson"

# Umbrales descriptivos del radar (no son umbrales de alerta operativa).
SIGNAL_MIN_CURRENT = 10
SIGNAL_MIN_INCREASE_PCT = 25.0

CONDUCTA_LABELS = {
    "HOMICIDIO": "Homicidio",
    "HURTO_VEHICULOS": "Hurto de vehículos",
    "HURTO_PERSONAS": "Hurto a personas",
    "LESIONES": "Lesiones personales",
    "HURTO_RESIDENCIAS": "Hurto a residencias",
    "HURTO_COMERCIO": "Hurto a comercio",
}

GROUP_LABELS = {
    "AT": "Territorios advertidos por la Defensoría",
    "SECTOR_AT": "Sectores y corredores asociados a la advertencia",
    "RURAL_NO_AT": "Resto de la zona rural",
    "URBANO": "Zona urbana",
    "SIN_POLIGONO": "Sin territorio oficial asignado",
}


@lru_cache(maxsize=1)
def load_registry() -> Dict[str, Any]:
    with REGISTRY_PATH.open(encoding="utf-8") as registry_file:
        return json.load(registry_file)


SMALL_BASE = 30


def _pct(current: int, previous: int) -> Optional[float]:
    if not previous:
        return None
    return round((current - previous) / previous * 100, 1)


def _window_end(year: int, cutoff: date) -> date:
    day = cutoff.day
    if cutoff.month == 2 and day == 29:
        day = 28
    return date(year, cutoff.month, day)


def _events(db: Session) -> List[Any]:
    """Una fila por hecho: versión de la entrega más reciente."""
    from api.analitica import _canonical_conducta_sql, _canonical_location_sql

    identity = "COALESCE(NULLIF(BTRIM(h.id_fuente), ''), NULLIF(BTRIM(h.fingerprint), ''), h.id::text)"
    location = _canonical_location_sql(
        "COALESCE(NULLIF(BTRIM(h.barrio_normalizado), ''), NULLIF(BTRIM(h.vereda_normalizada), ''), "
        "NULLIF(BTRIM(h.corregimiento), ''), 'SIN DATO')"
    )
    conducta = _canonical_conducta_sql("h.conducta_estandar")
    return db.execute(text(f"""
        WITH ranked AS (
            SELECT {identity} AS identity, h.fecha_evento AS fecha, {conducta} AS conducta, {location} AS lugar,
                   ROW_NUMBER() OVER (
                       PARTITION BY {identity}
                       ORDER BY (UPPER({location}) LIKE '%PENDIENTE%'), r.fecha_fin DESC NULLS LAST,
                                h.fecha_ingesta DESC NULLS LAST
                   ) AS rn
            FROM hechos_seguridad h
            LEFT JOIN ingestion_runs r ON r.id = h.ingestion_id
            WHERE h.fuente_codigo = 'POLICIA_SEMANAL' AND h.fecha_evento IS NOT NULL
        )
        SELECT identity, fecha, conducta, lugar FROM ranked WHERE rn = 1
    """)).fetchall()


def _location_conflicts(db: Session) -> int:
    from api.analitica import _canonical_location_sql

    identity = "COALESCE(NULLIF(BTRIM(id_fuente), ''), NULLIF(BTRIM(fingerprint), ''), id::text)"
    location = _canonical_location_sql(
        "COALESCE(NULLIF(BTRIM(barrio_normalizado), ''), NULLIF(BTRIM(vereda_normalizada), ''), "
        "NULLIF(BTRIM(corregimiento), ''), 'SIN DATO')"
    )
    return int(db.execute(text(f"""
        SELECT COUNT(*) FROM (
            SELECT {identity} FROM hechos_seguridad
            WHERE fuente_codigo = 'POLICIA_SEMANAL'
            GROUP BY 1 HAVING COUNT(DISTINCT {location}) > 1
        ) conflicts
    """)).scalar() or 0)


def _classifier(registry: Dict[str, Any]):
    at_names = {name for alert in registry["alertas"] for name in alert.get("territorios_oficiales", [])}
    sectors = [sector for alert in registry["alertas"] for sector in alert.get("sectores_sisc", [])]
    cache: Dict[str, tuple] = {}

    def classify(place: str) -> tuple:
        if place in cache:
            return cache[place]
        territory = GeocodingService.get_official_territory(place)
        name = territory.get("name") if territory else None
        normalized = GeocodingService.normalize_name(place)
        if name in at_names:
            result = ("AT", name)
        elif territory and territory.get("source") == RURAL_LAYER:
            result = ("RURAL_NO_AT", name)
        elif territory:
            result = ("URBANO", name)
        else:
            sector = next((item for item in sectors if item["patron"] in normalized), None)
            result = ("SECTOR_AT", sector["etiqueta"]) if sector else ("SIN_POLIGONO", place)
        cache[place] = result
        return result

    return classify, sectors


def build_sat_radar(db: Session) -> Dict[str, Any]:
    registry = load_registry()
    events = _events(db)
    if not events:
        return {"status": "SIN_DATOS", "reason": "No hay hechos de la sábana policial cargados.", "alerts": registry["alertas"]}

    cutoff = max(row.fecha for row in events)
    last_by_year: Dict[int, date] = {}
    for row in events:
        last_by_year[row.fecha.year] = max(last_by_year.get(row.fecha.year, row.fecha), row.fecha)

    # Ventanas equivalentes: solo años con cobertura hasta el mismo día del corte.
    windows = []
    for year in sorted(last_by_year):
        end = _window_end(year, cutoff)
        if last_by_year[year] >= end:
            windows.append({"year": year, "start": date(year, 1, 1).isoformat(), "end": end.isoformat()})
    years = [window["year"] for window in windows]
    if len(years) < 2:
        return {"status": "SIN_BASE", "reason": "Se necesitan al menos dos años con cobertura equivalente.",
                "alerts": registry["alertas"], "windows": windows}
    current_year, previous_year = years[-1], years[-2]
    window_by_year = {window["year"]: date.fromisoformat(window["end"]) for window in windows}

    classify, _ = _classifier(registry)
    groups = defaultdict(Counter)
    group_homicides = defaultdict(Counter)
    territory_counts = defaultdict(Counter)
    territory_group: Dict[str, str] = {}
    territory_conducts = defaultdict(Counter)
    conduct_by_group = defaultdict(Counter)
    for row in events:
        year = row.fecha.year
        if year not in window_by_year or row.fecha > window_by_year[year]:
            continue
        group, name = classify(row.lugar)
        groups[group][year] += 1
        if row.conducta == "HOMICIDIO":
            group_homicides[group][year] += 1
        conduct_by_group[(group, year)][row.conducta] += 1
        if group in ("AT", "SECTOR_AT"):
            territory_counts[name][year] += 1
            territory_group[name] = group
            if year == current_year:
                territory_conducts[name][row.conducta] += 1

    def series(counter: Counter) -> Dict[str, int]:
        return {str(year): int(counter.get(year, 0)) for year in years}

    group_rows = []
    for key, label in GROUP_LABELS.items():
        current, previous, first = groups[key][current_year], groups[key][previous_year], groups[key][years[0]]
        group_rows.append({
            "key": key,
            "label": label,
            "series": series(groups[key]),
            "homicides": series(group_homicides[key]),
            "variation_pct": _pct(current, previous),
            "variation_vs_first_pct": _pct(current, first) if years[0] != previous_year else None,
            "homicide_share_pct": round(group_homicides[key][current_year] / current * 100, 1) if current else None,
        })

    territories = []
    for name, counter in territory_counts.items():
        current, previous = counter[current_year], counter[previous_year]
        territories.append({
            "name": name,
            "group": territory_group[name],
            "series": series(counter),
            "variation_pct": _pct(current, previous),
            "top_conductas": [
                {"code": code, "label": CONDUCTA_LABELS.get(code, code.replace("_", " ").title()), "total": total}
                for code, total in territory_conducts[name].most_common(3)
            ],
        })
    territories.sort(key=lambda item: (-item["series"][str(current_year)], item["name"]))

    # Conductas advertidas: cuáles mide la sábana y cómo evolucionan en la zona advertida.
    advised = []
    seen = set()
    for alert in registry["alertas"]:
        for item in alert.get("conductas_advertidas", []):
            code = item.get("codigo_siedco")
            key = code or item["conducta"]
            if key in seen:
                continue
            seen.add(key)
            if code:
                at_series = {
                    str(year): int(conduct_by_group[("AT", year)][code] + conduct_by_group[("SECTOR_AT", year)][code])
                    for year in years
                }
                advised.append({
                    "conducta": item["conducta"], "code": code, "measurable": True,
                    "series_zona_advertida": at_series,
                    "variation_pct": _pct(at_series[str(current_year)], at_series[str(previous_year)]),
                    "series_urbano": series(Counter({year: conduct_by_group[("URBANO", year)][code] for year in years})),
                })
            else:
                advised.append({"conducta": item["conducta"], "code": None, "measurable": False,
                                "fuente_sugerida": item.get("fuente_sugerida")})

    blind_sources = _blind_source_status(db)
    forensic = _forensic_homicides(db)
    signals = _signals(group_rows, territories, advised, current_year, previous_year, years, forensic)

    return {
        "status": "OK",
        "generated_for": {
            "cutoff": cutoff.isoformat(),
            "current_year": current_year,
            "previous_year": previous_year,
            "windows": windows,
            "window_label": f"1 de enero al {cutoff.day} de {_MONTHS[cutoff.month - 1]} de cada año",
        },
        "alerts": registry["alertas"],
        "registry_note": registry.get("nota_metodologica"),
        "registry_verified_on": registry.get("verificado_el"),
        "groups": group_rows,
        "territories": territories,
        "advised_conducts": advised,
        "signals": signals,
        "blind_spots": blind_sources,
        "forensic_homicides": forensic,
        "data_quality": {
            "unique_events": len(events),
            "events_with_conflicting_location": _location_conflicts(db),
            "rule": "Un hecho por identidad; gana la entrega más reciente y una ubicación asignada sobre 'PENDIENTE POR ASIGNAR'.",
        },
        "disclaimer": "Lectura descriptiva. No es una alerta operativa ni una medición del riesgo: la sábana policial solo registra hechos denunciados o conocidos por la Policía.",
    }


_MONTHS = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
           "septiembre", "octubre", "noviembre", "diciembre")


def _fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "sin base comparable"
    return f"{'+' if value > 0 else ''}{_fmt_num(value)}%"


def _signals(groups, territories, advised, current_year, previous_year, years, forensic=None) -> List[Dict[str, Any]]:
    """Hallazgos deterministas, redactados solo a partir de los conteos calculados."""
    by_key = {group["key"]: group for group in groups}
    signals = []
    at, urban, rural = by_key["AT"], by_key["URBANO"], by_key["RURAL_NO_AT"]
    first = str(years[0])
    cur, prev = str(current_year), str(previous_year)

    if at["series"][first] and urban["series"][first]:
        at_change = _pct(at["series"][cur], at["series"][first])
        urban_change = _pct(urban["series"][cur], urban["series"][first])
        rural_change = _pct(rural["series"][cur], rural["series"][first])
        if at_change is not None and urban_change is not None and at_change > urban_change:
            signals.append({
                "kind": "DIVERGENCIA",
                "title": "La zona advertida no sigue la tendencia del municipio",
                "detail": (
                    f"Desde {first}, los hechos en los territorios advertidos cambiaron {_fmt_pct(at_change)} "
                    f"({at['series'][first]} → {at['series'][cur]}), mientras la zona urbana cambió "
                    f"{_fmt_pct(urban_change)} y el resto de la zona rural {_fmt_pct(rural_change)}."
                ),
            })

    if at["homicide_share_pct"] and urban["homicide_share_pct"] and at["homicide_share_pct"] > urban["homicide_share_pct"]:
        ratio = round(at["homicide_share_pct"] / urban["homicide_share_pct"], 1)
        signals.append({
            "kind": "LETALIDAD",
            "title": "Mayor peso del homicidio en la zona advertida",
            "detail": (
                f"En {cur}, el {str(at['homicide_share_pct']).replace('.', ',')}% de los hechos registrados en territorios "
                f"advertidos son homicidios, frente al {str(urban['homicide_share_pct']).replace('.', ',')}% en la zona urbana "
                f"({str(ratio).replace('.', ',')} veces más)."
            ),
        })

    for item in territories:
        current, previous = item["series"][cur], item["series"][prev]
        variation = item["variation_pct"]
        if current >= SIGNAL_MIN_CURRENT and variation is not None and variation >= SIGNAL_MIN_INCREASE_PCT:
            top = item["top_conductas"][0]["label"].lower() if item["top_conductas"] else "hechos"
            signals.append({
                "kind": "AUMENTO_TERRITORIAL",
                # Base pequeña (menos de 30 hechos): la diferencia en casos, no un porcentaje que exagera.
                "title": (f"{item['name']}: {current - previous:+d} hechos frente a {prev}" if previous < SMALL_BASE
                          else f"{item['name']}: {_fmt_pct(variation)} frente a {prev}"),
                "detail": f"{previous} → {current} hechos en la misma ventana; predomina {top}.",
                "territory": item["name"],
            })

    for item in advised:
        if item.get("measurable") and item["code"] == "HURTO_VEHICULOS":
            series = item["series_zona_advertida"]
            if series[cur] >= SIGNAL_MIN_CURRENT:
                urban_series = item["series_urbano"]
                signals.append({
                    "kind": "CONDUCTA_ADVERTIDA",
                    "title": "Se registra la modalidad que advirtió la Defensoría",
                    "detail": (
                        "La AT 005-24 advirtió hurtos de vehículos y bienes para exigir pago por su devolución. "
                        f"En la zona advertida el hurto de vehículos pasó de {series[first]} en {first} a {series[cur]} en {cur} "
                        f"({_fmt_pct(_pct(series[cur], series[first]))}); en la zona urbana, de {urban_series[first]} a "
                        f"{urban_series[cur]} ({_fmt_pct(_pct(urban_series[cur], urban_series[first]))}), en la misma ventana. "
                        "La sábana no indica si hubo exigencia de pago: confirmarlo requiere denuncias de extorsión."
                    ),
                })

    for item in territories:
        homicides = next((c["total"] for c in item["top_conductas"] if c["code"] == "HOMICIDIO"), 0)
        current = item["series"][cur]
        if homicides >= 5 and current and homicides / current >= 0.4:
            signals.append({
                "kind": "HOMICIDIO_CONCENTRADO",
                "title": f"{item['name']}: el homicidio domina los hechos registrados",
                "detail": f"{homicides} de {current} hechos registrados en {cur} son homicidios.",
                "territory": item["name"],
            })

    shift = (forensic or {}).get("urban_shift")
    if (shift and shift["urban_change_pct"] is not None and shift["rural_change_pct"] is not None
            and shift["urban_change_pct"] > shift["rural_change_pct"]):
        signals.append({
            "kind": "DESPLAZAMIENTO_URBANO",
            "title": "La violencia letal creció en la cabecera, no en la zona rural",
            "detail": (
                f"Medicina Legal (fuente independiente de la Policía): el promedio anual de homicidios en la cabecera pasó de "
                f"{_fmt_num(shift['urban_before'])} ({shift['before_label']}) a {_fmt_num(shift['urban_after'])} ({shift['after_label']}), "
                f"{_fmt_pct(shift['urban_change_pct'])}; en la zona rural, de {_fmt_num(shift['rural_before'])} a "
                f"{_fmt_num(shift['rural_after'])} ({_fmt_pct(shift['rural_change_pct'])}). "
                "Es coherente con la expansión hacia la parte plana que advierte la Defensoría."
            ),
        })
    return signals


def _fmt_num(value) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).replace(".", ",")


def _forensic_homicides(db: Session) -> Optional[Dict[str, Any]]:
    """Homicidios de Medicina Legal por zona: serie definitiva y preliminar comparable."""
    zone = ("CASE WHEN zona ILIKE 'Cabecera%' THEN 'CABECERA' "
            "WHEN NULLIF(BTRIM(zona), '') IS NULL THEN 'SIN_DATO' ELSE 'RURAL' END")
    try:
        definitive = db.execute(text(f"""
            SELECT year_hecho AS year, {zone} AS zone, COUNT(*) AS total
            FROM medicina_legal_records
            WHERE dataset_key = 'HOMICIDIOS_DEF' AND codigo_dane_municipio = '76364'
            GROUP BY 1, 2 ORDER BY 1
        """)).fetchall()
        preliminary = db.execute(text(f"""
            SELECT year_hecho AS year, month_hecho AS month, {zone} AS zone,
                   mecanismo_causal AS mechanism, COUNT(*) AS total
            FROM medicina_legal_records
            WHERE dataset_key = 'FATALES_PRE' AND codigo_dane_municipio = '76364'
              AND contexto ILIKE '%homicid%'
            GROUP BY 1, 2, 3, 4
        """)).fetchall()
    except Exception:
        db.rollback()
        return None
    if not definitive and not preliminary:
        return None

    by_year: Dict[int, Counter] = defaultdict(Counter)
    for row in definitive:
        by_year[int(row.year)][row.zone] += int(row.total)
    series = [
        {"year": year, "cabecera": counts["CABECERA"], "rural": counts["RURAL"], "sin_dato": counts["SIN_DATO"],
         "total": sum(counts.values()), "status": "definitivo"}
        for year, counts in sorted(by_year.items())
    ]

    shift = None
    if len(series) >= 6:
        before, after = series[:3], series[-3:]

        def avg(rows, key):
            return round(sum(r[key] for r in rows) / len(rows), 1)

        shift = {
            "before_label": f"{before[0]['year']}-{before[-1]['year']}",
            "after_label": f"{after[0]['year']}-{after[-1]['year']}",
            "urban_before": avg(before, "cabecera"), "urban_after": avg(after, "cabecera"),
            "rural_before": avg(before, "rural"), "rural_after": avg(after, "rural"),
        }
        shift["urban_change_pct"] = _pct(shift["urban_after"], shift["urban_before"])
        shift["rural_change_pct"] = _pct(shift["rural_after"], shift["rural_before"])

    prelim_years = sorted({int(row.year) for row in preliminary})
    comparable = None
    if len(prelim_years) >= 2:
        latest = prelim_years[-1]
        last_month = max(int(row.month) for row in preliminary if int(row.year) == latest)
        totals = defaultdict(Counter)
        for row in preliminary:
            if int(row.month) <= last_month:
                totals[int(row.year)][row.zone] += int(row.total)
        comparable = {
            "months": f"enero a {_MONTHS[last_month - 1]}",
            "status": "preliminar",
            "years": [{"year": year, "cabecera": totals[year]["CABECERA"], "rural": totals[year]["RURAL"],
                       "total": sum(totals[year].values())} for year in prelim_years],
        }
        comparable["variation_pct"] = _pct(comparable["years"][-1]["total"], comparable["years"][-2]["total"])

    explosives = sum(int(row.total) for row in preliminary if "explosiv" in (row.mechanism or "").lower())
    return {
        "source": "Instituto Nacional de Medicina Legal y Ciencias Forenses",
        "definitive_series": series,
        "urban_shift": shift,
        "preliminary_comparable": comparable,
        "explosive_homicides_preliminary": explosives,
        "note": "Las cifras preliminares cambian hasta su consolidación. La zona es la del hecho según el registro forense.",
    }


def _blind_source_status(db: Session) -> List[Dict[str, Any]]:
    """Fuentes que cubrirían las conductas advertidas que la sábana no mide."""
    checks = [
        ("Fiscalía SPOA", "fiscalia_spoa_records", "Denuncias de extorsión, secuestro y desaparición forzada",
         "Módulo instalado; cargar el conjunto de denuncias de Jamundí."),
        ("Medicina Legal", "medicina_legal_records", "Homicidios por zona del hecho (integrado en este radar)", None),
    ]
    result = []
    for label, table, covers, pending_note in checks:
        try:
            total = int(db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0)
        except Exception:
            db.rollback()
            total = None
        # Un puñado de filas de prueba no es cobertura.
        loaded = bool(total and total >= 50)
        item = {"source": label, "covers": covers, "records": total, "loaded": loaded}
        if not loaded and pending_note:
            item["note"] = pending_note
        result.append(item)
    result.append({"source": "Unidad para las Víctimas (RUV)", "covers": "Desplazamiento, confinamiento, reclutamiento",
                   "records": None, "loaded": False, "note": "Sin conector en el SISC."})
    return result
