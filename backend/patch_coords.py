from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://sisc_user:sisc_password@db:5432/sisc_jamundi")

# Coordenadas aproximadas para los barrios de la prueba
COORDS = {
    "PORTAL DE JORDAN E24": (3.2505, -76.5412),
    "VIA CALI JAMUNDI E24": (3.2753, -76.5281),
    "EL RODEO E24": (3.2598, -76.5345),
    "BARRIO PENDIENTE POR ASIGNAR": (3.2612, -76.5320)
}

def patch_coords():
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        # Buscar eventos sin coordenadas de precisión (que tengan el default 3.26, -76.53)
        # O simplemente actualizar los recién creados por su nombre de barrio
        for barrio, (lat, lng) in COORDS.items():
            conn.execute(
                text("UPDATE events SET location_geom = ST_SetSRID(ST_Point(:lng, :lat), 4326) WHERE barrio = :barrio"),
                {"lat": lat, "lng": lng, "barrio": barrio}
            )
        conn.commit()
        print("Coordenadas actualizadas para demostración de precisión.")

if __name__ == "__main__":
    patch_coords()
