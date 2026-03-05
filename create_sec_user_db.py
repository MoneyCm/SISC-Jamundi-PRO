import os
from sqlalchemy import create_engine, text
import bcrypt
import uuid

# DATABASE_URL from .env
DATABASE_URL = "postgresql://neondb_owner:npg_ZzBiN3DU6dgc@ep-holy-lake-aiso6dd5-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

engine = create_engine(DATABASE_URL)

def get_password_hash(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

with engine.begin() as conn:
    # 1. Verificar si existe
    user = conn.execute(text("SELECT id FROM users WHERE username = 'sec_seguridad'")).fetchone()
    
    password_hash = get_password_hash("Jamundi2026")
    
    if user:
        # 2. Actualizar si existe
        print(f"DEBUG: Actualizando usuario existente ID: {user.id}")
        conn.execute(text("""
            UPDATE users SET 
                full_name = 'Secretaría de Seguridad y Convivencia - Jamundí',
                email = 'seguridad@jamundi.gov.co',
                password_hash = :password_hash,
                dependency = 'Despacho Secretaría de Seguridad',
                position = 'Secretario(a) de Seguridad',
                data_level_max = 3,
                is_active = true
            WHERE id = :id
        """), {"password_hash": password_hash, "id": user.id})
        user_id = user.id
    else:
        # 3. Crear si no existe
        print("DEBUG: Creando nuevo usuario")
        user_id = uuid.uuid4()
        conn.execute(text("""
            INSERT INTO users (id, username, email, password_hash, full_name, dependency, position, data_level_max, is_active)
            VALUES (:id, 'sec_seguridad', 'seguridad@jamundi.gov.co', :password_hash, 
                    'Secretaría de Seguridad y Convivencia - Jamundí', 'Despacho Secretaría de Seguridad', 
                    'Secretario(a) de Seguridad', 3, true)
        """), {"id": user_id, "password_hash": password_hash})
    
    # 4. Asegurar roles (DIRECTIVE y ANALYST)
    # Primero obtener ids de roles
    roles = conn.execute(text("SELECT id, code FROM roles WHERE code IN ('DIRECTIVE', 'ANALYST')")).fetchall()
    role_ids = [r.id for r in roles]
    
    # Limpiar roles previos para este usuario si se está reseteando
    conn.execute(text("DELETE FROM user_roles WHERE user_id = :user_id"), {"user_id": user_id})
    
    # Insertar roles
    for rid in role_ids:
        conn.execute(text("INSERT INTO user_roles (user_id, role_id) VALUES (:user_id, :role_id)"), 
                    {"user_id": user_id, "role_id": rid})

print("\n--- OPERACIÓN EXITOSA ---")
print("Usuario: sec_seguridad")
print("Password: Jamundi2026")
print("Nivel: N3 (Restringido)")
print("Roles: DIRECTIVE, ANALYST")
print("-------------------------")
