from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from db.models import get_db, Event, User
import io
import os
from datetime import datetime, date
import base64
import re
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable, PageBreak
from services.alert_engine import AlertEngine
from api.ia import call_gemini, call_mistral, AI_PROVIDER
from db.models_hechos_seguridad import HechoSeguridad
from services.hechos_metrics import hechos_unicos_expr
from db.models import EventType
from api.auth import require_role

router = APIRouter()

AZUL_OSCURO = colors.HexColor("#0f172a") # Slate 900
AZUL_ESTRATEGICO = colors.HexColor("#1e293b") # Slate 800
AZUL_VIBRANTE = colors.HexColor("#2563eb") # Blue 600
AMARILLO_INSTITUCIONAL = colors.HexColor("#fbbf24") # Amber 400
GRIS_PREMIUM = colors.HexColor("#f8fafc") # Slate 50
BORDE_SUTIL = colors.HexColor("#e2e8f0") # Slate 200

@router.get("/generar-boletin")
async def generar_boletin_pdf(
    fuente: str = Query("MINDEFENSA"),
    fecha_inicio: date = Query(None),
    fecha_fin: date = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ANALYST", "DIRECTIVE", "FUNC_ADMIN"])),
):
    # Fechas y fuente
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

    if fuente == "POLICIA_SEMANAL":
        from db.models_hechos_seguridad import HechoSeguridad
        # 3. Consulta Periodo Actual
        datos_actual = db.query(
            HechoSeguridad.conducta_estandar.label("delito"),
            hechos_unicos_expr().label("total")
        ).filter(
            HechoSeguridad.fecha_evento >= fecha_inicio,
            HechoSeguridad.fecha_evento <= fecha_fin,
            HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL"
        ).group_by(HechoSeguridad.conducta_estandar).all()

        # 4. Consulta Periodo Anterior
        datos_prev = db.query(
            HechoSeguridad.conducta_estandar.label("delito"),
            hechos_unicos_expr().label("total")
        ).filter(
            HechoSeguridad.fecha_evento >= fecha_inicio_prev,
            HechoSeguridad.fecha_evento <= fecha_fin_prev,
            HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL"
        ).group_by(HechoSeguridad.conducta_estandar).all()
    else:
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

    monthly_data = []
    zone_data = []
    neighborhood_data = []
    if fuente == "POLICIA_SEMANAL":
        base_filter = [HechoSeguridad.fecha_evento >= fecha_inicio, HechoSeguridad.fecha_evento <= fecha_fin, HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL"]
        monthly_data = db.query(func.extract('month', HechoSeguridad.fecha_evento).label("month"), hechos_unicos_expr().label("total")).filter(*base_filter).group_by(func.extract('month', HechoSeguridad.fecha_evento)).order_by(func.extract('month', HechoSeguridad.fecha_evento)).all()
        zone_data = db.query(HechoSeguridad.zona.label("name"), hechos_unicos_expr().label("total")).filter(*base_filter, HechoSeguridad.zona.isnot(None), HechoSeguridad.zona != "").group_by(HechoSeguridad.zona).order_by(hechos_unicos_expr().desc()).all()
        neighborhood_data = db.query(HechoSeguridad.barrio_normalizado.label("name"), hechos_unicos_expr().label("total")).filter(*base_filter, HechoSeguridad.barrio_normalizado.isnot(None), HechoSeguridad.barrio_normalizado != "").group_by(HechoSeguridad.barrio_normalizado).having(hechos_unicos_expr() >= 3).order_by(hechos_unicos_expr().desc()).limit(10).all()
    # 5. Construcción del PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.2*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()

    # Estilos Personalizados
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=24, fontWeight='BLACK', textColor=AZUL_OSCURO, spaceAfter=2, leading=28)
    sub_style = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=11, textColor=AZUL_VIBRANTE, fontWeight='BLACK', textTransform='uppercase', tracking=1.5)
    meta_style = ParagraphStyle('Meta', parent=styles['Normal'], fontSize=9, textColor=AZUL_ESTRATEGICO, alignment=2, leading=11)

    content = []

    # --- ENCABEZADO ---
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "escudo_jamundi.png")

    logo_img = Image(logo_path, width=1.8*cm, height=2.3*cm) if os.path.exists(logo_path) else Paragraph("", styles['Normal'])

    title_block = [
        Paragraph("RESUMEN CIUDADANO SISC", title_style),
        Paragraph("SEGURIDAD Y CONVIVENCIA - DATOS ABIERTOS AGREGADOS", sub_style)
    ]

    meta_block = [
        Paragraph(f"<b>RESUMEN CIUDADANO DE SEGURIDAD</b>", ParagraphStyle('B', parent=meta_style, fontSize=10, textColor=AZUL_OSCURO)),
        Spacer(1, 2),
        Paragraph(f"Corte: {fecha_fin.strftime('%d/%m/%Y')}", meta_style),
        Paragraph(f"Fuente oficial: {fuente_label}", meta_style)
    ]

    header_table = Table([[logo_img, title_block, meta_block]], colWidths=[2.5*cm, 10*cm, 5.5*cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
    ]))
    content.append(header_table)
    content.append(HRFlowable(width="100%", thickness=3.5, color=AMARILLO_INSTITUCIONAL, spaceBefore=8, spaceAfter=25))

    # --- TARJETAS DE RESUMEN ---
    total_actual = sum(d.total for d in datos_actual)
    total_prev = sum(d.total for d in datos_prev)
    var_total = ((total_actual - total_prev) / total_prev * 100) if total_prev > 0 else 0
    color_var = colors.red if var_total > 0 else colors.green if var_total < 0 else colors.grey
    trend_text = "aumento" if var_total > 0 else "disminuyo" if var_total < 0 else "se mantuvo estable"
    citizen_summary = f"Entre {fecha_inicio.strftime('%d/%m/%Y')} y {fecha_fin.strftime('%d/%m/%Y')} se registraron <b>{total_actual}</b> casos unicos agregados. Frente al mismo periodo de {fecha_fin_prev.year}, el total {trend_text} <b>{abs(var_total):.1f}%</b>."

    content.append(Paragraph("LECTURA CIUDADANA", ParagraphStyle('CitizenTitle', parent=styles['Heading2'], fontSize=13, textColor=AZUL_OSCURO, spaceAfter=7)))
    content.append(Paragraph(citizen_summary, ParagraphStyle('CitizenText', parent=styles['Normal'], fontSize=10.5, leading=15, textColor=AZUL_ESTRATEGICO, backColor=GRIS_PREMIUM, borderColor=BORDE_SUTIL, borderWidth=0.5, borderPadding=10, spaceAfter=16)))

    card_label = ParagraphStyle('CardLabel', parent=styles['Normal'], fontSize=9, leading=11, textColor=colors.HexColor("#475569"), alignment=1)
    card_value = ParagraphStyle('CardValue', parent=styles['Normal'], fontSize=22, leading=27, textColor=AZUL_OSCURO, alignment=1)
    card_variation = ParagraphStyle('CardVariation', parent=card_value, textColor=color_var)
    summary_data = [[Paragraph(f"CASOS {fecha_fin_prev.year}", card_label), Paragraph(f"CASOS {fecha_fin.year}", card_label), Paragraph("VARIACION", card_label)], [Paragraph(str(total_prev), card_value), Paragraph(str(total_actual), card_value), Paragraph(f"{'+' if var_total > 0 else ''}{var_total:.1f}%", card_variation)]]
    st = Table(summary_data, colWidths=[6*cm, 6*cm, 6*cm], rowHeights=[0.7*cm, 1.15*cm])
    st.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), GRIS_PREMIUM), ('BOX', (0,0), (-1,-1), 0.5, BORDE_SUTIL), ('LINEABOVE', (0,1), (-1,1), 0.5, BORDE_SUTIL), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5)]))
    content.append(st)
    content.append(Spacer(1, 24))

    # --- TABLA DE DATOS COMPARATIVA ---
    if not datos_actual and not datos_prev:
        content.append(Paragraph("<br/><br/><b>AVISO:</b> No se encontraron registros cargados para esta fuente en los periodos seleccionados.", styles['Normal']))
    else:
        section_title = Paragraph("ANÁLISIS COMPARATIVO POR MODALIDAD", ParagraphStyle('H2', parent=styles['Heading2'], fontSize=14, textColor=AZUL_OSCURO, spaceAfter=12))
        content.append(section_title)

        table_data = [[
            Paragraph("<font color='white'><b>INDICADOR / MODALIDAD</b></font>", styles['Normal']),
            Paragraph(f"<font color='white'><b>{fecha_fin.year}</b></font>", styles['Normal']),
            Paragraph(f"<font color='white'><b>{fecha_fin.year - 1}</b></font>", styles['Normal']),
            Paragraph("<font color='white'><b>Δ %</b></font>", styles['Normal'])
        ]]

        # Agrupación y Cruce
        def clean_label_fn(txt):
            if not txt: return "SIN ESPECIFICAR"
            # Remover corchetes
            match = re.search(r'\[(.*?)\]', txt)
            txt = match.group(1) if match else txt
            # Remover prefijos comunes
            for prefix in ["Local Sync:", "MINDEFENSA:", "POLICIA:", "REPORT:"]:
                if txt.upper().startswith(prefix.upper()):
                    txt = txt[len(prefix):].strip()
            return txt.upper()

        agrupados_actual = {}
        for d in datos_actual:
            label = clean_label_fn(d.delito)
            agrupados_actual[label] = agrupados_actual.get(label, 0) + d.total

        agrupados_prev = {}
        for d in datos_prev:
            label = clean_label_fn(d.delito)
            agrupados_prev[label] = agrupados_prev.get(label, 0) + d.total

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

        t = Table(table_data, colWidths=[9.5*cm, 2.5*cm, 2.5*cm, 3.5*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), AZUL_OSCURO),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRIS_PREMIUM]),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDE_SUTIL),
            ('LINEBELOW', (0, 0), (-1, 0), 2.5, AMARILLO_INSTITUCIONAL),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        content.append(t)

    if monthly_data or zone_data or neighborhood_data:
        content.append(PageBreak())
        content.append(Paragraph("DATOS DESTACADOS DEL PERIODO", ParagraphStyle('DetailTitle', parent=styles['Heading2'], fontSize=14, textColor=AZUL_OSCURO, spaceAfter=10)))
        content.append(Paragraph("Estas tablas amplian el resumen con datos agregados. Para descargar el conjunto completo y reutilizable, use Datos abiertos CSV en el tablero ciudadano.", ParagraphStyle('DetailIntro', parent=styles['Normal'], fontSize=9.5, leading=13, textColor=AZUL_ESTRATEGICO, spaceAfter=12)))
        month_names = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        def public_table(rows, title, color):
            table = Table(rows, colWidths=[9*cm, 4*cm])
            table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), color), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('ALIGN', (1,0), (-1,-1), 'CENTER'), ('GRID', (0,0), (-1,-1), 0.4, BORDE_SUTIL), ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, GRIS_PREMIUM]), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('TOPPADDING', (0,0), (-1,-1), 7), ('BOTTOMPADDING', (0,0), (-1,-1), 7)]))
            content.append(Paragraph(title, ParagraphStyle(f'{title}Style', parent=styles['Heading2'], fontSize=11, textColor=AZUL_OSCURO, spaceAfter=6)))
            content.append(table)
            content.append(Spacer(1, 16))
        if monthly_data:
            public_table([["MES", "CASOS UNICOS"]] + [[month_names[int(item.month) - 1], str(item.total)] for item in monthly_data], "TENDENCIA MENSUAL", AZUL_OSCURO)
        if zone_data:
            public_table([["ZONA", "CASOS UNICOS"]] + [[str(item.name), str(item.total)] for item in zone_data], "DISTRIBUCION POR ZONA", AZUL_ESTRATEGICO)
        if neighborhood_data:
            public_table([["BARRIO PUBLICADO", "CASOS UNICOS"]] + [[str(item.name), str(item.total)] for item in neighborhood_data], "BARRIOS CON DATOS AGREGADOS", AZUL_VIBRANTE)
            content.append(Paragraph("Solo se incluyen barrios con al menos 3 casos agregados. No se publican direcciones ni registros individuales.", ParagraphStyle('NeighborhoodNote', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor("#64748b"), spaceBefore=2)))

    content.append(Spacer(1, 20))
    content.append(Paragraph("TRANSPARENCIA Y PRIVACIDAD", ParagraphStyle('PrivacyTitle', parent=styles['Heading2'], fontSize=12, textColor=AZUL_OSCURO, spaceAfter=6)))
    privacy_text = "Este resumen usa datos agregados de la fuente indicada y compara periodos equivalentes. No incluye nombres, direcciones, identificadores ni detalles de casos individuales. Los resultados sirven para comprender tendencias generales y no para reportar emergencias. Para una emergencia, llame al 123."
    content.append(Paragraph(privacy_text, ParagraphStyle('PrivacyText', parent=styles['Normal'], fontSize=9.5, leading=13, textColor=AZUL_ESTRATEGICO, spaceAfter=12)))

    # --- PIE DE PAGINA ---
    content.append(Spacer(1, 40))
    footer_text = "<b>ALCALDÍA DE JAMUNDÍ - VALLE DEL CAUCA</b><br/>Secretaría de Seguridad y Convivencia Ciudadana<br/><i>Documento Oficial Generado por el Sistema SISC</i>"
    content.append(Paragraph(footer_text, ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, alignment=1, textColor=colors.grey)))

    doc.build(content)
    pdf_out = buffer.getvalue()
    buffer.close()
    return Response(
        content=pdf_out,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=Resumen_Ciudadano_SISC.pdf"},
    )
@router.get("/generar-boletin-ejecutivo")
async def generar_boletin_ejecutivo(
    fecha_inicio: date = Query(None),
    fecha_fin: date = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ANALYST", "DIRECTIVE", "FUNC_ADMIN"])),
):
    """
    Genera el Boletín Estratégico de la Secretaría de Seguridad con IA.
    """
    # 1. Periodos (Año Actual vs Año Anterior)
    fin_act = fecha_fin or date.today()
    inicio_act = fecha_inicio or date(fin_act.year, 1, 1)
    if inicio_act > fin_act:
        raise HTTPException(status_code=400, detail="La fecha inicial no puede ser posterior a la fecha final.")
    try:
        inicio_prev = inicio_act.replace(year=inicio_act.year - 1)
        fin_prev = fin_act.replace(year=fin_act.year - 1)
    except ValueError:
        inicio_prev = inicio_act.replace(year=inicio_act.year - 1, day=28)
        fin_prev = fin_act.replace(year=fin_act.year - 1, day=28)

    # 2. Obtener Datos Deduplicados (SAT Logic)
    # Categorías a reportar
    categorias = ['HOMICIDIO', 'HURTO', 'VIF', 'LESIONES', 'EXTORSION']

    # Obtener conteos unificados
    stats_act = AlertEngine.get_unified_counts(db, inicio_act, fin_act)
    stats_prev = AlertEngine.get_unified_counts(db, inicio_prev, fin_prev)

    # 3. Generar Insight Ejecutivo con IA
    total_act = sum(stats_act.values())
    total_prev = sum(stats_prev.values())
    var_total = ((total_act - total_prev) / total_prev * 100) if total_prev > 0 else 0

    prompt_exec = f"""
    Como analista de la Secretaría de Seguridad de Jamundí, resume el panorama de seguridad actual:
    - Incidentes totales entre {inicio_act.isoformat()} y {fin_act.isoformat()}: {total_act} (Variación: {var_total:.1f}% frente al mismo periodo de {fin_act.year-1})
    - Homicidios: {stats_act.get('HOMICIDIO', 0)}
    - Hurtos: {stats_act.get('HURTO', 0)}
    SÉ BREVE Y ESTRATÉGICO. Máximo 50 palabras. Tono institucional.
    """
    try:
        if AI_PROVIDER == "MISTRAL": insight_exec = await call_mistral(prompt_exec)
        else: insight_exec = await call_gemini(prompt_exec)
    except: insight_exec = "Resumen estratégico temporalmente no disponible por alta demanda de procesos."

    # 4. Construcción del PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1*cm, bottomMargin=1*cm)
    styles = getSampleStyleSheet()

    # Estilos Premium
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=22, textColor=AZUL_OSCURO, spaceAfter=2)
    insight_style = ParagraphStyle('Insight', parent=styles['Normal'], fontSize=10, textColor=AZUL_ESTRATEGICO, italic=True, leading=14, leftIndent=10, borderLeftColor=AZUL_VIBRANTE, borderLeftWidth=2, borderPadding=5)

    content = []

    # Header
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "escudo_jamundi.png")
    logo_img = Image(logo_path, width=1.5*cm, height=2*cm) if os.path.exists(logo_path) else Paragraph("", styles['Normal'])
    header_data = [[logo_img, [Paragraph("RESUMEN CIUDADANO SISC", title_style), Paragraph("BOLETÍN ESTRATÉGICO DE SEGURIDAD", styles['Normal'])], Paragraph(f"Fecha: {fin_act.strftime('%d/%m/%y')}<br/>Corte: DATOS UNIFICADOS", styles['Normal'])]]
    t_header = Table(header_data, colWidths=[2*cm, 12*cm, 4*cm])
    t_header.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    content.append(t_header)
    content.append(HRFlowable(width="100%", thickness=3, color=AMARILLO_INSTITUCIONAL, spaceBefore=4, spaceAfter=20))

    # Resumen Ejecutivo IA
    content.append(Paragraph("PERSPECTIVA ESTRATÉGICA (IA)", ParagraphStyle('H', parent=styles['Heading2'], fontSize=12, textColor=AZUL_VIBRANTE)))
    content.append(Paragraph(insight_exec, insight_style))
    content.append(Spacer(1, 20))

    # Tabla Comparativa Unificada
    content.append(Paragraph("INDICADORES DE IMPACTO (CONSOLIDADO)", ParagraphStyle('H', parent=styles['Heading2'], fontSize=12)))
    table_data = [[Paragraph("<font color='white'><b>CATEGORÍA</b></font>", styles['Normal']), Paragraph("<font color='white'><b>ACTUAL</b></font>", styles['Normal']), Paragraph("<font color='white'><b>PREVIO</b></font>", styles['Normal']), Paragraph("<font color='white'><b>VAR %</b></font>", styles['Normal'])]]

    for cat in categorias:
        v_act = stats_act.get(cat, 0)
        v_prev = stats_prev.get(cat, 0)
        var = ((v_act - v_prev) / v_prev * 100) if v_prev > 0 else 0
        color = "red" if var > 0 else "green" if var < 0 else "black"
        table_data.append([cat, str(v_act), str(v_prev), Paragraph(f"<font color='{color}'>{var:+.1f}%</font>", styles['Normal'])])

    t_main = Table(table_data, colWidths=[8*cm, 3*cm, 3*cm, 4*cm])
    t_main.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), AZUL_OSCURO),
        ('GRID', (0,0), (-1,-1), 0.5, BORDE_SUTIL),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 10),
    ]))
    content.append(t_main)
    content.append(Spacer(1, 30))

    # Hotspots Territoriales
    content.append(Paragraph("MAPA DE CALOR: ZONAS DE ATENCIÓN", ParagraphStyle('H', parent=styles['Heading2'], fontSize=12)))
    top_barrios = db.query(HechoSeguridad.barrio_normalizado, hechos_unicos_expr()).filter(
        HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
        HechoSeguridad.fecha_evento >= inicio_act,
        HechoSeguridad.fecha_evento <= fin_act,
        HechoSeguridad.barrio_normalizado.isnot(None),
        HechoSeguridad.barrio_normalizado != "",
        ~func.upper(HechoSeguridad.barrio_normalizado).like("%PENDIENTE%"),
        ~func.upper(HechoSeguridad.barrio_normalizado).like("%POR ASIGNAR%"),
        ~func.upper(HechoSeguridad.barrio_normalizado).like("%NO APLICA%"),
        ~func.upper(HechoSeguridad.barrio_normalizado).like("%NAN%"),
    ).group_by(HechoSeguridad.barrio_normalizado).order_by(hechos_unicos_expr().desc()).limit(5).all()

    b_data = [["BARRIO / ZONA", "INCIDENTES"]]
    for b_name, b_count in top_barrios:
        if b_name: b_data.append([b_name, str(b_count)])

    t_barrios = Table(b_data, colWidths=[13*cm, 5*cm])
    t_barrios.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), AZUL_ESTRATEGICO),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, BORDE_SUTIL),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('ALIGN', (1,1), (1,-1), 'CENTER'),
    ]))
    content.append(t_barrios)

    content.append(Spacer(1, 40))
    footer = f"Reporte automático generado por SISC Jamundí - Inteligencia para la Secretaría de Seguridad."
    content.append(Paragraph(footer, ParagraphStyle('F', parent=styles['Normal'], fontSize=8, alignment=1, textColor=colors.grey)))

    doc.build(content)
    pdf_out = buffer.getvalue()
    buffer.close()

    return Response(
        content=pdf_out,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Boletin_Ejecutivo_SISC_{fin_act.strftime('%Y%m%d')}.pdf"}
    )
