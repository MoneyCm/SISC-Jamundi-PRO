"""Asuntos concretos que se tratan en Consejos, comités y reuniones de seguridad.

Sirve para dos cosas:
- asignar tema a un compromiso leído de un acta (los de la hoja ya traen tema puesto a mano);
- medir qué asuntos vuelven sesión tras sesión y año tras año ("temas que vuelven").

Los patrones se aplican sobre texto normalizado (mayúsculas, sin tildes).
"""
import re
import unicodedata
from typing import Dict, Iterable, List, Optional

# (clave, nombre para mostrar, tema de la hoja de compromisos, patrón)
TOPICS = [
    ("camaras", "Cámaras y videovigilancia", "Videovigilancia y tecnología", r"\bCAMARAS?\b|VIDEOVIGILANCIA|\bCCTV\b|CENTRO DE MONITOREO"),
    ("drones", "Drones", "Orden público y grupos armados", r"\bDRON(ES)?\b"),
    ("ataques", "Ataques y hostigamientos armados", "Orden público y grupos armados",
     r"HOSTIGAMIENTO|ATAQUES?\b|EXPLOSIV|ARTEFACTO|DISIDENCIA|GRUPOS? ARMADOS?|JAIME MARTINEZ|MINAS? ANTIPERSONA"),
    ("ocupaciones", "Ocupaciones ilegales y predios", "Ocupaciones ilegales",
     r"OCUPACION(ES)? ILEGAL|INVASION(ES)?|DESALOJO|RECUPERACION DE (LOS )?PREDIOS|\bSAE\b|POSESION"),
    ("caravanas", "Caravanas y patrullajes", "Espacio público y convivencia", r"CARAVANA|PATRULLAJE|PLAN DESARME"),
    ("pie_fuerza", "Pie de fuerza y refuerzos", "Recursos para seguridad", r"PIE DE FUERZA|REFUERZO|\bUNDMO\b|\bUNMDO\b|MAS UNIDADES"),
    ("radios", "Radios y comunicaciones", "Recursos para seguridad", r"\bRADIOS?\b"),
    ("dotacion", "Dotación y logística de la fuerza pública", "Recursos para seguridad",
     r"VEHICULO|CAMIONETA|DOTACION|CHALECO|\bBOTAS\b|NECROMOVIL|COMBUSTIBLE|GASOLINA|BOTIQUIN"),
    ("fonset", "FONSET y presupuesto de seguridad", "Recursos para seguridad", r"FONSET|FONDO (TERRITORIAL )?DE SEGURIDAD|\bPISCC\b|RECOMPENSA"),
    ("desplazamiento", "Desplazamiento y atención humanitaria", "Protección y derechos humanos",
     r"DESPLAZ|ALBERGUE|REFUGIO|ATENCION HUMANITARIA|AYUDAS? HUMANITARIA|DAMNIFICAD"),
    ("alertas", "Alertas tempranas", "Alertas tempranas", r"ALERTAS? TEMPRANAS?"),
    ("electoral", "Elecciones", "Seguridad electoral", r"ELECCION|ELECTORAL|JURADOS|REGISTRADURIA|LEY SECA|ESCRUTIN"),
    ("frentes", "Frentes de seguridad y redes comunitarias", "Articulación comunitaria",
     r"FRENTES? DE SEGURIDAD|REDES? DE (APOYO|INFORMANTES|INTELIGENCIA)|JUNTAS? DE ACCION COMUNAL|\bJAC\b"),
    ("alumbrado", "Alumbrado, poda y entornos", "Movilidad e infraestructura", r"ALUMBRADO|LUMINARIA|\bPODA\b|LOTES? BALDIO"),
    ("vias", "Movilidad y seguridad vial", "Movilidad e infraestructura",
     r"REDUCTORES? DE VELOCIDAD|RESALTO|SENALIZACION|SEGURIDAD VIAL|SINIESTRO|ACCIDENTE DE TRANSITO"),
    ("motos", "Motos y parrillero", "Movilidad e infraestructura", r"PARRILLERO|MOTOCICLETA"),
    ("microtrafico", "Microtráfico y consumo", "Espacio público y convivencia", r"MICROTRAFICO|ESTUPEFACIENTE|EXPENDIO|SUSTANCIAS PSICOACTIVAS"),
    ("extorsion", "Extorsión", "Orden público y grupos armados", r"EXTORSI"),
    ("hurto", "Hurtos", "Espacio público y convivencia", r"\bHURTOS?\b"),
    ("homicidio", "Homicidios", "Orden público y grupos armados", r"HOMICIDIO"),
    ("comercio", "Comercio, bares y horarios", "Espacio público y convivencia",
     r"ESTABLECIMIENTOS? (DE COMERCIO|ABIERTOS)|\bBARES\b|HORARIOS? DE|COMERCIANTES|CENTROS? COMERCIALES"),
    ("escolar", "Colegios y entornos escolares", "Protección y derechos humanos", r"ENTORNOS? ESCOLAR|COLEGIO|SEDES? EDUCATIVA|INSTITUCION(ES)? EDUCATIVA"),
    ("carcel", "Cárcel (COJAM / INPEC)", "Orden público y grupos armados", r"\bINPEC\b|\bCOJAM\b|CARCEL|PENITENCIARI"),
    ("mineria", "Minería ilegal", "Orden público y grupos armados", r"MINERIA|RETROEXCAVADORA"),
    ("judicializacion", "Denuncias y judicialización", "Capacitación y judicialización", r"JUDICIALIZ|DENUNCIA|IMPUTACION|ORDEN(ES)? DE CAPTURA"),
    ("contingencia", "Plan de contingencia y PMU", "Gestión institucional", r"PLAN DE CONTINGENCIA|\bPMU\b|PUESTO DE MANDO"),
    ("informes", "Informes y cifras de resultados", "Gestión documental e información",
     r"INFORME (DE|SOBRE) (LOS )?RESULTADOS|ESTADISTICA|OBSERVATORIO|CIFRAS"),
]
_COMPILED = [(key, label, theme, re.compile(pattern)) for key, label, theme, pattern in TOPICS]
LABELS = {key: label for key, label, _, _ in TOPICS}
THEMES = {key: theme for key, _, theme, _ in TOPICS}


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text).upper()


def topics_in(text: str) -> List[str]:
    """Asuntos que menciona un texto, en el orden de TOPICS."""
    normalized = _normalize(text)
    return [key for key, _, _, pattern in _COMPILED if pattern.search(normalized)]


def theme_for(text: str) -> Optional[str]:
    found = topics_in(text)
    return THEMES[found[0]] if found else None


def topic_counts(paragraphs: Iterable[str]) -> Dict[str, int]:
    """Cuántos párrafos del acta tocan cada asunto (sirve para saber de qué se habló en la sesión)."""
    counts: Dict[str, int] = {}
    for paragraph in paragraphs:
        for key in topics_in(paragraph):
            counts[key] = counts.get(key, 0) + 1
    return counts
