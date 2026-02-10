# PRD - Observatorio del Delito (SISC Jamundí)

## 1. Objetivos del Producto
El sistema se enmarca en la estrategia "Jamundí se transforma con seguridad y convivencia", actuando como el **Sistema de Información para la Seguridad y Convivencia (SISC)**. Su propósito es servir como la herramienta tecnológica del **Observatorio del Delito** para gestionar y consolidar información estratégica sobre los comportamientos contra la vida y la integridad personal.

### Misión del Observatorio:
Gestionar y consolidar información estratégica y periódica sobre los comportamientos contra la vida y la integridad personal para elaborar análisis e investigaciones sobre los fenómenos de violencia e inseguridad que afectan el territorio.

### Funciones Soportadas por el Sistema:
1. **Coordinación de datos**: Integrar información de entes de Seguridad Pública.
2. **Generación de informes**: Producir reportes periódicos de delitos y contravenciones.
3. **Diagnóstico y Caracterización**: Identificar problemáticas y factores de riesgo.
4. **Georreferenciación (GIS)**: Identificar las zonas más afectadas por delitos en el municipio.
5. **Priorización**: Facilitar la priorización de problemáticas a atender mediante datos.

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
