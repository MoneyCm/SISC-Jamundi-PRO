"""PDF de dos páginas del informe para decisión del Consejo (estilo del boletín institucional)."""
from __future__ import annotations

from datetime import date
from html import escape
from io import BytesIO

from functools import lru_cache

from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from services.sisc_cifras_pdf import BLUE, BORDER, CREST, GREEN, INK, MUTED, ORANGE, PALE, RED, YELLOW, _section, _styles

MONTHS = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")
WIDTH = 18.4 * cm
LEVEL_COLORS = {"ALTA": RED, "MEDIA": ORANGE, "OK": GREEN, "INFO": MUTED}
KIND_LABELS = {"RECOMENDACION": "Recomendación del Observatorio", "TERRITORIO": "Situación territorial", "COMPROMISO": "Compromiso estancado"}


def _t(value, fallback="") -> str:
    # Helvetica no trae flechas ni signos matemáticos: se escriben con palabras.
    text = str(value if value not in (None, "") else fallback).replace("→", "a").replace("≥", ">=")
    return escape(text)


def _long_date(iso: str) -> str:
    value = date.fromisoformat(iso)
    return f"{value.day} de {MONTHS[value.month - 1]} de {value.year}"


def _number(value) -> str:
    return f"{value:,}".replace(",", ".") if isinstance(value, int) else "-"


def _change(cell: dict) -> str:
    if cell.get("previous") is None:
        return "sin base"
    if cell.get("variation_pct") is None:
        diff = cell["difference"]
        return f"{diff:+d} {'hecho' if abs(diff) == 1 else 'hechos'}" if diff else "igual"
    return f"{cell['variation_pct']:+.1f}%".replace(".", ",")


def _grid(data, widths, styles, header=True, zebra=True):
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, BORDER),
    ]
    if header:
        commands += [("BACKGROUND", (0, 0), (-1, 0), BLUE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
    if zebra:
        commands += [("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, PALE])]
    table.setStyle(TableStyle(commands))
    return table


def _th(text, styles):
    return Paragraph(f"<font color='white'><b>{_t(text)}</b></font>", styles["td"])


def _decision_box(index, item, styles):
    rows = [
        [Paragraph(f"<font color='#667085'>{_t(KIND_LABELS.get(item['kind'], item['kind'])).upper()}"
                   f"{' | ' + _t(item['ref']) if item.get('ref') else ''}</font>", styles["small"])],
        [Paragraph(f"<b>{index}. {_t(item['title'])}</b>", styles["body"])],
        [Paragraph(_t(item["evidence"]), styles["td"])],
        [Paragraph(f"<b>Se pide al Consejo:</b> {_t(item['ask'])}", styles["td"])],
    ]
    box = Table(rows, colWidths=[WIDTH])
    box.setStyle(TableStyle([
        ("LINEBEFORE", (0, 0), (0, -1), 3, YELLOW), ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    return KeepTogether([box, Spacer(1, 0.18 * cm)])


@lru_cache(maxsize=1)
def _crest():
    """Escudo reducido: el original (1128x1798, 2 MB) hace pesado un PDF que circula por WhatsApp."""
    if not CREST.exists():
        return None
    from PIL import Image
    image = Image.open(CREST)
    image.thumbnail((180, 288))
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return ImageReader(buffer)


def _header_footer(report):
    def draw(canvas, doc):
        canvas.saveState()
        width, height = A4
        crest = _crest()
        if crest:
            canvas.drawImage(crest, 1.28 * cm, height - 2.45 * cm, width=0.9 * cm, height=1.2 * cm, preserveAspectRatio=True, mask="auto")
        canvas.setFillColor(BLUE); canvas.setFont("Helvetica-Bold", 13)
        canvas.drawString(2.45 * cm, height - 1.55 * cm, "INFORME PARA DECISIÓN")
        canvas.setFillColor(INK); canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(2.45 * cm, height - 2.0 * cm, f"{report['instance_label'].upper()} | SESIÓN DEL {_long_date(report['session_date']).upper()}")
        canvas.setFillColor(BLUE); canvas.setFont("Helvetica-Bold", 8)
        canvas.drawRightString(width - 1.25 * cm, height - 1.5 * cm, "Secretaría de Seguridad y Convivencia")
        canvas.setFillColor(INK); canvas.setFont("Helvetica", 6.6)
        canvas.drawRightString(width - 1.25 * cm, height - 1.88 * cm, "Observatorio del Delito | Alcaldía de Jamundí")
        canvas.setFillColor(YELLOW); canvas.rect(1.25 * cm, height - 2.75 * cm, width - 2.5 * cm, 0.12 * cm, fill=1, stroke=0)
        canvas.setStrokeColor(BORDER); canvas.line(1.25 * cm, 1.15 * cm, width - 1.25 * cm, 1.15 * cm)
        canvas.setFillColor(RED); canvas.setFont("Helvetica-Bold", 6)
        canvas.drawString(1.25 * cm, 0.78 * cm, "RESERVADO | Documento de trabajo para la instancia. No publicar.")
        canvas.setFillColor(INK); canvas.setFont("Helvetica", 6)
        canvas.drawRightString(width - 1.25 * cm, 0.78 * cm, f"Generado por el SISC el {_long_date(report['generated_on'])} | Página {doc.page}")
        canvas.restoreState()
    return draw


def build_decision_report_pdf(report: dict) -> bytes:
    styles = _styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=1.3 * cm, rightMargin=1.3 * cm, topMargin=3.05 * cm,
                            bottomMargin=1.5 * cm, title=f"Informe para decisión - {report['instance_label']}",
                            author="SISC Jamundí - Observatorio del Delito")
    story = []

    # 1. Qué requiere decisión
    story.append(_section(1, "Qué requiere decisión hoy", styles))
    items = report["decisions"]["items"]
    if not items:
        story.append(Paragraph("No hay asuntos nuevos que requieran decisión: el informe se limita al seguimiento.", styles["body"]))
    for index, item in enumerate(items, 1):
        story.append(_decision_box(index, item, styles))
    if report["decisions"]["more"]:
        story.append(Paragraph(f"Hay {report['decisions']['more']} asuntos más en el Centro de análisis del SISC.", styles["small"]))

    # 2. Situación
    situation = report["situation"]
    story.append(_section(2, "Situación del periodo", styles))
    if situation["status"] != "OK":
        story.append(Paragraph(_t(situation["reason"]), styles["body"]))
    else:
        data = [[_th("Conducta", styles), _th(f"Últimas 4 semanas ({situation['recent_label']})", styles), _th("Cambio", styles),
                 _th(f"Año corrido ({situation['year_label']})", styles), _th("Cambio", styles)]]
        for row in situation["rows"]:
            recent, year = row["recent"], row["year"]
            data.append([
                Paragraph(f"<b>{_t(row['label'])}</b>", styles["td"]),
                Paragraph(f"{_number(recent['current'])} <font color='#667085'>(antes {_number(recent['previous'])})</font>", styles["td"]),
                Paragraph(_t(_change(recent)), styles["num"]),
                Paragraph(f"{_number(year['current'])} <font color='#667085'>(antes {_number(year['previous'])})</font>", styles["td"]),
                Paragraph(_t(_change(year)), styles["num"]),
            ])
        story.append(_grid(data, [4.6 * cm, 4.4 * cm, 2.3 * cm, 4.8 * cm, 2.3 * cm], styles))
        story.append(Spacer(1, 0.1 * cm))
        story.append(Paragraph(f"Cifras: {_t(situation['unit'])}. Las últimas semanas pueden subir cuando se registren hechos tardíos.", styles["small"]))

    story.append(PageBreak())

    # 3. Compromisos
    block = report["commitments"]
    story.append(_section(3, "Compromisos", styles))
    last = f"desde la última sesión registrada ({_long_date(block['last_session'])})" if block["last_session"] else "sin sesión anterior registrada"
    story.append(Paragraph(
        f"<b>{block['open']}</b> abiertos | <b>{len(block['fulfilled_since_last'])}</b> cumplidos {last} | "
        f"<font color='#ED3237'><b>{block['overdue']}</b> atrasados</font> | <b>{block['repeated']}</b> pedidos más de una vez | "
        f"<b>{block['without_information']}</b> sin reporte de avance | <b>{block['without_deadline']}</b> sin fecha límite", styles["body"]))
    story.append(Spacer(1, 0.12 * cm))
    if block["fulfilled_since_last"]:
        story.append(Paragraph("<b>Cumplidos</b>", styles["sub"]))
        data = [[_th("Código", styles), _th("Compromiso", styles), _th("Cómo se verificó", styles)]]
        for item in block["fulfilled_since_last"][:6]:
            data.append([Paragraph(_t(item["code"]), styles["td"]), Paragraph(_t(item["text"]), styles["td"]),
                         Paragraph(_t(item["note"], "Sin nota"), styles["td"])])
        story.append(_grid(data, [2.4 * cm, 9.6 * cm, 6.4 * cm], styles))
        story.append(Spacer(1, 0.12 * cm))
    if block["attention"]:
        story.append(Paragraph("<b>Atrasados o repetidos</b>", styles["sub"]))
        data = [[_th("Código", styles), _th("Compromiso", styles), _th("Responsable", styles), _th("Situación", styles)]]
        for item in block["attention"]:
            marks = []
            if "REPETIDO" in item["flags"]:
                marks.append(f"pedido {item['mentions']} veces")
            if "ATRASADO" in item["flags"]:
                marks.append("atrasado")
            data.append([Paragraph(_t(item["code"]), styles["td"]), Paragraph(_t(item["text"]), styles["td"]),
                         Paragraph(_t(item["responsible"], "Por definir"), styles["td"]),
                         Paragraph(_t(", ".join(marks) + f". {item['status_label']}."), styles["td"])])
        story.append(_grid(data, [2.4 * cm, 9.0 * cm, 3.6 * cm, 3.4 * cm], styles))

    # 4. Intervenciones
    story.append(_section(4, "Intervenciones y resultados", styles))
    cases = report["interventions"]
    if not cases:
        story.append(Paragraph("Ninguna intervención documentada. Sin registrar qué se hizo, cuándo empezó y qué debería cambiar, "
                               "el Consejo no puede saber qué funcionó. Se sugiere documentar la intervención de cada compromiso en ejecución.", styles["body"]))
    else:
        data = [[_th("Origen", styles), _th("Qué se hizo", styles), _th("Etapa", styles), _th("Resultado más reciente", styles)]]
        for case in cases:
            window = case["latest_window"]
            if window:
                change = _change({"previous": window["before"], "variation_pct": window["variation_pct"], "difference": window["difference"]})
                result = f"{case['indicator']}, {window['days']} días: {window['before']} a {window['after']} ({change})"
            else:
                result = case.get("reason") or "Aún no medible"
            data.append([Paragraph(_t(case["origin"]), styles["td"]), Paragraph(_t(case["intervention"]), styles["td"]),
                         Paragraph(_t(case["status"].replace("_", " ").capitalize()), styles["td"]), Paragraph(_t(result), styles["td"])])
        story.append(_grid(data, [2.8 * cm, 7.2 * cm, 2.4 * cm, 6.0 * cm], styles))

    # 5. Calidad del dato
    story.append(_section(5, "Calidad del dato", styles))
    for row in report["data_quality"]:
        color = LEVEL_COLORS.get(row["level"], MUTED).hexval().replace("0x", "#")
        story.append(Paragraph(f"<font color='{color}' size='10'>•</font> <b>{_t(row['title'])}.</b> {_t(row['detail'])}", styles["td"]))
    story.append(Spacer(1, 0.2 * cm))
    for note in report["notes"]:
        story.append(Paragraph(_t(note), styles["small"]))

    draw = _header_footer(report)
    doc.build(story, onFirstPage=draw, onLaterPages=draw)
    return buffer.getvalue()
