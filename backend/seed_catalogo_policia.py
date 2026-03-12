from sqlalchemy.orm import Session
from db.models_hechos_seguridad import CatalogoConductaFuente
from db.session import SessionLocal

CONDUCTAS_POLICIA = [
    # HURTO
    ("POLICIA_SEMANAL", "H.PERSONAS", "Hurto a personas", "HURTO"),
    ("POLICIA_SEMANAL", "HURTO A PERSONAS", "Hurto a personas", "HURTO"),
    ("POLICIA_SEMANAL", "H.MOTOS", "Hurto a motocicletas", "HURTO"),
    ("POLICIA_SEMANAL", "H.AUTOMOTORES", "Hurto a automotores", "HURTO"),
    ("POLICIA_SEMANAL", "H.RESIDENCIAS", "Hurto a residencias", "HURTO"),
    ("POLICIA_SEMANAL", "HURTO A RESIDENCIAS", "Hurto a residencias", "HURTO"),
    ("POLICIA_SEMANAL", "H.COMERCIO", "Hurto a comercio", "HURTO"),
    ("POLICIA_SEMANAL", "HURTO A COMERCIO", "Hurto a comercio", "HURTO"),
    
    # LESIONES
    ("POLICIA_SEMANAL", "LESIONES PERSONALES", "Lesiones personales", "LESIONES"),
    ("POLICIA_SEMANAL", "LESIONES", "Lesiones personales", "LESIONES"),
    
    # HOMICIDIO
    ("POLICIA_SEMANAL", "HOMICIDIO", "Homicidio", "HOMICIDIO"),
    
    # VIF / SEXUALES
    ("POLICIA_SEMANAL", "VIOLENCIA INTRAFAMILIAR", "Violencia intrafamiliar", "VIF"),
    ("POLICIA_SEMANAL", "DELITOS SEXUALES", "Delitos sexuales", "SEXUAL"),
    
    # OTROS
    ("POLICIA_SEMANAL", "EXTORSION", "Extorsión", "EXTORSION"),
    ("POLICIA_SEMANAL", "SECUESTRO", "Secuestro", "SECUESTRO"),
]

def seed_catalogo():
    db = SessionLocal()
    try:
        for fuente, raw, est, cat in CONDUCTAS_POLICIA:
            exists = db.query(CatalogoConductaFuente).filter(
                CatalogoConductaFuente.fuente_codigo == fuente,
                CatalogoConductaFuente.valor_fuente == raw
            ).first()
            if not exists:
                c = CatalogoConductaFuente(
                    fuente_codigo=fuente,
                    valor_fuente=raw,
                    valor_estandar=est,
                    categoria_delito=cat
                )
                db.add(c)
        db.commit()
        print("Catálogo de conductas homologadas inicializado correctamente.")
    except Exception as e:
        print(f"Error seeding catalogo: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_catalogo()
