"""
Ingesta de Sabanas Semanales SIEDCO (formato Policía Nacional).
Uso: python ingest_sabanas_semanal.py <ruta_al_excel>
"""
import pandas as pd
import sys
import os
import hashlib
import uuid
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.session import SessionLocal
from db.models_hechos_seguridad import HechoSeguridad, IngestionRun

# Mapeo de conductas SIEDCO a estándar SISC
CONDUCTA_MAP = {
    'H.PERSONAS':    ('HURTO_PERSONAS',    'HURTO'),
    'H.RESIDENCIAS': ('HURTO_RESIDENCIAS', 'HURTO'),
    'H.COMERCIO':    ('HURTO_COMERCIO',    'HURTO'),
    'H.AUTOMOTORES': ('HURTO_AUTOMOTORES', 'HURTO'),
    'H.MOTOS':       ('HURTO_MOTOS',       'HURTO'),
    'LESIONES':      ('LESIONES',          'LESIONES_PERSONALES'),
    'HOMICIDIO':     ('HOMICIDIO',         'HOMICIDIO'),
}

def safe_str(val, default=''):
    if pd.isna(val):
        return default
    return str(val).strip()

def safe_int(val):
    try:
        return int(val)
    except:
        return None

def fingerprint(row):
    parts = [
        safe_str(row.get('HECHOS_ID')),
        safe_str(row.get('FECHA_HECHO')),
        safe_str(row.get('DESCRIPCION_CONDUCTA')),
        safe_str(row.get('BARRIOS_HECHO')),
        safe_str(row.get('GENERO')),
    ]
    key = '-'.join(parts)
    return hashlib.sha256(key.encode()).hexdigest()

def parse_hora(val):
    try:
        if pd.isna(val):
            return None
        s = str(val).strip().zfill(4)
        h, m = int(s[:2]), int(s[2:])
        return datetime.time(h, m)
    except:
        return None

def ingest(filepath):
    db = SessionLocal()
    filename = os.path.basename(filepath)

    print(f"\n📂 Leyendo: {filename}")
    df = pd.read_excel(filepath)
    df.columns = [str(c).strip() for c in df.columns]

    # Parsear fecha
    df['fecha_dt'] = pd.to_datetime(df['FECHA_HECHO'], errors='coerce')
    df = df[df['fecha_dt'].notna()].copy()
    print(f"   → {len(df)} filas con fecha válida")

    # Crear registro de ingesta
    run = IngestionRun(
        fuente_codigo='POLICIA_SEMANAL',
        filename=filename,
        total_filas=len(df),
        usuario_carga='sistema',
        status='IN_PROGRESS',
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    nuevos = 0
    duplicados = 0
    errores = 0

    for idx, row in df.iterrows():
        fp = fingerprint(row)

        # Idempotencia: si ya existe, saltar
        exists = db.query(HechoSeguridad).filter(
            HechoSeguridad.fuente_codigo == 'POLICIA_SEMANAL',
            HechoSeguridad.fingerprint == fp
        ).first()
        if exists:
            duplicados += 1
            continue

        conducta_raw = safe_str(row.get('DESCRIPCION_CONDUCTA', ''))
        conducta_std, categoria = CONDUCTA_MAP.get(conducta_raw, (conducta_raw, 'OTRO'))

        barrio = safe_str(row.get('BARRIOS_HECHO'))
        zona = safe_str(row.get('ZONA'))
        es_vereda = ('CGTO' in barrio.upper() or 'VIA ' in barrio.upper()
                     or zona.upper() == 'RURAL')

        try:
            hecho = HechoSeguridad(
                fuente_codigo='POLICIA_SEMANAL',
                id_fuente=safe_str(row.get('HECHOS_ID')),
                ingestion_id=run.id,
                conducta_original=conducta_raw,
                conducta_estandar=conducta_std,
                categoria_delito=categoria,
                fecha_evento=row['fecha_dt'].date(),
                hora_evento=parse_hora(row.get('HORA24')),
                semana_num=safe_int(row.get('NoSEMANA')),
                dia_semana=safe_str(row.get('DIA_SEMANA')),
                sexo=safe_str(row.get('GENERO')),
                edad=safe_int(row.get('EDAD')),
                grupo_edad=safe_str(row.get('AGRUPA_EDAD_PERSONA')),
                zona=zona,
                arma_medio=safe_str(row.get('ARMAS_MEDIOS')),
                modalidad=safe_str(row.get('MODALIDAD')),
                movil_agresor=safe_str(row.get('MOVIL_AGRESOR')),
                movil_victima=safe_str(row.get('MOVIL_VICTIMA')),
                clase_sitio=safe_str(row.get('CLASE_SITIO')),
                barrio_original=barrio,
                barrio_normalizado=barrio if not es_vereda else '',
                vereda_original=barrio if es_vereda else '',
                vereda_normalizada=barrio if es_vereda else '',
                municipio='JAMUNDI',
                estado_calidad='APROBADO',
                fingerprint=fp,
                fecha_ingesta=datetime.datetime.utcnow(),
                usuario_ingesta='sistema',
            )
            db.add(hecho)
            db.commit()
            nuevos += 1

        except Exception as e:
            db.rollback()
            errores += 1
            if errores <= 3:
                print(f"   ⚠️  Fila {idx}: {e}")

    # Actualizar resumen de la corrida
    run.aprobadas = nuevos
    run.duplicadas = duplicados
    run.rechazadas = errores
    run.fecha_fin = datetime.datetime.utcnow()
    run.status = 'COMPLETED'
    run.resumen = {
        'nuevos': nuevos,
        'duplicados': duplicados,
        'errores': errores,
        'rango_fechas': f"{df['fecha_dt'].min().date()} → {df['fecha_dt'].max().date()}"
    }
    db.commit()
    db.close()

    print(f"\n✅ Ingesta completada:")
    print(f"   → {nuevos} registros nuevos")
    print(f"   → {duplicados} duplicados (ya existían)")
    print(f"   → {errores} errores")
    print(f"   → Período: {df['fecha_dt'].min().date()} → {df['fecha_dt'].max().date()}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        filepath = os.path.join(os.path.dirname(__file__), 'SABANAS_SEM_27_2026.xlsx')
    else:
        filepath = sys.argv[1]

    if not os.path.exists(filepath):
        print(f"❌ Archivo no encontrado: {filepath}")
        sys.exit(1)

    ingest(filepath)
