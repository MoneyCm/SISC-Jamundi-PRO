from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from db.models import get_db, Event, EventType
import pandas as pd
import io
import uuid
from typing import List, Dict, Optional, Any
from datetime import datetime

router = APIRouter()

@router.post("/upload")
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Recibe un archivo Excel/CSV, procesa los datos y los inserta en PostGIS.
    Reporta éxitos y fallos individuales por fila.
    """
    contents = await file.read()
    
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(contents))
        elif file.filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(io.BytesIO(contents))
        else:
            raise HTTPException(status_code=400, detail="Formato de archivo no soportado")

        # Normalizar nombres de columnas a minúsculas
        df.columns = [c.lower().strip() for c in df.columns]

        required_cols = ['fecha', 'hora', 'delito', 'latitud', 'longitud']
        if not all(col in df.columns for col in required_cols):
            raise HTTPException(status_code=400, detail=f"Faltan columnas requeridas: {required_cols}")

        report = {
            "total": len(df),
            "success_count": 0,
            "error_count": 0,
            "errors": []
        }

        for index, row in df.iterrows():
            row_num = index + 2 # +1 for 0-index, +1 for header row
            try:
                # 1. Validar y normalizar Categoría
                delito_nombre = str(row.get('delito', '')).upper().strip()
                if not delito_nombre:
                    raise ValueError("El campo 'delito' no puede estar vacío")

                event_type = db.query(EventType).filter(EventType.category == delito_nombre).first()
                if not event_type:
                    event_type = EventType(category=delito_nombre, is_delicto=True)
                    db.add(event_type)
                    db.flush()

                # 2. Parsing de Fecha y Hora con validación
                try:
                    occ_date = pd.to_datetime(row['fecha']).date()
                    occ_time = pd.to_datetime(row['hora']).time()
                except Exception:
                    raise ValueError(f"Formato de fecha/hora inválido (Fecha: {row['fecha']}, Hora: {row['hora']})")

                # 3. Datos de Geometría
                try:
                    lng = float(row['longitud'])
                    lat = float(row['latitud'])
                    if not (-180 <= lng <= 180) or not (-90 <= lat <= 90):
                        raise ValueError("Coordenadas fuera de rango válido")
                except (ValueError, TypeError):
                    raise ValueError(f"Coordenadas inválidas (Lat: {row.get('latitud')}, Lng: {row.get('longitud')})")

                # 4. Crear el evento
                new_event = Event(
                    external_id=str(row.get('id_externo', uuid.uuid4())),
                    event_type_id=event_type.id,
                    occurrence_date=occ_date,
                    occurrence_time=occ_time,
                    barrio=str(row.get('barrio', 'Sin especificar')),
                    descripcion=str(row.get('descripcion', '')),
                    estado=str(row.get('estado', 'Abierto'))
                )
                db.add(new_event)
                db.flush()

                # 5. Insertar geometría PostGIS
                db.execute(
                    func.text("UPDATE events SET location_geom = ST_SetSRID(ST_Point(:lng, :lat), 4326) WHERE id = :id"),
                    {"lng": lng, "lat": lat, "id": new_event.id}
                )
                
                report["success_count"] += 1

            except Exception as row_err:
                report["error_count"] += 1
                report["errors"].append({"fila": row_num, "error": str(row_err)})

        db.commit()
        return {
            "status": "success" if report["error_count"] == 0 else "partial_success",
            "message": f"Carga completada: {report['success_count']} éxitos, {report['error_count']} errores.",
            "report": report
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error fatal procesando el archivo: {str(e)}")

@router.post("/bulk")
async def bulk_upload(data: List[dict], db: Session = Depends(get_db)):
    """
    Recibe una lista de eventos pre-analizados por la IA en JSON y los inserta.
    """
    report = {
        "total": len(data),
        "success_count": 0,
        "error_count": 0,
        "errors": []
    }

    for index, item in enumerate(data):
        try:
            with db.begin_nested(): # SAVEPOINT: falla solo esta fila si algo sale mal
                # 1. Validar Categoría
                raw_delito = str(item.get('tipo', '')).upper().strip()
                # Normalización inteligente
                delito_nombre = raw_delito
                if 'H.PERSONA' in raw_delito or raw_delito == 'H. PERSONAS': delito_nombre = 'HURTO A PERSONAS'
                elif 'H.COMERCIO' in raw_delito: delito_nombre = 'HURTO A COMERCIO'
                elif 'H.RESIDENCIA' in raw_delito: delito_nombre = 'HURTO A RESIDENCIAS'
                elif 'H.MOTOS' in raw_delito: delito_nombre = 'HURTO A MOTOCICLETAS'
                elif 'H.AUTOMO' in raw_delito: delito_nombre = 'HURTO A AUTOMOTORES'
                elif 'L.PERSONALES' in raw_delito or 'LESIONES' in raw_delito: delito_nombre = 'LESIONES PERSONALES'
                elif 'HOMICI' in raw_delito: delito_nombre = 'HOMICIDIO'
                elif 'VIOLENCIA' in raw_delito or 'VIF' in raw_delito: delito_nombre = 'VIOLENCIA INTRAFAMILIAR'

                event_type = db.query(EventType).filter(EventType.category == delito_nombre).first()
                if not event_type:
                    event_type = EventType(category=delito_nombre, is_delicto=True)
                    db.add(event_type)
                    db.flush()

                # 2. Fecha y Hora
                def parse_robust_time(val):
                    if not val or str(val).lower() == 'undefined' or str(val).strip() == '':
                        return datetime.strptime("00:00", "%H:%M").time()
                    val_str = str(val).split('-')[0].strip()
                    try:
                        if ':' in val_str:
                            parts = val_str.split(':')
                            h = int(parts[0])
                            m = int(parts[1]) if len(parts) > 1 else 0
                            return datetime.strptime(f"{h:02d}:{m:02d}", "%H:%M").time()
                        return pd.to_datetime(val_str).time()
                    except:
                        return datetime.strptime("00:00", "%H:%M").time()

                def parse_robust_date(val):
                    if not val or str(val).lower() == 'undefined':
                        return datetime.now().date()
                    try:
                        return pd.to_datetime(val).date()
                    except:
                        try:
                            val_clean = str(val).split(' ')[0]
                            return pd.to_datetime(val_clean).date()
                        except:
                            return datetime.now().date()

                occ_date = parse_robust_date(item.get('fecha'))
                occ_time = parse_robust_time(item.get('hora'))

                # 3. Geometría
                try:
                    def clean_coord(c):
                        if not c or str(c).lower() == 'undefined': return None
                        return float(str(c).replace(',', '.'))
                    lat = clean_coord(item.get('latitud')) or 3.26
                    lng = clean_coord(item.get('longitud')) or -76.53
                except:
                    lat, lng = 3.26, -76.53

                # 4. Crear Evento
                new_event = Event(
                    external_id=str(item.get('id_externo', uuid.uuid4())),
                    event_type_id=event_type.id,
                    occurrence_date=occ_date,
                    occurrence_time=occ_time,
                    barrio=str(item.get('barrio', 'Sin especificar')),
                    descripcion=str(item.get('descripcion', '')),
                    estado=str(item.get('estado', 'Abierto'))
                )
                db.add(new_event)
                db.flush()

                # 5. PostGIS
                db.execute(
                    text("UPDATE events SET location_geom = ST_SetSRID(ST_Point(:lng, :lat), 4326) WHERE id = :id"),
                    {"lng": lng, "lat": lat, "id": new_event.id}
                )
                report["success_count"] += 1
            
            # Commit masivo cada 50 filas (Mucho más rápido)
            if index % 50 == 0:
                db.commit()

        except Exception as e:
            # El uso de begin_nested() hace rollback automático de ESTA fila si falla
            report["error_count"] += 1
            report["errors"].append({"index": index, "error": str(e)})

    db.commit() # Commit final de lo que quede pendiente
    return {
        "status": "success" if report["error_count"] == 0 else "partial_success",
        "message": f"Carga masiva completada: {report['success_count']} registros integrados.",
        "report": report
    }

@router.delete("/clear")
def clear_all_events(db: Session = Depends(get_db)):
    """Elimina todos los eventos de la base de datos"""
    db.query(Event).delete()
    db.commit()
    return {"message": "Base de datos de eventos limpiada correctamente"}

@router.delete("/{event_id}")
def delete_event(event_id: uuid.UUID, db: Session = Depends(get_db)):
    """Elimina un evento específico"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    db.delete(event)
    db.commit()
    return {"message": "Evento eliminado correctamente"}
