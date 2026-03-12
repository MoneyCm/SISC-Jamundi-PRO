from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from db.models import get_db, Event
import io
import os
from datetime import datetime, date
import base64
import re
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable

router = APIRouter()

AZUL = colors.HexColor("#281FD0")
AMARILLO = colors.HexColor("#FFE000")
GRIS_FONDO = colors.HexColor("#F4F4F8")

@router.get("/generar-boletin")
async def generar_boletin_pdf(
    fuente: str = Query("MINDEFENSA"),
    fecha_inicio: date = Query(None),
    fecha_fin: date = Query(None),
    token: str = Query(None),
    db: Session = Depends(get_db)
):
    # 1. Seguridad Local/Prod
    is_local = os.getenv("PORT") == "8000" or "localhost" in str(os.getenv("DATABASE_URL", ""))
    if not is_local:
        if token:
            try:
                from core.security import decode_access_token
                decode_access_token(token)
            except: raise HTTPException(status_code=401, detail="Sesión inválida")
        else: raise HTTPException(status_code=401)

    # 2. Fechas y Fuente
    if not fecha_inicio: fecha_inicio = date(datetime.now().year, 1, 1)
    if not fecha_fin: fecha_fin = date.today()
    
    # Calcular periodo año anterior
    try:
        fecha_inicio_prev = date(fecha_inicio.year - 1, fecha_inicio.month, fecha_inicio.day)
        fecha_fin_prev = date(fecha_fin.year - 1, fecha_fin.month, fecha_fin.day)
    except ValueError: # Manejo de años bisiestos (29 feb)
        fecha_inicio_prev = date(fecha_inicio.year - 1, fecha_inicio.month, fecha_inicio.day - 1)
        fecha_fin_prev = date(fecha_fin.year - 1, fecha_fin.month, fecha_fin.day - 1)

    source_map = {
        "MINDEFENSA": "MINDEFENSA%", 
        "POLICIA_PORTAL": "POLICIA%", 
        "POLICIA_SEMANAL": "POLICIA_SEMANAL%"
    }
    prefix = source_map.get(fuente, "MINDEFENSA%")
    fuente_label = fuente.replace("_", " ")

    # 3. Consulta Periodo Actual
    datos_actual = db.query(
        Event.descripcion.label("delito"),
        func.count(Event.id).label("total")
    ).filter(
        Event.occurrence_date >= fecha_inicio,
        Event.occurrence_date <= fecha_fin,
        Event.source_name.like(prefix)
    ).group_by(Event.descripcion).all()

    # 4. Consulta Periodo Anterior
    datos_prev = db.query(
        Event.descripcion.label("delito"),
        func.count(Event.id).label("total")
    ).filter(
        Event.occurrence_date >= fecha_inicio_prev,
        Event.occurrence_date <= fecha_fin_prev,
        Event.source_name.like(prefix)
    ).group_by(Event.descripcion).all()

    # 5. Construcción del PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.2*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    
    # Estilos Personalizados
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=22, fontWeight='BOLD', textColor=colors.black, spaceAfter=2)
    sub_style = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=10, textColor=AZUL, fontWeight='BOLD', textTransform='uppercase')
    meta_style = ParagraphStyle('Meta', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=2)
    
    content = []

    # --- ENCABEZADO ---
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "escudo_jamundi.png")
    
    logo_img = Image(logo_path, width=1.6*cm, height=2.1*cm) if os.path.exists(logo_path) else Paragraph("", styles['Normal'])
    title_block = [Paragraph("SISC JAMUNDÍ", title_style), Paragraph("Observatorio del Delito", sub_style)]
    meta_block = [
        Paragraph(f"<b>BOLETÍN COMPARATIVO</b>", ParagraphStyle('B', parent=meta_style, fontSize=9, textColor=colors.black)),
        Paragraph(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", meta_style),
        Paragraph(f"Fuente: {fuente_label}", meta_style)
    ]
    
    header_table = Table([[logo_img, title_block, meta_block]], colWidths=[2*cm, 10*cm, 6*cm])
    header_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    content.append(header_table)
    content.append(HRFlowable(width="100%", thickness=2, color=AMARILLO, spaceBefore=10, spaceAfter=20))

    # --- TARJETAS DE RESUMEN ---
    total_actual = sum(d.total for d in datos_actual)
    total_prev = sum(d.total for d in datos_prev)
    var_total = ((total_actual - total_prev) / total_prev * 100) if total_prev > 0 else 0
    color_var = colors.red if var_total > 0 else colors.green if var_total < 0 else colors.grey

    summary_data = [
        [Paragraph(f"<b>PERIODO ACTUAL</b><br/><font size=14 color='#281FD0'>{total_actual}</font><br/><font size=8>{fecha_inicio} al {fecha_fin}</font>", styles['Normal']),
         Paragraph(f"<b>AÑO ANTERIOR</b><br/><font size=14 color='#64748b'>{total_prev}</font><br/><font size=8>{fecha_inicio_prev} al {fecha_fin_prev}</font>", styles['Normal']),
         Paragraph(f"<b>VARIACIÓN</b><br/><font size=14 color='{color_var.hexval()}'>{'+' if var_total > 0 else ''}{round(var_total, 1)}%</font>", styles['Normal'])]
    ]
    st = Table(summary_data, colWidths=[6*cm, 6*cm, 6*cm])
    st.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), GRIS_FONDO),
        ('BOX', (0,0), (-1,-1), 1, colors.lightgrey),
        ('ROUNDEDCORNERS', [10, 10, 10, 10]),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 15),
        ('BOTTOMPADDING', (0,0), (-1,-1), 15),
    ]))
    content.append(st)
    content.append(Spacer(1, 30))

    # --- TABLA DE DATOS COMPARATIVA ---
    if not datos_actual and not datos_prev:
        content.append(Paragraph("<br/><br/><b>AVISO:</b> No se encontraron registros cargados para esta fuente en los periodos seleccionados.", styles['Normal']))
    else:
        content.append(Paragraph("ANÁLISIS COMPARATIVO INTERANUAL", ParagraphStyle('H2', parent=styles['Heading2'], textColor=AZUL, borderLeftWidth=5, borderLeftColor=AMARILLO, leftIndent=10)))
        content.append(Spacer(1, 10))
        
        table_data = [[
            Paragraph("<b>INDICADOR / DELITO</b>", styles['Normal']), 
            Paragraph(f"<b>{fecha_fin.year}</b>", styles['Normal']), 
            Paragraph(f"<b>{fecha_fin.year - 1}</b>", styles['Normal']), 
            Paragraph("<b>VAR %</b>", styles['Normal'])
        ]]
        
        # Agrupación y Cruce
        agrupados_actual = {}
        for d in datos_actual:
            match = re.search(r'\[(.*?)\]', d.delito)
            clean_label = match.group(1).upper() if match else d.delito.upper()
            agrupados_actual[clean_label] = agrupados_actual.get(clean_label, 0) + d.total

        agrupados_prev = {}
        for d in datos_prev:
            match = re.search(r'\[(.*?)\]', d.delito)
            clean_label = match.group(1).upper() if match else d.delito.upper()
            agrupados_prev[clean_label] = agrupados_prev.get(clean_label, 0) + d.total

        # Unir todos los delitos que aparecen en alguno de los dos
        todos_delitos = sorted(list(set(agrupados_actual.keys()) | set(agrupados_prev.keys())))
            
        for label in todos_delitos:
            v_act = agrupados_actual.get(label, 0)
            v_prev = agrupados_prev.get(label, 0)
            variacion = ((v_act - v_prev) / v_prev * 100) if v_prev > 0 else (100 if v_act > 0 else 0)
            
            # Color por variacion
            var_text = f"{'+' if variacion > 0 else ''}{round(variacion, 1)}%"
            if variacion > 0:
                p_var = Paragraph(f"<font color='red'>{var_text}</font>", styles['Normal'])
            elif variacion < 0:
                p_var = Paragraph(f"<font color='green'>{var_text}</font>", styles['Normal'])
            else:
                p_var = Paragraph(var_text, styles['Normal'])

            table_data.append([label, str(v_act), str(v_prev), p_var])
        
        t = Table(table_data, colWidths=[9*cm, 3*cm, 3*cm, 3*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), AZUL),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRIS_FONDO]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('LINEBELOW', (0, 0), (-1, 0), 2, AMARILLO),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))
        content.append(t)

    # --- PIE DE PÁGINA ---
    content.append(Spacer(1, 40))
    footer_text = "<b>ALCALDÍA DE JAMUNDÍ - VALLE DEL CAUCA</b><br/>Secretaría de Seguridad y Convivencia Ciudadana<br/><i>Documento Oficial Generado por el Sistema SISC</i>"
    content.append(Paragraph(footer_text, ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, alignment=1, textColor=colors.grey)))

    doc.build(content)
    pdf_out = buffer.getvalue()
    buffer.close()

    return Response(
        content=pdf_out,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Reporte_SISC_Comparativo_{fuente}.pdf"}
    )
