# Guía de Despliegue en PC Dedicado - Observatorio del Delito 🖥️

Contar con un PC dedicado permite que el **SISC** funcione como un servidor local permanente para la oficina, con mayor control sobre los datos y sin depender de la nube externa.

## 1. Requisitos Previos en el PC
*   **Docker Desktop**: Instalado y corriendo ([Descargar aquí](https://www.docker.com/products/docker-desktop/)).
*   **Git**: Para sincronizar el código.
*   **RAM**: Mínimo 8GB (recomendado 16GB) para que la base de datos y la IA fluyan bien.

## 2. Pasos para la Instalación
1.  **Clonar el repositorio**:
    ```powershell
    git clone https://github.com/MoneyCm/SISC-Jamundi-PRO.git
    cd SISC-Jamundi-PRO
    ```
2.  **Configurar Variables (.env)**:
    Asegúrate de que el archivo `backend/.env` tenga el `AI_PROVIDER` y las llaves (Gemini/Mistral) configuradas. El `DATABASE_URL` debe apuntar a `db:5432` como está en el archivo actual.

3.  **Encender el Sistema**:
    Ejecuta el comando maestro que construye y levanta todo el servidor:
    ```powershell
    docker-compose up --build -d
    ```
    *La bandera `-d` lo deja corriendo en segundo plano como un servicio.*

## 4. Acceso en la Oficina (Red Local)
Una vez encendido, cualquier PC en la misma red WiFi podrá entrar:
*   **Frontend**: `http://[IP-DEL-PC]:5173`
*   **Backend**: `http://[IP-DEL-PC]:8000`

## 5. Acceso desde la WEB (Túneles)
Si necesitas que el Secretario de Seguridad vea el dashboard desde su celular fuera de la oficina, usa estas opciones:

### Opción A: Ngrok (Demos Rápidas)
1. Descarga Ngrok y en una terminal ejecuta:
   ```bash
   ngrok http 5173
   ```
2. Te dará una URL pública (ej. `https://abc-123.ngrok.io`). Ábrela en el celular y ¡listo!

### Opción B: Cloudflare Tunnel (Permanente y Profesional)
Es la opción de "blindaje" para 2026. Permite asociar el PC a un dominio oficial (ej. `datos.jamundi.gov.co`) sin abrir puertos.

## 6. Ventajas del PC Dedicado + Túnel:
*   **Soberanía**: Los datos no salen del PC de la oficina.
*   **Ahorro**: No pagas servidores costosos en la nube.
*   **Control**: Tú decides cuándo encender o apagar el acceso web.

## 5. Mantenimiento Diario
Para asegurar la "disponibilidad operativa" que pusimos en tus compromisos:
*   **Script de Inicio**: Podemos configurar Docker para que el SISC se encienda automáticamente apenas prendas el computador.
*   **Backups**: Simplemente copiar la carpeta del proyecto a un disco externo una vez al mes asegura toda la trazabilidad.

---

### ¿Quieres que configuremos el script de auto-encendido para ese PC?
Si lo dejas así, el SISC se comportará como un servidor profesional de la Alcaldía.
