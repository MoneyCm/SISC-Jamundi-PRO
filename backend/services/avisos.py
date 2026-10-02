"""Avisos: lo que está atrasado o se acerca, reunido en un solo lugar (Inicio).

Cada aviso sale de algo que el SISC ya calcula; aquí solo se junta y se ordena:
- la sábana de la Policía (más de 14 días sin llegar; a los 21 la reemplaza el aviso con cifras de MinDefensa);
- los comparendos del RNMC (más de 35 días sin datos nuevos);
- las solicitudes de datos vencidas (Centro de análisis → Solicitudes de datos);
- tareas atrasadas de la agenda semanal (por ejemplo, el boletín mensual);
- el próximo Consejo de Seguridad, cuando faltan 14 días o menos, con los compromisos vencidos;
- las actas pedidas que no han llegado después de 15 días (Archivo de actas);
- la copia de seguridad, si falló o lleva más de dos días sin hacerse.

Nivel: "alto" (hay que actuar ya) o "medio" (conviene revisarlo esta semana).
"""
import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
DIAS_SABANA = 14
DIAS_CONSEJO = 14
ESTADO_RESPALDO = Path(__file__).resolve().parents[1] / "data" / "respaldo_estado.json"


def _fecha(valor) -> str:
    if isinstance(valor, str):
        valor = date.fromisoformat(valor[:10])
    return f"{valor.day} de {MESES[valor.month - 1]}"


def _aviso(clave: str, nivel: str, titulo: str, detalle: str, destino: Optional[Dict] = None) -> Dict:
    return {"clave": clave, "nivel": nivel, "titulo": titulo, "detalle": detalle, "destino": destino}


def _sabana(db: Session, hoy: date) -> List[Dict]:
    from services.respaldo_sabana import estado

    datos = estado(db, hoy)
    dias = datos.get("dias_retraso")
    if dias is None or dias <= DIAS_SABANA or datos.get("atrasada"):
        return []  # al día, o ya lo cubre el aviso de respaldo con cifras de MinDefensa (más de 21 días)
    return [_aviso("sabana", "medio", f"La sábana de la Policía lleva {dias} días sin llegar",
                   f"El último dato es del {_fecha(datos['sabana_corte'])}. Conviene pedirla a la Policía.",
                   {"page": "boletin_replica"})]


def _rnmc(db: Session, hoy: date) -> List[Dict]:
    from services import comparendos_rnmc

    datos = comparendos_rnmc.estado_carga(db, hoy)
    if not datos["atrasado"]:
        return []
    detalle = (f"El último comparendo cargado es del {_fecha(datos['corte'])}." if datos["corte"]
               else "Todavía no hay comparendos cargados.")
    return [_aviso("rnmc", "medio", "Faltan los reportes del RNMC (comparendos)",
                   detalle + " Pida los dos reportes del mes y súbalos en Inspecciones de Policía.", {"page": "inspecciones"})]


def _solicitudes(db: Session, hoy: date) -> List[Dict]:
    from services.data_requests import board

    vencidas = [e for e in board(db, hoy)["entities"] if e.get("state") == "ATRASADA"]
    if not vencidas:
        return []
    partes = [f"{e['name']} (se pidió el {_fecha(e['open_since'])})" if e.get("open_since") else e["name"] for e in vencidas]
    nivel = "alto" if any((e.get("days_late") or 0) >= 14 for e in vencidas) else "medio"
    return [_aviso("solicitudes", nivel,
                   f"{len(vencidas)} {'dependencia no ha' if len(vencidas) == 1 else 'dependencias no han'} respondido a tiempo",
                   "; ".join(partes) + ". Conviene recordarles.", {"page": "observatory", "tab": "solicitudes"})]


def _agenda(db: Session, hoy: date) -> List[Dict]:
    from services.operating_calendar import weekly_items

    avisos = []
    for item in weekly_items(db, hoy):
        if item.get("status") == "ATRASADO":
            avisos.append(_aviso(f"agenda-{item['key']}", "medio", item["title"],
                                 f"Atrasado ({item.get('when')}). {item.get('detail') or ''}".strip(),
                                 {"page": (item.get("target") or {}).get("page", "observatory")}))
    return avisos


def _consejo(db: Session, hoy: date) -> List[Dict]:
    from db.models_council import CouncilCommitment
    from services import council_commitments_service as commitments
    from services.operating_calendar import _council_inputs

    _anterior, proximo, *_ = _council_inputs(db, hoy)
    faltan = (proximo.start - hoy).days
    if faltan < 0 or faltan > DIAS_CONSEJO:
        return []
    resumen = commitments.summary(db.query(CouncilCommitment).all(), today=hoy)
    cuando = _fecha(proximo.start) if proximo.start == proximo.end else f"entre el {_fecha(proximo.start)} y el {_fecha(proximo.end)}"
    estimado = " (fecha estimada; se puede fijar en el Centro de análisis)" if proximo.source != "REGISTRADA" else ""
    vencidos = resumen.get("overdue") or 0
    detalle = f"Será {cuando}{estimado}."
    if vencidos:
        detalle += f" Hay {vencidos} compromisos vencidos: conviene pedir su avance antes de la sesión."
    return [_aviso("consejo", "alto" if vencidos and faltan <= 7 else "medio",
                   f"Faltan {faltan} días para el Consejo de Seguridad" if faltan else "Hoy es el Consejo de Seguridad",
                   detalle, {"page": "council_commitments"})]


def _actas(db: Session, hoy: date) -> List[Dict]:
    from services.council_commitments_service import DIAS_ACTA_PEDIDA, actas_faltantes

    partes, total, a_quien = [], 0, set()
    for reunion in actas_faltantes(db, hoy):
        vencidas = [s for s in reunion["solicitudes"].values() if s["vencida"]]
        if vencidas:
            total += len(vencidas)
            a_quien |= {s["pedida_a"] for s in vencidas}
            partes.append(f"{reunion['instance_label']}: {len(vencidas)}")
    if not total:
        return []
    titulo = (f"1 acta pedida hace más de {DIAS_ACTA_PEDIDA} días no ha llegado" if total == 1
              else f"{total} actas pedidas hace más de {DIAS_ACTA_PEDIDA} días no han llegado")
    return [_aviso("actas", "medio", titulo,
                   "; ".join(partes) + f". Conviene recordarle a {', '.join(sorted(a_quien))}.", {"page": "actas_archive"})]


def _respaldo(hoy: date) -> List[Dict]:
    if not ESTADO_RESPALDO.exists():
        return [_aviso("respaldo", "alto", "No hay copias de seguridad automáticas",
                       "La tarea diaria de copia no ha corrido todavía en este computador.")]
    try:
        datos = json.loads(ESTADO_RESPALDO.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    avisos = []
    ultima = datos.get("ultima_exitosa")
    dias = (hoy - datetime.fromisoformat(ultima).date()).days if ultima else None
    if not datos.get("ok") or dias is None or dias > 2:
        avisos.append(_aviso("respaldo", "alto", "La copia de seguridad no se está haciendo",
                             (datos.get("mensaje") or "") + (f" La última copia buena es de hace {dias} días." if dias else "")))
    drive = datos.get("drive") or {}
    if drive and not drive.get("ok"):
        avisos.append(_aviso("respaldo-drive", "medio", "La copia cifrada en el Drive institucional falló",
                             drive.get("mensaje") or "Revise que Google Drive esté abierto en este computador."))
    return avisos


FUENTES: List[Callable] = [_respaldo, _sabana, _rnmc, _solicitudes, _consejo, _actas, _agenda]


def avisos(db: Session, hoy: Optional[date] = None) -> Dict:
    hoy = hoy or date.today()
    lista: List[Dict] = []
    for fuente in FUENTES:
        try:
            lista += fuente(hoy) if fuente is _respaldo else fuente(db, hoy)
        except Exception:  # noqa: BLE001 - un aviso que falla no debe tumbar los demás
            db.rollback()
            logger.exception("Avisos: no se pudo calcular %s", fuente.__name__)
    lista.sort(key=lambda a: 0 if a["nivel"] == "alto" else 1)
    return {"fecha": hoy.isoformat(), "avisos": lista}
