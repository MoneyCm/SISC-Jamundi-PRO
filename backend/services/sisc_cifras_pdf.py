from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


AZUL = colors.HexColor("#281FD0")
AZUL_OSCURO = colors.HexColor("#0E2442")
AMARILLO = colors.HexColor("#FFE000")
GRIS = colors.HexColor("#F1F5F9")
BORDE = colors.HexColor("#CBD5E1")


def _text(value):
    return escape(str(value if value not in (None, "") else "Sin informacion"))


def _period(publication, key="period"):
    value = publication.get(key) or {}
    return f"{value.get('start', 'sin inicio')} a {value.get('end', 'sin corte')}"


def _value(value):
    return f"{value:,.0f}" if isinstance(value, (int, float)) else _text(value)


def _variation(item):
    value = item.get("variation_percentage")
    return f"{value:+.1f}%" if isinstance(value, (int, float)) else "No comparable"


def _table(rows, widths, header=True):
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    commands = [
        ("BOX", (0, 0), (-1, -1), 0.45, BORDE),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]
    if header:
        commands.extend([
            ("BACKGROUND", (0, 0), (-1, 0), AZUL_OSCURO),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
        ])
    table.setStyle(TableStyle(commands))
    return table


def build_sisc_cifras_pdf(publication: dict) -> bytes:
    """Genera el boletin publico detallado de Seguridad, comparacion y gestion."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.45 * cm,
        leftMargin=1.45 * cm,
        topMargin=1.25 * cm,
        bottomMargin=1.25 * cm,
    )
    styles = getSampleStyleSheet()
    eyebrow = ParagraphStyle("Eyebrow", parent=styles["Normal"], fontSize=8, leading=10, textColor=AZUL, spaceAfter=5)
    title = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=19, leading=23, textColor=AZUL_OSCURO, spaceAfter=4)
    page_title = ParagraphStyle("PageTitle", parent=styles["Heading2"], fontSize=15, leading=18, textColor=AZUL_OSCURO, spaceAfter=8)
    section = ParagraphStyle("Section", parent=styles["Heading3"], fontSize=10.5, leading=13, textColor=AZUL_OSCURO, spaceBefore=12, spaceAfter=6)
    body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9, leading=12, textColor=colors.HexColor("#334155"))
    small = ParagraphStyle("Small", parent=body, fontSize=7.5, leading=9.5, textColor=colors.HexColor("#64748B"))
    kpi = ParagraphStyle("Kpi", parent=styles["Heading1"], fontSize=30, leading=32, textColor=AZUL, alignment=1)

    indicators = publication.get("indicators") or []
    police = [item for item in indicators if item.get("source_code") == "POLICIA_SEMANAL"]
    conductas = [item for item in police if item.get("category") == "Conducta"][:7]
    barrios = [item for item in police if item.get("domain") == "TERRITORIO"][:6]
    total = next((item for item in police if item.get("indicator_code") == "seguridad.total"), None)
    inspections = [item for item in indicators if item.get("source_code") == "INSPECCIONES_RNMC"]
    family = [item for item in indicators if item.get("source_code") == "COMISARIAS_FAMILIA"]
    comparison_label = publication.get("comparison_label") or "periodo de comparacion"
    story = [
        Paragraph("ALCALDIA DE JAMUNDI | SECRETARIA DE SEGURIDAD Y CONVIVENCIA", eyebrow),
        Paragraph("BOLETIN ESTADISTICO DE SEGURIDAD Y CONVIVENCIA", title),
        Paragraph(f"Periodo: <b>{_text(_period(publication))}</b> | Comparacion: {_text(comparison_label)}", body),
        Spacer(1, 10),
    ]

    # Pagina 1: balance de seguridad y territorio.
    if total:
        kpi_table = Table([
            [Paragraph("HECHOS REGISTRADOS", section), Paragraph("COMPARACION", section)],
            [Paragraph(_value(total.get("value")), kpi), Paragraph(_value(total.get("comparison_value")), kpi)],
            [Paragraph(f"Corte: {_text(total.get('cutoff_date'))}", small), Paragraph(_variation(total), small)],
        ], colWidths=[8.7 * cm, 8.7 * cm])
        kpi_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF2FF")),
            ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#FFF9CC")),
            ("BOX", (0, 0), (-1, -1), 0.6, BORDE),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, BORDE),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.append(kpi_table)

    story.append(Paragraph("CONDUCTAS DEL PERIODO", section))
    conducta_rows = [["Conducta", "Actual", "Comparacion", "Variacion"]]
    for item in conductas:
        conducta_rows.append([_text(item.get("indicator_name")), _value(item.get("value")), _value(item.get("comparison_value")), _variation(item)])
    if len(conducta_rows) == 1:
        conducta_rows.append(["Sin conductas publicables", "-", "-", "-"])
    story.append(_table(conducta_rows, [8.2 * cm, 2.8 * cm, 3.2 * cm, 3.2 * cm]))

    story.append(Paragraph("TERRITORIOS CON MAYOR REGISTRO", section))
    barrio_rows = [["Barrio o sector", "Hechos registrados"]]
    barrio_rows.extend([[_text(item.get("indicator_name")), _value(item.get("value"))] for item in barrios])
    if len(barrio_rows) == 1:
        barrio_rows.append(["Sin concentraciones territoriales publicables", "-"])
    story.extend([
        _table(barrio_rows, [13.7 * cm, 4 * cm]),
        Spacer(1, 8),
        Paragraph("Fuente: SISC | Policia Nacional. Informacion agregada y anonimizada.", small),
    ])

    # Pagina 2: comparacion y lectura tecnica.
    story.extend([PageBreak(), Paragraph("02 | COMPARACION Y HALLAZGOS", page_title)])
    story.append(Paragraph(f"Comparacion de {_text(_period(publication))} frente a {_text(_period(publication, 'comparison_period'))}.", body))
    comparison_rows = [["Indicador", "Actual", "Anterior", "Dif. abs.", "Variacion"]]
    for item in [entry for entry in police if entry.get("comparison_value") is not None][:12]:
        comparison_rows.append([
            _text(item.get("indicator_name")),
            _value(item.get("value")),
            _value(item.get("comparison_value")),
            _value(item.get("variation_absolute")),
            _variation(item),
        ])
    if len(comparison_rows) == 1:
        comparison_rows.append(["Sin indicadores comparables", "-", "-", "-", "-"])
    story.append(_table(comparison_rows, [7.4 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm, 2.8 * cm]))
    story.append(Paragraph("LECTURA TECNICA", section))
    insights = publication.get("insights") or []
    if insights:
        for insight in insights[:6]:
            story.extend([Paragraph(f"<b>{_text(insight.get('title'))}:</b> {_text(insight.get('detail'))}", body), Spacer(1, 5)])
    else:
        story.append(Paragraph("No se generaron hallazgos comparables para el periodo.", body))
    blockers = (publication.get("governance") or {}).get("review_blockers") or []
    if blockers:
        story.append(Paragraph("ADVERTENCIAS DE COBERTURA", section))
        for blocker in blockers:
            story.append(Paragraph(f"- {_text(blocker)}", small))
    story.extend([Spacer(1, 10), Paragraph(f"Generado: {_text(publication.get('generated_at'))} | Version: {_text(publication.get('id'))}", small)])

    # Pagina 3: Inspecciones, Comisarias y trazabilidad.
    story.extend([PageBreak(), Paragraph("03 | GESTION INSTITUCIONAL", page_title)])
    story.append(Paragraph("INSPECCIONES DE POLICIA", section))
    inspection_rows = [["Indicador", "Valor", "Comparacion", "Corte"]]
    for item in inspections[:7]:
        inspection_rows.append([_text(item.get("indicator_name")), _value(item.get("value")), _value(item.get("comparison_value")), _text(item.get("cutoff_date"))])
    if len(inspection_rows) == 1:
        inspection_rows.append(["Sin actuaciones publicables para el periodo", "-", "-", "-"])
    story.append(_table(inspection_rows, [8 * cm, 2.8 * cm, 3.2 * cm, 3.7 * cm]))

    story.append(Paragraph("COMISARIAS DE FAMILIA", section))
    family_rows = [["Indicador agregado", "Valor", "Unidad", "Corte"]]
    for item in family[:6]:
        family_rows.append([_text(item.get("indicator_name")), _value(item.get("value")), _text(item.get("unit")), _text(item.get("cutoff_date"))])
    if len(family_rows) == 1:
        family_rows.append(["Sin corte mensual publicable para el periodo", "-", "-", "-"])
    story.append(_table(family_rows, [8 * cm, 2.5 * cm, 3.5 * cm, 3.7 * cm]))

    story.append(Paragraph("FUENTES Y COBERTURA", section))
    source_rows = [["Fuente", "Corte", "Cobertura", "Calidad"]]
    for source in publication.get("sources") or []:
        source_rows.append([_text(source.get("name")), _text(source.get("last_cutoff_date")), _text(source.get("coverage_status")), _text(source.get("quality_status"))])
    story.append(_table(source_rows, [7.5 * cm, 3.5 * cm, 3.4 * cm, 3.3 * cm]))
    story.extend([
        Spacer(1, 10),
        Paragraph("Lectura correcta: Seguridad, Inspecciones y Comisarias describen gestiones distintas y sus valores no deben sumarse entre si.", body),
        Spacer(1, 6),
        Paragraph("Documento publico generado automaticamente por SISC Jamundi. No contiene datos personales ni registros individuales.", small),
    ])

    doc.build(story)
    result = buffer.getvalue()
    buffer.close()
    return result
