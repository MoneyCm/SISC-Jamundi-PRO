# Guía: Cómo usar un Dominio Personalizado (ej: www.siscjamundi.com)

El enlace que termina en `.trycloudflare.com` es un "Túnel Rápido" temporal y aleatorio. Para tener una dirección profesional y permanente, sigue estos pasos:

## 1. Requisitos
*   **Comprar un dominio**: Necesitas registrar el nombre (ej: `siscjamundi.com`) en un registrador (como GoDaddy, Namecheap o el mismo Cloudflare).
*   **Cuenta de Cloudflare (Gratis)**: Crea una cuenta en [cloudflare.com](https://www.cloudflare.com/).

## 2. Configuración en la Nube
1.  **Añade tu sitio**: En el panel de Cloudflare, añade el dominio que compraste y cambia los DNS según sus instrucciones.
2.  **Activa Zero Trust**: Ve a la sección "Zero Trust" (es gratuita para hasta 50 usuarios).
3.  **Crea un Túnel**:
    *   Ve a `Networks` -> `Tunnels`.
    *   Haz clic en `Create a Tunnel`.
    *   Ponle un nombre (ej: "SISC-Servidor-Local").
4.  **Obtén el Token**: El panel te dará un comando con una clave larga (Token). **No la compartas**.

## 3. Configuración en tu PC
En lugar de usar el script `EXPOSE_WEB.bat` actual, usaremos uno nuevo que use tu **Token**:

```batch
:: Nuevo comando para el túnel permanente
.\cloudflared.exe tunnel run --token TU_TOKEN_AQUI
```

## 4. Vincular el Dominio
1.  En el panel de Cloudflare (Tunnels), ve a la pestaña `Public Hostname`.
2.  Haz clic en `Add a public hostname`.
3.  Configura:
    *   **Subdomain**: (puedes dejarlo vacío para el dominio principal o poner `www`).
    *   **Domain**: Selecciona `siscjamundi.com`.
    *   **Service Type**: `HTTP`.
    *   **URL**: `localhost:5173`.

---

> [!TIP]
> **Ventajas de este método**:
> *   La dirección NUNCA cambia.
> *   Puedes añadir una capa de seguridad para que solo personas autorizadas (con su email) puedan entrar.
> *   Es mucho más rápido y confiable.

Si decides comprar el dominio, avísame y te ayudaré a configurar el nuevo script con tu Token.

## 5. Caso Especial: Usar un Subdominio de la Alcaldía (ej: sisc.jamundi.gov.co)

Si la Alcaldía ya tiene un dominio (`jamundi.gov.co`), no necesitas comprar uno nuevo. Puedes pedirle al equipo de sistemas que te cree un **Subdominio**.

### Opción A: Si la Alcaldía usa Cloudflare (Recomendado)
Es el método más sencillo. 
1. Pide al encargado que cree un túnel en su panel y te dé el **Token**.
2. Tú usas ese Token en tu PC.
3. El sistema queda visible bajo `sisc.jamundi.gov.co`.

### Opción B: Si la Alcaldía usa otro proveedor (GoDaddy, etc.)
Aunque ellos no tengan Cloudflare, el sistema funcionará igual:
1. Tú creas tu propia cuenta gratuita de Cloudflare.
2. Cloudflare te dará un nombre técnico para tu túnel (ej: `tu-id.cfargotunnel.com`).
3. Le pides al encargado de la Alcaldía: *"Por favor, crea un registro **CNAME** para `sisc.jamundi.gov.co` que apunte a `tu-id.cfargotunnel.com`"*.
4. **¡Listo!** El tráfico llega a tu PC de forma segura, pasando por Cloudflare hacia su proveedor.

### ¿Qué beneficios tiene esto?
*   **Gubernamental**: Se ve 100% oficial bajo el dominio de la Alcaldía.
*   **Seguro**: No tienes que abrir puertos en la red de la oficina ni darles acceso a tu PC.
*   **Independiente**: Puedes gestionar el túnel tú mismo desde tu propia cuenta.

---

## 6. Plantilla de Correo para el Equipo de Sistemas
Puedes copiar y enviar este correo al área correspondiente:

**Asunto:** Solicitud de creación de subdominio CNAME para Proyecto SISC Jamundí

**Cuerpo:**
Cordial saludo equipo de Sistemas,

Desde la Secretaría de Seguridad nos encontramos implementando el **Sistema Integrado de Seguridad y Convivencia (SISC Jamundí)** para el análisis de indicadores delictivos mediante IA.

Para facilitar el acceso operativo de manera segura, solicitamos su apoyo con la creación de un subdominio bajo el dominio oficial de la Alcaldía:

*   **Subdominio deseado:** `sisc.jamundi.gov.co` (o el que consideren pertinente).
*   **Tipo de registro:** CNAME.
*   **Destino (Apuntar a):** `[TU-NOMBRE-DE-TUNEL-AQUI].cfargotunnel.com`

**Nota de Seguridad:** Este direccionamiento utiliza la tecnología de Túneles de Cloudflare, lo que permite que el sistema sea visible externamente sin necesidad de abrir puertos en el firewall de la institución ni realizar cambios en la infraestructura de la Red WAN, manteniendo la integridad de la red local.

Agradecemos de antemano su colaboración. Quedo atento a cualquier requerimiento técnico adicional.

Atentamente,

[Tu Nombre]
[Tu Cargo]
