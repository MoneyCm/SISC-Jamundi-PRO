
import subprocess
import os
import sys

# DATABASE_URL from .env or provided
db_url = "postgresql://neondb_owner:npg_ZzBiN3DU6dgc@ep-holy-lake-aiso6dd5-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
os.environ["DATABASE_URL"] = db_url
os.environ["PYTHONIOENCODING"] = "utf-8"

backend_dir = os.path.join(os.getcwd(), 'backend')
log_file = os.path.join(backend_dir, 'server.log')

print(f"Iniciando servidor y guardando logs en: {log_file}")

with open(log_file, "w") as f:
    process = subprocess.Popen(
        ["py", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd=backend_dir,
        stdout=f,
        stderr=subprocess.STDOUT
    )
    print(f"Servidor iniciado con PID: {process.pid}")
