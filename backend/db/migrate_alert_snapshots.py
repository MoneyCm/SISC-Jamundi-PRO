from sqlalchemy import create_engine
import os
import sys

# Asegurar que el backend esté en el path (soporta entorno local y Render)
BACKEND_DIR = "/app" if os.path.exists("/app") else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from db.models import SQLALCHEMY_DATABASE_URL, Base
from db.models_alerts import IntelligenceAlertSnapshot


def migrate():
    """
    Migración ligera para asegurar la tabla intelligence_alert_snapshots.
    Usa SQLAlchemy metadata.create_all para evitar dependencias externas de migración.
    """
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

    Base.metadata.create_all(engine, tables=[IntelligenceAlertSnapshot.__table__])
    print("Tabla 'intelligence_alert_snapshots' verificada/creada correctamente.")


if __name__ == "__main__":
    migrate()


