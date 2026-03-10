import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from db.models import create_tables
from db.models_inspecciones import InspeccionExpediente, InspeccionMedida, InspeccionActuacion, InspeccionFinanza

if __name__ == "__main__":
    print("🛠️ Iniciando creación de tablas de Inspecciones...")
    create_tables()
    print("✅ Proceso completado.")
