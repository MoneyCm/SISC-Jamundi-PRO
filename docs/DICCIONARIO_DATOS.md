# Diccionario de Datos - SISC Jamundí

## 1. Entidad: EVENTOS (events)

| Campo | Tipo | Descripción | Ejemplo |
| :--- | :--- | :--- | :--- |
| `occurrence_date` | Date | Fecha exacta en que ocurrió el hecho. | 2024-05-12 |
| `occurrence_time` | Time | Hora (24h) en que ocurrió el hecho. | 22:15:00 |
| `event_type_id` | Integer | ID de la tipología del delito/convivencia. | 1 (Homicidio) |
| `territory_id` | Integer | ID del barrio o vereda (normalizado). | 45 (El Rosario) |
| `location_geom` | Geometry | Punto geográfico (Lat, Lon) en EPSG:4326. | POINT(-76.5 3.2) |
| `modality` | String | Modo de ejecución del evento. | Atraco, Sicariato |
| `weapon` | String | Medio o arma utilizada. | Arma de fuego |
| `victim_gender` | String | Sexo de la víctima (M, F, Otro). | M |
| `victim_age` | Integer | Edad aproximada de la víctima. | 25 |

## 2. Dominios y Clasificaciones

### Categorías de Evento (`event_types`)
- **Homicidio** (Diferenciando doloso, culposo).
- **Hurto** (A personas, residencias, comercio, vehículos).
- **Lesiones Personales**.
- **Violencia Intrafamiliar**.
- **Comportamientos Contrarios a la Convivencia** (Código de Policía).

### Tipos de Territorio (`territories`)
- **BARRIO**: Área urbana.
- **VEREDA**: Área rural.
- **COMUNA**: Agrupación urbana.
- **CORREGIMIENTO**: Agrupación rural.

### Fuentes de Información (`sources`)
- **SIEDCO**: Policía Nacional.
- **SPOA**: Fiscalía General de la Nación.
- **RUAF**: Salud / Defunciones.
- **INMLCF**: Medicina Legal.
