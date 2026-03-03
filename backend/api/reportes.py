from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from db.models import get_db, Event, EventType
from jinja2 import Environment, FileSystemLoader
import io
from datetime import datetime, date
import os
import base64

from api.auth import institutional_access, get_current_user

router = APIRouter()

# Configuración de Jinja2
template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
env = Environment(loader=FileSystemLoader(template_dir))

@router.get("/generar-boletin")
async def generar_boletin_pdf(
    anio: int = None, 
    token: str = Query(None),
    db: Session = Depends(get_db)
):
    """
    Genera un boletín de seguridad oficial en PDF con estadísticas actuales y comparativas YoY.
    Soporta autenticación por query parameter para apertura en nueva pestaña.
    """
    # Validar token manualmente si viene por query
    if token:
        try:
            from core.security import decode_access_token
            decode_access_token(token)
        except:
            raise HTTPException(status_code=401, detail="Token inválido")
    else:
        # Si no hay token en la URL, intentar el flujo normal de headers
        # (Esto es un fallback, el frontend enviará el token en la URL)
        raise HTTPException(status_code=401, detail="Autenticación requerida")

    if not anio:
        anio = datetime.now().year

    try:
        from db.models_intelligence import NationalCrimeStats
        
        # 0. Obtener Fecha de Corte (Dato más reciente)
        fecha_corte_raw = db.query(func.max(NationalCrimeStats.fecha_hecho)).filter(
            NationalCrimeStats.municipio_normalizado == "JAMUNDI"
        ).scalar()
        fecha_corte = fecha_corte_raw.strftime("%d/%m/%Y") if fecha_corte_raw else datetime.now().strftime("%d/%m/%Y")

        # 1. Recopilar Datos Año Actual
        local_data = db.query(
            NationalCrimeStats.tipo_delito,
            func.sum(NationalCrimeStats.cantidad).label("total")
        ).filter(
            NationalCrimeStats.municipio_normalizado == "JAMUNDI",
            NationalCrimeStats.anio == anio
        ).group_by(NationalCrimeStats.tipo_delito).all()

        total_incidentes = sum(int(row.total) for row in local_data)
        
        # 2. Datos Año Anterior (YoY)
        yoy_data = db.query(
            NationalCrimeStats.tipo_delito,
            func.sum(NationalCrimeStats.cantidad).label("total")
        ).filter(
            NationalCrimeStats.municipio_normalizado == "JAMUNDI",
            NationalCrimeStats.anio == anio - 1
        ).group_by(NationalCrimeStats.tipo_delito).all()
        yoy_dict = {row.tipo_delito: int(row.total) for row in yoy_data}
        total_yoy = sum(yoy_dict.values())

        # 3. Preparar lista de delitos con comparativa
        delitos_data = []
        for d in local_data:
            c_val = int(d.total)
            p_val = yoy_dict.get(d.tipo_delito, 0)
            var_pct = round(((c_val - p_val) / max(1, p_val) * 100), 1)
            delitos_data.append({
                "name": d.tipo_delito,
                "value": c_val,
                "prev_value": p_val,
                "percent": round((c_val / max(1, total_incidentes) * 100), 1),
                "var_pct": var_pct
            })
        
        delitos_data = sorted(delitos_data, key=lambda x: x['value'], reverse=True)

        # 4. Barrios (Top 10)
        barrios_query = db.query(
            NationalCrimeStats.barrio,
            func.sum(NationalCrimeStats.cantidad).label("total")
        ).filter(
            NationalCrimeStats.municipio_normalizado == "JAMUNDI",
            NationalCrimeStats.anio == anio
        ).group_by(NationalCrimeStats.barrio).order_by(func.sum(NationalCrimeStats.cantidad).desc()).limit(10).all()
        
        barrios_data = []
        for b in barrios_query:
            if b.barrio:
                barrios_data.append({"name": b.barrio, "delitos": int(b.total)})

        # 4.1 Cargar Escudo Base64
        logo_base64 = ""
        try:
            # Ruta relativa al proyecto para el escudo
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            logo_path = os.path.join(base_path, "monitor-mindefensa", "escudo_jamundi.png")
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as img_f:
                    encoded = base64.b64encode(img_f.read()).decode("utf-8")
                    logo_base64 = f"data:image/png;base64,{encoded}"
        except Exception as e:
            print(f"Aviso: No se pudo cargar el escudo: {e}")

        # 5. Renderizar HTML
        template = env.get_template("boletin.html")
        html_content = template.render(
            periodo=str(anio),
            logo_base64=logo_base64,
            fecha_generacion=datetime.now().strftime("%d/%m/%Y %H:%M"),
            fecha_corte=fecha_corte,
            total_incidentes=total_incidentes,
            total_yoy=total_yoy,
            var_total_pct=round(((total_incidentes - total_yoy) / max(1, total_yoy) * 100), 1),
            total_barrios=len(barrios_data),
            delitos=delitos_data,
            barrios=barrios_data
        )

        return StreamingResponse(
            io.BytesIO(html_content.encode()), 
            media_type="text/html",
            headers={"Content-Disposition": f"inline; filename=boletin_{anio}.html"}
        )

    except Exception as e:
        print(f"Error generando boletín: {e}")
        raise HTTPException(status_code=500, detail=f"Error en servidor: {str(e)}")
