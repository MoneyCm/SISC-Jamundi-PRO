"""Periodos que el Asesor SISC entiende en una pregunta: un mes, un rango de días, una semana o una quincena.

Si la pregunta nombra fechas que aquí no se entienden, `periodo` devuelve None y el asesor lo dice,
en lugar de responder con cifras de otro periodo.
"""
import re
import unicodedata
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional, Tuple

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
_MES = "|".join(MESES)
_ANIO = r"(?:\s+(?:de|del)\s+|\s+)((?:19|20)\d{2})\b"
_ORDINALES = {"primera": 0, "segunda": 1, "tercera": 2, "cuarta": 3}


@dataclass(frozen=True)
class Periodo:
    inicio: date
    fin: date
    etiqueta: str


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def fin_de_mes(anio: int, mes: int) -> date:
    return date(anio, mes, monthrange(anio, mes)[1])


def _dia(valor: date) -> str:
    return f"{valor.day} de {MESES[valor.month - 1]}"


def etiqueta(inicio: date, fin: date) -> str:
    if inicio == fin:
        return f"el {_dia(inicio)} de {inicio.year}"
    if inicio.day == 1 and fin == fin_de_mes(fin.year, fin.month):
        if (inicio.year, inicio.month) == (fin.year, fin.month):
            return f"{MESES[inicio.month - 1]} de {inicio.year}"
        desde = MESES[inicio.month - 1] + (f" de {inicio.year}" if inicio.year != fin.year else "")
        return f"de {desde} a {MESES[fin.month - 1]} de {fin.year}"
    if (inicio.year, inicio.month) == (fin.year, fin.month):
        return f"del {inicio.day} al {_dia(fin)} de {fin.year}"
    desde = _dia(inicio) + (f" de {inicio.year}" if inicio.year != fin.year else "")
    return f"del {desde} al {_dia(fin)} de {fin.year}"


def _anio_relativo(p: str, hoy: date) -> Optional[int]:
    if "ano antepasado" in p:
        return hoy.year - 2
    if "ano pasado" in p or "ano anterior" in p:
        return hoy.year - 1
    if "este ano" in p or "ano actual" in p:
        return hoy.year
    return None


def _anio(explicito: Optional[str], relativo: Optional[int], mes: int, dia: int, hoy: date) -> int:
    """Año escrito, o el relativo ("año pasado"), o el más reciente en que esa fecha ya pasó."""
    if explicito:
        return int(explicito) if len(explicito) == 4 else 2000 + int(explicito)
    if relativo is not None:
        return relativo
    return hoy.year if (mes, dia) <= (hoy.month, hoy.day) else hoy.year - 1


def _crear(inicio: date, fin: date) -> Optional[Periodo]:
    return Periodo(inicio, fin, etiqueta(inicio, fin)) if inicio <= fin else None


def periodo(pregunta: str, hoy: date) -> Optional[Periodo]:
    try:
        return _periodo(normalizar(pregunta), hoy)
    except ValueError:  # una fecha que no existe (31 de febrero)
        return None


def _periodo(p: str, hoy: date) -> Optional[Periodo]:
    relativo = _anio_relativo(p, hoy)
    # Números sueltos (sin contar años de cuatro cifras): cada patrón debe usarlos todos, o no se adivina.
    numeros = len(re.findall(r"(?<!\d)\d{1,2}(?!\d)", re.sub(r"\b(?:19|20)\d{2}\b", " ", p)))
    # Días relativos a hoy.
    if re.search(r"\banteayer\b", p):
        return _crear(hoy - timedelta(days=2), hoy - timedelta(days=2))
    if re.search(r"\bayer\b", p):
        return _crear(hoy - timedelta(days=1), hoy - timedelta(days=1))
    m = re.search(r"\bultimos?\s+(\d{1,3})\s+dias\b", p)
    if m:
        return _crear(hoy - timedelta(days=int(m.group(1)) - 1), hoy)
    if "semana pasada" in p:
        lunes = hoy - timedelta(days=hoy.weekday() + 7)
        return _crear(lunes, lunes + timedelta(days=6))
    # Fechas con números: 05/08, 5-08-2025.
    numericas = re.findall(r"(?<!\d)(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}|\d{2}))?(?!\d)", p)
    if numericas:
        if len(numericas) > 2 or numeros != sum(2 + (len(a) == 2) for _d, _m, a in numericas):
            return None
        d, mes, a = numericas[-1]
        fin = date(_anio(a, relativo, int(mes), int(d), hoy), int(mes), int(d))
        d, mes, a = numericas[0]
        # Sin año, la primera fecha toma el de la segunda ("del 01/08 al 15/08/2025").
        anio = _anio(a, None, int(mes), int(d), hoy) if a else (
            fin.year if (int(mes), int(d)) <= (fin.month, fin.day) else fin.year - 1)
        return _crear(date(anio, int(mes), int(d)), fin)
    # "del 5 al 10 de agosto [de 2025]"
    m = re.search(rf"\b(\d{{1,2}})\s+(?:al|a|y|hasta el)\s+(\d{{1,2}})\s+de\s+({_MES})(?:{_ANIO})?", p)
    if m:
        if numeros != 2:
            return None
        mes = MESES.index(m.group(3)) + 1
        anio = _anio(m.group(4), relativo, mes, int(m.group(2)), hoy)
        return _crear(date(anio, mes, int(m.group(1))), date(anio, mes, int(m.group(2))))
    # "el 5 de agosto", "del 5 de julio al 10 de agosto de 2025"
    dias = re.findall(rf"\b(\d{{1,2}})\s+de\s+({_MES})(?:{_ANIO})?", p)
    if dias:
        if len(dias) > 2 or numeros != len(dias):
            return None
        fin_d, fin_m, fin_a = dias[-1]
        mes_fin = MESES.index(fin_m) + 1
        fin = date(_anio(fin_a, relativo, mes_fin, int(fin_d), hoy), mes_fin, int(fin_d))
        ini_d, ini_m, ini_a = dias[0]
        mes_ini = MESES.index(ini_m) + 1
        anio_ini = int(ini_a) if ini_a else (fin.year if (mes_ini, int(ini_d)) <= (fin.month, fin.day) else fin.year - 1)
        return _crear(date(anio_ini, mes_ini, int(ini_d)), fin)
    if re.search(r"\d", re.sub(r"\b(?:19|20)\d{2}\b", " ", p)):
        return None  # otros números junto a fechas: mejor no adivinar
    # "primera semana de agosto", "segunda quincena de julio"
    m = re.search(rf"\b(primera|segunda|tercera|cuarta|ultima)\s+(semana|quincena)\s+de\s+({_MES})(?:{_ANIO})?", p)
    if m:
        mes = MESES.index(m.group(3)) + 1
        anio = _anio(m.group(4), relativo, mes, 1, hoy)
        ultimo = fin_de_mes(anio, mes)
        if m.group(2) == "quincena":
            if m.group(1) not in ("primera", "segunda", "ultima"):
                return None
            return _crear(date(anio, mes, 1), date(anio, mes, 15)) if m.group(1) == "primera" else \
                _crear(date(anio, mes, 16), ultimo)
        if m.group(1) == "ultima":
            return _crear(ultimo - timedelta(days=6), ultimo)
        inicio = date(anio, mes, 1 + 7 * _ORDINALES[m.group(1)])
        return _crear(inicio, inicio + timedelta(days=6))
    if re.search(r"\b(semana|quincena|dia|dias|primeros?|ultimos?|trimestre|semestre)\b", p):
        return None
    # "de enero a marzo", "entre julio y agosto de 2025", "desde agosto"
    m = re.search(rf"\b(?:de|desde|entre)\s+({_MES})\s+(?:a|al|hasta|y)\s+({_MES})(?:{_ANIO})?", p)
    if m:
        mes_ini, mes_fin = MESES.index(m.group(1)) + 1, MESES.index(m.group(2)) + 1
        anio_fin = _anio(m.group(3), relativo, mes_fin, 1, hoy)
        anio_ini = anio_fin if mes_ini <= mes_fin else anio_fin - 1
        return _crear(date(anio_ini, mes_ini, 1), fin_de_mes(anio_fin, mes_fin))
    m = re.search(rf"\bdesde\s+({_MES})(?:{_ANIO})?", p)
    if m:
        mes = MESES.index(m.group(1)) + 1
        return _crear(date(_anio(m.group(2), relativo, mes, 1, hoy), mes, 1), hoy)
    if "mes pasado" in p:
        fin = hoy.replace(day=1) - timedelta(days=1)
        return _crear(fin.replace(day=1), fin)
    if "este mes" in p:
        return _crear(hoy.replace(day=1), hoy)
    meses = re.findall(rf"\b({_MES})\b(?:{_ANIO})?", p)
    if len(meses) != 1:
        return None
    nombre, anio = meses[0]
    mes = MESES.index(nombre) + 1
    anio = _anio(anio, relativo, mes, 1, hoy)
    return _crear(date(anio, mes, 1), fin_de_mes(anio, mes))


def meses_de(inicio: date, fin: date) -> List[Tuple[date, date]]:
    """Cada mes que toca el periodo, recortado al periodo."""
    tramos, actual = [], inicio.replace(day=1)
    while actual <= fin:
        ultimo = fin_de_mes(actual.year, actual.month)
        tramos.append((max(actual, inicio), min(ultimo, fin)))
        actual = ultimo + timedelta(days=1)
    return tramos
