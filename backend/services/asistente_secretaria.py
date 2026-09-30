"""Asesor SISC: responde preguntas de la dirección con cifras oficiales verificadas.

Cómo evita inventar:
1. El código arma un expediente con las cifras oficiales (las mismas de la hoja ejecutiva, el
   boletín, el PISCC, los compromisos del Consejo y las fuentes externas) y, según la pregunta,
   agrega lo específico de un barrio, un delito o una entidad.
2. La IA (Gemini y, si falla, Mistral) solo redacta a partir de ese expediente.
3. services/ai_output_guard.verify_ai_text comprueba cada número y cada "subió/bajó". Si ninguna
   IA pasa la verificación, se responde con un texto calculado sin IA.
Solo cifras agregadas: el expediente no lleva nombres ni datos personales.
"""
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models_hechos_seguridad import HechoSeguridad
from services.entrega_vigente import filtro_hechos
from services.hechos_metrics import hechos_unicos_expr

MAX_PALABRAS = 140
SUGERENCIAS_INICIALES = [
    "¿Cómo vamos esta semana?",
    "¿Qué le pido a la Policía en el próximo Consejo?",
    "¿Qué barrio me debe preocupar más?",
    "¿Cómo va el PISCC?",
    "¿Cómo va la convivencia este año?",
    "Resúmame la semana para WhatsApp",
]
DELITOS = {
    "homicidio": ["Homicidio"], "asesinat": ["Homicidio"], "muert": ["Homicidio"],
    "lesion": ["Lesiones personales"], "rina": ["Lesiones personales"],
    "hurto a persona": ["Hurto a personas"], "robo a persona": ["Hurto a personas"], "atraco": ["Hurto a personas"],
    "celular": ["Hurto a personas"], "moto": ["Hurto a motocicletas"], "carro": ["Hurto a automotores"],
    "vehiculo": ["Hurto a motocicletas", "Hurto a automotores"], "residencia": ["Hurto a residencias"],
    "casa": ["Hurto a residencias"], "comercio": ["Hurto a comercio"], "tienda": ["Hurto a comercio"],
    "hurto": ["Hurto a personas", "Hurto a motocicletas", "Hurto a automotores", "Hurto a residencias", "Hurto a comercio"],
}
ENTIDADES = {
    "policia": "Policía", "ejercito": "Ejército", "gobierno": "Secretaría de Gobierno", "movilidad": "Movilidad",
    "personeria": "Personería", "defensoria": "Defensoría", "fiscalia": "Fiscalía", "educacion": "Educación",
    "salud": "Salud", "icbf": "ICBF", "comisaria": "Comisaría", "secretaria de seguridad": "Secretaría de Seguridad",
}
# Preguntas sobre el Código de Convivencia: comparendos del RNMC (Inspecciones de Policía).
CONVIVENCIA = ("convivencia", "comparendo", "rnmc", "inspecc", "codigo de policia", "medida correctiva",
               "rina", "irrespeto", "espacio publico", "ruido", "multa")
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def cambio(actual: int, anterior: int) -> str:
    """Dirección ya escrita, para que la IA no la interprete por su cuenta."""
    if actual > anterior:
        return f"subió en {actual - anterior}"
    if actual < anterior:
        return f"bajó en {anterior - actual}"
    return "igual"


def fecha_larga(valor) -> str:
    if isinstance(valor, str):
        valor = date.fromisoformat(valor[:10])
    return f"{valor.day} de {MESES[valor.month - 1]} de {valor.year}"


@dataclass
class Expediente:
    bloques: List[Tuple[str, str]] = field(default_factory=list)
    fuentes: List[str] = field(default_factory=list)
    temas: Dict[str, List[str]] = field(default_factory=dict)

    def agregar(self, titulo: str, lineas: List[str], fuente: Optional[str] = None):
        lineas = [l for l in lineas if l]
        if lineas:
            self.bloques.append((titulo, "\n".join(f"- {l}" for l in lineas)))
            if fuente and fuente not in self.fuentes:
                self.fuentes.append(fuente)

    def texto(self) -> str:
        return "\n\n".join(f"## {t}\n{c}" for t, c in self.bloques)


# ------------------------------------------------------------------ qué pregunta

def detectar_temas(db: Session, pregunta: str) -> Dict[str, List[str]]:
    p = normalizar(pregunta)
    temas: Dict[str, List[str]] = {"delitos": [], "entidades": [], "barrios": []}
    for clave, conductas in DELITOS.items():
        if clave in p:
            temas["delitos"] += [c for c in conductas if c not in temas["delitos"]]
    temas["entidades"] = [nombre for clave, nombre in ENTIDADES.items() if clave in p]
    barrios = [b for (b,) in db.query(HechoSeguridad.barrio_normalizado).filter(
        HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL", HechoSeguridad.barrio_normalizado.isnot(None)).distinct()]
    palabras = set(re.findall(r"[a-z0-9]+", p))
    for barrio in barrios:
        nombre = normalizar(barrio)
        partes = [w for w in re.findall(r"[a-z0-9]+", nombre) if len(w) >= 5 and w not in {"barrio", "sector", "urbanizacion", "conjunto", "corregimiento"}]
        if nombre and (nombre in p or (partes and all(w in palabras for w in partes))):
            temas["barrios"].append(barrio)
    temas["barrios"] = temas["barrios"][:2]
    return temas


# ------------------------------------------------------------------ expediente

def _general(db: Session, exp: Expediente, hoy: date):
    from services import hoja_ejecutiva
    datos = hoja_ejecutiva.construir(db, hoy=hoy)
    semana, anterior = datos["semana"], datos["semana_anterior"]
    lineas = [f"Datos policiales al {fecha_larga(datos['corte'])} ({datos['dias_retraso']} días de retraso); "
              f"última entrega: {datos.get('entrega')}.",
              f"Semana del {fecha_larga(semana[0])} al {fecha_larga(semana[1])}; semana anterior del "
              f"{fecha_larga(anterior[0])} al {fecha_larga(anterior[1])}."]
    for fila in datos["filas"] + [datos["total"]]:
        variacion = f"{fila['variacion_anio']:+.1f} %" if fila["variacion_anio"] is not None else "sin base"
        lineas.append(f"{fila['delito']}: {fila['semana']} esta semana y {fila['semana_anterior']} la anterior "
                      f"({cambio(fila['semana'], fila['semana_anterior'])} frente a la semana anterior); en el año "
                      f"{fila['anio']} frente a {fila['anio_anterior']} en el mismo periodo del año pasado "
                      f"({cambio(fila['anio'], fila['anio_anterior'])}, {variacion}).")
    exp.agregar("Cifras de la sábana policial (hechos únicos)", lineas, f"Sábana de la Policía al {fecha_larga(datos['corte'])}")
    exp.agregar("Barrios con más casos en las últimas cuatro semanas",
                [f"{b['barrio']}: {b['casos']} casos, sobre todo {b['principal'].lower() if b['principal'] else 'varios delitos'}."
                 for b in datos["barrios"]])
    comp = datos["compromisos"]
    lineas = [f"{comp['vencidos']} vencidos, {comp['abiertos']} abiertos y {comp['cumplidos']} cumplidos."]
    lineas += [f"{c['texto']} (responsable: {c['responsable']}; pedido {c['veces']} veces)" for c in comp["atencion"]]
    exp.agregar("Compromisos del Consejo de Seguridad que requieren atención", lineas, "Compromisos y acuerdos del SISC")
    exp.agregar("Lo más importante según la hoja ejecutiva", datos["frases"])
    respaldo = datos.get("respaldo") or {}
    if respaldo.get("atrasada"):
        exp.agregar("Estado de la sábana", [f"La sábana está atrasada: {respaldo['dias_retraso']} días desde su último dato."])
    return datos


def _piscc(db: Session, exp: Expediente, corte: date):
    from services.piscc_goals import build_goals
    metas = build_goals(db, corte, None)
    lineas = [f"{g.get('label') or g.get('id')}: {g.get('status_label') or g.get('status')}. {g.get('detail') or ''}"
              for g in metas.get("indicators", [])]
    exp.agregar("Metas del PISCC 2024-2027 (tabla 16)", lineas, "PISCC 2024-2027, tabla 16")


def _externas(db: Session, exp: Expediente):
    from db.models_source_center import SourceConnectorState
    for codigo, titulo, fuente in (
        ("POLICIA_NACIONAL_DATOS", "Registro oficial de la Policía Nacional, año a la fecha", "Policía Nacional en datos.gov.co"),
        ("FISCALIA_DATOS", "Procesos de la Fiscalía por hechos en Jamundí", "Fiscalía (SPOA V3) en datos.gov.co"),
        ("OBSERVATORIO_VALLE", "Observatorio del Delito del Valle", "Observatorio del Delito del Valle"),
    ):
        estado = db.get(SourceConnectorState, codigo)
        filas = ((estado.details or {}).get("contraste") if estado else None) or []
        if not filas:
            continue
        corte = filas[0].get("corte")
        lineas = [f"Corte {fecha_larga(corte)}."] if corte else []
        for f in filas:
            extra = f"; año anterior (mismo periodo) {f['oficial_anterior']}" if f.get("oficial_anterior") is not None else ""
            if codigo == "OBSERVATORIO_VALLE":
                extra = f"; año anterior completo {f['oficial_anterior']}" if f.get("oficial_anterior") is not None else ""
            lineas.append(f"{f['delito']}: {f['oficial_actual']}{extra}.")
        etapas = (estado.details or {}).get("respuesta_judicial")
        if etapas:
            lineas.append("En qué van los procesos del año: " + "; ".join(f"{k}: {v}" for k, v in etapas.items()) + ".")
        exp.agregar(titulo, lineas, fuente)


def _resumen_whatsapp(db: Session, exp: Expediente):
    from db.models_narrative_alerts import NarrativeAlert
    alerta = (db.query(NarrativeAlert).filter(NarrativeAlert.frequency == "SEMANAL", NarrativeAlert.superseded_by.is_(None))
              .order_by(NarrativeAlert.period_end.desc(), NarrativeAlert.created_at.desc()).first())
    if alerta:
        exp.agregar("Último resumen semanal para WhatsApp (ya redactado por el SISC)", [alerta.text.replace("\n", " ")],
                    "Resúmenes para WhatsApp del SISC")
        return alerta.text
    return None


def _delito(db: Session, exp: Expediente, conductas: List[str], corte: date):
    base = [HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL", HechoSeguridad.conducta_estandar.in_(conductas), filtro_hechos(db)]
    lineas = []
    for semanas_atras in range(7, -1, -1):
        fin = corte - timedelta(days=7 * semanas_atras)
        inicio = fin - timedelta(days=6)
        n = db.query(hechos_unicos_expr()).filter(*base, HechoSeguridad.fecha_evento.between(inicio, fin)).scalar() or 0
        lineas.append(f"Semana que termina el {fecha_larga(fin)}: {n}.")
    lineas.append(_franjas(db, base, corte))
    exp.agregar(f"Tendencia de {', '.join(c.lower() for c in conductas)} (últimas 8 semanas)", lineas)


def _franjas(db: Session, base: list, corte: date) -> Optional[str]:
    filas = db.query(func.extract("hour", HechoSeguridad.hora_evento).label("h"), hechos_unicos_expr()).filter(
        *base, HechoSeguridad.fecha_evento.between(date(corte.year, 1, 1), corte), HechoSeguridad.hora_evento.isnot(None)
    ).group_by("h").all()
    grupos = {"madrugada (0 a 6)": 0, "mañana (6 a 12)": 0, "tarde (12 a 18)": 0, "noche (18 a 24)": 0}
    for hora, n in filas:
        grupos[list(grupos)[min(int(hora) // 6, 3)]] += int(n)
    if not sum(grupos.values()):
        return None
    return "Horario de los hechos en el año: " + "; ".join(f"{k}: {v}" for k, v in grupos.items()) + "."


def _barrio(db: Session, exp: Expediente, barrio: str, corte: date):
    base = [HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL", HechoSeguridad.barrio_normalizado == barrio, filtro_hechos(db)]
    anio = db.query(hechos_unicos_expr()).filter(*base, HechoSeguridad.fecha_evento.between(date(corte.year, 1, 1), corte)).scalar() or 0
    previo_fin = corte.replace(year=corte.year - 1) if not (corte.month == 2 and corte.day == 29) else corte.replace(year=corte.year - 1, day=28)
    previo = db.query(hechos_unicos_expr()).filter(*base, HechoSeguridad.fecha_evento.between(date(corte.year - 1, 1, 1), previo_fin)).scalar() or 0
    recientes = db.query(hechos_unicos_expr()).filter(*base, HechoSeguridad.fecha_evento.between(corte - timedelta(days=27), corte)).scalar() or 0
    conductas = db.query(HechoSeguridad.conducta_estandar, hechos_unicos_expr().label("n")).filter(
        *base, HechoSeguridad.fecha_evento.between(date(corte.year, 1, 1), corte)
    ).group_by(HechoSeguridad.conducta_estandar).order_by(hechos_unicos_expr().desc()).limit(3).all()
    lineas = [f"En el año: {anio} casos, frente a {previo} en el mismo periodo del año pasado ({cambio(anio, previo)}).",
              f"Últimas cuatro semanas: {recientes} casos."]
    if conductas:
        lineas.append("Delitos principales en el año: " + "; ".join(f"{c.lower()}: {n}" for c, n in conductas) + ".")
    lineas.append(_franjas(db, base, corte))
    lineas.append(_comparendos_barrio(db, barrio))
    exp.agregar(f"Barrio {barrio.title()}", lineas, f"Sábana de la Policía al {fecha_larga(corte)}")


def _comparendos_barrio(db: Session, barrio: str) -> Optional[str]:
    """Comparendos del RNMC en el barrio (mismo nombre en mayúsculas), con su comportamiento más común."""
    try:
        from db.models_inspecciones import InspeccionExpediente, InspeccionMedida
        from services import comparendos_rnmc

        corte = comparendos_rnmc.corte(db)
        if not corte:
            return None
        mismo = [func.upper(func.trim(InspeccionExpediente.localidad)) == normalizar(barrio).upper().strip()]
        total = comparendos_rnmc.agrupar(db, InspeccionExpediente.localidad, date(corte.year, 1, 1), corte, filtros=mismo)
        if not total:
            return None
        texto = f"Comparendos del RNMC en el año (al {fecha_larga(corte)}): {total[0][1]}"
        filas = comparendos_rnmc.agrupar(db, InspeccionMedida.articulo, date(corte.year, 1, 1), corte, filtros=mismo, limite=1)
        if filas:
            texto += f"; lo más común: {minuscula(comparendos_rnmc.etiqueta_articulo(filas[0][0]))} ({filas[0][1]})"
        return texto + "."
    except Exception:  # noqa: BLE001 - sin comparendos, el resto de la respuesta sigue
        db.rollback()
        return None


def _convivencia(db: Session, exp: Expediente, hoy: date, pregunta: str = ""):
    """Comparendos del año (cada uno una vez), meta del PISCC, comportamientos, barrios y meses recientes."""
    from services import comparendos_rnmc
    from services.piscc_goals import GOALS, evaluate

    estado = comparendos_rnmc.estado_carga(db, hoy)
    if not estado["corte"]:
        exp.agregar("Convivencia (comparendos del RNMC)", ["Todavía no hay comparendos del RNMC cargados en el SISC."])
        return
    corte = date.fromisoformat(estado["corte"])
    resumen = comparendos_rnmc.resumen_convivencia(db, date(corte.year, 1, 1), corte, barrios=5)
    meta = evaluate(resumen["total"], corte, GOALS["convivencia"])
    lineas = [f"Comparendos del año al {fecha_larga(corte)}: {resumen['total']} (cada comparendo se cuenta una vez).",
              f"Meta del PISCC para comportamientos contrarios a la convivencia: {GOALS['convivencia']} en el año. {meta['detail']}"]
    if estado["atrasado"]:
        lineas.append(f"Los reportes del RNMC no se actualizan desde hace {estado['dias_desde_corte']} días; conviene pedirlos.")
    lineas += [f"{c['etiqueta']} (artículo {c['articulo']} del Código de Convivencia): {c['total']} comparendos, "
               f"{str(c['porcentaje']).replace('.', ',')} % del total." for c in resumen["comportamientos"][:4]]
    for b in resumen["barrios"]:
        principal = (f"; lo más común: {minuscula(b['principal']['etiqueta'])} "
                     f"({str(b['principal']['porcentaje']).replace('.', ',')} % del barrio)") if b["principal"] else ""
        lineas.append(f"Barrio {nombre_barrio(b['barrio'])}: {b['total']} comparendos{principal}; "
                      f"{str(b['fin_de_semana_pct']).replace('.', ',')} % en fin de semana.")
    dias = sorted(resumen["dias"], key=lambda d: -d["total"])
    if dias and dias[0]["total"]:
        lineas.append(f"Día con más comparendos: {dias[0]['dia'].lower()} ({dias[0]['total']}).")
    lineas += [f"Comparendos en {m['mes']}: {m['total']}." for m in resumen["meses"][-3:]]
    # Si preguntan por un comportamiento (riñas, espacio público...), sus barrios.
    from db.models_inspecciones import InspeccionExpediente, InspeccionMedida
    p = normalizar(pregunta)
    for claves, articulo in ((("rina", "arma", "amenaza"), "27"), (("irrespeto", "autoridad"), "35"),
                             (("espacio publico", "vendedor"), "140"), (("ruido",), "33")):
        if any(c in p for c in claves):
            filas = comparendos_rnmc.agrupar(
                db, InspeccionExpediente.localidad, date(corte.year, 1, 1), corte, limite=5,
                filtros=comparendos_rnmc.filtros_barrio() + [InspeccionMedida.articulo.like(f"Art. {articulo} %")])
            etiqueta = comparendos_rnmc.ETIQUETAS_ARTICULO[articulo]
            lineas += [f"Barrios con más comparendos por {minuscula(etiqueta)}: "
                       + "; ".join(f"{nombre_barrio(b)}: {n}" for b, n in filas) + "."] if filas else []
    lineas.append("Nota: un comparendo muestra la actuación de la Policía, no solo el comportamiento de la gente; "
                  "si sube, puede ser por más controles.")
    exp.agregar("Convivencia: comparendos del RNMC", lineas, f"RNMC (Policía Nacional / Inspecciones) al {fecha_larga(corte)}")


def minuscula(texto: str) -> str:
    return texto[:1].lower() + texto[1:] if texto else ""


def nombre_barrio(valor: str) -> str:
    return " ".join(p.capitalize() if len(p) > 2 else p.lower() for p in str(valor or "").split())


def _entidad(db: Session, exp: Expediente, entidad: str):
    from db.models_council import CouncilCommitment
    from services import council_commitments_service as svc
    clave = normalizar(entidad).split()[0][:6]
    abiertos = [svc.serialize(r) for r in db.query(CouncilCommitment).all()]
    propios = [c for c in abiertos if clave in normalizar(c["responsible"] or "") and c["status"] not in svc.CLOSED_STATUSES]
    vencidos = [c for c in propios if "ATRASADO" in c["flags"]]
    propios.sort(key=lambda c: (-(c["mentions"] or 1), "ATRASADO" not in c["flags"]))
    lineas = [f"{len(propios)} compromisos abiertos a cargo de {entidad}, {len(vencidos)} vencidos."]
    lineas += [f"{c['text']} (pedido {c['mentions'] or 1} veces{'; vencido' if 'ATRASADO' in c['flags'] else ''})" for c in propios[:6]]
    exp.agregar(f"Compromisos del Consejo a cargo de {entidad}", lineas, "Compromisos y acuerdos del SISC")


def construir_expediente(db: Session, pregunta: str, hoy: Optional[date] = None) -> Tuple[Expediente, Dict]:
    hoy = hoy or date.today()
    exp = Expediente()
    temas = detectar_temas(db, pregunta)
    exp.temas = temas
    datos = _general(db, exp, hoy)
    corte = datos["corte"]
    p = normalizar(pregunta)
    if "piscc" in p or "meta" in p or "plan" in p:
        _piscc(db, exp, corte)
    if any(w in p for w in CONVIVENCIA):
        try:
            _convivencia(db, exp, hoy, pregunta)
        except Exception:  # noqa: BLE001 - la convivencia no debe impedir responder lo demás
            db.rollback()
    if any(w in p for w in ("fiscal", "justicia", "judicial", "juicio", "denuncia", "valle", "oficial", "nacional", "compar")):
        _externas(db, exp)
    whatsapp = _resumen_whatsapp(db, exp) if "whatsapp" in p or "resum" in p else None
    for conductas in ([temas["delitos"]] if temas["delitos"] else []):
        _delito(db, exp, conductas, corte)
    for barrio in temas["barrios"]:
        _barrio(db, exp, barrio, corte)
    for entidad in temas["entidades"]:
        _entidad(db, exp, entidad)
    return exp, {"datos": datos, "whatsapp": whatsapp}


# ------------------------------------------------------------------ respuesta

def instrucciones(pregunta: str, historial: List[Dict], expediente: Expediente, hoy: date) -> str:
    conversacion = "\n".join(f"{'Secretaria' if m.get('rol') == 'usuario' else 'Asesor'}: {m.get('texto', '')[:500]}"
                             for m in historial[-4:])
    return f"""Eres el Asesor SISC de la Secretaría de Seguridad y Convivencia de Jamundí. Le respondes a la Secretaria,
que no es técnica, lee en el celular o en papel y necesita saber qué pasa y qué conviene hacer.

Reglas obligatorias:
- Responde en español sencillo, en máximo {MAX_PALABRAS} palabras. Empieza por la respuesta directa.
- Usa SOLO cifras y fechas que aparezcan en el EXPEDIENTE. No calcules porcentajes ni sumas nuevas. No inventes nada.
- Si el expediente no tiene lo que se pregunta, dilo con claridad y sugiere quién podría tener el dato.
- Para decir si algo subió, bajó o quedó igual, usa exactamente lo que el expediente dice entre paréntesis; nunca lo deduzcas.
- Menciona la fecha de corte cuando des cifras. Si la última semana puede estar incompleta, advierte que una baja puede ser falta de registro.
- Sin jerga técnica, sin tablas, sin listas numeradas (usa viñetas "•" si hace falta). Sin datos personales.
- Tono respetuoso e institucional: sugiere ("conviene pedir…", "se puede solicitar…"), no uses "exija", "reclame" ni "demande", y no des órdenes operativas a la fuerza pública.
- Hoy es {fecha_larga(hoy)}.

Conversación reciente:
{conversacion or '(inicio)'}

EXPEDIENTE (cifras oficiales del SISC):
{expediente.texto()}

Pregunta de la Secretaria: {pregunta}
Respuesta:"""


def respuesta_sin_ia(pregunta: str, expediente: Expediente, extra: Dict) -> str:
    p = normalizar(pregunta)
    if extra.get("whatsapp") and ("whatsapp" in p or "resum" in p):
        return extra["whatsapp"]
    datos = extra["datos"]
    convivencia = next((c for t, c in expediente.bloques if t.startswith("Convivencia")), None)
    if convivencia and any(w in p for w in CONVIVENCIA) and not expediente.temas.get("barrios"):
        # Pregunta de convivencia: total, meta, dos comportamientos y el barrio con más comparendos.
        filas = [l.lstrip("- ") for l in convivencia.split("\n")]
        elegidas = filas[:2] + [l for l in filas if "artículo" in l][:2] + [l for l in filas if l.startswith("Barrio ")][:1]
        return "• " + "\n• ".join(elegidas)
    lineas = datos["frases"][:4]
    for titulo, contenido in expediente.bloques[1:]:
        if titulo.startswith(("Barrio ", "Tendencia de", "Compromisos del Consejo a cargo", "Convivencia")):
            lineas.append(f"{titulo}: " + contenido.replace("\n- ", " ").lstrip("- "))
    return "• " + "\n• ".join(lineas)


def sugerencias(temas: Dict[str, List[str]], datos: Dict, pregunta: str = "") -> List[str]:
    opciones = []
    if temas.get("barrios"):
        opciones.append(f"¿Qué delitos pasan más en {temas['barrios'][0].title()} y a qué hora?")
    if datos.get("barrios"):
        opciones.append(f"¿Qué está pasando en {datos['barrios'][0]['barrio']}?")
    opciones += ["¿Qué compromisos tiene vencidos la Policía?", "¿Cómo va el PISCC?", "¿Cómo va la convivencia este año?",
                 "¿Qué dice la Fiscalía de este año?", "Resúmame la semana para WhatsApp"]
    hecha = normalizar(pregunta).strip(" ¿?")
    return [o for o in dict.fromkeys(opciones) if normalizar(o).strip(" ¿?") != hecha][:3]


async def responder(db: Session, pregunta: str, historial: Optional[List[Dict]] = None, hoy: Optional[date] = None) -> Dict:
    from api import ia
    from services.ai_output_guard import verify_ai_text

    hoy = hoy or date.today()
    historial = historial or []
    from services.asistente_compromisos import es_consulta, responder_ranking
    if es_consulta(pregunta):
        return responder_ranking(db, normalizar(pregunta), hoy)
    expediente, extra = construir_expediente(db, pregunta, hoy)
    datos_texto = expediente.texto() + "\n" + fecha_larga(hoy)
    prompt = instrucciones(pregunta, historial, expediente, hoy)
    intentos, problemas = [], []
    proveedores = []
    if ia.GEMINI_API_KEY:
        proveedores.append(("Gemini", ia.call_gemini))
    if ia.MISTRAL_API_KEY:
        proveedores.append(("Mistral", ia.call_mistral))
    for nombre, llamar in proveedores:
        try:
            texto = (await llamar(prompt) or "").strip()
        except Exception as error:  # noqa: BLE001 - cualquier falla pasa al siguiente proveedor
            problemas.append(f"{nombre} no respondió ({type(error).__name__}).")
            continue
        guardia = verify_ai_text(texto, datos_texto)
        intentos.append(nombre)
        if guardia.ok and texto:
            return {"respuesta": texto, "verificada": True, "redactada_por": nombre, "fuentes": expediente.fuentes,
                    "sugerencias": sugerencias(expediente.temas, extra["datos"], pregunta), "temas": expediente.temas}
        problemas.append(f"{nombre}: {'; '.join(guardia.problems)[:200]}")
    return {"respuesta": respuesta_sin_ia(pregunta, expediente, extra), "verificada": True, "redactada_por": "SISC (sin IA)",
            "fuentes": expediente.fuentes, "sugerencias": sugerencias(expediente.temas, extra["datos"], pregunta),
            "temas": expediente.temas, "problemas": problemas}
