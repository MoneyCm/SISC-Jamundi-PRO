import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://sisc_user:sisc_password@db:5432/sisc_jamundi")

def check_coords():
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, barrio, occurrence_date, ST_X(location_geom::geometry) as lng, ST_Y(location_geom::geometry) as lat FROM events ORDER BY created_at DESC LIMIT 10")).fetchall()
        for row in result:
            print(f"ID: {row.id} | Barrio: {row.barrio} | Coords: {row.lat}, {row.lng}")

if __name__ == "__main__":
    check_coords()
