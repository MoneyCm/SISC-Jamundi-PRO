from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


AZUL = colors.HexColor("#281FD0")
AZUL_OSCURO = colors.HexColor("#0F172A")
AMARILLO = colors.HexColor("#FFE000")
GRIS = colors.HexColor("#F1F5F9")
BORDE = colors.HexColor("#CBD5E1")


def _text(value):
    return escape(str(value or "Sin informacion"))


def _period(publication, key):
    value = publication.get(key) or {}
    return f"{value.get('start', 'sin inicio')} a {value.get('end', 'sin corte')}"


def build_sisc_cifras_pdf(publication: dict) -> bytes:
    """Crea un boletin PDF a partir de indicadores ya filtrados como publicables."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.35 * cm,
        bottomMargin=1.4 * cm,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("SiscTitle", parent=styles["Heading1"], fontSize=23, leading=27, textColor=AZUL_OSCURO, spaceAfter=3)
    eyebrow = ParagraphStyle("SiscEyebrow", parent=styles["Normal"], fontSize=8.5, leading=11, textColor=AZUL, spaceAfter=7)
    body = ParagraphStyle("SiscBody", parent=styles["Normal"], fontSize=9.5, leading=13, textColor=AZUL_OSCURO)
    small = ParagraphStyle("SiscSmall", parent=body, fontSize=8, leading=10, textColor=colors.HexColor("#475569"))
    section = ParagraphStyle("SiscSection", parent=styles["Heading2"], fontSize=12, leading=15, textColor=AZUL_OSCURO, spaceBefore=16, spaceAfter=7)

    period = _period(publication, "period")
    comparison = _period(publication, "comparison_period")
    comparison_label = publication.get("comparison_label") or "periodo de comparacion"
    story = [
        Paragraph("ALCALDIA DE JAMUNDI | SECRETARIA DE SEGURIDAD Y CONVIVENCIA", eyebrow),
        Paragraph("SISC EN CIFRAS", title),
        Paragraph(f"Boletin institucional para el periodo <b>{_text(period)}</b>.", body),
        Spacer(1, 9),
    ]

    source_lines = []
    for source in publication.get("sources", []):
        if source.get("included") is False:
            continue
        cutoff = source.get("last_cutoff_date") or "sin corte informado"
        note = source.get("status_note")
        line = f"<b>{_text(source.get('name'))}</b>: corte { _text(cutoff) }."
        if note:
            line += f" {_text(note)}"
        source_lines.append(Paragraph(line, small))

    source_cell = source_lines or [Paragraph("No hay fuentes publicables para el periodo seleccionado.", small)]
    meta = Table([
        [Paragraph("<b>PERIODO ANALIZADO</b><br/>" + _text(period), body), Paragraph("<b>COMPARACION</b><br/>" + _text(comparison_label) + "<br/>" + _text(comparison), body)],
        [Paragraph("<b>FUENTES Y CORTES</b>", body), source_cell],
    ], colWidths=[8.2 * cm, 9.2 * cm])
    meta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GRIS),
        ("BACKGROUND", (0, 1), (0, 1), colors.HexColor("#FFF8CC")),
        ("BOX", (0, 0), (-1, -1), 0.6, BORDE),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, BORDE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.extend([meta, Paragraph("INDICADORES PUBLICABLES", section)])

    indicators = publication.get("indicators", [])[:12]
    indicator_rows = [["INDICADOR", "VALOR", "COMPARACION", "VARIACION"]]
    for item in indicators:
        value = item.get("value", 0)
        previous = item.get("comparison_value")
        variation = item.get("variation_percentage")
        indicator_rows.append([
            _text(item.get("indicator_name") or item.get("title")),
            f"{value:,.0f}" if isinstance(value, (int, float)) else _text(value),
            f"{previous:,.0f}" if isinstance(previous, (int, float)) else "No comparable",
            f"{variation:+.1f}%" if isinstance(variation, (int, float)) else "No comparable",
        ])
    if len(indicator_rows) == 1:
        indicator_rows.append(["No hay indicadores publicables para el periodo seleccionado.", "-", "-", "-"])

    indicator_table = Table(indicator_rows, colWidths=[8.4 * cm, 2.7 * cm, 3.1 * cm, 3.2 * cm], repeatRows=1)
    indicator_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL_OSCURO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
        ("GRID", (0, 0), (-1, -1), 0.35, BORDE),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(indicator_table)

    insights = publication.get("insights", [])[:5]
    if insights:
        story.append(Paragraph("LECTURA TECNICA", section))
        for insight in insights:
            detail = insight.get("detail") or insight.get("value_text") or "Sin detalle adicional."
            story.append(Paragraph(f"<b>{_text(insight.get('title'))}:</b> {_text(detail)}", body))
            story.append(Spacer(1, 5))

    governance = publication.get("governance") or {}
    note = governance.get("privacy_note") or "Solo se incluyen datos agregados y publicables; no se exponen registros individuales."
    story.extend([
        Paragraph("TRAZABILIDAD Y USO DE LA INFORMACION", section),
        Paragraph(_text(note), small),
        Spacer(1, 12),
        Paragraph("Documento generado por SISC Jamundi. Las fuentes se presentan por separado y sus valores no deben sumarse entre si.", small),
    ])

    doc.build(story)
    result = buffer.getvalue()
    buffer.close()
    return result
