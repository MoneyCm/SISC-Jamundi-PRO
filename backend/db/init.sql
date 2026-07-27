-- Extensiones Geoespaciales y UUID
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Seguridad y Usuarios (RBAC v2)
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT
);

-- Los roles se insertarán vía create_roles_v2.py, pero dejamos unos básicos por respaldo
INSERT INTO roles (id, code, name, description) VALUES
(uuid_generate_v4(), 'TI_ADMIN', 'Administrador TI', 'Control total técnico y seguridad'),
(uuid_generate_v4(), 'ANALYST', 'Analista', 'Acceso a datos institucionales');

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(150),
    is_active BOOLEAN DEFAULT TRUE,
    data_level_max SMALLINT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_roles (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, role_id)
);

-- Los usuarios administradores se crean mediante un proceso seguro de aprovisionamiento.

-- 2. Fuentes y Convenios
CREATE TABLE sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    acronym VARCHAR(20) UNIQUE,
    description TEXT,
    contact_person VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE
);

INSERT INTO sources (name, acronym, description) VALUES
('Policía Nacional - SIEDCO', 'SIEDCO', 'Sistema Estadístico Delictivo'),
('Fiscalía General - SPOA', 'SPOA', 'Sistema de Información de la Fiscalía'),
('Instituto Medicina Legal', 'INMLCF', 'Datos de necropsias y lesiones'),
('Secretaría de Salud Jamundí', 'SALUD', 'Registros de atención y RUAF');

-- 3. Geografía (Límites de Jamundí)
CREATE TABLE territories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50) NOT NULL, -- BARRIO, VEREDA, COMUNA, CORREGIMIENTO
    code VARCHAR(20),
    geom GEOMETRY(GEOMETRY, 4326)
);

-- 4. Tipologías
CREATE TABLE event_types (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    subcategory VARCHAR(100),
    is_delicto BOOLEAN DEFAULT TRUE
);

INSERT INTO event_types (category, subcategory) VALUES
('HOMICIDIO', 'DOLOSO'),
('HOMICIDIO', 'CULPOSO (ACCIDENTE TRANSITO)'),
('HURTO', 'A PERSONAS'),
('HURTO', 'A RESIDENCIAS'),
('HURTO', 'A COMERCIO'),
('LESIONES PERSONALES', 'EN RIÑA'),
('VIOLENCIA INTRAFAMILIAR', 'GENERAL');

-- 5. Eventos (Cuerpo Central)
CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id VARCHAR(100), -- ID en el sistema de origen
    source_id INT REFERENCES sources(id),
    event_type_id INT REFERENCES event_types(id),
    occurrence_date DATE NOT NULL,
    occurrence_time TIME NOT NULL,
    barrio VARCHAR(100),
    estado VARCHAR(50) DEFAULT 'Abierto',
    descripcion TEXT,
    territory_id INT REFERENCES territories(id),
    location_geom GEOMETRY(POINT, 4326),
    address_text TEXT,
    modality VARCHAR(100),
    weapon VARCHAR(100),
    victim_gender VARCHAR(20),
    victim_age INT,
    victim_id_hashed TEXT, -- Seudonimización
    ingestion_id UUID, -- Referencia al log de carga
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Índices Espaciales
CREATE INDEX idx_events_geom ON events USING GIST (location_geom);
CREATE INDEX idx_territories_geom ON territories USING GIST (geom);
CREATE INDEX idx_events_date ON events (occurrence_date);
