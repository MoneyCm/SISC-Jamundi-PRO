from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Event
from backend.main import get_db

DATABASE_URL = "postgresql://neondb_owner:npg_ZzBiN3DU6dgc@ep-holy-lake-aiso6dd5-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

from sqlalchemy import func, text

prefix = "MINDEFENSA%"
query = db.query(Event.descripcion.label('category'), func.count(Event.id).label('total'))
query = query.filter(Event.occurrence_date >= '2026-01-01')
query = query.filter(Event.source_name.like(prefix))
results = query.group_by(Event.descripcion).order_by(text('total DESC')).all()
    
print([{"name": r.category or "Sin Definir", "value": r.total} for r in results])
