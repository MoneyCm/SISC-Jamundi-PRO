"""Reporte semanal para la Secretaria: homicidios y hurto de vehículos, en cuadros.

Lo que pidió la Secretaria (audios del 11 de noviembre de 2026): cada semana, cuántos homicidios van en
el año a la fecha y el hurto de vehículos (carros y motos). Sale de la sábana de la Policía (última
entrega, metodología v2: homicidio por víctima, hurtos por hecho), con corte en el último día que trae.
"""
from datetime import date, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models_hechos_seguridad import HechoSeguridad
from services.entrega_vigente import filtro_hechos
from services.hechos_metrics import hechos_unicos_expr

MESES_CORTOS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
FILAS = [
    ("Homicidios", ["Homicidio"], "víctimas"),
    ("Hurto de carros", ["Hurto a automotores"], "hechos"),
    ("Hurto de motos", ["Hurto a motocicletas"], "hechos"),
]
PALABRAS = ("reporte semanal", "informe semanal", "reporte de la semana", "reporte para la secretaria",
            "cuadro semanal", "reporte de la secretaria", "informe para la secretaria")


def pide_reporte(p: str) -> bool:
    return any(w in p for w in PALABRAS) or ("reporte" in p and "secretaria" in p)


def _un_anio_antes(dia: date) -> date:
    return dia.replace(year=dia.year - 1, day=28) if (dia.month, dia.day) == (2, 29) else dia.replace(year=dia.year - 1)


def _dia(valor: date) -> str:
    return f"{valor.day} de {MESES[valor.month - 1]}"


def _variacion(actual: int, anterior: int) -> Dict:
    if not anterior:
        return {"diferencia": actual - anterior, "porcentaje": None}
    return {"diferencia": actual - anterior, "porcentaje": round(100 * (actual - anterior) / anterior, 1)}


def generar(db: Session, hoy: Optional[date] = None) -> Optional[Dict]:
    hoy = hoy or date.today()
    base = [HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL", filtro_hechos(db)]
    corte = db.query(func.max(HechoSeguridad.fecha_evento)).filter(*base, HechoSeguridad.fecha_evento <= hoy).scalar()
    if not corte:
        return None

    def contar(conductas: List[str], desde: date, hasta: date) -> int:
        return int(db.query(hechos_unicos_expr()).filter(
            *base, HechoSeguridad.conducta_estandar.in_(conductas), HechoSeguridad.fecha_evento.between(desde, hasta)
        ).scalar() or 0)

    inicio_anio, inicio_semana = date(corte.year, 1, 1), corte - timedelta(days=6)
    previa_fin = inicio_semana - timedelta(days=1)
    previa_ini = previa_fin - timedelta(days=6)
    anterior_fin = _un_anio_antes(corte)
    filas = []
    for nombre, conductas, unidad in FILAS:
        anio = contar(conductas, inicio_anio, corte)
        anterior = contar(conductas, date(corte.year - 1, 1, 1), anterior_fin)
        filas.append({"nombre": nombre, "unidad": unidad, "semana": contar(conductas, inicio_semana, corte),
                      "semana_previa": contar(conductas, previa_ini, previa_fin),
                      "anio": anio, "anio_anterior": anterior, **_variacion(anio, anterior)})

    # Homicidios por mes del año, frente al mismo mes del año anterior (el mes del corte, hasta el mismo día).
    meses = []
    for mes in range(1, corte.month + 1):
        desde = date(corte.year, mes, 1)
        hasta = corte if mes == corte.month else (date(corte.year, mes + 1, 1) - timedelta(days=1))
        meses.append({"mes": MESES_CORTOS[mes - 1], "parcial": mes == corte.month,
                      "actual": contar(["Homicidio"], desde, hasta),
                      "anterior": contar(["Homicidio"], _un_anio_antes(desde), _un_anio_antes(hasta))})

    from services.cobertura_sabana import meses_incompletos, nombre_mes
    faltan = meses_incompletos(db, date(corte.year - 1, 1, 1), anterior_fin, corte)
    notas = ["Homicidios: cada víctima cuenta. Hurtos: cada hecho cuenta una vez, con la última entrega de la Policía.",
             "Cifras preliminares: los días recientes pueden subir por reportes tardíos."]
    if faltan:
        notas.append(f"El registro de {corte.year - 1} no trae completo {nombre_mes(faltan[0])}: la comparación puede quedar baja.")
    return {
        "titulo": "Así va la seguridad en Jamundí",
        "periodo": f"Del 1 de enero al {_dia(corte)} de {corte.year}",
        "corte": corte.isoformat(),
        "anio": corte.year,
        "anio_anterior": corte.year - 1,
        "semana": f"Del {_dia(inicio_semana)} al {_dia(corte)}",
        "semana_previa": f"Del {_dia(previa_ini)} al {_dia(previa_fin)}",
        "filas": filas,
        "homicidios_por_mes": meses,
        "fuente": f"Policía Nacional, registro semanal con corte al {_dia(corte)} de {corte.year}",
        "notas": notas,
    }


def texto(reporte: Dict) -> str:
    """Versión en texto, para copiar o enviar por WhatsApp."""
    lineas = [f"*{reporte['titulo']}*", reporte["periodo"], ""]
    for f in reporte["filas"]:
        cambio = "igual" if not f["diferencia"] else (f"subió {f['diferencia']}" if f["diferencia"] > 0 else f"bajó {-f['diferencia']}")
        lineas.append(f"• {f['nombre']}: *{f['anio']}* (mismo periodo de {reporte['anio_anterior']}: {f['anio_anterior']}; {cambio}). "
                      f"Última semana: {f['semana']}.")
    lineas += ["", f"Última semana: {reporte['semana'].lower()}.", f"Fuente: {reporte['fuente']}. Cifras preliminares."]
    return "\n".join(lineas)
