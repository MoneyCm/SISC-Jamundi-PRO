from db.session import SessionLocal
from db.models_dq import DqReport

def list_all_reports():
    db = SessionLocal()
    try:
        reports = db.query(DqReport).order_by(DqReport.created_at.desc()).limit(10).all()
        if not reports:
            print("La tabla de reportes DQ está vacía.")
            return
            
        print(f"{'ID':<40} | {'Archivo':<30} | {'Fuente':<20} | {'Score'}")
        print("-" * 100)
        for r in reports:
            print(f"{str(r.id):<40} | {str(r.filename):<30} | {str(r.source_name):<20} | {r.score_overall}")
            
    finally:
        db.close()

if __name__ == "__main__":
    list_all_reports()
