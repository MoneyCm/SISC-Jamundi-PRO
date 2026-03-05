from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://neondb_owner:npg_ZzBiN3DU6dgc@ep-holy-lake-aiso6dd5-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("--- ROLES DEL ADMIN SISC ---")
    query = "SELECT username, roles FROM users WHERE username = 'admin-sisc' OR username = 'admin_sisc' OR username = 'admin'"
    res = conn.execute(text(query)).fetchall()
    for r in res:
        print(f"User: {r[0]} | Roles: {r[1]}")
