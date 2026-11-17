"""Seguimiento de las metas del PISCC por periodo: un mes, un trimestre, un semestre o el rango que se pida.

Las metas del PISCC (tabla 16) son anuales. Para leerlas en un periodo más corto se muestra:
- lo ocurrido en el periodo y en los mismos meses del año anterior;
- el acumulado del año hasta el último mes del periodo, frente a la meta anual;
- el ritmo: el acumulado del año frente a la parte de la meta anual que corresponde a esos meses
  (meta x mes final / 12). Se mide con el acumulado y no con el periodo solo, porque un mes suelto con
  pocos casos cambia de color por uno o dos hechos y contradice la lectura anual. Es una referencia:
  los delitos no se reparten parejo en el año. Con metas menores de 20 no se calcula.

Solo cuentan meses completos y publicados por la fuente; un periodo que va más allá se recorta y se avisa.
Homicidios, secuestro, extorsión, violencia intrafamiliar, hurto a motocicletas y lesiones salen de la
serie mensual de MinDefensa (data/piscc/historico.json). Convivencia sale del RNMC: quien llama entrega
los comparendos por mes (`convivencia`), para que este módulo no dependa de la base de datos.

Meses que MinDefensa aún no publica: si el periodo pedido cae completo después de su último mes, homicidios,
hurto a motocicletas y lesiones se muestran con la sábana de la Policía (`preliminar`), marcados como
preliminares y sin calificar frente a la meta. Nunca se suman meses de las dos fuentes: cuentan distinto.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

Mes = Tuple[int, int]

NOMBRES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
           "noviembre", "diciembre"]
MAX_MESES = 24
META_PEQUENA = 20
FUENTE_RNMC = "RNMC / Inspecciones de Policía (comparendos, cada uno una vez)"
FUENTE_SABANA = {
    "homicidios": "Sábana de la Policía (víctimas), preliminar",
    "motos": "Sábana de la Policía (hechos únicos), preliminar",
    "lesiones": "Sábana de la Policía (hechos únicos), preliminar",
}
ESTADOS = {
    "SUPERADA": "Ya pasó la meta anual",
    "EN_RITMO": "Dentro del ritmo de la meta",
    "SOBRE_RITMO": "Por encima del ritmo de la meta",
    "SIN_REFERENCIA": "Meta pequeña: se lee con el acumulado del año",
    "PRELIMINAR": "Preliminar: aún no se califica frente a la meta",
    "SIN_DATOS": "Sin datos publicados para el periodo",
}


def parse_mes(texto: str) -> Mes:
    """'2026-07' -> (2026, 7). Lanza ValueError si no es un mes válido."""
    partes = str(texto or "").strip().split("-")
    if len(partes) < 2:
        raise ValueError("El mes va como AAAA-MM, por ejemplo 2026-07.")
    anio, mes = int(partes[0]), int(partes[1])
    if not (2023 <= anio <= 2100 and 1 <= mes <= 12):
        raise ValueError("El mes va como AAAA-MM, desde 2023.")
    return anio, mes


def meses_entre(desde: Mes, hasta: Mes) -> List[Mes]:
    if desde > hasta:
        raise ValueError("El mes inicial no puede ser posterior al final.")
    meses, (anio, mes) = [], desde
    while (anio, mes) <= hasta:
        meses.append((anio, mes))
        anio, mes = (anio, mes + 1) if mes < 12 else (anio + 1, 1)
    if len(meses) > MAX_MESES:
        raise ValueError(f"El periodo no puede pasar de {MAX_MESES} meses.")
    return meses


def texto_periodo(desde: Mes, hasta: Mes) -> str:
    if desde == hasta:
        return f"{NOMBRES[desde[1] - 1]} de {desde[0]}"
    if desde[0] == hasta[0]:
        return f"{NOMBRES[desde[1] - 1]} a {NOMBRES[hasta[1] - 1]} de {hasta[0]}"
    return f"{NOMBRES[desde[1] - 1]} de {desde[0]} a {NOMBRES[hasta[1] - 1]} de {hasta[0]}"


def ultimo_mes_cerrado(hoy: date) -> Mes:
    if hoy.day == monthrange(hoy.year, hoy.month)[1]:
        return hoy.year, hoy.month
    return (hoy.year, hoy.month - 1) if hoy.month > 1 else (hoy.year - 1, 12)


def _valor_mindefensa(clave: str, mes: Mes, datos: Optional[Dict], publicado: Optional[Mes]) -> Optional[int]:
    """Casos del mes. Un mes publicado sin casos vale 0; uno sin publicar, None."""
    if not publicado or mes > publicado:
        return None
    serie = (((datos or {}).get("series") or {}).get(clave) or {}).get(str(mes[0])) or {}
    return int(serie.get(str(mes[1]), 0))


def _suma(valores: List[Optional[int]]) -> Optional[int]:
    return sum(valores) if valores and all(v is not None for v in valores) else None


def _variacion(actual: Optional[int], anterior: Optional[int]) -> Dict[str, Any]:
    if actual is None or anterior is None:
        return {"diferencia": None, "variacion_pct": None}
    return {"diferencia": actual - anterior,
            "variacion_pct": round((actual - anterior) * 100 / anterior, 1) if anterior else None}


def _fila_preliminar(clave: str, pedido: List[Mes], preliminar: Optional[Dict[str, Dict[Mes, int]]],
                     hasta: Optional[Mes], publicado) -> Optional[Dict[str, Any]]:
    """Periodo completo posterior a MinDefensa, medido con la sábana de la Policía. None si no aplica."""
    datos = (preliminar or {}).get(clave)
    meses = [m for m in pedido if hasta and m <= hasta]
    if not datos or not meses:
        return None
    total = _suma([datos.get(m) for m in meses])
    if total is None:
        return None
    anterior = _suma([datos.get((a - 1, m)) for a, m in meses])
    fin = meses[-1]
    actual = [publicado((fin[0], m)) for m in range(1, 13)]
    indices = [m - 1 for a, m in meses if a == fin[0]]
    for i in indices:
        actual[i] = datos.get((fin[0], i + 1))
    detalle = f"{total} en {texto_periodo(meses[0], fin)} según la sábana de la Policía"
    if anterior is not None:
        detalle += f"; {anterior} en los mismos meses del año anterior, con la misma fuente"
    detalle += ". MinDefensa todavía no publica este periodo: la cifra es preliminar y no se suma al acumulado del año."
    return {
        "status": "PRELIMINAR", "status_label": ESTADOS["PRELIMINAR"], "preliminary": True,
        "source": FUENTE_SABANA.get(clave, "Sábana de la Policía, preliminar"),
        "value": total, "previous": anterior, **_variacion(total, anterior),
        "year_to_date": None, "year_to_date_over_goal": False, "goal_share": None, "year_to_date_reference": None,
        "months_counted": len(meses), "counted_from": f"{meses[0][0]}-{meses[0][1]:02d}",
        "counted_to": f"{fin[0]}-{fin[1]:02d}",
        "series": [{"anio": fin[0] - 1, "valores": [publicado((fin[0] - 1, m)) for m in range(1, 13)]},
                   {"anio": fin[0], "valores": actual, "preliminares": indices}],
        "detail": detalle,
    }


def seguimiento(desde: Mes, hasta: Mes, datos: Optional[Dict], convivencia: Optional[Dict[Mes, int]] = None,
                convivencia_hasta: Optional[Mes] = None, hoy: Optional[date] = None,
                preliminar: Optional[Dict[str, Dict[Mes, int]]] = None,
                preliminar_hasta: Optional[Mes] = None) -> Dict[str, Any]:
    """Metas del PISCC en el periodo `desde`..`hasta` (meses, ambos incluidos).

    `convivencia`: comparendos del RNMC por mes; `convivencia_hasta`: último mes completo cargado.
    `preliminar`: {meta: {(año, mes): casos}} de la sábana de la Policía para meses que MinDefensa no publica
    (y los mismos meses del año anterior); `preliminar_hasta`: último mes completo de la sábana.
    """
    from services.piscc_goals import TABLE_16
    from services.piscc_historico import FUENTE, _ultimo_publicado

    hoy = hoy or date.today()
    pedido = meses_entre(desde, hasta)
    cerrado = ultimo_mes_cerrado(hoy)
    publicado_md = _ultimo_publicado(datos)
    publicado_md = min(publicado_md, cerrado) if publicado_md else None
    publicado_rnmc = min(convivencia_hasta, cerrado) if convivencia_hasta else None
    convivencia = convivencia or {}

    def valor(clave: str, mes: Mes) -> Optional[int]:
        if clave == "convivencia":
            # Un mes sin comparendos cargados no es cero: es un mes sin reporte del RNMC.
            return convivencia.get(mes) if publicado_rnmc and mes <= publicado_rnmc else None
        return _valor_mindefensa(clave, mes, datos, publicado_md)

    indicadores = []
    for clave, etiqueta, linea_base, meta, _indicador in TABLE_16:
        publicado = publicado_rnmc if clave == "convivencia" else publicado_md
        meses = [m for m in pedido if publicado and m <= publicado]
        fila: Dict[str, Any] = {
            "id": clave, "label": etiqueta, "baseline_2023": linea_base, "goal_2027": meta,
            "source": FUENTE_RNMC if clave == "convivencia" else FUENTE,
            "published_until": f"{publicado[0]}-{publicado[1]:02d}" if publicado else None,
            "months_requested": len(pedido), "months_counted": len(meses),
        }
        actuales = [valor(clave, m) for m in meses]
        total = _suma(actuales)
        if not meses:
            fila_preliminar = _fila_preliminar(clave, pedido, preliminar, preliminar_hasta,
                                               lambda mes, clave=clave: valor(clave, mes))
            if fila_preliminar:
                indicadores.append({**fila, **fila_preliminar})
                continue
        if not meses or total is None:
            indicadores.append({**fila, "status": "SIN_DATOS", "status_label": ESTADOS["SIN_DATOS"], "value": None,
                                "previous": None, "diferencia": None, "variacion_pct": None, "year_to_date": None,
                                "goal_share": None, "series": [],
                                "detail": "La fuente todavía no publica meses completos de este periodo."})
            continue
        anterior = _suma([valor(clave, (a - 1, m)) for a, m in meses])
        fin = meses[-1]
        acumulado = _suma([valor(clave, (fin[0], m)) for m in range(1, fin[1] + 1)])
        parte = None if meta < META_PEQUENA else round(meta * len(meses) / 12, 1)
        # Parte de la meta anual que corresponde de enero al último mes contado.
        referencia = None if meta < META_PEQUENA else round(meta * fin[1] / 12, 1)
        if acumulado is not None and acumulado > meta:
            estado = "SUPERADA"
        elif parte is None:
            estado = "SIN_REFERENCIA"
        elif acumulado is not None:
            estado = "EN_RITMO" if acumulado <= referencia else "SOBRE_RITMO"
        else:
            # Sin todos los meses del año no hay acumulado: se compara el periodo solo.
            estado = "EN_RITMO" if total <= parte else "SOBRE_RITMO"
        detalle = f"{total} en {texto_periodo(meses[0], fin)}"
        if anterior is not None:
            detalle += f"; {anterior} en los mismos meses del año anterior"
        if acumulado is not None:
            detalle += f". Acumulado de {fin[0]} hasta {NOMBRES[fin[1] - 1]}: {acumulado}; meta anual: {meta}"
        if len(meses) < len(pedido):
            detalle += f". La fuente publica hasta {NOMBRES[publicado[1] - 1]} de {publicado[0]}: el periodo se recortó"
        indicadores.append({
            **fila, "status": estado, "status_label": ESTADOS[estado], "value": total, "previous": anterior,
            **_variacion(total, anterior), "year_to_date": acumulado,
            "year_to_date_over_goal": acumulado is not None and acumulado > meta,
            "goal_share": parte, "year_to_date_reference": referencia if acumulado is not None else None,
            "counted_from": f"{meses[0][0]}-{meses[0][1]:02d}",
            "counted_to": f"{fin[0]}-{fin[1]:02d}",
            "series": [{"anio": anio, "valores": [valor(clave, (anio, m)) for m in range(1, 13)]}
                       for anio in (fin[0] - 1, fin[0])],
            "detail": detalle + ".",
        })
    return {
        "desde": f"{desde[0]}-{desde[1]:02d}", "hasta": f"{hasta[0]}-{hasta[1]:02d}",
        "periodo": texto_periodo(desde, hasta), "months_requested": len(pedido),
        "source": "PISCC 2024-2027, tabla 16 (indicadores de resultado)",
        "indicators": indicadores,
        "over_pace": [i["id"] for i in indicadores if i["status"] in ("SOBRE_RITMO", "SUPERADA")],
        "status_legend": ESTADOS,
        "note": ("Las metas del PISCC son anuales. El ritmo compara el acumulado del año con la parte de la meta "
                 "que corresponde a esos meses (meta x mes / 12); es una referencia, porque los casos no se "
                 "distribuyen parejo en el año. "
                 "Solo se cuentan meses completos publicados por cada fuente. MinDefensa cuenta víctimas. "
                 "Un periodo que MinDefensa aún no publica se muestra con la sábana de la Policía como "
                 "preliminar, sin sumarlo al acumulado ni calificarlo frente a la meta."),
    }


def periodo_por_defecto(datos: Optional[Dict], hoy: Optional[date] = None) -> Tuple[Mes, Mes]:
    """El último mes completo que publica MinDefensa (o el último mes cerrado si no hay archivo)."""
    from services.piscc_historico import _ultimo_publicado

    hoy = hoy or date.today()
    cerrado = ultimo_mes_cerrado(hoy)
    publicado = _ultimo_publicado(datos)
    mes = min(publicado, cerrado) if publicado else cerrado
    return mes, mes


def opciones(datos: Optional[Dict], hoy: Optional[date] = None, preliminar_hasta: Optional[Mes] = None) -> Dict[str, Any]:
    """Periodos listos para el selector: meses, trimestres y semestres con al menos un mes publicado.

    Los que caen completos después de MinDefensa y dentro de la sábana se ofrecen como "(preliminar)".
    """
    from services.piscc_historico import _ultimo_publicado

    hoy = hoy or date.today()
    publicado = _ultimo_publicado(datos)
    ultimo = min(publicado, ultimo_mes_cerrado(hoy)) if publicado else ultimo_mes_cerrado(hoy)
    extendido = max(ultimo, min(preliminar_hasta, ultimo_mes_cerrado(hoy))) if preliminar_hasta else ultimo
    lista: List[Dict[str, str]] = []

    def tramo(tipo: str, etiqueta: str, anio: int, ini: int, fin: int, tope: int, tope_extendido: int) -> None:
        if ini <= tope:
            lista.append({"tipo": tipo, "label": etiqueta, "desde": f"{anio}-{ini:02d}",
                          "hasta": f"{anio}-{min(fin, tope):02d}"})
        elif ini <= tope_extendido:
            lista.append({"tipo": tipo, "label": f"{etiqueta} (preliminar)", "desde": f"{anio}-{ini:02d}",
                          "hasta": f"{anio}-{min(fin, tope_extendido):02d}", "preliminar": True})

    for anio in range(extendido[0], 2023, -1):
        tope = 12 if anio < ultimo[0] else (ultimo[1] if anio == ultimo[0] else 0)
        tope_extendido = 12 if anio < extendido[0] else extendido[1]
        if tope:
            lista.append({"tipo": "anio", "label": f"Año {anio}" + (" (lo publicado)" if tope < 12 else ""),
                          "desde": f"{anio}-01", "hasta": f"{anio}-{tope:02d}"})
        for n, (ini, fin) in enumerate(((1, 6), (7, 12)), start=1):
            tramo("semestre", f"Semestre {n} de {anio}", anio, ini, fin, tope, tope_extendido)
        for n in range(4, 0, -1):
            tramo("trimestre", f"Trimestre {n} de {anio}", anio, 3 * n - 2, 3 * n, tope, tope_extendido)
        for mes in range(tope_extendido, 0, -1):
            tramo("mes", f"{NOMBRES[mes - 1].capitalize()} de {anio}", anio, mes, mes, tope, tope_extendido)
    return {"ultimo_mes": f"{ultimo[0]}-{ultimo[1]:02d}", "ultimo_mes_consulta": f"{extendido[0]}-{extendido[1]:02d}",
            "primer_mes": "2024-01", "periodos": lista}
