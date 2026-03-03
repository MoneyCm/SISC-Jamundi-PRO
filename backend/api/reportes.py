from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from db.models import get_db, Event
import io
import os
from datetime import datetime, date
import base64
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
    
    source_map = {"MINDEFENSA": "MINDEFENSA%", "POLICIA_PORTAL": "POLICIA%", "POLICIA_SEMANAL": "SEMANAL%"}
    prefix = source_map.get(fuente, "MINDEFENSA%")
    fuente_label = fuente.replace("_", " ")

    # 3. Consulta
    datos_raw = db.query(
        Event.descripcion.label("delito"),
        func.count(Event.id).label("total")
    ).filter(
        Event.occurrence_date >= fecha_inicio,
        Event.occurrence_date <= fecha_fin,
        Event.source_name.like(prefix)
    ).group_by(Event.descripcion).all()

    # 4. Construcción del PDF
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
    
    header_data = []
    col_widths = [2*cm, 10*cm, 6*cm]
    
    logo_img = Image(logo_path, width=1.6*cm, height=2.1*cm) if os.path.exists(logo_path) else Paragraph("", styles['Normal'])
    title_block = [Paragraph("SISC JAMUNDÍ", title_style), Paragraph("Observatorio del Delito", sub_style)]
    meta_block = [
        Paragraph(f"<b>BOLETÍN OFICIAL</b>", ParagraphStyle('B', parent=meta_style, fontSize=9, textColor=colors.black)),
        Paragraph(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", meta_style),
        Paragraph(f"Fuente: {fuente_label}", meta_style)
    ]
    
    header_table = Table([[logo_img, title_block, meta_block]], colWidths=col_widths)
    header_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    content.append(header_table)
    content.append(HRFlowable(width="100%", thickness=2, color=AMARILLO, spaceBefore=10, spaceAfter=20))

    # --- TARJETAS DE RESUMEN ---
    total_casos = sum(d.total for d in datos_raw)
    summary_data = [
        [Paragraph(f"<b>FECHA DE CORTE</b><br/><font size=14 color='#281FD0'>{fecha_fin}</font>", styles['Normal']),
         Paragraph(f"<b>TOTAL INCIDENTES</b><br/><font size=14 color='#281FD0'>{total_casos}</font>", styles['Normal']),
         Paragraph(f"<b>PERIODO</b><br/><font size=9>{fecha_inicio} al {fecha_fin}</font>", styles['Normal'])]
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

    # --- TABLA DE DATOS ---
    if not datos_raw:
        content.append(Paragraph("<br/><br/><b>AVISO:</b> No se encontraron registros cargados para esta fuente.", styles['Normal']))
    else:
        content.append(Paragraph("ANÁLISIS POR INDICADOR DE CRIMINALIDAD", ParagraphStyle('H2', parent=styles['Heading2'], textColor=AZUL, borderLeftWidth=5, borderLeftColor=AMARILLO, leftIndent=10)))
        content.append(Spacer(1, 10))
        
        table_data = [[Paragraph("<b>TIPO DE DELITO</b>", styles['Normal']), Paragraph("<b>CANTIDAD</b>", styles['Normal']), Paragraph("<b>PARTICIPACIÓN</b>", styles['Normal'])]]
        for d in sorted(datos_raw, key=lambda x: x.total, reverse=True):
            label = d.delito.replace("Carga Directa: ", "").replace("Local Sync: ", "").replace("HURTO ", "HURTO A ")
            pct = round((d.total / total_casos * 100), 1) if total_casos > 0 else 0
            table_data.append([label, str(d.total), f"{pct}%"])
        
        t = Table(table_data, colWidths=[10*cm, 4*cm, 4*cm])
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
        headers={"Content-Disposition": f"attachment; filename=Reporte_SISC_{fuente}.pdf"}
    )
