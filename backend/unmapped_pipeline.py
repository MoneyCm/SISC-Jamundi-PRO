#!/usr/bin/env python3
"""
Orquestador para depurar territorios no mapeados del mapa ciudadano.

Flujo:
1) Consulta /analitica/public/dashboard
2) Extrae map.unmapped_names
3) (opcional) sugiere aliases con similitud
4) (opcional) genera stubs GeoJSON para completar polígonos
"""

from __future__ import annotations

import argparse
import csv
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path
from typing import Dict, List, Set, Tuple
import unicodedata


def normalize_name(value: str) -> str:
    if not value:
        return ""
    normalized = "".join(
        char for char in unicodedata.normalize("NFD", str(value))
        if not unicodedata.combining(char)
    )
    return " ".join(normalized.upper().strip().split())


def fetch_dashboard(base_url: str, min_location_count: int) -> Dict:
    endpoint = f"{base_url.rstrip('/')}/api/analitica/public/dashboard?min_location_count={int(min_location_count)}"
    request = urllib.request.Request(endpoint, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status} desde {endpoint}")
        return json.loads(response.read().decode("utf-8"))


def write_csv(path: Path, unmapped: List[Dict[str, int]]) -> None:
    if not unmapped:
        path.write_text("\n", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "total"])
        writer.writeheader()
        writer.writerows(unmapped)


def load_geojson_names(paths: List[str]) -> Set[str]:
    names: Set[str] = set()
    for path_text in paths:
        p = Path(path_text)
        if not p.exists():
            continue
        with p.open(encoding="utf-8") as f:
            raw = json.load(f)
        for feature in raw.get("features", []):
            props = feature.get("properties") or {}
            if not isinstance(props, dict):
                continue
            name = props.get("Nombre") or props.get("name") or props.get("NOMBRE")
            if name:
                names.add(normalize_name(name))
    return names


def build_alias_suggestions(unmapped: List[Dict[str, int]], official_names: Set[str]) -> Dict[str, str]:
    official_list = sorted(official_names)
    suggestions: Dict[str, str] = {}
    for item in unmapped:
        name = item.get("name")
        if not name:
            continue
        key = normalize_name(name)
        close = get_close_matches(key, official_list, n=1, cutoff=0.72)
        if close:
            suggestions[key] = close[0]
    return suggestions


def square_polygon(lat: float, lng: float, step: float) -> List[list]:
    return [
        [
            [lng - step, lat - step],
            [lng + step, lat - step],
            [lng + step, lat + step],
            [lng - step, lat + step],
            [lng - step, lat - step],
        ]
    ]


def make_stubs(unmapped: List[Dict[str, int]], out: Path, center_lat: float, center_lng: float, step: float, skip_dupes: bool) -> int:
    features = []
    seen = set()
    for idx, item in enumerate(unmapped):
        name = item.get("name", "").strip()
        if not name:
            continue
        if skip_dupes and name in seen:
            continue
        seen.add(name)

        base_lat = center_lat + (idx % 12) * (step * 0.35)
        base_lng = center_lng + (idx // 12) * (step * 0.45)

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "Nombre": name,
                    "fuente": "Stub pendiente verificacion",
                    "estado": "placeholder",
                    "total": item.get("total", 0),
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": square_polygon(base_lat, base_lng, step),
                },
            }
        )

    geo = {
        "type": "FeatureCollection",
        "features": features,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(geo, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(features)


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline único de territorios no mapeados")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--min-location-count", type=int, default=1)
    parser.add_argument("--out-json", default="backend/data/unmapped_territorios.json")
    parser.add_argument("--out-csv", default="backend/data/unmapped_territorios.csv")
    parser.add_argument("--geojson", nargs="+", default=["backend/data/barrios_jamundi_valle.geojson", "backend/data/barrios_jamundi_valle_extra.geojson"], help="GeoJSON base y extra")
    parser.add_argument("--aliases-out", default="backend/data/barrios_official_aliases_autogenerated.json")
    parser.add_argument("--stubs-out", default="backend/data/barrios_jamundi_valle_extra.geojson")
    parser.add_argument("--center-lat", type=float, default=3.2606)
    parser.add_argument("--center-lng", type=float, default=-76.5364)
    parser.add_argument("--step", type=float, default=0.0015)
    parser.add_argument("--skip-dupes", action="store_true", default=True)
    parser.add_argument("--no-stubs", action="store_true", help="No generar stubs GeoJSON")
    parser.add_argument("--no-alias", action="store_true", help="No generar aliases sugeridos")
    args = parser.parse_args()

    if args.min_location_count < 1:
        raise SystemExit("--min-location-count debe ser >= 1")

    try:
        payload = fetch_dashboard(args.base_url, args.min_location_count)
    except urllib.error.URLError as exc:
        raise SystemExit(f"No se pudo consultar backend: {exc}")

    map_data = payload.get("map") or {}
    unmapped = map_data.get("unmapped_names") or []
    print(f"Unmapped: {len(unmapped)}")
    print(f"Suppressed: {map_data.get('suppressed_count', 0)}")
    print(f"Min aplicado: {map_data.get('min_location_count', args.min_location_count)}")

    out_json = Path(args.out_json)
    out_csv = Path(args.out_csv)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(unmapped, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    write_csv(out_csv, unmapped)
    print(f"Guardado: {out_json}")
    print(f"Guardado: {out_csv}")

    official_names = load_geojson_names(args.geojson)
    if official_names and not args.no_alias:
        suggestions = build_alias_suggestions(unmapped, official_names)
        alias_out = Path(args.aliases_out)
        alias_out.parent.mkdir(parents=True, exist_ok=True)
        alias_out.write_text(
            json.dumps(suggestions, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(f"Aliases sugeridos: {alias_out}")
    elif not official_names:
        print("No se cargaron nombres oficiales desde los geojson indicados; se omite generación de aliases.")

    if not args.no_stubs:
        stubs_out = Path(args.stubs_out)
        created = make_stubs(
            unmapped,
            stubs_out,
            center_lat=args.center_lat,
            center_lng=args.center_lng,
            step=args.step,
            skip_dupes=args.skip_dupes,
        )
        print(f"Stubs creados: {created} -> {stubs_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

