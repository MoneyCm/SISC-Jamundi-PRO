from sqlalchemy import create_engine, text
import os
import sys

# Asegurar que el backend esté en el path
BACKEND_DIR = "/app" if os.path.exists("/app") else os.path.join(os.getcwd(), "backend")
sys.path.append(BACKEND_DIR)

from db.models import SQLALCHEMY_DATABASE_URL
from db.models_intelligence import Base

def migrate():
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    # 1. Crear tablas si no existen
    print("Sincronizando modelos con la base de datos...")
    Base.metadata.create_all(engine)
    print("- Tablas creadas/verificadas.")

    # 2. Limpiar columnas obsoletas si existen (refinamiento del modelo)
    with engine.connect() as conn:
        for col in ["estado", "fecha_estado"]:
            try:
                conn.execute(text(f"ALTER TABLE rnmc_status_history DROP COLUMN {col};"))
                conn.commit()
                print(f"- Columna obsoleta 'rnmc_status_history.{col}' eliminada.")
            except Exception:
                pass # Ya no existía

    # 2. Definir columnas adicionales por tabla
    tables_to_ensure = {
        "report_runs": [
            ("report_name", "VARCHAR(255)"),
            ("pdf_generated_at", "TIMESTAMP"),
            ("pdf_path", "VARCHAR(512)"),
            ("pdf_sha256", "VARCHAR(64)"),
            ("download_count", "INTEGER DEFAULT 0")
        ],
        "rnmc_status_history": [
            ("source_id", "VARCHAR(50)"),
            ("event_fingerprint", "VARCHAR(64)"),
            ("estado_anterior", "VARCHAR(100)"),
            ("estado_nuevo", "VARCHAR(100)"),
            ("fecha_reportada", "TIMESTAMP"),
            ("changed_at", "TIMESTAMP")
        ]
    }
    
    for table_name, columns in tables_to_ensure.items():
        print(f"\nVerificando coumnas en '{table_name}'...")
        for col_name, col_type in columns:
            try:
                # Cada columna en su propia mini-transacción para no abortar el bloque
                with engine.connect() as conn:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type};"))
                    conn.commit()
                    print(f"- Columna '{col_name}' añadida.")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e).lower():
                    # Si ya existe, asegurar que el tipo sea correcto (para String(64))
                    try:
                        with engine.connect() as conn:
                            conn.execute(text(f"ALTER TABLE {table_name} ALTER COLUMN {col_name} TYPE {col_type};"))
                            conn.commit()
                            print(f"- Columna '{col_name}' verificada/actualizada.")
                    except Exception:
                        pass
                else:
                    print(f"- Error añadiendo '{col_name}': {e}")
    
    # Agregar Índice a history
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE INDEX idx_rnmc_hist_source_fp ON rnmc_status_history (source_id, event_fingerprint);"))
            conn.commit()
            print("- Índice idx_rnmc_hist_source_fp creado.")
    except Exception as e:
        if "already exists" in str(e):
             print("- Índice idx_rnmc_hist_source_fp ya existía.")
        else:
             print(f"- Error creando índice: {e}")
    
    print("\n¡Migración RNMC completada!")

if __name__ == "__main__":
    migrate()
