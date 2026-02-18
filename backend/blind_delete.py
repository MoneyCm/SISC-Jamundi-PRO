from sqlalchemy.orm import Session
from db.models import SessionLocal, User

def blind_delete(target_username):
    db = SessionLocal()
    try:
        print(f"Intentando delete ciego de '{target_username}'...")
        # synchronize_session=False evita que SQLAlchemy intente leer/actualizar objetos en memoria
        # Esto genera un DELETE directo en SQL
        
        # Opcion A: Filter y Delete directo
        num_deleted = db.query(User).filter(User.username == target_username).delete(synchronize_session=False)
        
        db.commit()
        print(f"Eliminado(s): {num_deleted}")
            
    except Exception as e:
        print(f"Error borrando '{target_username}': {e}")
    finally:
        db.close()

if __name__ == "__main__":
    blind_delete("admi")
    blind_delete("admin")
