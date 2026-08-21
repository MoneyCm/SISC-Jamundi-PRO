from datetime import date
from html import escape
from io import BytesIO
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)


BLUE = colors.HexColor("#063B9D")
YELLOW = colors.HexColor("#FBB900")
GREEN = colors.HexColor("#00A651")
RED = colors.HexColor("#ED3237")
ORANGE = colors.HexColor("#E66A12")
INK = colors.HexColor("#263244")
MUTED = colors.HexColor("#667085")
PALE = colors.HexColor("#F7F9FC")
BORDER = colors.HexColor("#D7DDE5")
CREST = Path(__file__).resolve().parents[1] / "templates" / "escudo_jamundi.png"


def _text(value, fallback="Sin informacion"):
    return escape(str(value if value not in (None, "") else fallback))


def _number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:,.0f}".replace(",", ".")
    return _text(value, "-")


def _period(publication, key="period"):
    value = publication.get(key) or {}
    return f"{value.get('start', 'sin inicio')} al {value.get('end', 'sin corte')}"


def _edition(publication):
    raw = str(publication.get("edition_type") or publication.get("frequency") or "TECNICO").upper()
    return {"WEEKLY": "SEMANAL", "MONTHLY": "MENSUAL", "SEMIANNUAL": "SEMESTRAL", "ANNUAL": "ANUAL"}.get(raw, raw)


def _variation_value(item):
    value = item.get("variation_percentage")
    return value if isinstance(value, (int, float)) else None


def _variation(item):
    value = _variation_value(item)
    return f"{value:+.1f}%" if value is not None else "No comparable"


def _difference_value(item):
    value = item.get("variation_absolute")
    if isinstance(value, (int, float)):
        return value
    current, previous = item.get("value"), item.get("comparison_value")
    if isinstance(current, (int, float)) and isinstance(previous, (int, float)):
        return current - previous
    return None


def _difference(item):
    value = _difference_value(item)
    return f"{value:+,.0f}".replace(",", ".") if value is not None else "-"


def _styles():
    base = getSampleStyleSheet()
    return {
        "body": ParagraphStyle("body", parent=base["Normal"], fontName="Helvetica", fontSize=8.1, leading=11.3, textColor=INK),
        "small": ParagraphStyle("small", parent=base["Normal"], fontName="Helvetica", fontSize=6.5, leading=8.2, textColor=MUTED),
        "section": ParagraphStyle("section", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12.5, leading=15, textColor=BLUE),
        "sub": ParagraphStyle("sub", parent=base["Heading3"], fontName="Helvetica-Bold", fontSize=10, leading=12, textColor=BLUE),
        "label": ParagraphStyle("label", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=6.3, leading=7.4, alignment=TA_CENTER, textColor=INK),
        "value": ParagraphStyle("value", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=21, leading=23, alignment=TA_CENTER, textColor=BLUE),
        "note": ParagraphStyle("note", parent=base["Normal"], fontName="Helvetica", fontSize=6.1, leading=7.2, alignment=TA_CENTER, textColor=MUTED),
        "th": ParagraphStyle("th", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=6.7, leading=8, alignment=TA_CENTER, textColor=colors.HexColor("#999999")),
        "td": ParagraphStyle("td", parent=base["Normal"], fontName="Helvetica", fontSize=7.2, leading=8.6, textColor=INK),
        "num": ParagraphStyle("num", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=7.2, leading=8.6, alignment=TA_CENTER, textColor=INK),
    }


def _section(number, title, styles):
    stripe = Table([[""]], colWidths=[0.09 * cm], rowHeights=[0.55 * cm])
    stripe.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), YELLOW)]))
    row = Table([[stripe, Paragraph(f"{number}. {_text(title).upper()}", styles["section"])]], colWidths=[0.23 * cm, 16.87 * cm])
    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return KeepTogether([Spacer(1, 0.08 * cm), row, Spacer(1, 0.12 * cm)])


def _card(label, value, note, styles, accent=BLUE):
    box = Table([
        [Paragraph(_text(label).upper(), styles["label"])],
        [Paragraph(_text(value, "-"), styles["value"])],
        [Paragraph(_text(note, ""), styles["note"])],
    ], colWidths=[4.05 * cm], rowHeights=[0.43 * cm, 0.66 * cm, 0.43 * cm])
    box.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 2.5, accent), ("BOX", (0, 0), (-1, -1), 0.55, colors.HexColor("#555555")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return box


def _cards(items, widths):
    table = Table([items], colWidths=widths, hAlign="CENTER")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def _comparison_table(items, styles, limit=8):
    rows = [[Paragraph(x, styles["th"]) for x in ("DELITO", "PER. COMPARADO", "PER. ACTUAL", "VARIACION", "VARIACION %")]]
    for item in items[:limit]:
        variation = _variation_value(item)
        color = GREEN if variation is not None and variation < 0 else RED if variation is not None and variation > 0 else INK
        rows.append([
            Paragraph(_text(item.get("indicator_name")), styles["td"]),
            Paragraph(_number(item.get("comparison_value")), styles["num"]),
            Paragraph(_number(item.get("value")), styles["num"]),
            Paragraph(f'<font color="{color.hexval()}"><b>{_difference(item)}</b></font>', styles["num"]),
            Paragraph(f'<font color="{color.hexval()}"><b>{_variation(item)}</b></font>', styles["num"]),
        ])
    if len(rows) == 1:
        rows.append([Paragraph("Sin indicadores comparables para este periodo.", styles["td"]), "-", "-", "-", "-"])
    table = Table(rows, colWidths=[7.25 * cm, 2.8 * cm, 2.55 * cm, 2.3 * cm, 2.2 * cm], repeatRows=1)
    table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.35, BORDER), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _trend(items, styles):
    temporal = [
        item for item in items
        if str(item.get("domain") or "").upper() in {"TIEMPO", "TEMPORAL"}
        and isinstance(item.get("value"), (int, float))
    ][:12]
    if len(temporal) < 2:
        box = Table([[Paragraph(
            "La serie temporal no esta disponible en esta seleccion. El SISC conserva el comparativo verificable sin completar valores ausentes.",
            styles["body"],
        )]], colWidths=[17.1 * cm], rowHeights=[1.55 * cm])
        box.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER), ("BACKGROUND", (0, 0), (-1, -1), PALE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ]))
        return box
    drawing = Drawing(490, 115)
    left, bottom, chart_w, chart_h = 32, 25, 445, 75
    maximum = max(float(item["value"]) for item in temporal) or 1
    for index in range(4):
        y = bottom + chart_h * index / 3
        drawing.add(Line(left, y, left + chart_w, y, strokeColor=colors.HexColor("#DDE5EF"), strokeWidth=0.5, strokeDashArray=[2, 2]))
        drawing.add(String(2, y - 2, _number(maximum * index / 3), fontName="Helvetica", fontSize=6, fillColor=colors.HexColor("#90A0B7")))
    points = []
    for index, item in enumerate(temporal):
        x = left + chart_w * index / max(len(temporal) - 1, 1)
        y = bottom + chart_h * float(item["value"]) / maximum
        points.append((x, y))
        drawing.add(String(x - 8, 5, str(item.get("indicator_name") or index + 1)[:7], fontName="Helvetica", fontSize=5.5, fillColor=colors.HexColor("#90A0B7")))
    for first, second in zip(points, points[1:]):
        drawing.add(Line(first[0], first[1], second[0], second[1], strokeColor=BLUE, strokeWidth=2))
    for x, y in points:
        drawing.add(Line(x, y, x + 0.01, y, strokeColor=colors.white, strokeWidth=5))
        drawing.add(Line(x, y, x + 0.01, y, strokeColor=BLUE, strokeWidth=2.5))
    return drawing


def _management(title, items, color, styles):
    result = [Spacer(1, 0.3 * cm), Paragraph(title, ParagraphStyle(f"sub-{title}", parent=styles["sub"], textColor=color))]
    if not items:
        box = Table([[Paragraph("No existe un corte publicable para el periodo seleccionado.", styles["body"])]], colWidths=[17.1 * cm], rowHeights=[0.8 * cm])
        box.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, BORDER), ("BACKGROUND", (0, 0), (-1, -1), PALE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 10)]))
        return result + [box]

    has_context = any(
        (item.get("metadata") or {}).get("coverage_type") == "CONTEXT"
        for item in items
    )
    headers = ["INDICADOR", "VALOR", "UNIDAD", "CORTE"]
    if has_context:
        headers.extend(["MES ORIGEN", "NOTA"])
    rows = [[Paragraph(x, styles["th"]) for x in headers]]
    for item in items[:6]:
        md = item.get("metadata") or {}
        is_ctx = md.get("coverage_type") == "CONTEXT"
        row = [
            Paragraph(_text(item.get("indicator_name")), styles["td"]),
            Paragraph(_number(item.get("value")), styles["num"]),
            Paragraph(_text(item.get("unit"), "-"), styles["num"]),
            Paragraph(_text(item.get("cutoff_date"), "-"), styles["num"]),
        ]
        if has_context:
            row.append(Paragraph(_text(md.get("period"), "-"), styles["num"]))
            row.append(Paragraph("Contexto" if is_ctx else "-", styles["num"]))
        rows.append(row)

    if has_context:
        col_widths = [6.2 * cm, 1.8 * cm, 2.6 * cm, 2.6 * cm, 2.0 * cm, 1.9 * cm]
    else:
        col_widths = [8.2 * cm, 2.4 * cm, 3.1 * cm, 3.4 * cm]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 0.6, BORDER), ("LINEBELOW", (0, 0), (-1, -1), 0.35, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return result + [table]


def _source_card(source, styles):
    coverage = str(source.get("coverage_status") or "Sin clasificar")
    normalized = coverage.upper()
    accent = GREEN if ("COMPLETA" in normalized or "VIGENTE" in normalized) and "DESACT" not in normalized else RED if any(x in normalized for x in ("DESACT", "PARCIAL", "PENDIENTE")) else YELLOW
    name = source.get("name") or source.get("source_name") or source.get("source_code")
    cutoff = source.get("last_cutoff_date") or source.get("cutoff_date") or "Sin corte"
    table = Table([[Paragraph(
        f'<b>{_text(name)}</b><br/><font size="6">{_text(coverage)}</font><br/><font size="5.5">Corte: {_text(cutoff)}</font>',
        styles["small"],
    )]], colWidths=[5.15 * cm], rowHeights=[1.15 * cm])
    table.setStyle(TableStyle([
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, accent), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _header_footer(canvas, doc, publication):
    canvas.saveState()
    page, width, height = canvas.getPageNumber(), A4[0], A4[1]
    if CREST.exists():
        canvas.drawImage(str(CREST), 1.28 * cm, height - 2.55 * cm, width=0.95 * cm, height=1.3 * cm, preserveAspectRatio=True, mask="auto")
    canvas.setFillColor(BLUE)
    if page == 1:
        canvas.setFont("Helvetica-Bold", 16)
        canvas.drawString(2.55 * cm, height - 1.45 * cm, "BOLETIN ESTADISTICO DE")
        canvas.drawString(2.55 * cm, height - 2.05 * cm, "SEGURIDAD Y CONVIVENCIA")
        canvas.setFillColor(INK); canvas.setFont("Helvetica-Bold", 8.5)
        canvas.drawString(2.55 * cm, height - 2.48 * cm, "ALCALDIA MUNICIPAL DE JAMUNDI")
    else:
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(2.35 * cm, height - 1.55 * cm, "BOLETIN ESTADISTICO DE SEGURIDAD Y CONVIVENCIA")
        canvas.setFillColor(INK); canvas.setFont("Helvetica", 6.4)
        canvas.drawString(2.35 * cm, height - 1.88 * cm, "ALCALDIA MUNICIPAL DE JAMUNDI")
    canvas.setFillColor(BLUE); canvas.setFont("Helvetica-Bold", 8.2)
    canvas.drawRightString(width - 1.25 * cm, height - 1.42 * cm, "Secretaria de Seguridad y Convivencia")
    canvas.setFillColor(INK); canvas.setFont("Helvetica", 6.4)
    canvas.drawRightString(width - 1.25 * cm, height - 1.82 * cm, f"Boletin {_edition(publication)} | {_period(publication)}")
    canvas.setFillColor(YELLOW); canvas.rect(1.25 * cm, height - 2.9 * cm, width - 2.5 * cm, 0.13 * cm, fill=1, stroke=0)
    canvas.setStrokeColor(BORDER); canvas.line(1.25 * cm, 1.15 * cm, width - 1.25 * cm, 1.15 * cm)
    canvas.setFillColor(INK); canvas.setFont("Helvetica-Bold", 5.8)
    canvas.drawString(1.25 * cm, 0.78 * cm, "Fuente: SISC | Secretaria de Seguridad y Convivencia - Alcaldia de Jamundi")
    canvas.setFont("Helvetica", 5.8)
    canvas.drawRightString(width - 1.25 * cm, 0.78 * cm, f"Pagina {page} | Informacion agregada y anonimizada")
    canvas.restoreState()


def build_sisc_cifras_pdf(publication: dict) -> bytes:
    """Genera el boletin institucional publicable y sin datos personales."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=1.25 * cm, leftMargin=1.25 * cm,
        topMargin=3.2 * cm, bottomMargin=1.45 * cm,
        title="Boletin Estadistico de Seguridad y Convivencia",
        author="SISC Jamundi - Secretaria de Seguridad y Convivencia",
    )
    styles = _styles()
    indicators = publication.get("indicators") or []
    police = [item for item in indicators if item.get("source_code") == "POLICIA_SEMANAL"]
    total = next((item for item in police if item.get("indicator_code") == "seguridad.total"), None)
    comparable = [item for item in police if item.get("comparison_value") is not None and item is not total]
    conductas = [item for item in comparable if item.get("category") == "Conducta"] or comparable
    inspections = [item for item in indicators if item.get("source_code") == "INSPECCIONES_RNMC"]
    family = [item for item in indicators if item.get("source_code") == "COMISARIAS_FAMILIA"]
    insights, sources = publication.get("insights") or [], publication.get("sources") or []
    current = total.get("value") if total else None
    previous = total.get("comparison_value") if total else None
    variation_value = _variation_value(total or {})
    variation_color = GREEN if variation_value is not None and variation_value < 0 else RED if variation_value is not None and variation_value > 0 else BLUE
    generated = str(publication.get("generated_at") or publication.get("published_at") or date.today().isoformat())[:10]
    story = []

    story.append(_section("1", "Introduccion y alcance", styles))
    intro = Table([[Paragraph(
        f'<b>Periodo del boletin:</b> {_text(_period(publication))}<br/>'
        f'<b>Periodo comparado:</b> {_text(_period(publication, "comparison_period"))}<br/>'
        f'<b>Fecha de generacion:</b> {generated}', styles["body"],
    )]], colWidths=[17.1 * cm])
    intro.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER), ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([intro, Spacer(1, 0.22 * cm)])
    lines = []
    for index, insight in enumerate(insights[:3], 1):
        lines.append(f'<b>{index}. {_text(insight.get("title") or f"Hallazgo {index}").upper()}</b><br/>{_text(insight.get("detail") or insight.get("text") or "")}')
    if not lines:
        lines = ["<b>ANALISIS DE HALLAZGOS EJECUTIVOS</b><br/>No se generaron hallazgos comparables para el periodo seleccionado."]
    insight_box = Table([[Paragraph("<br/><br/>".join(lines), styles["body"])]], colWidths=[17.1 * cm])
    insight_box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.65, colors.HexColor("#4C4C4C")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([insight_box, Spacer(1, 0.22 * cm), _section("2", "Panorama general", styles)])
    story.append(Paragraph(f"Periodo comparado: {_text(_period(publication))}, frente a {_text(_period(publication, 'comparison_period'))}.", styles["body"]))
    story.append(Spacer(1, 0.1 * cm))
    story.append(_cards([
        _card("Total periodo comparado", _number(previous), "hechos registrados", styles),
        _card("Total periodo actual", _number(current), "hechos registrados", styles),
        _card("Variacion", _variation(total or {}), f"Diferencia: {_difference(total or {})} hechos", styles, variation_color),
    ], [5.55 * cm] * 3))
    story.extend([Spacer(1, 0.22 * cm), _section("3", "Comportamiento del periodo", styles)])
    top = conductas[0] if conductas else {}
    story.append(_cards([
        _card("Hechos del periodo", _number(current), "periodo actual", styles),
        _card("Periodo comparado", _number(previous), f"diferencia {_difference(total or {})}", styles, RED),
        _card("Principal cambio", _number(top.get("value")), _text(top.get("indicator_name"), "sin dato"), styles, ORANGE),
        _card("Fuentes", _number(len(sources)), "con corte visible", styles, YELLOW),
    ], [4.2 * cm] * 4))

    story.extend([PageBreak(), _section("4", "Comparativo por delito", styles), _comparison_table(conductas, styles)])
    story.extend([Spacer(1, 0.25 * cm), _section("5", "Cambios destacados", styles)])
    ranked = sorted(conductas, key=lambda item: abs(_variation_value(item) or 0), reverse=True)[:5]
    story.append(_comparison_table(ranked, styles, 5))
    story.extend([Spacer(1, 0.25 * cm), _section("6", "Evolucion temporal del delito", styles), _trend(police, styles)])
    story.extend([Spacer(1, 0.12 * cm), Paragraph(
        f"Version de publicacion: {_text(publication.get('id'), 'sin identificador')} | Estado: PUBLICADO | Generado: {generated}",
        styles["small"],
    )])

    story.extend([PageBreak(), _section("7", "Gestion y convivencia", styles)])
    story.append(Paragraph("Actuaciones de Inspecciones y atencion de Comisarias, cada una con su propio corte y unidad de medida.", styles["body"]))
    blockers = (publication.get("governance") or {}).get("review_blockers") or []
    if blockers:
        warning = Table([[Paragraph(f'<b>Revision de cobertura:</b> {_text(blockers[0])}', styles["small"])]], colWidths=[17.1 * cm])
        warning.setStyle(TableStyle([
            ("LINEBEFORE", (0, 0), (0, -1), 2.5, ORANGE), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF9F0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.extend([Spacer(1, 0.15 * cm), warning])
    story.extend(_management("INSPECCIONES DE POLICIA", inspections, BLUE, styles))
    story.extend(_management("COMISARIAS DE FAMILIA", family, colors.HexColor("#00695C"), styles))
    story.extend([Spacer(1, 0.28 * cm), Paragraph("COBERTURA DEL BOLETIN", styles["sub"])])
    if sources:
        cards = [_source_card(source, styles) for source in sources[:3]]
        while len(cards) < 3:
            cards.append(Spacer(5.15 * cm, 1))
        story.append(_cards(cards, [5.55 * cm] * 3))
    story.extend([Spacer(1, 0.28 * cm), Paragraph("LECTURA DEL PERIODO", ParagraphStyle("reading", parent=styles["sub"], textColor=YELLOW))])
    reading = blockers[0] if blockers else "Las fuentes seleccionadas cuentan con trazabilidad y fecha de corte visible."
    story.append(Paragraph(f"<b>{_text(reading)}</b>", ParagraphStyle("reading-body", parent=styles["body"], fontSize=10.2, leading=13.5, textColor=colors.HexColor("#9E9E9E"))))
    story.extend([Spacer(1, 0.3 * cm), Paragraph(
        "<b>Lectura correcta:</b> los valores de Seguridad, Inspecciones y Comisarias describen gestiones distintas y no deben sumarse entre si. Las cifras son agregadas y anonimizadas; cada fuente conserva su fecha de corte y advertencias de cobertura.",
        styles["small"],
    )])
    callback = lambda canvas, current_doc: _header_footer(canvas, current_doc, publication)
    doc.build(story, onFirstPage=callback, onLaterPages=callback)
    result = buffer.getvalue()
    buffer.close()
    return result
