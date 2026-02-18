from sqlalchemy import func
from db.models import SessionLocal, Event

def check_dates():
    db = SessionLocal()
    try:
        min_date = db.query(func.min(Event.occurrence_date)).scalar()
        max_date = db.query(func.max(Event.occurrence_date)).scalar()
        count = db.query(func.count(Event.id)).scalar()
        
        print(f"Total Eventos: {count}")
        print(f"Fecha Mínima: {min_date}")
        print(f"Fecha Máxima: {max_date}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_dates()
