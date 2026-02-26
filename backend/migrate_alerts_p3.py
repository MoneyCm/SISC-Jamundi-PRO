from sqlalchemy import text
from db.models import engine

def migrate():
    columns = [
        ("action_score", "FLOAT"),
        ("priority_tier", "VARCHAR(10)"),
        ("recommended_action", "TEXT"),
        ("rationale_md", "TEXT"),
        ("ai_rationale_md", "TEXT"),
        ("ai_provider", "VARCHAR(50)"),
        ("ai_request_id", "VARCHAR(100)"),
        ("scored_at", "TIMESTAMPTZ")
    ]
    
    with engine.connect() as conn:
        for col_name, col_type in columns:
            try:
                # Verificar si existe
                check = conn.execute(text(f"SELECT 1 FROM information_schema.columns WHERE table_name='intelligence_alerts' AND column_name='{col_name}'")).fetchone()
                if not check:
                    print(f"Adding column {col_name}...")
                    conn.execute(text(f"ALTER TABLE intelligence_alerts ADD COLUMN {col_name} {col_type}"))
                else:
                    print(f"Column {col_name} already exists.")
            except Exception as e:
                print(f"Error adding {col_name}: {e}")
        
        # Agregar indices si no existen
        try:
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_alerts_status_score ON intelligence_alerts (status, action_score DESC)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_alerts_priority_tier ON intelligence_alerts (priority_tier)"))
        except Exception as e:
            print(f"Error creating indices: {e}")
            
        conn.commit()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
