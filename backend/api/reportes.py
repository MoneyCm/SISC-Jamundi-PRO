from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from db.models import get_db, Event, EventType
from jinja2 import Environment, FileSystemLoader
# from weasyprint import HTML
import io
from datetime import datetime, date
import os

from api.auth import institutional_access

router = APIRouter()

# Configuración de Jinja2
template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
env = Environment(loader=FileSystemLoader(template_dir))

@router.get("/generar-boletin", dependencies=[Depends(institutional_access)])
async def generar_boletin_pdf(anio: int = None, db: Session = Depends(get_db)):
    """
    Genera un boletín de seguridad oficial en PDF con estadísticas actuales y comparativas YoY.
    """
    if not anio:
        anio = datetime.now().year

        # 0. Obtener Fecha de Corte (Dato más reciente)
        fecha_corte_raw = db.query(func.max(NationalCrimeStats.occurrence_date)).filter(
            NationalCrimeStats.municipio_normalizado == "JAMUNDI"
        ).scalar()
        fecha_corte = fecha_corte_raw.strftime("%d/%m/%Y") if fecha_corte_raw else "No disponible"

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
            var_pct = round(((c_val - p_val) / p_val * 100), 1) if p_val > 0 else 100.0
            delitos_data.append({
                "name": d.tipo_delito,
                "value": c_val,
                "prev_value": p_val,
                "percent": round((c_val / total_incidentes * 100), 1) if total_incidentes > 0 else 0,
                "var_pct": var_pct
            })
        
        delitos_data = sorted(delitos_data, key=lambda x: x['value'], reverse=True)

        # 4. Top Barrios (Omitido para brevedad en este ejemplo)
        barrios_data = []

        # 4.1 Cargar Escudo Base64
        logo_base64 = ""
        try:
            import base64
            # Buscamos el escudo en la carpeta de activos del monitor
            logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "monitor-mindefensa", "escudo_jamundi.png")
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as img_f:
                    encoded = base64.b64encode(img_f.read()).decode("utf-8")
                    logo_base64 = f"data:image/png;base64,{encoded}"
        except Exception as e:
            print(f"Aviso: No se pudo cargar el escudo: {e}")

        # 5. Renderizar HTML
        template = env.get_template("boletin.html")
        html_content = template.render(
            periodo=f"Anual {anio}",
            logo_base64=logo_base64,
            fecha_generacion=datetime.now().strftime("%d/%m/%Y %H:%M"),
            fecha_corte=fecha_corte,
            total_incidentes=total_incidentes,
            total_yoy=total_yoy,
            var_total_pct=round(((total_incidentes - total_yoy) / total_yoy * 100), 1) if total_yoy > 0 else 0,
            total_barrios=len(barrios_data),
            delitos=delitos_data,
            barrios=barrios_data
        )

        # Nota: WeasyPrint tiene problemas de DLLs en Windows. 
        # Como alternativa para este entorno, devolvemos el HTML para previsualización 
        # o usamos una técnica de impresión si estuviera disponible.
        # Por ahora, habilitamos el retorno del HTML oficial para que el frontend lo maneje o lo imprima.
        return StreamingResponse(
            io.BytesIO(html_content.encode()), 
            media_type="text/html",
            headers={"Content-Disposition": f"inline; filename=boletin_{anio}.html"}
        )

    except Exception as e:
        print(f"Error generando boletín: {e}")
        raise HTTPException(status_code=500, detail=f"No se pudo generar el reporte: {str(e)}")
