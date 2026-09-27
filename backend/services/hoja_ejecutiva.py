"""Hoja ejecutiva semanal: una página impresa para la Secretaría de Seguridad.

Cifras de la sábana policial (hechos únicos), los barrios con más casos y los compromisos del
Consejo que necesitan atención. Las frases se arman con reglas fijas a partir de las cifras.
"""
import io
import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models_council import CouncilCommitment
from db.models_hechos_seguridad import HechoSeguridad
from services import council_commitments_service as commitments
from services.alert_engine import NON_PUBLIC_TERRITORY_VALUES, is_public_territory_name
from services.hechos_metrics import hechos_unicos_expr

FUENTE = "POLICIA_SEMANAL"
# Los seis delitos de la hoja, con las conductas de la sábana que agrupa cada uno.
DELITOS = [
    ("Homicidios", ["Homicidio"]),
    ("Lesiones personales", ["Lesiones personales"]),
    ("Hurto a personas", ["Hurto a personas"]),
    ("Hurto de motos y carros", ["Hurto a motocicletas", "Hurto a automotores"]),
    ("Hurto a residencias", ["Hurto a residencias"]),
    ("Hurto a comercio", ["Hurto a comercio"]),
]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_larga(value: date) -> str:
    return f"{value.day} de {MESES[value.month - 1]} de {value.year}"


def fecha_corta(value: date) -> str:
    return f"{value.day} de {MESES[value.month - 1]}"


MINUSCULAS = {"de", "del", "la", "las", "los", "el", "y", "e"}


def nombre_lugar(valor: str) -> str:
    """'CGTO BOCAS DEL PALO' -> 'Corregimiento Bocas del Palo'."""
    palabras = valor.strip().lower().split()
    if palabras and palabras[0] in {"cgto", "cgto."}:
        palabras[0] = "corregimiento"
    return " ".join(p if i and p in MINUSCULAS else p.capitalize() for i, p in enumerate(palabras))


def un_anio_antes(value: date) -> date:
    try:
        return value.replace(year=value.year - 1)
    except ValueError:  # 29 de febrero
        return value.replace(year=value.year - 1, day=28)


def variacion(actual: int, referencia: int) -> Optional[float]:
    return None if not referencia else round((actual - referencia) / referencia * 100, 1)


def tendencia(actual: int, referencia: int) -> str:
    if actual > referencia:
        return "subió"
    if actual < referencia:
        return "bajó"
    return "igual"


def _conteo(db: Session, inicio: date, fin: date, conductas: Optional[List[str]] = None) -> int:
    query = db.query(hechos_unicos_expr()).filter(
        HechoSeguridad.fuente_codigo == FUENTE,
        HechoSeguridad.fecha_evento >= inicio,
        HechoSeguridad.fecha_evento <= fin,
    )
    if conductas:
        query = query.filter(HechoSeguridad.conducta_estandar.in_(conductas))
    return int(query.scalar() or 0)


def _barrios(db: Session, inicio: date, fin: date, limite: int = 3) -> List[Dict[str, Any]]:
    barrio = HechoSeguridad.barrio_normalizado
    filas = db.query(barrio, hechos_unicos_expr().label("total")).filter(
        HechoSeguridad.fuente_codigo == FUENTE,
        HechoSeguridad.fecha_evento >= inicio,
        HechoSeguridad.fecha_evento <= fin,
        barrio.isnot(None), barrio != "",
        func.upper(func.trim(barrio)).notin_(NON_PUBLIC_TERRITORY_VALUES),
        ~func.upper(barrio).like("%PENDIENTE%"),
    ).group_by(barrio).order_by(hechos_unicos_expr().desc(), barrio).limit(limite * 3).all()
    resultado = []
    for nombre, total in filas:
        if not is_public_territory_name(nombre):
            continue
        principal = db.query(HechoSeguridad.conducta_estandar, hechos_unicos_expr().label("n")).filter(
            HechoSeguridad.fuente_codigo == FUENTE,
            HechoSeguridad.fecha_evento >= inicio,
            HechoSeguridad.fecha_evento <= fin,
            barrio == nombre,
        ).group_by(HechoSeguridad.conducta_estandar).order_by(hechos_unicos_expr().desc()).first()
        resultado.append({"barrio": nombre_lugar(nombre), "casos": int(total),
                          "principal": principal[0] if principal else None})
        if len(resultado) == limite:
            break
    return resultado


def frases(filas: List[Dict[str, Any]], total: Dict[str, Any], barrios: List[Dict[str, Any]],
           compromisos: Dict[str, Any], dias_retraso: int) -> List[str]:
    """Tres a cinco frases sencillas, siempre verificables contra la tabla de la hoja."""
    lineas = []
    homicidios = next(fila for fila in filas if fila["delito"] == "Homicidios")
    if homicidios["semana"] == 0:
        lineas.append("No se registraron homicidios en la semana.")
    else:
        verbo, palabra = ("Se registró", "homicidio") if homicidios["semana"] == 1 else ("Se registraron", "homicidios")
        lineas.append(f"{verbo} {homicidios['semana']} {palabra} en la semana "
                      f"({homicidios['semana_anterior']} la semana anterior).")

    con_base = [fila for fila in filas if fila["anio_anterior"] >= 10 and fila["variacion_anio"] is not None]
    subidas = sorted([f for f in con_base if f["variacion_anio"] >= 10], key=lambda f: -f["variacion_anio"])
    bajadas = sorted([f for f in con_base if f["variacion_anio"] <= -10], key=lambda f: f["variacion_anio"])
    if subidas:
        f = subidas[0]
        lineas.append(f"En lo que va del año, {f['delito'].lower()} es lo que más preocupa: "
                      f"{f['anio']} casos frente a {f['anio_anterior']} el año pasado (+{f['variacion_anio']:.0f} %).")
    if bajadas:
        f = bajadas[0]
        lineas.append(f"La mayor baja del año está en {f['delito'].lower()}: "
                      f"{f['anio']} casos frente a {f['anio_anterior']} ({f['variacion_anio']:.0f} %).")
    if barrios:
        lineas.append(f"En las últimas cuatro semanas, {barrios[0]['barrio']} es el barrio con más casos "
                      f"({barrios[0]['casos']}).")
    if compromisos.get("overdue"):
        lineas.append(f"Hay {compromisos['overdue']} compromisos del Consejo vencidos: conviene pedir su avance "
                      "antes de la próxima sesión.")
    if dias_retraso > 10:
        lineas.append(f"Ojo: la última semana puede estar incompleta; los datos de la Policía llegan con "
                      f"{dias_retraso} días de retraso.")
    return lineas


def construir(db: Session, corte: Optional[date] = None, hoy: Optional[date] = None) -> Dict[str, Any]:
    hoy = hoy or date.today()
    ultimo = db.query(func.max(HechoSeguridad.fecha_evento)).filter(
        HechoSeguridad.fuente_codigo == FUENTE, HechoSeguridad.fecha_evento <= hoy).scalar()
    if ultimo is None:
        raise ValueError("Todavía no hay sábana policial cargada.")
    corte = min(corte or ultimo, ultimo)
    semana = (corte - timedelta(days=6), corte)
    anterior = (semana[0] - timedelta(days=7), semana[0] - timedelta(days=1))
    anio = (date(corte.year, 1, 1), corte)
    anio_previo = (date(corte.year - 1, 1, 1), un_anio_antes(corte))

    filas = []
    for nombre, conductas in DELITOS + [("Total de delitos", None)]:
        fila = {
            "delito": nombre,
            "semana": _conteo(db, *semana, conductas),
            "semana_anterior": _conteo(db, *anterior, conductas),
            "anio": _conteo(db, *anio, conductas),
            "anio_anterior": _conteo(db, *anio_previo, conductas),
        }
        fila["tendencia_semana"] = tendencia(fila["semana"], fila["semana_anterior"])
        fila["variacion_anio"] = variacion(fila["anio"], fila["anio_anterior"])
        filas.append(fila)
    total = filas.pop()

    barrios = _barrios(db, corte - timedelta(days=27), corte)
    resumen = commitments.summary(db.query(CouncilCommitment).all(), today=hoy)
    atencion = [{
        "codigo": item["code"],
        "texto": item["text"],
        "responsable": item["responsible"] or "Responsable por definir",
        "veces": item.get("mentions") or 1,
        "vencido": "ATRASADO" in item["flags"],
    } for item in resumen["attention"][:3]]
    dias_retraso = (hoy - corte).days

    return {
        "corte": corte,
        "hoy": hoy,
        "dias_retraso": dias_retraso,
        "semana": semana,
        "semana_anterior": anterior,
        "anio": anio,
        "anio_anterior": anio_previo,
        "filas": filas,
        "total": total,
        "barrios": barrios,
        "compromisos": {"abiertos": resumen["open"], "vencidos": resumen["overdue"],
                        "cumplidos": resumen["by_status"].get("CUMPLIDO", 0), "atencion": atencion},
        "frases": frases(filas, total, barrios, resumen, dias_retraso),
    }


# ---------------------------------------------------------------- PDF (una página A4)

AZUL = "#281FD0"
TINTA = "#1F2937"
GRIS = "#6B7280"


def _cambio_semana(fila: Dict[str, Any]) -> str:
    diferencia = fila["semana"] - fila["semana_anterior"]
    return f"{diferencia:+d}" if diferencia else "igual"


def _pct(valor: Optional[float]) -> str:
    if valor is None:
        return "sin base"
    return f"{'+' if valor > 0 else ''}{valor:.0f} %"


def _escudo_liviano(ruta: str):
    """El escudo original pesa varios MB; a 300 px de alto se imprime nítido y el PDF queda liviano."""
    try:
        from PIL import Image as PilImage
        imagen = PilImage.open(ruta)
        imagen.thumbnail((300, 300))
        salida = io.BytesIO()
        imagen.save(salida, format="PNG", optimize=True)
        salida.seek(0)
        return salida
    except Exception:
        return ruta


def render_pdf(datos: Dict[str, Any]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, KeepInFrame, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    azul, tinta, gris = colors.HexColor(AZUL), colors.HexColor(TINTA), colors.HexColor(GRIS)
    def estilo(nombre, **cambios):
        return ParagraphStyle(nombre, **{"fontName": "Helvetica", "textColor": tinta, "alignment": TA_LEFT, **cambios})

    titulo = estilo("titulo", fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=azul)
    sub = estilo("sub", fontSize=10.5, leading=14, textColor=gris)
    seccion = estilo("seccion", fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=azul,
                     spaceBefore=8, spaceAfter=4)
    texto = estilo("texto", fontSize=11.5, leading=15.5)
    celda = estilo("celda", fontSize=11, leading=13.5)
    celda_b = estilo("celda_b", fontName="Helvetica-Bold", fontSize=11, leading=13.5)
    pie = estilo("pie", fontSize=8, leading=10, textColor=gris)

    semana, anterior = datos["semana"], datos["semana_anterior"]
    ancho, alto = A4[0] - 3.2 * cm, A4[1] - 2.5 * cm
    historia = []

    escudo = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "escudo_jamundi.png")
    encabezado = [
        Paragraph("Hoja ejecutiva de seguridad", titulo),
        Paragraph(f"Semana del {fecha_corta(semana[0])} al {fecha_larga(semana[1])} · "
                  f"Secretaría de Seguridad y Convivencia · Alcaldía de Jamundí", sub),
    ]
    if os.path.exists(escudo):
        cabecera = Table([[Image(_escudo_liviano(escudo), width=1.4 * cm, height=1.8 * cm), encabezado]],
                         colWidths=[1.9 * cm, None])
        cabecera.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        historia.append(cabecera)
    else:
        historia.extend(encabezado)
    historia.append(Spacer(1, 4))
    historia.append(Table([[""]], hAlign="LEFT", colWidths=[ancho], rowHeights=[2.5],
                          style=[("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFE000"))]))

    historia.append(Paragraph("1. Lo más importante", seccion))
    for linea in datos["frases"]:
        historia.append(Paragraph(f"•&nbsp;&nbsp;{linea}", texto))
        historia.append(Spacer(1, 2))

    historia.append(Paragraph("2. Las cifras", seccion))
    anio_actual, anio_prev = datos["anio"][1].year, datos["anio_anterior"][1].year
    tabla = [[Paragraph(t, celda_b) for t in (
        "Delito", "Esta semana", "Semana anterior", "Cambio", f"En el año<br/>{anio_actual}",
        f"Mismo corte<br/>{anio_prev}", "Cambio<br/>en el año")]]

    def color(diferencia) -> str:  # más delitos en rojo, menos en verde
        if not diferencia:
            return GRIS
        return "#B91C1C" if diferencia > 0 else "#047857"

    for fila in datos["filas"] + [datos["total"]]:
        estilo = celda_b if fila is datos["total"] else celda
        semanal = f"<font color='{color(fila['semana'] - fila['semana_anterior'])}'>{_cambio_semana(fila)}</font>"
        anual = f"<font color='{color(fila['variacion_anio'])}'>{_pct(fila['variacion_anio'])}</font>"
        tabla.append([Paragraph(fila["delito"], estilo), Paragraph(str(fila["semana"]), celda_b),
                      Paragraph(str(fila["semana_anterior"]), estilo), Paragraph(semanal, estilo),
                      Paragraph(str(fila["anio"]), estilo), Paragraph(str(fila["anio_anterior"]), estilo),
                      Paragraph(anual, estilo)])
    cifras = Table(tabla, hAlign="LEFT", colWidths=[4.6 * cm, 2 * cm, 2.9 * cm, 2 * cm, 2 * cm, 2.1 * cm, 2 * cm], repeatRows=1)
    estilos = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF0FF")),
        ("LINEBELOW", (0, 0), (-1, 0), 1, azul),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, colors.HexColor("#D1D5DB")),
        ("LINEABOVE", (0, -1), (-1, -1), 1, tinta),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    cifras.setStyle(TableStyle(estilos))
    historia.append(cifras)
    historia.append(Spacer(1, 2))
    historia.append(Paragraph(
        f"Semana anterior: {fecha_corta(anterior[0])} al {fecha_corta(anterior[1])}. Hechos únicos registrados por la "
        "Policía (sábana SIEDCO). Una baja puede ser falta de registro: confírmela con la siguiente entrega.", pie))

    historia.append(Paragraph("3. Barrios con más casos (últimas cuatro semanas)", seccion))
    if datos["barrios"]:
        for i, b in enumerate(datos["barrios"], start=1):
            detalle = f" · sobre todo {b['principal'].lower()}" if b["principal"] else ""
            historia.append(Paragraph(f"{i}.&nbsp;&nbsp;<b>{b['barrio']}</b>: {b['casos']} casos{detalle}.", texto))
    else:
        historia.append(Paragraph("Sin barrios identificados en el periodo.", texto))

    comp = datos["compromisos"]
    historia.append(Paragraph("4. Compromisos del Consejo de Seguridad", seccion))
    historia.append(Paragraph(f"<b>{comp['vencidos']}</b> vencidos · <b>{comp['abiertos']}</b> abiertos · "
                              f"<b>{comp['cumplidos']}</b> cumplidos.", texto))
    for item in comp["atencion"]:
        veces = f" (pedido {item['veces']} veces)" if item["veces"] > 1 else ""
        texto_item = item["texto"] if len(item["texto"]) <= 150 else item["texto"][:147].rstrip() + "…"
        historia.append(Paragraph(f"•&nbsp;&nbsp;{texto_item} <font color='{GRIS}'>— {item['responsable']}{veces}</font>",
                                  texto))

    historia.append(Paragraph("5. Notas", seccion))
    renglones = Table([[""]] * 4, hAlign="LEFT", colWidths=[ancho], rowHeights=[0.75 * cm] * 4,
                      style=[("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#9CA3AF"))])
    historia.append(renglones)

    historia.append(Spacer(1, 6))
    historia.append(Paragraph(
        f"Datos policiales al {fecha_larga(datos['corte'])} ({datos['dias_retraso']} días de retraso). "
        f"Generado por el SISC el {fecha_larga(datos['hoy'])}. Documento de uso interno.", pie))

    salida = io.BytesIO()
    doc = SimpleDocTemplate(salida, pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm,
                            topMargin=1.3 * cm, bottomMargin=1.2 * cm,
                            title="Hoja ejecutiva de seguridad", author="SISC Jamundí")
    # Si un texto largo no cabe, se reduce la escala: la hoja siempre es una sola página.
    doc.build([KeepInFrame(ancho, alto, historia, mode="shrink")])
    return salida.getvalue()
