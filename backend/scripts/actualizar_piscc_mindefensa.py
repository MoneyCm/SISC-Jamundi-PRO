"""Actualiza ya (sin esperar la revisión semanal) los indicadores del PISCC que salen de MinDefensa.

Uso (en la carpeta backend):  python scripts/actualizar_piscc_mindefensa.py
La lógica está en services/piscc_mindefensa_sync.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.piscc_mindefensa_sync import actualizar_archivo  # noqa: E402


def main() -> int:
    resultado = actualizar_archivo()
    for nombre, valores in resultado["indicadores"].items():
        print(f"{nombre}: {valores['actual']} (año anterior {valores['anterior']}), corte {valores['ultimo_registro']}")
    print("Cambios: " + ("; ".join(resultado["cambios"]) if resultado["cambios"] else "ninguno"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
