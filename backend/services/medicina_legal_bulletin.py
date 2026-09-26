"""Medicina Legal en los boletines mensual, semestral y anual.

Medicina Legal (INMLCF) publica cifras preliminares por mes vencido, con uno a tres meses de
rezago. Por eso no entra en el boletín semanal, y en los demás se publica el tramo de meses
del periodo que la fuente ya cubre; si todavía no cubre ninguno, su último mes disponible,
señalado como contexto de otro periodo. Nunca se suma con la sábana policial: son unidades
distintas (necropsias y exámenes frente a hechos denunciados).
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models_medicina_legal import MedicinaLegalRecord, MedicinaLegalSnapshot

SOURCE_CODE = "MEDICINA_LEGAL"
SOURCE_NAME = "Medicina Legal (INMLCF)"
DOMAIN = "VIDA E INTEGRIDAD"
JAMUNDI_DANE = "76364"
APPLICABLE_EDITIONS = {"monthly", "semester", "annual"}
# Con menos de 3 casos el dato se publica como "menos de 3" (evita identificar personas).
PRIVACY_THRESHOLD = 3
MONTH_NAMES_ES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                  "septiembre", "octubre", "noviembre", "diciembre")

# dataset, número de contexto de la fuente, código, nombre público, unidad, prioridad
INDICATORS = (
    ("FATALES_PRE", "1", "medicina.homicidios", "Presuntos homicidios", "necropsias", 0.95),
    ("FATALES_PRE", "3", "medicina.transporte", "Muertes en eventos de transporte", "necropsias", 0.8),
    ("FATALES_PRE", "2", "medicina.suicidios", "Suicidios", "necropsias", 0.7),
    ("NOFATALES_PRE", "1", "medicina.interpersonal", "Lesiones por violencia interpersonal", "exámenes", 0.85),
    ("NOFATALES_PRE", "6", "medicina.pareja", "Lesiones por violencia de pareja", "exámenes", 0.85),
    ("NOFATALES_PRE", "2", "medicina.sexual", "Exámenes por presunto delito sexual", "exámenes", 0.85),
)
DATASETS = ("FATALES_PRE", "NOFATALES_PRE")


def month_key(year: int, month: int) -> int:
    return year * 100 + month


def split_key(key: int) -> Tuple[int, int]:
    return key // 100, key % 100


def month_end(key: int) -> date:
    year, month = split_key(key)
    return date(year, month, calendar.monthrange(year, month)[1])


def range_label(first: int, last: int) -> str:
    (y1, m1), (y2, m2) = split_key(first), split_key(last)
    if first == last:
        return f"{MONTH_NAMES_ES[m1 - 1]} de {y1}"
    if y1 == y2:
        return f"{MONTH_NAMES_ES[m1 - 1]} a {MONTH_NAMES_ES[m2 - 1]} de {y2}"
    return f"{MONTH_NAMES_ES[m1 - 1]} de {y1} a {MONTH_NAMES_ES[m2 - 1]} de {y2}"


@dataclass
class Window:
    first: int  # primer mes publicado (AAAAMM)
    last: int  # último mes publicado
    aligned: bool  # los meses publicados son los del periodo pedido
    latest: int  # último mes que tiene la fuente

    @property
    def label(self) -> str:
        return range_label(self.first, self.last)

    @property
    def previous(self) -> Tuple[int, int]:
        return self.first - 100, self.last - 100  # mismos meses del año anterior


def plan_window(start: date, end: date, latest: int) -> Window:
    """Meses del periodo que la fuente ya cubre; si no cubre ninguno, su último mes disponible."""
    requested_first, requested_last = month_key(start.year, start.month), month_key(end.year, end.month)
    last = min(requested_last, latest)
    if last < requested_first:
        return Window(first=latest, last=latest, aligned=False, latest=latest)
    return Window(first=requested_first, last=last, aligned=last == requested_last, latest=latest)


def latest_snapshots(db: Session) -> Dict[str, MedicinaLegalSnapshot]:
    snapshots = {}
    for key in DATASETS:
        row = (db.query(MedicinaLegalSnapshot).filter(MedicinaLegalSnapshot.dataset_key == key)
               .order_by(MedicinaLegalSnapshot.cutoff_date.desc(), MedicinaLegalSnapshot.created_at.desc()).first())
        if row:
            snapshots[key] = row
    return snapshots


def _ym():
    return MedicinaLegalRecord.year_hecho * 100 + MedicinaLegalRecord.month_hecho


def latest_month(db: Session, snapshots: Dict[str, MedicinaLegalSnapshot]) -> Optional[int]:
    """Último mes con datos de Jamundí que cubren todos los conjuntos (el más atrasado manda)."""
    if set(snapshots) != set(DATASETS):
        return None
    months = []
    for snapshot in snapshots.values():
        value = db.query(func.max(_ym())).filter(
            MedicinaLegalRecord.snapshot_id == snapshot.id,
            MedicinaLegalRecord.codigo_dane_municipio == JAMUNDI_DANE,
        ).scalar()
        if value is None:
            return None
        months.append(int(value))
    return min(months)


def counts(db: Session, snapshots: Dict[str, MedicinaLegalSnapshot], first: int, last: int) -> Dict[Tuple[str, str], int]:
    """Casos por (conjunto, número de contexto) entre dos meses, ambos incluidos."""
    result: Dict[Tuple[str, str], int] = {}
    for key, snapshot in snapshots.items():
        rows = db.query(MedicinaLegalRecord.contexto, func.count(func.distinct(MedicinaLegalRecord.record_key))).filter(
            MedicinaLegalRecord.snapshot_id == snapshot.id,
            MedicinaLegalRecord.codigo_dane_municipio == JAMUNDI_DANE,
            _ym() >= first, _ym() <= last,
        ).group_by(MedicinaLegalRecord.contexto).all()
        for contexto, total in rows:
            number = str(contexto or "").strip().split(" ", 1)[0]
            result[(key, number)] = result.get((key, number), 0) + int(total)
    return result


def resolve(db: Session, start: date, end: date) -> Optional[Dict[str, object]]:
    snapshots = latest_snapshots(db)
    latest = latest_month(db, snapshots)
    if latest is None:
        return None
    window = plan_window(start, end, latest)
    return {"snapshots": snapshots, "window": window}


def indicator_rows(db: Session, start: date, end: date) -> List[Dict[str, object]]:
    """Filas listas para `SiscCifrasService.indicator`, con su periodo propio."""
    resolved = resolve(db, start, end)
    if not resolved:
        return []
    window: Window = resolved["window"]
    snapshots = resolved["snapshots"]
    current = counts(db, snapshots, window.first, window.last)
    previous = counts(db, snapshots, *window.previous)
    first_year, first_month = split_key(window.first)
    rows = []
    for dataset, number, code, name, unit, priority in INDICATORS:
        value = current.get((dataset, number), 0)
        prior = previous.get((dataset, number), 0)
        hidden = value < PRIVACY_THRESHOLD
        rows.append({
            "code": code, "name": name, "unit": unit, "priority": priority,
            "value": None if hidden else float(value),
            "comparison_value": None if hidden or prior < PRIVACY_THRESHOLD else float(prior),
            "start": date(first_year, first_month, 1), "end": month_end(window.last),
            "cutoff": snapshots[dataset].cutoff_date,
            "metadata": {
                "period_label": window.label,
                "coverage_type": "ALIGNED" if window.aligned else "CONTEXT",
                "reporting_entity": SOURCE_NAME,
                "comparison_label": "mismos meses del año anterior",
                "preliminary": True,
                "below_threshold": hidden,
                "public_detail": "Cifra preliminar de Medicina Legal; puede cambiar cuando la fuente publique la definitiva.",
            },
        })
    return rows
