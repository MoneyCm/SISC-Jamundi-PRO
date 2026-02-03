# Modelo de Datos - SISC Jamundí

## 1. Tablas Nucleares

### Usuarios y Roles
- `users`: id, username, email, password_hash, role_id, active.
- `roles`: id, name (Admin, Analista, etc), permissions (JSON).

### Configuración y Fuentes
- `sources`: id, name (Policía, Fiscalía), description, contact_info.
- `agreements`: id, source_id, frequency, responsible, status.
- `territories`: id, name, type (Barrio, Vereda, Comuna, Corregimiento), geom (Geometry).

### Hechos (Eventos de Seguridad)
- `events`: 
    - `id` (UUID)
    - `external_id` (ID de la fuente)
    - `source_id` (FK a sources)
    - `event_datetime` (Timestamp)
    - `event_type` (FK a tipologías)
    - `modality`
    - `weapon`
    - `territory_id` (FK a territories)
    - `address_description`
    - `geom` (Point - PostGIS)
    - `victim_details` (JSON seudonimizado)
    - `ingestion_id` (FK a ingestion_logs)

### Auditoría y ETL
- `ingestion_logs`: id, user_id, source_id, filename, start_time, end_time, status, records_processed, errors.
- `audit_logs`: id, user_id, action, table_name, record_id, timestamp.

## 2. SQL Schema (Simplificado para DB Init)

```sql
-- Extensiones
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Tablas Maestras
CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role_id INT REFERENCES roles(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    acronym VARCHAR(20),
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE territories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50), -- BARRIO, VEREDA, COMUNA, CORREGIMIENTO
    geom GEOMETRY(GEOMETRY, 4326)
);

CREATE TABLE event_types (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50), -- HOMICIDIO, HURTO, LESIONES, etc
    subcategory VARCHAR(100)
);

CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id INT REFERENCES sources(id),
    event_type_id INT REFERENCES event_types(id),
    occurrence_date DATE NOT NULL,
    occurrence_time TIME NOT NULL,
    territory_id INT REFERENCES territories(id),
    location_geom GEOMETRY(POINT, 4326),
    modality VARCHAR(100),
    weapon VARCHAR(100),
    victim_gender VARCHAR(20),
    victim_age INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
