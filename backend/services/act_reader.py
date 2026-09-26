"""Lector de actas de reunión (Consejo de Seguridad, comités, reuniones de planeación).

Extrae compromisos y acuerdos como PROPUESTAS para que una persona los confirme. Todo
se procesa en el servidor, sin servicios externos: las actas pueden contener información
reservada. Reconoce los formatos encontrados en las actas de Jamundí:

1. Tabla de compromisos ("Compromiso | Responsable | Plazo" o "Qué hacer | Responsable | Fecha").
2. Lista al final del acta bajo el título "Compromisos".
3. Un compromiso en línea ("COMPROMISO: ...").
4. Acuerdos aprobados por votación (sección "Aprobación" con votos "SI").

Y señala problemas de calidad: acta sin compromisos concretos, compromisos sin responsable
o sin plazo, fechas con un año distinto al del acta y cierres que no coinciden con la fecha.
"""

from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree

from services.council_topics import topic_counts

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MONTHS = {
    "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6, "JULIO": 7,
    "AGOSTO": 8, "SEPTIEMBRE": 9, "SETIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12,
}

# Instancias y cómo reconocerlas en el objetivo o el título del acta.
INSTANCES = {
    "CONSEJO_SEGURIDAD": {"label": "Consejo de Seguridad", "prefix": "CS", "patterns": [r"CON[CS]EJO (MUNICIPAL )?(DE )?SEGURIDAD"]},
    "COMITE_ORDEN_PUBLICO": {"label": "Comité Territorial de Orden Público", "prefix": "COP", "patterns": [r"ORDEN PUBLICO"]},
    "COMITE_CIVIL_CONVIVENCIA": {"label": "Comité Civil de Convivencia", "prefix": "CCC", "patterns": [r"COMITE CIVIL"]},
    "PLANEACION_SEMANAL": {"label": "Reunión semanal de planeación", "prefix": "RSP", "patterns": [r"PLANEACION", r"REUNION (DE )?SEGURIDAD"]},
    "MESA_TECNICA": {"label": "Mesa técnica", "prefix": "MT", "patterns": [r"MESA TECNICA", r"MESA CAMPESINA"]},
    "OTRA": {"label": "Otra reunión", "prefix": "RE", "patterns": []},
}

ENTITY_PATTERN = (
    r"(SECRETAR[IÍ]A( DE)? SEGURIDAD Y CONVIVENCIA|SECRETAR[IÍ]A( DE)? GOBIERNO|"
    r"SECRETAR[IÍ]A[S]?( DE)? [A-ZÁÉÍÓÚÑ ,Y]+?|POLIC[IÍ]A( NACIONAL)?|EJ[EÉ]RCITO( NACIONAL)?|"
    r"FISCAL[IÍ]A|PERSONER[IÍ]A|DEFENSOR[IÍ]A( DEL PUEBLO)?|ALCALD[IÍ]A|ALCALDESA|ADMINISTRACI[OÓ]N MUNICIPAL|"
    r"GESTI[OÓ]N DEL RIESGO|OBSERVATORIO|ICBF|COMISAR[IÍ]A[S]?( DE FAMILIA)?|INSPECCI[OÓ]N(ES)?( DE POLIC[IÍ]A)?)"
)
PERSON_TITLES = r"\b(DRA?\.|DOCTORA?|COMANDANTE|GESTORA SOCIAL|ALCALDESA|ALCALDE|CORONEL|MAYOR|CAPIT[AÁ]N|PERSONER[AO]|BOMBEROS)"
VAGUE_DEADLINES = ("POR DEFINIR", "SIN FECHA", "PROXIMA", "PROXIMO", "INMEDIATO", "EN CURSO", "PERMANENTE",
                   "ANTES DE", "SEGUN", "MENSUAL", "SEMANAL", "YA SE HIZO")
GENERIC_RESPONSIBLES = ("TODAS LAS INSTITUCIONES", "TODOS LOS", "LAS ENTIDADES", "ENTIDADES ARTICULADAS")


def normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text).strip().upper()


def _clean(text: str) -> str:
    # Word y PDF usan viñetas de fuentes Symbol/Wingdings (zona privada Unicode, p. ej. U+F0B7).
    text = re.sub(r"[\uf000-\uf8ff▪●·]", " ", str(text or ""))
    return re.sub(r"\s+", " ", text).strip(" .;:-•◦•")


# ---------------------------------------------------------------------------
# Extracción de texto: bloques en orden (párrafo = str, tabla = lista de filas)
# ---------------------------------------------------------------------------

MAX_DOCX_XML_BYTES = 40 * 1024 * 1024
MAX_PDF_PAGES = 150


def _paragraph_text(node) -> str:
    parts = []
    for element in node.iter():
        if element.tag == f"{W}t" and element.text:
            parts.append(element.text)
        elif element.tag in (f"{W}tab",):
            parts.append(" ")
        elif element.tag in (f"{W}br", f"{W}cr"):
            parts.append("\n")
    return "".join(parts)


def docx_blocks(content: bytes) -> List[Any]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        info = archive.getinfo("word/document.xml")
        # Un .docx de pocos MB puede descomprimirse en GB (bomba zip).
        if info.file_size > MAX_DOCX_XML_BYTES:
            raise ValueError("El documento es demasiado grande para leerlo como acta.")
        xml = archive.read(info)
    # Word nunca declara DOCTYPE; si aparece, se rechaza (entidades XML maliciosas).
    if b"<!DOCTYPE" in xml[:4096].upper() or b"<!ENTITY" in xml.upper():
        raise ValueError("El documento Word no es válido.")
    root = ElementTree.fromstring(xml)
    body = root.find(f"{W}body")
    blocks: List[Any] = []
    for node in list(body) if body is not None else []:
        if node.tag == f"{W}p":
            text = _paragraph_text(node).strip()
            if text:
                blocks.append(text)
        elif node.tag == f"{W}tbl":
            rows = []
            for row in node.iter(f"{W}tr"):
                cells = [" ".join(_paragraph_text(p).strip() for p in cell.iter(f"{W}p")).strip() for cell in row.findall(f"{W}tc")]
                if any(cells):
                    rows.append(cells)
            if rows:
                blocks.append(rows)
    return blocks


def pdf_blocks(content: bytes) -> List[Any]:
    import logging
    from pypdf import PdfReader

    logging.getLogger("pypdf").setLevel(logging.ERROR)
    reader = PdfReader(io.BytesIO(content))
    if len(reader.pages) > MAX_PDF_PAGES:
        raise ValueError(f"El PDF tiene más de {MAX_PDF_PAGES} páginas; no parece un acta.")
    lines: List[Any] = []
    for page in reader.pages:
        for line in (page.extract_text() or "").splitlines():
            if line.strip():
                lines.append(line.strip())
    return lines


def ocr_blocks(content: bytes, filename: str) -> Tuple[List[Any], Optional[str]]:
    """PDF escaneado -> texto con OCR de Gemini (solo con autorización). Las tablas Markdown pasan a filas."""
    from services.institutional_agent_service import InstitutionalAgentService

    service = InstitutionalAgentService(db=None)
    pages = service._extract_pdf_ocr(content, filename)
    blocks: List[Any] = []
    table: List[List[str]] = []
    for page in pages:
        for raw in page.splitlines():
            line = raw.strip()
            if line.startswith("|") and line.endswith("|"):
                cells = [cell.strip() for cell in line.strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", cell) for cell in cells if cell):
                    table.append(cells)
                continue
            if table:
                blocks.append(table)
                table = []
            if line:
                blocks.append(re.sub(r"^#+\s*|\*\*", "", line))
    if table:
        blocks.append(table)
    return blocks, getattr(service, "ocr_model_used", None)


def document_blocks(content: bytes, filename: str) -> List[Any]:
    name = (filename or "").lower()
    if content[:4] == b"%PDF" or name.endswith(".pdf"):
        return pdf_blocks(content)
    if content[:2] == b"PK":
        return docx_blocks(content)
    raise ValueError("Formato no admitido. Suba el acta en Word (.docx) o PDF.")


def blocks_text(blocks: List[Any]) -> str:
    out = []
    for block in blocks:
        if isinstance(block, list):
            out.extend(" | ".join(row) for row in block)
        else:
            out.append(block)
    return "\n".join(out)


@dataclass
class Proposal:
    kind: str  # COMPROMISO | ACUERDO
    text: str
    responsible: Optional[str] = None
    deadline_text: Optional[str] = None
    deadline_date: Optional[str] = None
    source: str = ""  # frase del acta de donde salió
    method: str = ""  # TABLA | LISTA | EN_LINEA | APROBACION
    flags: List[str] = field(default_factory=list)


@dataclass
class ActReading:
    instance: str
    instance_label: str
    act_number: Optional[str]
    act_date: Optional[str]
    objective: Optional[str]
    proposals: List[Proposal]
    warnings: List[Dict[str, str]]
    # Asunto -> párrafos del acta que lo mencionan (de qué se habló, haya o no compromiso).
    topics: Dict[str, int] = field(default_factory=dict)
    # Texto útil del acta: si no hay, probablemente es un PDF escaneado.
    text_chars: int = 0

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["proposals"] = [asdict(item) for item in self.proposals]
        return data


# ---------------------------------------------------------------------------
# Normalización de PDF: quitar encabezados de página y unir líneas partidas
# ---------------------------------------------------------------------------

_BOILERPLATE = re.compile(
    r"^(CODIGO:|FECHA ACTUALIZACION|VERSION:|ESTE DOCUMENTO ES PROPIEDAD|CUALQUIER MEDIO|PAGINA \d|PAGINA DE|ACTA DE REUNION( \d+)?$)"
)
_HEADING = re.compile(r"^(\d+\.?\s+[A-ZÁÉÍÓÚÑ]|[A-ZÁÉÍÓÚÑ ,\-]{4,60}:?$)")


def _is_boilerplate(line: str) -> bool:
    return bool(_BOILERPLATE.match(normalize(line)))


def paragraphs_from_lines(lines: List[Any]) -> List[Any]:
    """Une las líneas de un PDF en párrafos (una línea sin punto final continúa en la siguiente)."""
    result: List[Any] = []
    for line in lines:
        if isinstance(line, list):
            result.append(line)
            continue
        if _is_boilerplate(line):
            continue
        line = line.strip()
        previous = result[-1] if result and isinstance(result[-1], str) else None
        # Títulos de sección (aunque no estén en mayúsculas), viñetas y votos inician párrafo.
        starts_new = (
            bool(_HEADING.match(line)) or bool(re.match(r"^[•◦\-–]\s", line))
            or _is_commitments_heading(line) or bool(_STOP_SECTION.match(normalize(line)))
            or normalize(line).strip(" .:") in {"APROBACION", "LECTURA DE COMPROMISOS", "PROPOSICIONES Y VARIOS"}
            or bool(re.search(r"\)\s*\.?\s*SI$", normalize(line)))
        )
        previous_is_heading = previous is not None and (
            bool(_HEADING.match(previous)) or _is_commitments_heading(previous)
            or normalize(previous).strip(" .:") in {"APROBACION", "LECTURA DE COMPROMISOS", "PROPOSICIONES Y VARIOS"}
        )
        if previous and not re.search(r"[.:;]$", previous) and not starts_new and not previous_is_heading:
            result[-1] = f"{previous} {line}"
        else:
            result.append(line)
    return result


# ---------------------------------------------------------------------------
# Metadatos
# ---------------------------------------------------------------------------

def _parse_date(text: str) -> Optional[date]:
    match = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", text or "")
    if not match:
        return None
    day, month, year = (int(part) for part in match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _fallback_date(header: str) -> Optional[date]:
    """Actas antiguas: 'FECHA: 12/03/2025', '12-03-2025' o '12 DE MARZO DE 2025' en el encabezado."""
    # La "fecha de actualización" y la versión son del formato institucional, no de la sesión.
    header = re.sub(r"FECHA (DE )?ACTUALIZACION:?\s*\|?\s*\S+|VERSION:?\s*\S+", " ", header)
    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b", header)
    if match:
        return _parse_date("/".join(match.groups()))
    match = re.search(r"\b(\d{1,2}) DE ([A-Z]+) (?:DE|DEL) (20\d{2})\b", header)
    if match and match.group(2) in MONTHS:
        try:
            return date(int(match.group(3)), MONTHS[match.group(2)], int(match.group(1)))
        except ValueError:
            return None
    return None


def detect_instance(objective: str, header_text: str, filename: str) -> str:
    """El objetivo del acta manda; el nombre del archivo y el encabezado sirven de respaldo."""
    order = ["COMITE_CIVIL_CONVIVENCIA", "PLANEACION_SEMANAL", "CONSEJO_SEGURIDAD", "COMITE_ORDEN_PUBLICO", "MESA_TECNICA"]
    for source in (normalize(objective), normalize(filename), normalize(header_text)):
        if not source:
            continue
        for key in order:
            if any(re.search(pattern, source) for pattern in INSTANCES[key]["patterns"]):
                return key
    return "OTRA"


def read_metadata(blocks: List[Any], filename: str) -> Dict[str, Any]:
    raw_header = blocks_text(blocks[:40])
    header = normalize(raw_header)
    number = re.search(r"ACTA NO\.?\s*\|?\s*(\d+)", header)
    act_date = re.search(r"FECHA \(DD/MM/AAAA\):?\s*\|?\s*(\d{1,2}/\d{1,2}/\d{4})", header)
    objective = re.search(r"Objetivo:\s*([^|\n]+)", raw_header, flags=re.IGNORECASE)
    objective_text = _clean(objective.group(1)) if objective else ""
    parsed_date = _parse_date(act_date.group(1)) if act_date else None
    if parsed_date is None:
        parsed_date = _fallback_date(header)
    if number is None:
        number = re.search(r"ACTA (?:NO\.?|N[°º]|NUMERO)\s*:?\s*([\d-]{1,14})", header)
    return {
        "act_number": number.group(1) if number else None,
        "act_date": parsed_date,
        "objective": objective_text or None,
        "instance": detect_instance(objective_text, raw_header, filename),
    }


# ---------------------------------------------------------------------------
# Responsables y plazos
# ---------------------------------------------------------------------------

def split_responsible(text: str) -> Tuple[Optional[str], str]:
    """Separa el responsable cuando la frase empieza por la entidad ("Policía Nacional: ...")."""
    clean = _clean(text)
    match = re.match(r"^por parte de (?:la |el )?(.{3,60}?)[,:]?\s+(?=[a-záéíóúñ]+r\b)", clean, flags=re.IGNORECASE)
    if match:
        rest = clean[match.end():].strip()
        return _clean(match.group(1)).capitalize(), rest[:1].upper() + rest[1:]
    entity_list = rf"(?:{ENTITY_PATTERN})(?:\s*(?:,|\by\b|/)\s*(?:{ENTITY_PATTERN}))*"
    match = re.match(rf"^({entity_list})\s*[:,]?\s+(?=[A-ZÁÉÍÓÚ][a-záéíóúñ]+)", clean, flags=re.IGNORECASE)
    if match and len(match.group(1)) < 140:
        rest = clean[match.end():].strip()
        # Evita cortar frases donde la entidad es el sujeto de una oración ya redactada.
        if rest and not rest.lower().startswith(("de ", "del ", "la ", "el ")):
            return _clean(match.group(1)), rest[:1].upper() + rest[1:]
    # "La Policía Nacional y la Dra. Carolina Obando: Trabajar ..." / "Comandante de Bomberos: Presentar ..."
    match = re.match(r"^(?:la |el |los |las )?([^:]{3,90}?)\s*\]?\s*:\s+(?=[A-ZÁÉÍÓÚ])", clean, flags=re.IGNORECASE)
    if match and re.search(rf"{ENTITY_PATTERN}|{PERSON_TITLES}", match.group(1), flags=re.IGNORECASE):
        rest = clean[match.end():].strip()
        who = match.group(1)
        # "Secretaría de Gobierno Coordinar Visita": el título del compromiso (verbo en mayúscula) sobra.
        who = re.sub(r"\]?\s+[A-ZÁÉÍÓÚ][a-záéíóúñ]+(?:ar|er|ir)(?:\s+[A-ZÁÉÍÓÚ][a-záéíóúñ]+){0,3}\s*$", "", who)
        return _clean(who.rstrip("] ")), rest[:1].upper() + rest[1:]
    return None, clean


def evaluate_deadline(deadline_text: Optional[str], act_date: Optional[date]) -> Tuple[Optional[date], List[str]]:
    flags: List[str] = []
    text = normalize(deadline_text)
    parsed = _parse_date(deadline_text or "")
    if not text:
        flags.append("SIN_PLAZO")
    elif any(word in text for word in VAGUE_DEADLINES) and not parsed:
        flags.append("PLAZO_VAGO")
    if parsed and act_date:
        if parsed.year != act_date.year:
            flags.append("FECHA_ANIO_DISTINTO")
        elif parsed < act_date:
            flags.append("FECHA_ANTERIOR_AL_ACTA")
    return parsed, flags


def _responsible_flags(responsible: Optional[str]) -> List[str]:
    if not responsible:
        return ["SIN_RESPONSABLE"]
    if any(word in normalize(responsible) for word in GENERIC_RESPONSIBLES):
        return ["RESPONSABLE_GENERICO"]
    return []


# ---------------------------------------------------------------------------
# Estrategias de extracción
# ---------------------------------------------------------------------------

_TEXT_HEADER = re.compile(r"COMPROMISO|QUE HACER|TAREA|ACCION")


def _table_columns(table: List[List[str]]) -> Optional[Tuple[int, int, int, Optional[int]]]:
    for row_index, row in enumerate(table[:3]):
        cells = [normalize(cell) for cell in row]
        text_col = next((i for i, cell in enumerate(cells) if _TEXT_HEADER.search(cell) and len(cell) < 60), None)
        resp_col = next((i for i, cell in enumerate(cells) if "RESPONSABLE" in cell), None)
        if text_col is not None and resp_col is not None and text_col != resp_col:
            date_col = next((i for i, cell in enumerate(cells) if re.search(r"PLAZO|FECHA", cell)), None)
            return row_index, text_col, resp_col, date_col
    return None


def from_tables(blocks: List[Any], act_date: Optional[date]) -> Tuple[List[Proposal], int]:
    proposals: List[Proposal] = []
    empty_tables = 0
    for block in blocks:
        if not isinstance(block, list):
            continue
        columns = _table_columns(block)
        if not columns:
            continue
        header_row, text_col, resp_col, date_col = columns
        rows = [row for row in block[header_row + 1:] if text_col < len(row) and _clean(row[text_col])]
        if not rows:
            empty_tables += 1
        for row in rows:
            text = _clean(row[text_col])
            responsible = _clean(row[resp_col]) if resp_col < len(row) else None
            deadline_text = _clean(row[date_col]) if date_col is not None and date_col < len(row) else None
            deadline_text = re.sub(r"^\\?\[|\\?\]$", "", deadline_text or "").strip() or None
            parsed, deadline_flags = evaluate_deadline(deadline_text, act_date)
            proposals.append(Proposal(
                kind="COMPROMISO", text=text, responsible=responsible or None, deadline_text=deadline_text,
                deadline_date=parsed.isoformat() if parsed else None,
                source=" | ".join(_clean(cell) for cell in row if _clean(cell)), method="TABLA",
                flags=_responsible_flags(responsible) + deadline_flags,
            ))
    return proposals, empty_tables


_STOP_SECTION = re.compile(
    r"^(FIRMA|ATENTAMENTE|OBSERVACIONES|NOTA:|ELABORO|REVISO|PROYECTO|CONTROL DE MODIFICACIONES|ANEXO"
    r"|SIENDO LAS|NO SIENDO OTRO|NO HABIENDO|SE DA POR TERMINAD|SE LEVANTA LA|PARA CONSTANCIA|SE FINALIZA)"
)


def _is_commitments_heading(text: str) -> bool:
    value = re.sub(r"^[\d.\s]+", "", normalize(text)).strip(" .:")
    return value in {"COMPROMISOS", "TAREAS Y COMPROMISOS", "COMPROMISOS ADQUIRIDOS", "COMPROMISOS ESTABLECIDOS"}


# Secciones del orden del día / cuerpo del acta: si aparecen, la lista de compromisos ya terminó.
_AGENDA_SECTION = re.compile(
    r"^(\d+[.)]\s*)?(INSTALACION|VERIFICACION|LLAMADO A LISTA|SALUDO|ORDEN DEL DIA|LECTURA|INFORME|SITUACION|"
    r"PROPOSICIONES|VARIOS|CIERRE|DESARROLLO|APROBACION|CONTEXTO|INTERVENCION|PRESENTACION|ASISTENTES|INVITADOS)\b"
)


def from_list(blocks: List[Any], act_date: Optional[date]) -> List[Proposal]:
    proposals: List[Proposal] = []
    for index, block in enumerate(blocks):
        if not isinstance(block, str) or not _is_commitments_heading(block):
            continue
        # Una tabla "COMPROMISO | RESPONSABLE" que el PDF convirtió en texto: las columnas se mezclan
        # y el responsable puede quedar en la fila vecina. Se lee, pero se pide verificarlo.
        flattened_table = False
        for item in blocks[index + 1:]:
            if isinstance(item, list):
                break
            cleaned = normalize(_clean(item))
            if re.fullmatch(r"(COMPROMISOS?|TAREAS?|ACCION(ES)?)( Y)? (RESPONSABLES?|PLAZO|FECHA)( .{0,30})?", cleaned):
                flattened_table = True
                continue
            if _STOP_SECTION.match(cleaned) or _is_commitments_heading(item) or _AGENDA_SECTION.match(cleaned):
                break
            if len(_clean(item)) < 12:
                continue
            responsible, text = split_responsible(item)
            if len(text) < 12:
                continue
            _, deadline_flags = evaluate_deadline(None, act_date)
            flags = _responsible_flags(responsible) + deadline_flags
            if flattened_table:
                flags.append("RESPONSABLE_POR_VERIFICAR")
            proposals.append(Proposal(
                kind="COMPROMISO", text=text, responsible=responsible, source=_clean(item), method="LISTA", flags=flags,
            ))
    return proposals


def from_inline(blocks: List[Any], act_date: Optional[date]) -> List[Proposal]:
    proposals = []
    for block in blocks:
        if not (isinstance(block, str) and re.match(r"^\s*COMPROMISO\s*:", normalize(block))):
            continue
        text = _clean(re.sub(r"^\s*compromiso\s*:", "", block, flags=re.IGNORECASE))
        match = re.match(r"^(todas las instituciones|todos los integrantes|todas las entidades)", text, flags=re.IGNORECASE)
        responsible = _clean(match.group(1)).capitalize() if match else None
        _, deadline_flags = evaluate_deadline(None, act_date)
        deadline_text = None
        if re.search(r"pr[oó]ximo (comit[eé]|consejo)", text, flags=re.IGNORECASE):
            deadline_flags, deadline_text = ["PLAZO_VAGO"], "Próxima sesión"
        proposals.append(Proposal(kind="COMPROMISO", text=text, responsible=responsible, source=_clean(block),
                                  deadline_text=deadline_text, method="EN_LINEA",
                                  flags=_responsible_flags(responsible) + deadline_flags))
    return proposals


def from_approvals(blocks: List[Any]) -> List[Proposal]:
    """Acuerdos aprobados por votación (Comité de Orden Público)."""
    proposals = []
    for index, block in enumerate(blocks):
        if not isinstance(block, str) or re.sub(r"^[\d.\s]+", "", normalize(block)).strip(" .:") != "APROBACION":
            continue
        for offset, item in enumerate(blocks[index + 1:index + 6], start=index + 1):
            if not (isinstance(item, str) and re.search(r"DE ACUERDO|SE APRUEBA|APROBAD", normalize(item))):
                continue
            text = _clean(re.sub(r"^.*?\)\s*:\s*", "", item)) or _clean(item)
            # "Todos los miembros ... presentes están de acuerdo con el presupuesto..." -> "Aprobado: el presupuesto..."
            lead = re.match(r"^todos los (miembros|integrantes|asistentes).{0,160}?(est[aá]n )?de acuerdo (con|en|que)\s+", text, flags=re.IGNORECASE)
            if lead and len(text) - lead.end() > 20 and not re.match(r"^(el|lo) propuesto", text[lead.end():], flags=re.IGNORECASE):
                text = f"Aprobado: {text[lead.end():]}"
            # "De acuerdo con lo propuesto:" no dice qué se aprobó: se toma el párrafo de la propuesta.
            if item.rstrip().endswith(":") or re.search(r"CON (EL|LO) PROPUESTO", normalize(item)):
                proposal_text = next(
                    (candidate for candidate in reversed(blocks[max(0, index - 6):index])
                     if isinstance(candidate, str) and re.search(r"PROPUESTA|PROPONE|DISTRIBUIR", normalize(candidate))),
                    None,
                )
                if proposal_text:
                    text = f"Aprobado: {_clean(proposal_text)}"
            votes = 0
            for other in blocks[offset + 1:offset + 12]:
                if isinstance(other, list):
                    votes += sum(1 for row in other if row and normalize(row[-1]) == "SI")
                elif isinstance(other, str):
                    if re.match(r"^(\d+\.\s*)?PROPOSICIONES", normalize(other)):
                        break
                    votes += len(re.findall(r"\)\s*\.?\s*SI\b", normalize(other)))
            # "De acuerdo con lo propuesto" sin el párrafo de la propuesta: el acta no dice qué se aprobó.
            unclear = bool(re.search(r"(CON|EN) (EL|LO) PROPUESTO\W*$", normalize(text)))
            proposals.append(Proposal(
                kind="ACUERDO", text=text, source=_clean(item), method="APROBACION",
                flags=["SIN_RESPONSABLE", "SIN_PLAZO"] + (["ACUERDO_SIN_CONTENIDO"] if unclear else [])
                + ([f"VOTOS_{votes}"] if votes else []),
            ))
            break
    return proposals


def reread_commitments(blocks: List[Any]) -> List[str]:
    """Compromisos anteriores leídos en el punto "Lectura de compromisos" (no son nuevos)."""
    items: List[str] = []
    headings = [i for i, block in enumerate(blocks)
                if isinstance(block, str) and normalize(block).strip(" .:") == "LECTURA DE COMPROMISOS"]
    # La primera aparición suele ser el orden del día; el contenido está en la última.
    for index in headings[-1:]:
        for item in blocks[index + 1:index + 15]:
            if not isinstance(item, str):
                break
            normalized = normalize(item)
            if normalized.startswith(("CONTEXTO", "INFORME", "DESARROLLO", "PROPOSICIONES")) or re.match(r"^\d+\.", normalized):
                break
            if len(item) > 15:
                items.append(_clean(item))
    return items


def closing_date_warning(blocks: List[Any], act_date: Optional[date]) -> Optional[Dict[str, str]]:
    if not act_date:
        return None
    text = normalize(blocks_text(blocks))
    match = re.search(r"HOY (\d{1,2}) (?:DEL? )?(?:MES DE )?([A-Z]+) DEL? (\d{4})", text)
    if not match or match.group(2) not in MONTHS:
        return None
    try:
        closing = date(int(match.group(3)), MONTHS[match.group(2)], int(match.group(1)))
    except ValueError:
        return None
    if closing == act_date:
        return None
    return {"code": "CIERRE_FECHA_DISTINTA",
            "message": f"El acta tiene fecha {act_date.strftime('%d/%m/%Y')}, pero el cierre dice {closing.strftime('%d/%m/%Y')}: posible plantilla copiada de otra sesión."}


def read_act(content: bytes, filename: str, instance_hint: Optional[str] = None,
             use_ocr: bool = False) -> Tuple[ActReading, List[str]]:
    blocks = document_blocks(content, filename)
    is_pdf = content[:4] == b"%PDF" or (filename or "").lower().endswith(".pdf")
    ocr_model, ocr_used = None, False
    if is_pdf and use_ocr and len(blocks_text(blocks).strip()) < 400:
        blocks, ocr_model = ocr_blocks(content, filename)
        ocr_used = True
    # Solo el PDF parte los párrafos en líneas; en Word cada párrafo ya viene completo.
    if is_pdf:
        blocks = paragraphs_from_lines(blocks)
    meta = read_metadata(blocks, filename)
    instance = instance_hint if instance_hint in INSTANCES else meta["instance"]
    act_date = meta["act_date"]

    table_proposals, empty_tables = from_tables(blocks, act_date)
    # Si el acta trae tabla de compromisos, la lista narrativa suele repetirla: se usa solo la tabla.
    proposals = list(table_proposals) or from_list(blocks, act_date)
    known = {normalize(item.text) for item in proposals}
    proposals += [item for item in from_inline(blocks, act_date) if normalize(item.text) not in known]
    proposals += from_approvals(blocks)

    warnings: List[Dict[str, str]] = []
    if not proposals:
        warnings.append({"code": "SIN_COMPROMISOS", "message": "El acta no registra compromisos ni acuerdos concretos."})
    if empty_tables and not table_proposals:
        warnings.append({"code": "TABLA_VACIA", "message": "La tabla de compromisos del acta está vacía."})
    closing = closing_date_warning(blocks, act_date)
    if closing:
        warnings.append(closing)
    if not act_date:
        warnings.append({"code": "SIN_FECHA_ACTA", "message": "No se encontró la fecha del acta en el encabezado."})
    vague = sum(1 for item in proposals if {"SIN_PLAZO", "PLAZO_VAGO"} & set(item.flags))
    if proposals and vague:
        warnings.append({"code": "PLAZOS_INDEFINIDOS", "message": f"{vague} de {len(proposals)} compromisos o acuerdos no tienen una fecha límite concreta."})
    wrong_year = sum(1 for item in proposals if "FECHA_ANIO_DISTINTO" in item.flags)
    if wrong_year:
        warnings.append({"code": "FECHA_ANIO_DISTINTO", "message": f"{wrong_year} compromiso(s) tienen una fecha con un año distinto al del acta; revise si es un error de digitación."})

    body = blocks_text(blocks)
    if len(body.strip()) < 400:
        warnings.append({"code": "SIN_TEXTO", "message": "El archivo casi no tiene texto legible: puede ser un PDF escaneado."})
    if ocr_used:
        warnings.append({"code": "LEIDA_CON_OCR",
                         "message": f"Acta escaneada leída con OCR ({ocr_model or 'Gemini'}): revise nombres, fechas y cifras contra el original."})
    reading = ActReading(
        instance=instance, instance_label=INSTANCES[instance]["label"], act_number=meta["act_number"],
        act_date=act_date.isoformat() if act_date else None, objective=meta["objective"],
        proposals=proposals, warnings=warnings,
        topics=topic_counts(line for line in body.splitlines() if len(line) > 25), text_chars=len(body.strip()),
    )
    return reading, reread_commitments(blocks)
