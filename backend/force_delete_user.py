from sqlalchemy import text
from db.models import engine

def force_delete(target_username):
    print(f"Intentando eliminar '{target_username}' con SQL crudo...")
    try:
        with engine.connect() as connection:
            # Opción 1: SQLite/Postgres standard
            result = connection.execute(
                text("DELETE FROM users WHERE username = :u"),
                {"u": target_username}
            )
            connection.commit()
            print(f"Filas afectadas para '{target_username}': {result.rowcount}")
    except Exception as e:
        print(f"Error borrando '{target_username}': {e}")

if __name__ == "__main__":
    force_delete("admi")
    # Para 'admin', solo borrar si NO es el admin_sisc (que es el real)
    # El usuario objetivo fue identificado explicitamente para esta utilidad administrativa.
    # El admin real es 'admin_sisc'.
    # Si existe un usuario 'admin' a secas, debe ser borrado.
    force_delete("admin")
