"""Reclasifica hechos guardados como "Delito General" cuya conducta original
ahora si se reconoce (p. ej. H.PERSONAS, H.MOTOS, H.AUTOMOTORES).

Uso (dentro del contenedor del backend):
    python scripts/rehomologar_delito_general.py          # solo muestra el resumen
    python scripts/rehomologar_delito_general.py --aplicar
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.session import SessionLocal  # noqa: E402
from db.models_hechos_seguridad import HechoSeguridad  # noqa: E402
from services.conducta_homologation import homologar_conducta_policia  # noqa: E402


def main(aplicar: bool) -> None:
    db = SessionLocal()
    try:
        hechos = db.query(HechoSeguridad).filter(
            HechoSeguridad.conducta_estandar.in_(["Delito General", "DELITO GENERAL"])
        ).all()
        cambios = Counter()
        sin_cambio = Counter()
        for h in hechos:
            nueva, categoria, matched = homologar_conducta_policia(h.conducta_original)
            if matched:
                cambios[(h.conducta_original, nueva)] += 1
                if aplicar:
                    h.conducta_estandar = nueva
                    h.categoria_delito = categoria
            else:
                sin_cambio[h.conducta_original] += 1
        for (orig, nueva), n in cambios.most_common():
            print(f"{n:6d}  {orig!s:40.40} -> {nueva}")
        print(f"\nReclasificables: {sum(cambios.values())}. Siguen como Delito General: {sum(sin_cambio.values())}")
        for orig, n in sin_cambio.most_common(15):
            print(f"        {n:6d}  {orig}")
        if aplicar:
            db.commit()
            print("\nCambios guardados.")
        else:
            print("\nModo revision: no se guardo nada. Usa --aplicar para guardar.")
    finally:
        db.close()


if __name__ == "__main__":
    main("--aplicar" in sys.argv)
