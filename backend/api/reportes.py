from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from db.models import get_db, Event, EventType
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import io
from datetime import datetime, date
import os

router = APIRouter()

# Configuración de Jinja2
template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
env = Environment(loader=FileSystemLoader(template_dir))

@router.get("/generar-boletin")
async def generar_boletin_pdf(db: Session = Depends(get_db)):
    """
    Genera un boletín de seguridad oficial en PDF con estadísticas actuales.
    """
    try:
        # 1. Recopilar KPI Generales
        total_incidentes = db.query(Event).count()
        tasa_homicidios_raw = db.query(func.count(Event.id)).join(EventType).filter(EventType.category == "HOMICIDIO").scalar() or 0
        tasa_homicidios = round((tasa_homicidios_raw / 150000) * 100000, 2)
        
        # 2. Distribución por Delito (Top 5)
        delitos_query = db.query(
            EventType.category, 
            func.count(Event.id).label('total')
        ).join(Event).group_by(EventType.category).order_by(func.count(Event.id).desc()).limit(5).all()
        
        delitos_data = []
        for d in delitos_query:
            percent = round((d.total / total_incidentes * 100), 1) if total_incidentes > 0 else 0
            delitos_data.append({"name": d.category, "value": d.total, "percent": percent})

        # 3. Top Barrios
        barrios_query = db.query(
            Event.barrio, 
            func.count(Event.id).label('total')
        ).group_by(Event.barrio).order_by(func.count(Event.id).desc()).limit(5).all()
        
        barrios_data = [{"name": b.barrio or "Sin especificar", "delitos": b.total} for b in barrios_query]

        # 4. Renderizar HTML con Jinja2
        template = env.get_template("boletin.html")
        html_content = template.render(
            periodo="Histórico Actualizado",
            fecha_generacion=datetime.now().strftime("%d/%m/%Y %H:%M"),
            total_incidentes=total_incidentes,
            tasa_homicidios=tasa_homicidios,
            total_barrios=len(barrios_query),
            delitos=delitos_data,
            barrios=barrios_data
        )

        # 5. Convertir a PDF con WeasyPrint
        pdf_file = io.BytesIO()
        HTML(string=html_content).write_pdf(pdf_file)
        pdf_file.seek(0)

        return StreamingResponse(
            pdf_file, 
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=boletin_seguridad_jamundi.pdf"}
        )

    except Exception as e:
        print(f"Error generando PDF: {e}")
        raise HTTPException(status_code=500, detail=f"No se pudo generar el reporte: {str(e)}")
