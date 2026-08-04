#!/usr/bin/env python3
"""
Compara dos snapshots de territorios no mapeados y muestra diff (antes vs después).

Ejemplos:
  # 1) Tras dos ejecuciones del pipeline:
  python backend/unmapped_pipeline.py ... --out-json backend/data/unmapped_antes.json
  ... aplicar mejoras ...
  python backend/unmapped_pipeline.py ... --out-json backend/data/unmapped_despues.json
  python backend/compare_unmapped_snapshots.py --before backend/data/unmapped_antes.json --after backend/data/unmapped_despues.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple


def load_names(path: str) -> Tuple[Set[str], List[dict], int]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No existe el archivo: {p}")

    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Formato invalido en {p}, se esperaba lista JSON de unmapped_names")

    names = set()
    for item in data:
        if isinstance(item, dict) and "name" in item:
            names.add(str(item["name"]).strip())
    return names, data, len(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Diff de unmapped entre dos snapshots")
    parser.add_argument("--before", required=True, help="JSON anterior: unmapped_territorios.json")
    parser.add_argument("--after", required=True, help="JSON posterior: unmapped_territorios.json")
    args = parser.parse_args()

    before_names, before_rows, before_count = load_names(args.before)
    after_names, after_rows, after_count = load_names(args.after)

    resolved = sorted(before_names - after_names)
    added = sorted(after_names - before_names)

    print("==== COMPARATIVO UNMAPPED (ANTES vs DESPUÉS) ====")
    print(f"Antes: {before_count}")
    print(f"Después: {after_count}")
    print(f"Resueltos: {len(resolved)}")
    print(f"Nuevos no mapeados: {len(added)}")
    print(f"Delta neto: {- (before_count - after_count)}")

    if resolved:
        print("\n[RESUELTOS] -> desaparecieron de unmapped")
        for name in resolved:
            print(f" - {name}")
    else:
        print("\n[RESUELTOS] Ninguno")

    if added:
        print("\n[NUEVOS] -> aparecieron en unmapped")
        for name in added:
            print(f" + {name}")
    else:
        print("\n[NUEVOS] Ninguno")

    if not resolved and not added:
        print("\nSin cambios de unmapped entre snapshots.")

    print("\nArchivo de detalle opcional:")
    print(f" antes: {Path(args.before).resolve()}")
    print(f" despues: {Path(args.after).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
