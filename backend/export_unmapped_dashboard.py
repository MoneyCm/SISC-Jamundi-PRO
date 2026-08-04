#!/usr/bin/env python3
"""
Exporta territorios no mapeados desde el endpoint de dashboard público.

Uso:
  python backend/export_unmapped_dashboard.py \
    --base-url http://127.0.0.1:8000 \
    --min-location-count 1 \
    --out-csv backend/data/unmapped_territorios.csv \
    --out-json backend/data/unmapped_territorios.json
"""

from __future__ import annotations

import argparse
import csv
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import List


def fetch_dashboard(url: str, min_location_count: int) -> dict:
    endpoint = f"{url.rstrip('/')}/api/analitica/public/dashboard?min_location_count={int(min_location_count)}"
    request = urllib.request.Request(endpoint, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status} desde {endpoint}")
        return json.loads(response.read().decode("utf-8"))


def write_csv(path: Path, names: List[dict]):
    if not names:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "total"])
        writer.writeheader()
        writer.writerows(names)


def main() -> int:
    parser = argparse.ArgumentParser(description="Exportar territorios no mapeados desde dashboard")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="URL base del backend")
    parser.add_argument("--min-location-count", type=int, default=1, help="min_location_count usado en endpoint")
    parser.add_argument("--out-json", default="backend/data/unmapped_territorios.json")
    parser.add_argument("--out-csv", default="backend/data/unmapped_territorios.csv")
    args = parser.parse_args()

    if args.min_location_count < 1:
        raise SystemExit("min-location-count debe ser >= 1")

    try:
        data = fetch_dashboard(args.base_url, args.min_location_count)
    except urllib.error.URLError as exc:
        raise SystemExit(f"No fue posible conectar con {args.base_url}: {exc}")

    map_data = data.get("map") or {}
    unmapped = map_data.get("unmapped_names") or []

    print(f"territorios no mapeados: {len(unmapped)}")
    print(f"suprimidos por baja frecuencia: {map_data.get('suppressed_count', 0)}")
    print(f"umbral usado: {map_data.get('min_location_count', args.min_location_count)}")

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(unmapped, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    write_csv(out_csv, unmapped)

    print(f"JSON: {out_json}")
    print(f"CSV: {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

