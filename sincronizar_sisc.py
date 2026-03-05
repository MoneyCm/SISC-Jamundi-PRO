import requests, os
from pathlib import Path

# Configuración
API_URL = "https://sisc-backend.onrender.com"
USERNAME = "admin_sisc"
PASSWORD = "Jamundi2026"

DIR_MINDEFENSA = Path(r"C:\Proyectos\monitor-mindefensa")
DIR_POLICIA = Path(r"C:\Proyectos\monitor-policia\policia_xlsx")

def sincronizar_todo():
    print("🚀 INICIANDO SUPER-SINCRONIZACIÓN SISC (MINDEFENSA + POLICÍA)")
    
    # 1. Login
    try:
        r_auth = requests.post(f"{API_URL}/api/auth/login", data={"username": USERNAME, "password": PASSWORD})
        if r_auth.status_code != 200: return print("❌ Error de Autenticación")
        token = r_auth.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("✅ Conexión con SISC PRO establecida.")
    except: return print("❌ No se pudo conectar con el servidor.")

    # 2. Sincronizar Mindefensa
    print("\n📂 CARGANDO DATOS MINDEFENSA...")
    archivos_md = list(DIR_MINDEFENSA.glob("*.xlsx"))
    for path in archivos_md:
        # Detectar el código simplificado del nombre del archivo
        name = path.name.upper()
        code = name.replace(".XLSX", "").replace(" ", "_")
        print(f"  ⬆️ {path.name}...", end="", flush=True)
        with open(path, "rb") as f:
            r = requests.post(f"{API_URL}/api/ingesta/gate/{code.lower()}?force=true", headers=headers, files={"file": f})
            print(" ✅ OK" if r.status_code == 200 else f" ❌ Salto/Error ({r.status_code})")

    # 3. Sincronizar Policía
    print("\n📂 CARGANDO DATOS POLICÍA (SIEDCO)...")
    if DIR_POLICIA.exists():
        archivos_pol = list(DIR_POLICIA.glob("*.xlsx"))
        for path in archivos_pol:
            print(f"  ⬆️ {path.name}...", end="", flush=True)
            with open(path, "rb") as f:
                # El Gate Universal también procesa Policía si las columnas coinciden
                r = requests.post(f"{API_URL}/api/ingesta/gate/policia_general?force=true", headers=headers, files={"file": f})
                print(" ✅ OK" if r.status_code == 200 else f" ❌ Salto/Error ({r.status_code})")
    else:
        print("  ⚠️ Carpeta de Policía no encontrada.")

    print("\n" + "="*60 + "\n✨ TODA LA INTELIGENCIA HA SIDO SINCRONIZADA\n" + "="*60)

if __name__ == "__main__":
    sincronizar_todo()
