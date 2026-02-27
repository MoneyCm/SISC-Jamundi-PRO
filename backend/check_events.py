from db.session import SessionLocal
from db.models import Event, EventType
from sqlalchemy import func

def check_homicide_events():
    db = SessionLocal()
    try:
        # Contar eventos por categoría
        stats = db.query(EventType.category, func.count(Event.id)).join(Event).group_by(EventType.category).all()
        
        if not stats:
            print("No hay eventos registrados en la tabla general.")
            return
            
        print("ESTADÍSTICAS GENERALES DE EVENTOS:")
        for category, count in stats:
            print(f"- {category}: {count} registros")
            
    finally:
        db.close()

if __name__ == "__main__":
    check_homicide_events()
