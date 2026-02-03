import os
import sys

# Añadir el directorio actual al path para que las importaciones funcionen
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from sqlalchemy import func
from db.models import SessionLocal, Event, EventType, Role, User
from core.security import get_password_hash
from datetime import date, time
import uuid

def seed():
    db = SessionLocal()
    try:
        # 1. Asegurarse de que existan los roles
        roles_data = [
            {"name": "Admin SISC", "description": "Administrador total del sistema"},
            {"name": "Analista Observatorio", "description": "Usuario técnico para análisis y boletines"},
            {"name": "Cargador de Datos", "description": "Enlace para subida de archivos"},
            {"name": "Consulta Interna", "description": "Visualización de tableros directivos"},
            {"name": "Público", "description": "Acceso limitado a datos agregados"}
        ]
        
        for r_data in roles_data:
            role = db.query(Role).filter(Role.name == r_data["name"]).first()
            if not role:
                role = Role(name=r_data["name"], description=r_data["description"])
                db.add(role)
        
        db.commit()
        admin_role = db.query(Role).filter(Role.name == "Admin SISC").first()

        # 2. Crear usuario admin por defecto si no existe
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            admin_user = User(
                username="admin",
                email="admin@jamundi.gov.co",
                password_hash=get_password_hash("admin123"),
                role_id=admin_role.id,
                is_active=True
            )
            db.add(admin_user)
            print("Usuario administrador creado.")

        # 3. Asegurarse de que existan los tipos de eventos básicos
        homicidio = db.query(EventType).filter(EventType.category == "HOMICIDIO").first()
        if not homicidio:
            homicidio = EventType(category="HOMICIDIO", subcategory="DOLOSO", is_delicto=True)
            db.add(homicidio)
            db.commit()
            db.refresh(homicidio)
        
        # 4. Insertar algunos eventos de prueba para el año 2024
        # (Solo si no hay eventos previos para no duplicar en cada corrida)
        if db.query(Event).count() == 0:
            eventos_prueba = [
                {"date": date(2024, 1, 15), "time": time(22, 30), "ext_id": "POL-001", "geom": "POINT(-76.538 3.262)"},
                {"date": date(2024, 2, 20), "time": time(14, 00), "ext_id": "POL-002", "geom": "POINT(-76.545 3.255)"},
                {"date": date(2024, 3, 5), "time": time(3, 15), "ext_id": "POL-003", "geom": "POINT(-76.525 3.270)"}
            ]
            
            for ep in eventos_prueba:
                ev = Event(
                    occurrence_date=ep["date"],
                    occurrence_time=ep["time"],
                    event_type_id=homicidio.id,
                    external_id=ep["ext_id"]
                )
                db.add(ev)
                db.flush()
                db.execute(
                    func.text("UPDATE events SET location_geom = ST_GeomFromText(:wkt, 4326) WHERE id = :id"),
                    {"wkt": ep["geom"], "id": ev.id}
                )
        
        db.commit()
        print("¡Semilla de datos (roles, usuarios, eventos) completada con éxito!")
        
    except Exception as e:
        print(f"Error insertando datos: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed()
