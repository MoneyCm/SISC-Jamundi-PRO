"""Asistente ciudadano del portal público: cifras públicas verificadas y rutas de atención.

No usa IA: responde con el mismo motor verificado del Asesor SISC (periodos, metodología v2, última
entrega de la Policía), pero solo con información pública:
- Rutas de atención primero cuando la persona describe una situación de violencia o peligro.
- Sin cifras por barrio: remite a "Mi barrio", que protege a las víctimas (menos de 3 casos no se muestran).
- Nada del seguimiento interno (compromisos del Consejo, entidades, actas).
"""
import re
from datetime import date
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from services import asistente_secretaria as asesor
from services.asistente_periodos import Periodo, etiqueta, periodo as leer_periodo

EMERGENCIA = "En una emergencia llame al 123."

RUTAS = {
    "vbg": ("Si usted o alguien vive violencia en la familia o por ser mujer:\n"
            "• Si hay peligro inmediato, llame al 123 y busque un lugar seguro.\n"
            "• Puede ir a urgencias del centro de salud más cercano: la atención es prioritaria y no exige denuncia.\n"
            "• La Línea 155 orienta a mujeres víctimas de violencia (gratuita y confidencial).\n"
            "• Una Comisaría de Familia puede ordenar medidas de protección para que el agresor se aleje.\n"
            "• Puede denunciar en la Fiscalía (línea 122) o en una estación de Policía. Denunciar no es requisito "
            "para recibir atención ni protección."),
    "infancia": ("Si un niño, niña o adolescente está en riesgo o es maltratado:\n"
                 "• Llame a la Línea 141 del ICBF. Puede reportar aunque no esté seguro, y el reporte puede ser anónimo.\n"
                 "• Si hay peligro inmediato, llame al 123."),
    "denuncia": ("Para denunciar un delito:\n"
                 "• Fiscalía General de la Nación: línea 122.\n"
                 "• En cualquier estación de Policía.\n"
                 "• Si hay peligro inmediato, llame al 123."),
    "emergencia": ("Si hay peligro para la vida o la integridad, llame ya al 123 (todo el día, todos los días). "
                   "Busque un lugar seguro y, si puede, la compañía de alguien de confianza."),
}

# Palabras de una situación personal (no de una pregunta por cifras).
_SITUACION = {
    "vbg": r"\b(me pega|me golpea|me maltrata|me amenaza|mi (pareja|esposo|esposa|novio|novia|marido|ex)\b|"
           r"violencia (de genero|contra la mujer)|me violo|abuso sexual|acoso|me encerr)",
    "infancia": r"\b(nino|nina|menor|hijo|hija|bebe)\b.*\b(maltrat|golpe|abus|pega|abandon|riesgo)",
    "emergencia": r"\b(auxilio|emergencia|me quieren matar|me van a matar|esta(n)? disparando|disparos|"
                  r"me estan robando|estoy en peligro|socorro)\b",
    "denuncia": r"\b(como|donde|quiero|necesito)\b.*\bdenunci",
}
_PIDE_CIFRAS = r"\b(cuant[oa]s?|cifras?|casos|estadistic|como va|como van|aument|disminu|bajo|subio|tasa|numero)\b"
_INTERNO = ("compromiso", "consejo de seguridad", "acta", "le pido a la policia", "pendientes", "vencid")

SUGERENCIAS = ["¿Cuántos homicidios van en 2026?", "¿Cómo van los hurtos este año?",
               "¿Qué hago si sufro violencia intrafamiliar?"]


def _ayuda() -> str:
    return ("Puedo ayudarle con cifras públicas de seguridad de Jamundí y con las rutas de atención. Por ejemplo:\n"
            "• «¿Cuántos homicidios van en 2026?»\n"
            "• «Hurtos de enero a octubre»\n"
            "• «Homicidios 2025 vs 2026»\n"
            "• «¿Qué hago si sufro violencia intrafamiliar?»\n"
            "Para su barrio, use la sección «Mi barrio» del portal. " + EMERGENCIA)


def _situacion(p: str) -> Optional[str]:
    if re.search(_PIDE_CIFRAS, p):
        return None
    for ruta, patron in _SITUACION.items():
        if re.search(patron, p):
            return ruta
    if re.search(r"\b(violencia intrafamiliar|maltrato)\b", p) and re.search(r"\b(que hago|ayuda|donde|a quien)\b", p):
        return "vbg"
    return None


def _historial(history: List[Dict]) -> List[Dict]:
    """Del formato del portal (sender/text) al del Asesor (rol/texto)."""
    return [{"rol": "usuario" if (m.get("sender") or "") == "user" else "asesor", "texto": m.get("text") or ""}
            for m in history]


def _limpiar(respuesta: Dict) -> str:
    """Texto público: sin la línea de "sábana" interna, con el aviso de emergencia."""
    texto = (respuesta.get("respuesta") or "").replace(
        "La sábana de la Policía cargada en el SISC", "El registro semanal de la Policía")
    texto = texto.replace("Sábana de la Policía al", "Registro semanal de la Policía al").replace("Con la sábana,", "Con el registro semanal,")
    texto = texto.replace("así que con ella no doy", "así que con él no doy")
    return f"{texto}\n\n{EMERGENCIA}"


NOMBRES_PISCC = {"vif": "Violencia intrafamiliar", "extorsion": "Extorsión", "secuestro": "Secuestro"}


def _mindefensa_anio(clave: str, hoy: date) -> Optional[str]:
    """Lo corrido del año según MinDefensa (hasta el último mes publicado), frente al mismo periodo anterior."""
    from services import piscc_historico as ph
    from services.asistente_periodos import MESES
    datos = ph.cargar()
    actual = ph.serie_mensual(clave, hoy.year, datos)
    hasta = max((i for i, v in enumerate(actual) if v is not None), default=-1)
    if hasta < 0 or clave not in NOMBRES_PISCC:
        return None
    anterior = ph.serie_mensual(clave, hoy.year - 1, datos)[:hasta + 1]
    total = sum(actual[:hasta + 1])
    linea = f"• {NOMBRES_PISCC[clave]}: {total} casos de enero a {MESES[hasta]} de {hoy.year}"
    if all(v is not None for v in anterior):
        linea += f" (mismo periodo de {hoy.year - 1}: {sum(anterior)}; {asesor.cambio(total, sum(anterior))})"
    return (f"Registro oficial de MinDefensa / Policía Nacional:\n{linea}.\n\n"
            "El registro semanal de la Policía no trae este delito; esta cifra se publica por mes.")


def responder(db: Session, pregunta: str, history: Optional[List[Dict]] = None, hoy: Optional[date] = None) -> Dict:
    hoy = hoy or date.today()
    p = asesor.normalizar(pregunta)
    resultado = {"tipo": "ayuda", "sugerencias": SUGERENCIAS, "fuentes": []}

    ruta = _situacion(p)
    if ruta:
        return {**resultado, "tipo": "ruta", "respuesta": RUTAS[ruta] + "\n\nTambién puede ver «Rutas de atención» en el portal."}
    if any(w in p for w in _INTERNO):
        return {**resultado, "respuesta": "Ese seguimiento es interno de la Secretaría de Seguridad y no está en el portal. "
                "Aquí puedo darle cifras públicas y rutas de atención.\n\n" + _ayuda()}

    historial = _historial(history or [])
    temas = asesor.detectar_temas(db, pregunta)
    barrios = [b for b in temas.get("barrios", []) if "jamundi" not in asesor.normalizar(b)]  # "Jamundí" no es un barrio
    if barrios or re.search(r"\b(mi barrio|barrio|vereda|sector)\b", p):
        return {**resultado, "tipo": "barrio", "respuesta":
                "Las cifras por barrio están en la sección «Mi barrio» del portal. Allí, para proteger a las víctimas, "
                "un barrio con menos de 3 casos no muestra la cifra exacta.\n\n" + EMERGENCIA}
    if temas.get("piscc") and not temas.get("delitos") and not re.search(r"\bmetas?\b|piscc", p):
        # Violencia intrafamiliar, extorsión, secuestro: la sábana no los trae; MinDefensa sí, por mes.
        texto = _mindefensa_anio(temas["piscc"][0], hoy)
        if texto:
            extra = "\n\n" + RUTAS["vbg"] if temas["piscc"][0] == "vif" else ""
            return {**resultado, "tipo": "cifras", "fuentes": ["MinDefensa / Policía Nacional (datos.gov.co)"],
                    "respuesta": texto + extra + "\n\n" + EMERGENCIA}
    if temas.get("piscc") and not temas.get("delitos") or "piscc" in p or re.search(r"\bmetas?\b", p):
        return {**resultado, "tipo": "metas", "respuesta":
                "El avance de las metas del Plan de Seguridad (PISCC 2024-2027) está en la sección «Metas» del portal, "
                "con la fuente y la fecha de corte de cada una.\n\n" + EMERGENCIA}

    if asesor.periodo_no_soportado(pregunta) and not leer_periodo(pregunta, hoy):
        return {**resultado, "respuesta": "No entendí las fechas de la pregunta. Puede escribir, por ejemplo, «homicidios en "
                "agosto», «hurtos de enero a octubre» o «homicidios en 2026».\n\n" + EMERGENCIA}

    pedido = leer_periodo(pregunta, hoy)
    pregunta_con_tema = asesor.con_tema_previo(db, pregunta, historial)
    tiene_tema = pregunta_con_tema != pregunta or temas.get("delitos") or any(w in p for w in asesor.CONVIVENCIA)
    if not pedido and not tiene_tema and not re.search(r"\b(como va|como esta|seguridad|delitos|jamundi)\b", p):
        return {**resultado, "respuesta": _ayuda()}
    if not pedido:
        # Sin fechas: lo corrido del año.
        pedido = Periodo(date(hoy.year, 1, 1), hoy, etiqueta(date(hoy.year, 1, 1), hoy))
    # "Jamundí" es el municipio entero: no debe leerse como uno de los barrios que llevan ese nombre.
    sin_municipio = re.sub(r"jamund[ií]", " ", pregunta_con_tema, flags=re.IGNORECASE)
    respuesta = asesor.responder_periodo(db, sin_municipio, pedido, hoy)
    fuentes = [f.replace("Sábana de la Policía", "Registro semanal de la Policía") for f in respuesta.get("fuentes", [])]
    return {**resultado, "tipo": "cifras", "fuentes": fuentes, "respuesta": _limpiar(respuesta)}
