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


def cubre(db: Session, desde: date, hasta: date, margen: int = 20) -> bool:
    """Si hay comparendos al principio y al final del periodo: sin eso, comparar daría cambios falsos
    (por ejemplo, 2025 solo tiene reportes de enero a mayo)."""
    sub = primeras_fechas(db)
    inicio, fin = _limites(desde, hasta)
    primero, ultimo = db.query(func.min(sub.c.fecha), func.max(sub.c.fecha)).filter(
        sub.c.fecha >= inicio, sub.c.fecha < fin).one()
    if not primero or not ultimo:
        return False
    primero = primero.date() if isinstance(primero, datetime) else primero
    ultimo = ultimo.date() if isinstance(ultimo, datetime) else ultimo
    return primero <= desde + timedelta(days=margen) and ultimo >= hasta - timedelta(days=margen)


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


def comportamientos_por_barrio(db: Session, desde: date, hasta: date, nombres=None) -> dict:
    """{barrio: [(etiqueta, comparendos), ...]} de mayor a menor, por artículo del Código de Convivencia."""
    sub = primeras_fechas(db)
    inicio, fin = _limites(desde, hasta)
    query = (db.query(InspeccionExpediente.localidad, InspeccionMedida.articulo,
                      func.count(func.distinct(sub.c.expediente_id)))
             .select_from(sub)
             .join(InspeccionExpediente, InspeccionExpediente.id == sub.c.expediente_id)
             .join(InspeccionMedida, InspeccionMedida.expediente_id == InspeccionExpediente.id)
             .filter(sub.c.fecha >= inicio, sub.c.fecha < fin, InspeccionMedida.articulo.isnot(None)))
    if nombres is not None:
        query = query.filter(InspeccionExpediente.localidad.in_(list(nombres)))
    acumulado = {}
    for barrio, texto, valor in query.group_by(InspeccionExpediente.localidad, InspeccionMedida.articulo).all():
        numero = numero_articulo(texto) or texto
        por_barrio = acumulado.setdefault(barrio, {})
        por_barrio.setdefault(numero, [etiqueta_articulo(texto), 0])[1] += int(valor)
    return {barrio: sorted((tuple(v) for v in datos.values()), key=lambda item: -item[1])
            for barrio, datos in acumulado.items()}


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
    principal = comportamientos_por_barrio(db, desde, hasta, nombres) if nombres else {}
    fin_de_semana = {}
    if nombres:
        dia = func.extract("isodow", sub.c.fecha)
        for barrio, valor in (db.query(InspeccionExpediente.localidad, func.count(sub.c.expediente_id))
                              .select_from(sub)
                              .join(InspeccionExpediente, InspeccionExpediente.id == sub.c.expediente_id)
                              .filter(*en_periodo, InspeccionExpediente.localidad.in_(nombres), dia.in_([6, 7]))
                              .group_by(InspeccionExpediente.localidad).all()):
            fin_de_semana[barrio] = int(valor)

    lista_barrios = []
    for nombre, valor in top_barrios:
        opciones = principal.get(nombre, [])
        mayor = opciones[0] if opciones else None
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


def capa_mapa(db: Session, desde: date, hasta: date, articulo: Optional[str] = None, minimo: int = 3) -> dict:
    """Comparendos por territorio oficial (mismo polígono y punto interior que la capa de delitos)."""
    from services.geocoding_service import GeocodingService

    filtros = filtros_barrio()
    if articulo:
        filtros.append(InspeccionMedida.articulo.like(f"Art. {articulo} %"))
    filas = agrupar(db, InspeccionExpediente.localidad, desde, hasta, filtros=filtros, limite=2000)
    detalle = comportamientos_por_barrio(db, desde, hasta, [nombre for nombre, _ in filas])
    puntos, sin_poligono, ocultos = {}, [], 0
    for nombre, total in filas:
        total = int(total)
        if total < minimo:
            ocultos += total
            continue
        territorio = GeocodingService.get_official_territory(nombre)
        comportamientos = [etiqueta for etiqueta, _ in detalle.get(nombre, [])]
        if not territorio:
            sin_poligono.append({"name": nombre, "total": total, "reason": "sin polígono oficial para este nombre"})
            continue
        clave = territorio.get("name") or nombre
        actual = puntos.get(clave)
        if actual:
            actual["total"] += total
            actual["aliases"].append(nombre)
            actual["conductas"] = list(dict.fromkeys(actual["conductas"] + comportamientos))
            continue
        lat, lng = territorio["coords"]
        puntos[clave] = {"name": clave, "total": total, "aliases": [nombre], "lat": lat, "lng": lng,
                         "geometry": territorio["geometry"], "source": territorio.get("source", "cartografia oficial"),
                         "zones": [], "conductas": comportamientos}
    return {
        "type": "official_territory_polygons",
        "min_location_count": minimo,
        "suppressed_count": ocultos,
        "excluded_non_territorial_count": 0,
        "unmapped_count": len(sin_poligono),
        "unmapped_names": sin_poligono,
        "points": sorted(puntos.values(), key=lambda punto: -punto["total"]),
    }


def _mismo_tramo(anio: int, corte: date) -> date:
    """El mismo día de corte en otro año (el 29 de febrero cae en el 28)."""
    try:
        return corte.replace(year=anio)
    except ValueError:
        return corte.replace(year=anio, day=28)


def _por_anio(db: Session, columna, anios, corte: Optional[date], filtros=()) -> dict:
    """{(valor, año): comparendos}. Con `corte`, cada año solo cuenta de enero hasta ese mismo día."""
    sub = primeras_fechas(db)
    anio = func.extract("year", sub.c.fecha)
    query = db.query(columna, anio, func.count(func.distinct(sub.c.expediente_id))).select_from(sub)
    if columna is not None and columna is not True:
        query = query.join(InspeccionExpediente, InspeccionExpediente.id == sub.c.expediente_id) \
                     .join(InspeccionMedida, InspeccionMedida.expediente_id == InspeccionExpediente.id)
    condiciones = [anio.in_(list(anios)), *filtros]
    if corte:
        # Día del año hasta el corte: compara tramos iguales entre años.
        condiciones.append(func.to_char(sub.c.fecha, "MM-DD") <= corte.strftime("%m-%d"))
    filas = query.filter(*condiciones).group_by(columna, anio).all()
    return {(valor, int(a)): int(n) for valor, a, n in filas}


def tendencia(db: Session, desde: int = 2018, hoy: Optional[date] = None) -> dict:
    """Comparendos por año (completo y mismo tramo), por comportamiento y por barrio."""
    hoy = hoy or date.today()
    ultimo = corte(db, hoy)
    if not ultimo:
        return {"anios": [], "comportamientos": [], "barrios": []}
    anios = list(range(desde, ultimo.year + 1))
    # Una sola consulta: por año, total, mismo tramo y primera/última fecha (para saber si está completo).
    sub = primeras_fechas(db)
    anio_col = func.extract("year", sub.c.fecha)
    en_tramo = func.to_char(sub.c.fecha, "MM-DD") <= ultimo.strftime("%m-%d")
    filas = (db.query(anio_col, func.count(sub.c.expediente_id),
                      func.count(sub.c.expediente_id).filter(en_tramo),
                      func.min(sub.c.fecha), func.max(sub.c.fecha), func.max(sub.c.fecha).filter(en_tramo))
             .filter(anio_col.between(desde, ultimo.year), sub.c.fecha < _limites(ultimo, ultimo)[1])
             .group_by(anio_col).all())
    por = {int(a): (int(t), int(tr), mn, mx, mxt) for a, t, tr, mn, mx, mxt in filas}
    dia = lambda valor: valor.date() if isinstance(valor, datetime) else valor
    margen = timedelta(days=20)
    total_anio = {a: por.get(a, (0,))[0] for a in anios}
    tramo = {a: por[a][1] if a in por else 0 for a in anios}
    completos = {a for a in anios if a in por and a < ultimo.year
                 and dia(por[a][2]) <= date(a, 1, 1) + margen and dia(por[a][3]) >= date(a, 12, 31) - margen}
    tramo_ok = {a: a in por and por[a][4] is not None and dia(por[a][2]) <= date(a, 1, 1) + margen
                and dia(por[a][4]) >= _mismo_tramo(a, ultimo) - margen for a in anios}

    def variacion(actual, anterior):
        return round((actual - anterior) * 100 / anterior, 1) if anterior else None

    serie = [{"anio": a, "total": total_anio[a], "completo": a in completos or a == ultimo.year,
              "en_curso": a == ultimo.year, "mismo_tramo": tramo[a] if tramo_ok[a] else None} for a in anios]

    # Comportamientos: mismo tramo en cada año, agrupados por artículo.
    crudo = _por_anio(db, InspeccionMedida.articulo, anios, ultimo, [InspeccionMedida.articulo.isnot(None)])
    por_articulo: dict = {}
    for (texto, a), n in crudo.items():
        numero = numero_articulo(texto) or texto
        fila = por_articulo.setdefault(numero, {"articulo": numero, "etiqueta": etiqueta_articulo(texto), "por_anio": {}})
        fila["por_anio"][a] = fila["por_anio"].get(a, 0) + n
    previo = ultimo.year - 1
    comportamientos = sorted(por_articulo.values(), key=lambda f: -f["por_anio"].get(ultimo.year, 0))[:6]
    for fila in comportamientos:
        fila["variacion"] = variacion(fila["por_anio"].get(ultimo.year, 0), fila["por_anio"].get(previo, 0)) if tramo_ok.get(previo) else None

    # Barrios: mismo tramo; los 8 con más comparendos este año y su cambio frente al año anterior.
    crudo = _por_anio(db, InspeccionExpediente.localidad, [previo, ultimo.year], ultimo, filtros_barrio())
    barrios: dict = {}
    for (nombre, a), n in crudo.items():
        barrios.setdefault(nombre, {"barrio": nombre, "por_anio": {}})["por_anio"][a] = n
    lista = sorted(barrios.values(), key=lambda f: -f["por_anio"].get(ultimo.year, 0))[:8]
    for fila in lista:
        fila["variacion"] = variacion(fila["por_anio"].get(ultimo.year, 0), fila["por_anio"].get(previo, 0)) if tramo_ok.get(previo) else None

    return {
        "corte": ultimo.isoformat(),
        "tramo": f"1 de enero al {ultimo.day} de {['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'][ultimo.month - 1]}",
        "anios": serie,
        "variacion_tramo": variacion(tramo[ultimo.year], tramo.get(previo, 0)) if tramo_ok.get(previo) else None,
        "comportamientos": comportamientos,
        "barrios": lista,
        "anio_actual": ultimo.year,
        "anio_previo": previo,
    }
