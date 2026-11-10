# Publicar el portal ciudadano del Sistema de Información para la Seguridad y Convivencia (SISC)

El mismo código produce dos versiones:

| | Institucional | Portal ciudadano |
|---|---|---|
| Frontend | build normal | `VITE_PUBLIC_ONLY=true` (sin login ni botón "Ingreso institucional") |
| Backend | todas las rutas | `SISC_PUBLIC_ONLY=true` (solo rutas públicas, ver `backend/core/public_mode.py`) |
| Dónde vive | tu PC, acceso por Tailscale | Render (prueba) → `sisc.jamundi.gov.co` (oficial) |
| Base de datos | dueña, lectura y escritura | usuario `sisc_portal`, solo lectura |

En modo público el backend **no** migra tablas, **no** crea usuarios, **no** corre sincronizaciones
y **no** publica `/docs`. Login, carga de sábanas, usuarios, monitores, alertas y actas responden 404.

## Pasos

1. **Usuario de solo lectura.** En Neon → SQL Editor, cambia la contraseña de
   `docs/despliegue/rol_portal_lectura.sql` y ejecútalo.
2. **Subir el código a GitHub** (rama principal o la que use Render).
3. **Render → Blueprints → sincronizar `render.yaml`.** Aparecen `sisc-api-publico` y `sisc-portal`.
4. En `sisc-api-publico` pon `DATABASE_URL` con el usuario `sisc_portal`
   (`postgresql://sisc_portal:CLAVE@HOST/neondb?sslmode=require`) y, si quieres el asistente, `GEMINI_API_KEY`.
5. Abre `https://sisc-portal.onrender.com` y revisa: no debe aparecer "Ingreso institucional";
   `https://sisc-api-publico.onrender.com/api/auth/login` y `/docs` deben dar 404.
6. **Dominio oficial:** pedir a la oficina TIC un registro CNAME `sisc.jamundi.gov.co` → `sisc-portal.onrender.com`
   y agregarlo como dominio personalizado en Render.

## Formularios ciudadanos

Reporte seguro, propuestas y frentes de seguridad escriben en la base, así que están apagados
(`SISC_PUBLIC_ALLOW_WRITES=false`). Para activarlos hace falta permiso de escritura en esas tablas
y definir quién revisa lo que llega.

## Datos que ve el portal

El portal lee la base que alimenta el SISC institucional. Si la carga se hace en el PC (Docker) y Neon
no se actualiza, el portal mostrará cifras viejas: hay que sincronizar Neon después de cada carga.
