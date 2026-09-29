"""Conteo único de comparendos del RNMC (comportamientos contrarios a la convivencia).

Los reportes del RNMC entran por Inspecciones (services/inspeccion_service.py) a las tablas
inspeccion_*. Un mismo comparendo (expediente) puede tener varias actuaciones y medidas, así que
la cifra oficial cuenta cada expediente una sola vez, en la fecha de su primer registro (la del
hecho en el reporte de comparendos). La usan la meta del PISCC, SISC en cifras y el boletín.

Se excluyen los archivos de prueba y las fechas posteriores a hoy.
"""
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from db.models_inspecciones import InspeccionActuacion, InspeccionExpediente, InspeccionMedida


def filtros_publicos() -> List:
    nombre = func.lower(func.coalesce(InspeccionActuacion.fuente_archivo, ""))
    return [~nombre.like("%test%"), ~nombre.like("%prueba%")]


def _manana() -> datetime:
    return datetime.combine(date.today() + timedelta(days=1), datetime.min.time())


def primeras_fechas(db: Session):
    """Subconsulta (expediente_id, fecha): primer registro de cada comparendo."""
    return (
        db.query(InspeccionMedida.expediente_id.label("expediente_id"),
                 func.min(InspeccionActuacion.fecha_actuacion).label("fecha"))
        .join(InspeccionActuacion, InspeccionActuacion.medida_id == InspeccionMedida.id)
        .filter(*filtros_publicos(), InspeccionActuacion.fecha_actuacion < _manana())
        .group_by(InspeccionMedida.expediente_id)
        .subquery()
    )


def _limites(desde: date, hasta: date) -> Tuple[datetime, datetime]:
    return datetime.combine(desde, datetime.min.time()), datetime.combine(hasta + timedelta(days=1), datetime.min.time())


def contar(db: Session, desde: date, hasta: date) -> int:
    sub = primeras_fechas(db)
    inicio, fin = _limites(desde, hasta)
    return db.query(func.count(sub.c.expediente_id)).filter(sub.c.fecha >= inicio, sub.c.fecha < fin).scalar() or 0


def corte(db: Session, hasta: Optional[date] = None) -> Optional[date]:
    sub = primeras_fechas(db)
    query = db.query(func.max(sub.c.fecha))
    if hasta:
        query = query.filter(sub.c.fecha < _limites(hasta, hasta)[1])
    valor = query.scalar()
    return valor.date() if isinstance(valor, datetime) else valor


def agrupar(db: Session, columna, desde: date, hasta: date, filtros=(), minimo: int = 1, limite: int = 10):
    """Comparendos del periodo por una columna de la medida o del expediente (cada expediente una vez por valor)."""
    sub = primeras_fechas(db)
    inicio, fin = _limites(desde, hasta)
    total = func.count(func.distinct(sub.c.expediente_id))
    return (
        db.query(columna.label("nombre"), total.label("total"))
        .select_from(sub)
        .join(InspeccionExpediente, InspeccionExpediente.id == sub.c.expediente_id)
        .join(InspeccionMedida, InspeccionMedida.expediente_id == InspeccionExpediente.id)
        .filter(sub.c.fecha >= inicio, sub.c.fecha < fin, columna.isnot(None), columna != "", *filtros)
        .group_by(columna)
        .having(total >= minimo)
        .order_by(desc("total"))
        .limit(limite)
        .all()
    )


# Artículos del Código Nacional de Seguridad y Convivencia (Ley 1801 de 2016), en palabras sencillas.
ETIQUETAS_ARTICULO = {
    "27": "Riñas, amenazas y porte de armas o elementos peligrosos",
    "33": "Ruido y perturbación de la tranquilidad",
    "35": "Irrespeto o desobediencia a la autoridad de Policía",
    "38": "Comportamientos que afectan a niños, niñas y adolescentes",
    "92": "Actividad económica sin cumplir requisitos",
    "95": "Celulares sin soporte de procedencia",
    "124": "Tenencia de animales que pone en riesgo la convivencia",
    "135": "Infracciones urbanísticas",
    "140": "Uso indebido del espacio público",
    "146": "Comportamientos en el transporte público",
}
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def numero_articulo(texto: Optional[str]) -> Optional[str]:
    import re

    encontrado = re.search(r"art[íi]?c?u?l?o?\.?\s*(\d+)", str(texto or ""), re.IGNORECASE)
    return encontrado.group(1) if encontrado else None


def etiqueta_articulo(texto: Optional[str]) -> str:
    numero = numero_articulo(texto)
    if numero in ETIQUETAS_ARTICULO:
        return ETIQUETAS_ARTICULO[numero]
    resto = str(texto or "").split(" - ", 1)[-1].strip()
    return resto[:1].upper() + resto[1:].lower() if resto else "Sin artículo registrado"


def por_comportamiento(db: Session, desde: date, hasta: date, limite: int = 8):
    """[(numero, etiqueta, texto oficial, comparendos)], agrupados por artículo."""
    totales = {}
    for texto, total in agrupar(db, InspeccionMedida.articulo, desde, hasta, limite=200):
        numero = numero_articulo(texto) or texto
        actual = totales.setdefault(numero, [numero, etiqueta_articulo(texto), texto, 0])
        actual[3] += int(total)
    return sorted((tuple(v) for v in totales.values()), key=lambda fila: -fila[3])[:limite]


def filtros_barrio() -> List:
    """Descarta valores que no son un barrio (sin dato, no aplica, pendiente...)."""
    nombre = func.upper(func.trim(InspeccionExpediente.localidad))
    return [~nombre.like(f"%{texto}%") for texto in
            ("NO APLICA", "SIN DATO", "PENDIENTE", "POR ASIGNAR", "NO DEFINIDO", "SIN LOCALIDAD", "SIN COMUNA")] + [
        nombre.notin_(["NONE", "NAN", "NULL", "-"])]


def resumen_convivencia(db: Session, desde: date, hasta: date, barrios: int = 10) -> dict:
    """Qué comportamientos y dónde: para la página de Inspecciones (uso institucional, nivel 2)."""
    sub = primeras_fechas(db)
    inicio, fin = _limites(desde, hasta)
    en_periodo = [sub.c.fecha >= inicio, sub.c.fecha < fin]
    total = contar(db, desde, hasta)

    comportamientos = [
        {"articulo": numero, "etiqueta": etiqueta, "texto_oficial": texto, "total": valor,
         "porcentaje": round(valor * 100 / total, 1) if total else 0}
        for numero, etiqueta, texto, valor in por_comportamiento(db, desde, hasta)
    ]

    top_barrios = agrupar(db, InspeccionExpediente.localidad, desde, hasta, filtros=filtros_barrio(), limite=barrios)
    nombres = [nombre for nombre, _ in top_barrios]
    principal = {}
    fin_de_semana = {}
    if nombres:
        cruce = (db.query(InspeccionExpediente.localidad, InspeccionMedida.articulo,
                          func.count(func.distinct(sub.c.expediente_id)))
                 .select_from(sub)
                 .join(InspeccionExpediente, InspeccionExpediente.id == sub.c.expediente_id)
                 .join(InspeccionMedida, InspeccionMedida.expediente_id == InspeccionExpediente.id)
                 .filter(*en_periodo, InspeccionExpediente.localidad.in_(nombres), InspeccionMedida.articulo.isnot(None))
                 .group_by(InspeccionExpediente.localidad, InspeccionMedida.articulo).all())
        for barrio, texto, valor in cruce:
            numero = numero_articulo(texto) or texto
            por_barrio = principal.setdefault(barrio, {})
            por_barrio[numero] = por_barrio.get(numero, [etiqueta_articulo(texto), 0])
            por_barrio[numero][1] += int(valor)
        dia = func.extract("isodow", sub.c.fecha)
        for barrio, valor in (db.query(InspeccionExpediente.localidad, func.count(sub.c.expediente_id))
                              .select_from(sub)
                              .join(InspeccionExpediente, InspeccionExpediente.id == sub.c.expediente_id)
                              .filter(*en_periodo, InspeccionExpediente.localidad.in_(nombres), dia.in_([6, 7]))
                              .group_by(InspeccionExpediente.localidad).all()):
            fin_de_semana[barrio] = int(valor)

    lista_barrios = []
    for nombre, valor in top_barrios:
        opciones = sorted(principal.get(nombre, {}).items(), key=lambda item: -item[1][1])
        mayor = opciones[0][1] if opciones else None
        lista_barrios.append({
            "barrio": nombre, "total": int(valor),
            "porcentaje": round(valor * 100 / total, 1) if total else 0,
            "principal": {"etiqueta": mayor[0], "total": mayor[1],
                          "porcentaje": round(mayor[1] * 100 / valor, 1)} if mayor else None,
            "fin_de_semana_pct": round(fin_de_semana.get(nombre, 0) * 100 / valor, 1) if valor else 0,
        })

    dia = func.extract("isodow", sub.c.fecha)
    por_dia = dict(db.query(dia, func.count(sub.c.expediente_id)).filter(*en_periodo).group_by(dia).all())
    mes = func.extract("month", sub.c.fecha)
    por_mes = db.query(mes, func.count(sub.c.expediente_id)).filter(*en_periodo).group_by(mes).order_by(mes).all()

    return {
        "desde": desde.isoformat(), "hasta": hasta.isoformat(), "corte": (corte(db, hasta) or hasta).isoformat(),
        "total": total,
        "comportamientos": comportamientos,
        "barrios": lista_barrios,
        "dias": [{"dia": nombre, "total": int(por_dia.get(i + 1, 0))} for i, nombre in enumerate(DIAS)],
        "meses": [{"mes": MESES[int(m) - 1], "total": int(v)} for m, v in por_mes],
    }


DIAS_ALERTA = 35  # los reportes del RNMC llegan cada mes; más de 35 días sin datos nuevos es atraso


def estado_carga(db: Session, hoy: Optional[date] = None) -> dict:
    """Qué tan al día están los comparendos: último dato, última carga y si ya toca pedir los reportes."""
    hoy = hoy or date.today()
    ultimo = corte(db, hoy)
    ultima_carga = db.query(func.max(InspeccionActuacion.created_at)).filter(*filtros_publicos()).scalar()
    dias = (hoy - ultimo).days if ultimo else None
    return {
        "corte": ultimo.isoformat() if ultimo else None,
        "ultima_carga": ultima_carga.date().isoformat() if ultima_carga else None,
        "dias_desde_corte": dias,
        "dias_alerta": DIAS_ALERTA,
        "atrasado": ultimo is None or dias > DIAS_ALERTA,
        "comparendos_anio": contar(db, date(ultimo.year, 1, 1), ultimo) if ultimo else 0,
    }
