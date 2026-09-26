"""Verificación de textos redactados por IA antes de mostrarlos.

La IA del SISC solo redacta: las cifras se calculan en el código y se le entregan en el
prompt. Este guardián comprueba que el texto devuelto no las altere:

1. Cada número del texto debe existir en los datos entregados (se aceptan los formatos
   colombianos: "1.052" = 1052, "25,6" = 25.6).
2. Si una frase dice que algo aumentó o disminuyó junto a un porcentaje, el signo de ese
   porcentaje en los datos debe coincidir.

Si falla, quien llama muestra el texto de respaldo calculado sin IA.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Dict, Iterable, List, Optional, Set

# Números con separador de miles (1.052 / 180,942), decimales (25,6 / 25.6) o enteros.
_NUMBER = re.compile(r"(?<![\w.,])[-+−]?\d{1,3}(?:[.,]\d{3})+(?![\d])|(?<![\w.,])[-+−]?\d+(?:[.,]\d+)?(?![\d])")
_PERCENT = re.compile(r"([-+−]?\d+(?:[.,]\d+)?)\s*%")
_UP = re.compile(r"\b(aument\w*|increment\w*|sub(?:e|io|ió|ieron)\w*|creci\w*|alza|ascend\w*)\b", re.IGNORECASE)
_DOWN = re.compile(r"\b(disminu\w*|reduc\w*|redujo|baj(?:a|o|ó|aron)\w*|descen\w*|ca(?:e|yo|yó|yeron)\w*|retroce\w*)\b", re.IGNORECASE)
_SENTENCE = re.compile(r"[^.;!?\n]+")


@dataclass
class GuardResult:
    ok: bool
    problems: List[str] = field(default_factory=list)


def _to_decimal(raw: str) -> Optional[Decimal]:
    text = raw.replace("−", "-").replace("+", "")
    if re.fullmatch(r"-?\d{1,3}(?:[.,]\d{3})+", text):
        text = text.replace(".", "").replace(",", "")          # separador de miles
    else:
        text = text.replace(",", ".")                           # coma decimal
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def extract_numbers(text: str) -> List[Decimal]:
    values = []
    for match in _NUMBER.finditer(text or ""):
        value = _to_decimal(match.group(0))
        if value is not None:
            values.append(value)
    return values


def _allowed_values(source: str, extra: Iterable[str] = ()) -> Set[Decimal]:
    allowed = set()
    for value in extract_numbers(source) + [v for item in extra for v in extract_numbers(str(item))]:
        allowed.add(abs(value).normalize())
        # "1.052" puede llegar como miles (1052) o como decimal (1.052): se aceptan ambos.
    for raw in re.findall(r"\d+[.,]\d{3}\b", source or ""):
        value = _to_decimal(raw.replace(",", "."))
        if value is not None:
            allowed.add(abs(value).normalize())
    return allowed


def _source_percent_signs(source: str) -> Dict[Decimal, Set[int]]:
    signs: Dict[Decimal, Set[int]] = {}
    for match in _PERCENT.finditer(source or ""):
        value = _to_decimal(match.group(1))
        if value is None:
            continue
        signs.setdefault(abs(value).normalize(), set()).add(-1 if value < 0 else 1 if value > 0 else 0)
    return signs


def verify_ai_text(text: str, source: str, *, extra_allowed: Iterable[str] = ()) -> GuardResult:
    """`source` son los datos entregados a la IA (no las instrucciones del prompt)."""
    if not text or not text.strip():
        return GuardResult(False, ["Respuesta vacia."])
    problems = []

    allowed = _allowed_values(source, extra_allowed)
    unknown = []
    for value in extract_numbers(text):
        if abs(value).normalize() not in allowed:
            unknown.append(str(value))
    if unknown:
        problems.append("Cifras que no estan en los datos: " + ", ".join(sorted(set(unknown))))

    signs = _source_percent_signs(source)
    for sentence in _SENTENCE.findall(text):
        says_up, says_down = bool(_UP.search(sentence)), bool(_DOWN.search(sentence))
        if says_up == says_down:
            continue  # sin verbo de dirección, o ambos en la misma frase: no se puede atribuir
        for match in _PERCENT.finditer(sentence):
            value = _to_decimal(match.group(1))
            if value is None:
                continue
            source_signs = signs.get(abs(value).normalize())
            if not source_signs or len(source_signs) > 1:
                continue
            sign = next(iter(source_signs))
            if (says_up and sign < 0) or (says_down and sign > 0):
                problems.append(
                    f"Direccion contraria a los datos: '{sentence.strip()[:120]}' "
                    f"({'aumento' if says_up else 'disminucion'} frente a {'-' if sign < 0 else '+'}{abs(value)}%)."
                )
    return GuardResult(not problems, problems)
