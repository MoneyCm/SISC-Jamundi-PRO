from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from db.models import get_db, User
from api.auth import institutional_access
from db.models_panic import PanicAlert, PanicEvidence
import uuid
import os
import json
from typing import List, Optional
from datetime import datetime

router = APIRouter()

UPLOAD_DIR = "static/uploads/panic"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/alert")
async def create_panic_alert(
    request: Request,
    db: Session = Depends(get_db)
):
    try:
        # Bypassear validaciones automáticas procesando el formulario manualmente
        form_data = await request.form()
        print(f"DEBUG: Form keys detectadas: {list(form_data.keys())}")
        
        payload = form_data.get("payload")
        media = form_data.getlist("media") # Retorna lista vacía si no hay
        
        alert_data = {}
        if payload:
            try:
                alert_data = json.loads(payload)
                print(f"DEBUG: Payload obtenido de Form: {alert_data}")
            except Exception as e:
                print(f"DEBUG: Error parseando payload JSON: {e}")
        
        if not alert_data:
            # Intentar ver si es un body JSON puro
            try:
                raw_body = await request.body()
                if raw_body:
                    alert_data = json.loads(raw_body)
                    print(f"DEBUG: Payload obtenido de Body JSON: {alert_data}")
            except:
                pass

        if not alert_data and not media:
            print("DEBUG: Petición vacía (nada en form ni en body)")
            return JSONResponse(status_code=400, content={"detail": "Petición vacía o malformada"})
        
        # Obtener IP real
        ip_address = request.headers.get("x-forwarded-for") or request.client.host
        
        media_count = len(media) if media else 0
        print(f"DEBUG: Archivos recibidos en 'media': {media_count}")
        if media:
            for m in media:
                if hasattr(m, 'filename'):
                    print(f"DEBUG: Archivo detectado: {m.filename}")
        
        # 1. Crear la alerta en DB
        new_alert = PanicAlert(
            timestamp=datetime.fromisoformat(alert_data.get("timestamp", datetime.now().isoformat()).replace('Z', '+00:00')),
            lat=alert_data.get("lat"),
            lon=alert_data.get("lon"),
            accuracy=alert_data.get("accuracy"),
            note=alert_data.get("note", "Alerta Móvil"),
            device_info=alert_data.get("device_info", {}),
            status="OPEN",
            ip_address=ip_address
        )
        db.add(new_alert)
        db.flush() # Para obtener el ID
        
        evidence_urls = []
        
        # 2. Procesar medios si existen
        if media:
            for file in media:
                file_id = uuid.uuid4()
                extension = os.path.splitext(file.filename)[1]
                file_name = f"{new_alert.id}_{file_id}{extension}"
                file_path = os.path.join(UPLOAD_DIR, file_name)
                
                with open(file_path, "wb") as f:
                    f.write(await file.read())
                
                # Crear registro de evidencia
                evidence = PanicEvidence(
                    alert_id=new_alert.id,
                    file_path=f"/{UPLOAD_DIR}/{file_name}",
                    file_type=file.content_type,
                    file_size=os.path.getsize(file_path)
                )
                db.add(evidence)
                evidence_urls.append(evidence.file_path)
        
        new_alert.evidence_urls = evidence_urls
        db.commit()
        db.refresh(new_alert)
        
        return {
            "status": "success",
            "message": "Alerta de pánico recibida y procesada",
            "alert_id": str(new_alert.id)
        }
    except Exception as e:
        import traceback
        print(f"CRITICAL ERROR EN PANIC: {str(e)}")
        print(traceback.format_exc())
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo procesar la alerta.")

@router.get("/history")
def get_panic_history(
    limit: int = 50, 
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(institutional_access),
):
    query = db.query(PanicAlert)
    if status:
        query = query.filter(PanicAlert.status == status)
    
    return query.order_by(PanicAlert.timestamp.desc()).limit(limit).all()

@router.patch("/alert/{alert_id}")
async def update_alert_status(
    alert_id: uuid.UUID,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(institutional_access),
):
    alert = db.query(PanicAlert).filter(PanicAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    
    if "status" in data:
        alert.status = data["status"]
    if "assigned_to" in data:
        alert.assigned_to = data["assigned_to"]
        
    db.commit()
    return {"status": "success", "alert_id": str(alert.id), "new_status": alert.status}

@router.get("/stats")
def get_panic_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(institutional_access),
):
    """Estadísticas rápidas para el dashboard"""
    total = db.query(PanicAlert).count()
    open_alerts = db.query(PanicAlert).filter(PanicAlert.status == "OPEN").count()
    dispatched = db.query(PanicAlert).filter(PanicAlert.status == "DISPATCHED").count()
    
    return {
        "total": total,
        "open": open_alerts,
        "dispatched": dispatched
    }
