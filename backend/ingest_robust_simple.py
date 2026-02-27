import pandas as pd
import sys
import os
import hashlib
from datetime import datetime

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from db.session import SessionLocal
from db.models_intelligence import NationalCrimeStats

def generate_fingerprint(row, dataset_name):
    d = row.to_dict()
    key = str(dataset_name) + "-" + str(d.get("fecha_hecho","NA")) + "-" + str(d.get("sexo","X")) + "-" + str(d.get("cantidad","1"))
    return hashlib.sha256(key.encode()).hexdigest()

def ingest_robust(filename, label):
    db = SessionLocal()
    print("Iniciando:", label)
    try:
        df = pd.read_csv(filename)
        df["fecha_dt"] = pd.to_datetime(df["fecha_hecho"], errors="coerce")
        df = df[df["fecha_dt"].dt.year >= 2024].copy()
        
        count = 0
        skipped = 0
        for _, row in df.iterrows():
            fp = generate_fingerprint(row, label)
            exists = db.query(NationalCrimeStats).filter(NationalCrimeStats.event_fingerprint == fp).first()
            if exists:
                skipped += 1
                continue
            
            try:
                item = NationalCrimeStats(
                    source_id="DATOS_GOV_MINDEFENSA",
                    departamento=str(row.get("departamento", "VALLE")),
                    municipio=str(row.get("municipio", "JAMUNDI")),
                    municipio_normalizado="JAMUNDI",
                    codigo_dane="76364",
                    fecha_hecho=row["fecha_dt"].date(),
                    anio=int(row["fecha_dt"].year),
                    mes=int(row["fecha_dt"].month),
                    tipo_delito=label,
                    genero=str(row.get("sexo", "NA")),
                    cantidad=int(row.get("cantidad", 1)),
                    event_fingerprint=fp,
                    fuente_archivo=os.path.basename(filename)
                )
                db.add(item)
                db.commit()
                count += 1
            except:
                db.rollback()
                skipped += 1
        print("Resultado", label, ":", count, "nuevos,", skipped, "duplicados")
        return count
    finally:
        db.close()

if __name__ == "__main__":
    files = [
        ("backend/JAMUNDI_LATEST_HOMICIDIO.csv", "HOMICIDIO"),
        ("backend/JAMUNDI_LATEST_HURTO_PERSONAS.csv", "HURTO_PERSONAS")
    ]
    total = 0
    for f, l in files:
        if os.path.exists(f):
            total += ingest_robust(f, l)
    print("FIN. Total:", total)
