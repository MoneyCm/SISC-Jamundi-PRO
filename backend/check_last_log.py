import sqlalchemy
from sqlalchemy.orm import Session
from db.models import engine
from db.models_intelligence import IngestionLog

with Session(engine) as db:
    log = db.query(IngestionLog).order_by(IngestionLog.id.desc()).first()
    if log:
        print(f"Log ID: {log.id}")
        print(f"Estado: {log.estado}")
        print(f"Detalles: {log.detalles}")
    else:
        print("No logs")
