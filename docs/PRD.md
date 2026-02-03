# PRD - Sistema de Información para la Seguridad y la Convivencia (SISC) Jamundí

## 1. Objetivos del Producto
El SISC Jamundí busca centralizar, procesar y analizar información estratégica sobre violencia, delincuencia y convivencia ciudadana para orientar la política pública del municipio.

### Objetivos específicos:
- Consolidar fuentes administrativas (Policía, Fiscalía, etc.).
- Producir indicadores georreferenciados y temporales.
- Automatizar la generación de boletines de seguridad.
- Ofrecer transparencia a la ciudadanía mediante datos agregados.

## 2. Usuarios y Roles
| Rol | Descripción | Permisos Clave |
| :--- | :--- | :--- |
| **Admin SISC** | Administrador del sistema | Gestión de usuarios, fuentes y configuración global. |
| **Analista Observatorio** | Usuario técnico | Creación de indicadores, generación de boletines, análisis geoespacial. |
| **Cargador de Datos** | Enlace de fuente | Subida de archivos (CSV/Excel) y validación de ingesta. |
| **Consulta Interna** | Secretarios, directivos | Visualización de tableros y reportes privados. |
| **Público** | Ciudadanía general | Acceso a portal de transparencia con datos agregados. |

## 3. Scope del MVP
- **Ingesta**: Carga de archivos manual + API mock.
- **Analítica**: Conteos, tasas por 100k, variaciones, hotspots (PostGIS).
- **Reportes**: Boletín mensual y semanal en PDF.
- **GIS**: Visualización de eventos en mapa de Jamundí por barrios/veredas.
- **Seguridad**: Autenticación JWT y seudonimización de datos sensibles.

## 4. No Alcance (Fuera del MVP)
- Integración en tiempo real con sistemas nacionales mediante VPNs complejas.
- Predicción basada en IA (Deep Learning).
- Aplicación móvil nativa (será Web Responsive).
- Gestión de inventarios físicos de la Secretaría.
