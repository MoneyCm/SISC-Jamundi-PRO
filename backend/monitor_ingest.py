from db.models import engine
from db.models_intelligence import IngestionLog
from sqlalchemy.orm import Session
import time

print("Monitoring IngestionLog for 30 seconds...")
with Session(engine) as db:
    for i in range(30):
        log = db.query(IngestionLog).order_by(IngestionLog.id.desc()).first()
        if log:
            print(f"Log ID: {log.id}, Estado: {log.estado}, Detalles: {log.detalles}")
        else:
            print("No logs")
        time.sleep(1)
