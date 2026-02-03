# Guía de Ejecución en la Nube (GitHub Codespaces) ☁️

Esta configuración permite que **SISC Jamundí** funcione en cualquier PC sin instalar Docker ni Python localmente.

### Pasos para iniciar:

1.  **Subir el código a GitHub**:
    Asegúrate de que esta carpeta sea un repositorio en tu cuenta de GitHub.

2.  **Abrir Codespaces**:
    - En GitHub, haz clic en el botón verde **"<> Code"**.
    - Ve a la pestaña **"Codespaces"**.
    - Haz clic en **"Create codespace on main"**.

3.  **Preparación Automática**:
    GitHub levantará una máquina potente en la nube. Yo he configurado el sistema para que automáticamente:
    - Instale todas las dependencias.
    - Levante la base de datos PostgreSQL/PostGIS.
    - Ejecute la semilla de datos (`seed_data.py`).

4.  **Acceder al Sistema**:
    Una vez que termine de cargar (verás una terminal que dice `npm install` terminado):
    - **Frontend**: Te aparecerá un mensaje flotante para "Open in Browser" en el puerto **5173** (o 3000).
    - **IMPORTANTE (Visibilidad del Puerto)**: Para que el sistema funcione, ve a la pestaña **"Ports"** abajo (al lado de la terminal), busca el puerto **8000**, haz clic derecho y selecciona **Port Visibility > Public**. Sin esto, la aplicación no podrá leer los datos.

### Qué hacer si sale "Error al cargar":
1.  Verifica que el **Backend** esté corriendo en una terminal (`python backend/main.py`).
2.  Asegúrate de haber hecho `git pull origin main` en la terminal para tener los últimos arreglos.
3.  Confirma que el puerto **8000** esté en modo **Public**.

### Ventajas:
- **Gratis**: Incluido en las horas gratuitas de GitHub.
- **Sin Instalación**: Útil para presentaciones en computadores ajenos.
- **Colaborativo**: Puedes compartir el link del puerto 3000 con otros para que vean tu avance en tiempo real.
