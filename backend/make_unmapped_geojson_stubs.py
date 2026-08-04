#!/usr/bin/env python3
"""
Genera una plantilla GeoJSON tipo stubs para territorios no mapeados.
Sirve para capturar los nombres en el mismo esquema esperado por el sistema.

Ejemplos:
  python backend/make_unmapped_geojson_stubs.py \
    --source backend/data/unmapped_territorios.csv --source-column name \
    --out backend/data/barrios_jamundi_valle_extra.geojson \
    --center-lat 3.2606 --center-lng -76.5364 --step 0.0015
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def read_names(path: Path, column: str | None) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"No existe: {path}")
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return []
    if column is None:
        column = list(rows[0].keys())[0]

    names = []
    for row in rows:
        raw = (row.get(column) or "").strip()
        if raw:
            names.append(raw)
    return names


def make_square(center_lat: float, center_lng: float, step: float):
    return [
        [
            [
                [center_lng - step, center_lat - step],
                [center_lng + step, center_lat - step],
                [center_lng + step, center_lat + step],
                [center_lng - step, center_lat + step],
                [center_lng - step, center_lat - step],
            ]
        ]
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Crear plantilla de stubs GeoJSON para territorios no mapeados")
    parser.add_argument("--source", required=True, help="CSV con nombres no mapeados")
    parser.add_argument("--source-column", default=None, help="Columna del CSV con el nombre")
    parser.add_argument("--out", default="backend/data/barrios_jamundi_valle_extra.geojson")
    parser.add_argument("--center-lat", type=float, default=3.2606)
    parser.add_argument("--center-lng", type=float, default=-76.5364)
    parser.add_argument("--step", type=float, default=0.0015)
    parser.add_argument("--skip-dupes", action="store_true", help="Omitir nombres repetidos")
    args = parser.parse_args()

    names = read_names(Path(args.source), args.source_column)
    if not names:
        print("No hay nombres en la fuente.")
        return 0

    features = []
    seen = set()
    lat = args.center_lat
    lng = args.center_lng

    for idx, name in enumerate(names):
        if args.skip_dupes and name in seen:
            continue
        seen.add(name)
        offset = (idx * args.step * 2)
        ring = make_square(lat + (idx % 12) * (args.step * 0.35), lng + offset, args.step)
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "Nombre": name,
                    "fuente": "Stub pendiente validación",
                    "estado": "placeholder",
                    "orden": idx + 1,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": ring,
                },
            }
        )

    out = {
        "type": "FeatureCollection",
        "features": features,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generado {len(features)} stubs en: {out_path}")
    print("Reemplaza geometrías con el polígono real antes de activar en producción.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
