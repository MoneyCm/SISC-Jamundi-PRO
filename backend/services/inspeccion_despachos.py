"""A qué inspección de policía (despacho) pertenece cada expediente del RNMC.

Los reportes del RNMC no traen la inspección. Se deduce así, para cada expediente:
1. Si alguna anotación la nombra ("... EXPEDIDA POR LA INSPECCION TERCERA DE POLICIA"), vale la de
   la anotación más reciente que la nombre.
2. Si no, la del funcionario que registró la actuación más reciente, según la tabla de funcionarios
   por inspección vigente en la fecha de esa actuación.
3. Si no hay ninguna de las dos, queda sin identificar (por ejemplo, los comparendos pendientes:
   el RNMC no dice a qué inspección se repartieron).

La asignación se recalcula completa después de cada carga y cada cambio en la tabla de funcionarios.
"""
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models_inspecciones import (
    InspeccionActuacion, InspeccionExpediente, InspeccionFinanza, InspeccionFuncionario, InspeccionMedida,
)

INSPECCIONES = ["PRIMERA", "SEGUNDA", "TERCERA", "CUARTA", "QUINTA", "SEXTA"]
SIN_IDENTIFICAR = "SIN IDENTIFICAR"
_ORDINAL = "|".join(INSPECCIONES)
# "INSPECCION TERCERA", "INSPECCION DE POLICIA SEGUNDA", "INSPECCIONES SEGUNDA" y "SEGUNDA INSPECCION".
_PATRONES = [
    re.compile(rf"\bINSPECCION(?:ES)?\s+(?:DE\s+POLIC\w*\s+)?({_ORDINAL})\b"),
    re.compile(rf"\b({_ORDINAL})\s+INSPECCION"),
]
_SIN_REGISTRADOR = {"", "NAN", "NONE", "NULL"}


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(texto.upper().split())


def inspeccion_en_texto(texto: Optional[str]) -> Optional[str]:
    """La inspección que nombra una anotación, o None si no nombra ninguna."""
    if not texto or not isinstance(texto, str):
        return None
    limpio = _normalizar(texto)
    for patron in _PATRONES:
        encontrado = patron.search(limpio)
        if encontrado:
            return encontrado.group(1)
    return None


def documento_limpio(valor) -> Optional[str]:
    """Documento del registrador sin decimales ni espacios ("12345678.0" -> "12345678")."""
    if valor is None:
        return None
    texto = str(valor).strip()
    if texto.upper() in _SIN_REGISTRADOR:
        return None
    if re.fullmatch(r"\d+\.0+", texto):
        texto = texto.split(".")[0]
    return texto


def _a_fecha(valor) -> Optional[date]:
    if isinstance(valor, datetime):
        return valor.date()
    return valor


class _Vigencias:
    """Funcionarios por documento con su inspección vigente en cada fecha."""

    def __init__(self, funcionarios: List[InspeccionFuncionario]):
        self._por_documento: Dict[str, List[InspeccionFuncionario]] = defaultdict(list)
        for funcionario in funcionarios:
            self._por_documento[documento_limpio(funcionario.documento)].append(funcionario)

    def inspeccion(self, documento: Optional[str], fecha) -> Optional[str]:
        dia = _a_fecha(fecha)
        for funcionario in self._por_documento.get(documento_limpio(documento), []):
            if dia is None or (funcionario.desde <= dia and (funcionario.hasta is None or dia <= funcionario.hasta)):
                return funcionario.inspeccion
        return None


def asignar(db: Session) -> Dict[str, int]:
    """Recalcula la inspección de todos los expedientes. Devuelve cuántos quedaron en cada una."""
    vigencias = _Vigencias(db.query(InspeccionFuncionario).all())
    filas = (
        db.query(InspeccionMedida.expediente_id, InspeccionActuacion.fecha_actuacion,
                 InspeccionActuacion.anotacion, InspeccionActuacion.id_registrador)
        .join(InspeccionActuacion, InspeccionActuacion.medida_id == InspeccionMedida.id)
        .all()
    )
    # Por expediente: (fecha, inspección) de la última anotación que la nombra y del último registrador conocido.
    por_anotacion: Dict = {}
    por_funcionario: Dict = {}
    for expediente_id, fecha, anotacion, registrador in filas:
        nombrada = inspeccion_en_texto(anotacion)
        if nombrada and (expediente_id not in por_anotacion or fecha >= por_anotacion[expediente_id][0]):
            por_anotacion[expediente_id] = (fecha, nombrada)
        del_funcionario = vigencias.inspeccion(registrador, fecha)
        if del_funcionario and (expediente_id not in por_funcionario or fecha >= por_funcionario[expediente_id][0]):
            por_funcionario[expediente_id] = (fecha, del_funcionario)

    conteo: Dict[str, int] = defaultdict(int)
    for expediente in db.query(InspeccionExpediente).all():
        if expediente.id in por_anotacion:
            nueva, origen = por_anotacion[expediente.id][1], "ANOTACION"
        elif expediente.id in por_funcionario:
            nueva, origen = por_funcionario[expediente.id][1], "FUNCIONARIO"
        else:
            nueva, origen = None, None
        if expediente.inspeccion != nueva or expediente.inspeccion_origen != origen:
            expediente.inspeccion, expediente.inspeccion_origen = nueva, origen
        conteo[nueva or SIN_IDENTIFICAR] += 1
    db.flush()
    return dict(conteo)


def _es_gestion():
    """Actuación registrada por la Inspección (el reporte de comparendos no trae registrador)."""
    registrador = func.upper(func.trim(func.coalesce(InspeccionActuacion.id_registrador, "")))
    return registrador.notin_(tuple(_SIN_REGISTRADOR))


def gestion_por_inspeccion(db: Session, anio: int, hoy: Optional[date] = None) -> dict:
    """Gestión del año por inspección: expedientes con actuaciones de la Inspección en el año
    (incluye los de años anteriores), estado actual de sus medidas y recaudo con fecha de pago en el año.

    Las medidas pendientes no se reparten: el RNMC no dice a qué inspección se asignaron.
    """
    inicio_dia = date(anio, 1, 1)
    fin_dia = date(anio + 1, 1, 1)
    if hoy:
        fin_dia = min(fin_dia, hoy + timedelta(days=1))
    inicio, fin = datetime.combine(inicio_dia, datetime.min.time()), datetime.combine(fin_dia, datetime.min.time())
    despacho = func.coalesce(InspeccionExpediente.inspeccion, SIN_IDENTIFICAR)

    gestionados = (
        db.query(InspeccionMedida.expediente_id.label("expediente_id"),
                 func.count(InspeccionActuacion.id).label("actuaciones"))
        .join(InspeccionActuacion, InspeccionActuacion.medida_id == InspeccionMedida.id)
        .filter(_es_gestion(), InspeccionActuacion.fecha_actuacion >= inicio, InspeccionActuacion.fecha_actuacion < fin)
        .group_by(InspeccionMedida.expediente_id)
        .subquery()
    )
    filas: Dict[str, dict] = {}

    def fila(nombre: str) -> dict:
        return filas.setdefault(nombre, {
            "inspeccion": nombre, "expedientes": 0, "actuaciones": 0, "pagadas": 0, "ratificadas": 0,
            "no_impuestas": 0, "en_proceso": 0, "otras": 0, "recaudo": 0.0,
        })

    for nombre, expedientes, actuaciones in (
        db.query(despacho, func.count(gestionados.c.expediente_id), func.sum(gestionados.c.actuaciones))
        .join(gestionados, gestionados.c.expediente_id == InspeccionExpediente.id)
        .group_by(despacho).all()
    ):
        registro = fila(nombre)
        registro["expedientes"] = int(expedientes or 0)
        registro["actuaciones"] = int(actuaciones or 0)

    for nombre, estado, total in (
        db.query(despacho, InspeccionMedida.estado_actual, func.count(InspeccionMedida.id))
        .join(InspeccionMedida, InspeccionMedida.expediente_id == InspeccionExpediente.id)
        .join(gestionados, gestionados.c.expediente_id == InspeccionExpediente.id)
        .group_by(despacho, InspeccionMedida.estado_actual).all()
    ):
        registro = fila(nombre)
        estado = estado or ""
        if "PAGADO" in estado:
            registro["pagadas"] += total
        elif "RATIFICADA" in estado:
            registro["ratificadas"] += total
        elif "NO IMPUESTA" in estado:
            registro["no_impuestas"] += total
        elif "EN PROCESO" in estado:
            registro["en_proceso"] += total
        else:
            registro["otras"] += total

    for nombre, recaudo in (
        db.query(despacho, func.sum(InspeccionFinanza.valor_pagado))
        .join(InspeccionMedida, InspeccionMedida.expediente_id == InspeccionExpediente.id)
        .join(InspeccionFinanza, InspeccionFinanza.medida_id == InspeccionMedida.id)
        .filter(InspeccionFinanza.fecha_pago >= inicio_dia, InspeccionFinanza.fecha_pago < fin_dia)
        .group_by(despacho).all()
    ):
        if recaudo:
            fila(nombre)["recaudo"] = float(recaudo)

    orden = {nombre: i for i, nombre in enumerate(INSPECCIONES)}
    inspecciones = sorted(filas.values(), key=lambda item: orden.get(item["inspeccion"], len(orden)))
    pendientes = (
        db.query(func.count(func.distinct(InspeccionMedida.id)))
        .join(InspeccionActuacion, InspeccionActuacion.medida_id == InspeccionMedida.id)
        .filter(InspeccionMedida.estado_actual == "PENDIENTE",
                InspeccionActuacion.fecha_actuacion >= inicio, InspeccionActuacion.fecha_actuacion < fin)
        .scalar() or 0
    )
    return {"anio": anio, "inspecciones": inspecciones, "pendientes_sin_repartir": int(pendientes)}
