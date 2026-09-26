"""Lectura verificada de tablas mensuales en informes institucionales.

Los informes de gestión (p. ej. Comisarías de Familia) presentan cada indicador como
una fila: etiqueta + 12 meses + total. En lugar de tomar "el último número" cercano a
un título (que suele ser un número de página o una fecha), este lector toma la fila
completa y la verifica:

- Suma de meses contra el total declarado.
- Filas con valores idénticos mes a mes (posible fila copiada en la plantilla).
- Desgloses (zona, género, grupo étnico, consumo) contra el total de casos por mes.
- Filas "TOTAL V.I.F. RECIBIDOS" contra el total de casos por mes.

Funciona igual con el texto de un PDF y con tablas Markdown del OCR (el separador "|"
se descarta al normalizar).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

MONTH_TOKENS = {
    "ENE", "ENER", "ENERO", "FEB", "FEBR", "FEBRERO", "MAR", "MARZO", "ABR", "ABRIL", "MAY", "MAYO",
    "JUN", "JUNIO", "JUL", "JULIO", "AGO", "AGOSTO", "SEP", "SEPT", "SET", "SEPTIEMBRE",
    "OCT", "OCTUBRE", "NOV", "NOVIEMBRE", "DIC", "DICIEMBRE",
}
MONTH_LABELS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
CONTEXT_TOKENS = 10

# Etiqueta de fila (normalizada) -> (indicador, unidad, categoría). El orden importa:
# se usa la primera regla que coincide.
COMISARIA_ROWS: List[Tuple[str, str, str, str]] = [
    (r"ADULTO MAYOR", "Casos de violencia contra adultos mayores", "casos", "Gestion de comisaria"),
    (r"APERTURA NUEVO PROCESO.*V I F", "Nuevos procesos de violencia en el contexto familiar", "casos", "Gestion de comisaria"),
    (r"TOTAL AUDIENCIAS REALIZADAS", "Audiencias realizadas", "casos", "Gestion de comisaria"),
    (r"MEDIDA DE PROTECCION POLICIVA URGENTE", "Medidas de proteccion urgentes", "medidas", "Gestion de comisaria"),
    (r"(^| )MEDIDAS DEFINITIVAS$", "Medidas de proteccion definitivas", "medidas", "Gestion de comisaria"),
    (r"ZONAS VIF URBANO", "Casos reportados en zona urbana", "casos", "Gestion de comisaria"),
    (r"ZONAS VIF RURAL", "Casos reportados en zona rural", "casos", "Gestion de comisaria"),
    (r"(^| )FEMENINO$", "Casos de violencia contra mujeres en el contexto familiar", "casos", "Gestion de comisaria"),
    (r"(^| )MASCULINO$", "Casos de violencia contra hombres en el contexto familiar", "casos", "Gestion de comisaria"),
    (r"SUSTANCIAS PSICOACTIVAS", "Casos asociados a consumo de sustancias psicoactivas", "casos", "Gestion de comisaria"),
    (r"(^| )ALCOHOL$", "Casos asociados a consumo de alcohol", "casos", "Gestion de comisaria"),
    (r"(^| )AFRO", "Casos en poblacion afrodescendiente", "casos", "Enfoque diferencial"),
    (r"(^| )MESTIZO", "Casos en poblacion mestiza", "casos", "Enfoque diferencial"),
    (r"(^| )INDIGENA", "Casos en poblacion indigena", "casos", "Enfoque diferencial"),
    (r"POBLACION MIGRANTE", "Casos con poblacion migrante involucrada", "casos", "Gestion de comisaria"),
    (r"(^| )PARD$", "Procesos Administrativos de Restablecimiento de Derechos", "procesos", "Gestion de comisaria"),
    (r"TRABAJO SOCIAL", "Valoraciones de trabajo social", "casos", "Gestion de comisaria"),
    (r"PSICOLOGIC", "Acompanamientos psicologicos", "casos", "Gestion de comisaria"),
    (r"DESPACHOS COMIS[AO]RIOS", "Despachos comisorios recibidos", "despachos", "Gestion de comisaria"),
]
REFERENCE_INDICATOR = "Nuevos procesos de violencia en el contexto familiar"
# Desgloses del total de casos: (marcadores que identifican la tabla, categorías que la
# componen). Solo se suman las filas de esas categorías, aunque la tabla tenga otras filas.
PARTITIONS = {
    "zona": (("ZONAS VIF",), r"ZONAS VIF|OTRO MUNICIPIO|NO REGISTRA"),
    "genero": (("FEMENINO", "MASCULINO"), r"FEMENINO|MASCULINO|LGTB|NO REGISTRA"),
    "grupo etnico": (("MESTIZO", "AFRO"), r"INDIGENA|AFRO|RROM|GITANO|MESTIZO|RAIZAL|PALENQUER|NINGUNO|NO REGISTRA"),
    "tipo de consumo": (("SUSTANCIAS PSICOACTIVAS",), r"SUSTANCIAS|ALCOHOL|JUEGO|NINGUNA|NO REGISTRA"),
}


@dataclass
class TableRow:
    label: str
    months: List[int]
    total: Optional[int]
    table: int
    consistent: Optional[bool]  # None = sin total declarado

    @property
    def months_sum(self) -> int:
        return sum(self.months)


@dataclass
class TableCandidate:
    indicator: str
    value: int
    unit: str
    category: str
    confidence: float
    evidence: str
    public_allowed: bool = True


@dataclass
class TableFinding:
    code: str
    message: str
    evidence: str
    indicators: List[str] = field(default_factory=list)


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^A-Z0-9]+", " ", text.upper())
    return re.sub(r"\s+", " ", text).strip()


def _is_header(tokens: List[str]) -> bool:
    return sum(1 for token in tokens if token in MONTH_TOKENS) >= 10


def _label_tokens(tokens: Iterable[str]) -> List[str]:
    return [token for token in tokens if not token.isdigit()]


def _split_row(numbers: List[int]) -> Optional[Tuple[List[int], Optional[int], Optional[bool]]]:
    """Ubica 12 meses + total dentro de una secuencia numérica.

    La secuencia puede empezar con un año de la etiqueta ("V.I.F.- 2026 28 26 ...").
    Se prefiere la ventana cuyo total coincide con la suma de los meses.
    """
    for offset in range(0, len(numbers) - 12):
        months, total = numbers[offset:offset + 12], numbers[offset + 12]
        leading = numbers[:offset]
        if sum(months) == total and all(2000 <= value <= 2100 for value in leading):
            return months, total, True
    offset = 0
    while offset < len(numbers) and 2000 <= numbers[offset] <= 2100 and len(numbers) - offset > 12:
        offset += 1
    remaining = numbers[offset:]
    if len(remaining) >= 13:
        return remaining[:12], remaining[12], False
    if len(remaining) == 12:
        return remaining, None, None
    return None


def parse_monthly_rows(blocks: Iterable[str]) -> List[TableRow]:
    rows: List[TableRow] = []
    table = 0
    for block in blocks:
        context: List[str] = []   # texto desde la última fila o encabezado
        pending: List[str] = []   # etiqueta tomada del encabezado de la tabla
        for raw_line in str(block or "").splitlines():
            tokens = normalize(raw_line).split()
            if not tokens:
                continue
            if _is_header(tokens):
                table += 1
                first_month = next(index for index, token in enumerate(tokens) if token in MONTH_TOKENS)
                pending = (_label_tokens(context) + _label_tokens(tokens[:first_month]))[-CONTEXT_TOKENS:]
                context = []
                continue
            trailing = 0
            while trailing < len(tokens) and tokens[len(tokens) - 1 - trailing].isdigit():
                trailing += 1
            if trailing >= 12:
                numbers = [int(token) for token in tokens[len(tokens) - trailing:]]
                split = _split_row(numbers)
                if split:
                    own = _label_tokens(tokens[:len(tokens) - trailing])
                    label_tokens = (_label_tokens(context) + own)[-CONTEXT_TOKENS:] if own else (_label_tokens(context) or pending)
                    months, total, consistent = split
                    rows.append(TableRow(" ".join(label_tokens), months, total, table, consistent))
                    context = []
                    continue
            context.extend(tokens)
            context = context[-40:]
    return rows


def _months_text(months: List[int], total: Optional[int] = None) -> str:
    active = [f"{MONTH_LABELS[index]} {value}" for index, value in enumerate(months) if value or index < 1]
    text = ", ".join(active)
    return f"{text}; total declarado {total}" if total is not None else text


def _match(label: str, rules) -> Optional[Tuple[str, str, str]]:
    for pattern, indicator, unit, category in rules:
        if re.search(pattern, label):
            return indicator, unit, category
    return None


def extract_comisaria_tables(blocks: Iterable[str]) -> Tuple[List[TableCandidate], List[TableFinding]]:
    rows = parse_monthly_rows(blocks)
    candidates: Dict[str, TableCandidate] = {}
    row_by_indicator: Dict[str, TableRow] = {}
    findings: List[TableFinding] = []

    for row in rows:
        matched = _match(row.label, COMISARIA_ROWS)
        if not matched:
            continue
        indicator, unit, category = matched
        if indicator in candidates:
            continue
        value = row.total if row.total is not None else row.months_sum
        if row.consistent:
            confidence, public_allowed = 0.97, True
            evidence = f"Tabla mensual verificada: los meses suman {row.months_sum} y coinciden con el total."
        elif row.consistent is None:
            confidence, public_allowed = 0.8, True
            evidence = f"Tabla mensual sin total declarado; valor calculado como suma de meses ({_months_text(row.months)})."
        else:
            confidence, public_allowed = 0.5, False
            value = row.months_sum
            evidence = f"Los meses suman {row.months_sum}, pero el informe declara {row.total}."
            findings.append(TableFinding(
                "INFORME_SUMA_INCONSISTENTE",
                f"{indicator}: los meses suman {row.months_sum} y el informe declara {row.total}. "
                "Se carga la suma de meses como no publica hasta confirmacion.",
                f"Fila '{row.label}': {_months_text(row.months, row.total)}.",
                [indicator],
            ))
        candidates[indicator] = TableCandidate(indicator, value, unit, category, confidence, evidence, public_allowed)
        row_by_indicator[indicator] = row

    tables: Dict[int, List[TableRow]] = {}
    for row in rows:
        tables.setdefault(row.table, []).append(row)

    def is_total(row: TableRow) -> bool:
        return row.label.startswith("TOTAL") or " TOTAL " in f" {row.label} "

    def supported_by_its_table(row: TableRow) -> bool:
        """Una fila TOTAL respaldada por la suma de las demás filas de su tabla."""
        parts = [other for other in tables.get(row.table, []) if other is not row and not is_total(other)]
        return is_total(row) and bool(parts) and all(
            sum(other.months[index] for other in parts) == row.months[index] for index in range(12)
        )

    # Filas idénticas mes a mes en tablas distintas: posible copia de plantilla. Si una de
    # las dos es un total respaldado por su propia tabla, la sospechosa es la otra.
    reference = row_by_indicator.get(REFERENCE_INDICATOR)
    for indicator, row in row_by_indicator.items():
        if row.months_sum == 0 or (reference and row.months == reference.months):
            continue
        if supported_by_its_table(row):
            continue
        for other in rows:
            if other is row or other.table == row.table or other.months != row.months:
                continue
            if reference and other.months == reference.months:
                continue
            other_indicator = (_match(other.label, COMISARIA_ROWS) or (None,))[0]
            if other_indicator == indicator:
                continue
            findings.append(TableFinding(
                "INFORME_FILA_DUPLICADA",
                f"{indicator} repite mes a mes la fila '{other.label}' de otra tabla "
                f"({', '.join(str(value) for value in row.months[:6])}...): posible error de plantilla. "
                "Se carga como no publico hasta confirmacion.",
                f"Filas '{row.label}' y '{other.label}'.",
                [indicator],
            ))
            candidates[indicator].public_allowed = False
            candidates[indicator].confidence = min(candidates[indicator].confidence, 0.5)
            break

    if reference:
        # Desgloses que deben sumar el total de casos de cada mes.
        for name, (markers, members) in PARTITIONS.items():
            for table_rows in tables.values():
                if not any(marker in row.label for row in table_rows for marker in markers):
                    continue
                parts = [row for row in table_rows if not is_total(row) and re.search(members, row.label)]
                sums = [sum(row.months[index] for row in parts) for index in range(12)]
                gaps = [
                    f"{MONTH_LABELS[index]}: {sums[index]} de {reference.months[index]}"
                    for index in range(12) if sums[index] != reference.months[index]
                ]
                if gaps:
                    affected = [
                        indicator for indicator, row in row_by_indicator.items()
                        if row in parts
                    ]
                    for indicator in affected:
                        candidates[indicator].public_allowed = False
                    findings.append(TableFinding(
                        "INFORME_DESGLOSE_INCOMPLETO",
                        f"La tabla por {name} no suma el total de casos del mes ({'; '.join(gaps)}). "
                        + ("Sus indicadores se cargan como no publicos hasta confirmacion." if affected else ""),
                        f"Total de referencia: {_months_text(reference.months, reference.total)}.",
                        affected,
                    ))
                break

        for row in rows:
            if "TOTAL V I F RECIBIDOS" in row.label and row.months != reference.months:
                gaps = [
                    f"{MONTH_LABELS[index]}: {row.months[index]} en lugar de {reference.months[index]}"
                    for index in range(12) if row.months[index] != reference.months[index]
                ]
                findings.append(TableFinding(
                    "INFORME_TOTAL_INCONSISTENTE",
                    f"Una fila 'Total V.I.F. recibidos' no coincide con el total de casos ({'; '.join(gaps)}).",
                    f"Fila '{row.label}'.",
                ))

    return list(candidates.values()), findings
