from db.models import engine, Base
from db.models_panic import PanicAlert, PanicEvidence

def init_panic():
    print("Iniciando creación de tablas para Botón de Pánico...")
    try:
        PanicAlert.__table__.create(bind=engine, checkfirst=True)
        PanicEvidence.__table__.create(bind=engine, checkfirst=True)
        print("[OK] Tablas panic_alerts y panic_evidences creadas/verificadas.")
    except Exception as e:
        print(f"[ERROR] Error al crear tablas: {e}")

if __name__ == "__main__":
    init_panic()
