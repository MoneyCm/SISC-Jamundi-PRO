import pandas as pd
import sys
import os
import hashlib
from datetime import datetime

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from db.session import SessionLocal
from db.models_intelligence import NationalCrimeStats

def generate_fp(row, label):
    d = row.to_dict()
    # Usar campos clave del registro
    date_val = d.get('fecha_hecho') or d.get('fecha', 'NA')
    key = str(label) + "-" + str(date_val) + "-" + str(d.get("sexo","X")) + "-" + str(d.get("municipio","X"))
    return hashlib.sha256(key.encode()).hexdigest()

def ingest_extra(filename, label):
    db = SessionLocal()
    print("Iniciando inyeccion de", label)
    try:
        df = pd.read_csv(filename)
        date_col = 'fecha_hecho' if 'fecha_hecho' in df.columns else 'fecha'
        df["fecha_dt"] = pd.to_datetime(df[date_col], errors="coerce")
        df = df[df["fecha_dt"].dt.year >= 2024].copy()
        
        count = 0
        for _, row in df.iterrows():
            fp = generate_fp(row, label)
            exists = db.query(NationalCrimeStats).filter(NationalCrimeStats.event_fingerprint == fp).first()
            if exists: continue
            
            try:
                item = NationalCrimeStats(
                    source_id="DATOS_GOV_MINDEFENSA",
                    departamento="VALLE",
                    municipio="JAMUNDI",
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
        print("Fin", label, ":", count, "nuevos")
        return count
    finally:
        db.close()

if __name__ == "__main__":
    files = [
        ("backend/JAMUNDI_EXTRA_EXTORSION.csv", "EXTORSION"),
        ("backend/JAMUNDI_EXTRA_HURTO_VEHICULOS.csv", "HURTO_VEHICULOS"),
        ("backend/JAMUNDI_EXTRA_LESIONES_PERSONALES.csv", "LESIONES_PERSONALES")
    ]
    total = 0
    for f, l in files:
        if os.path.exists(f):
            total += ingest_extra(f, l)
    print("TOTAL PROCESADO:", total)
