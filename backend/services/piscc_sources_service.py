import json
from datetime import date, datetime, time, timedelta
from pathlib import Path

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from services.piscc_goals import GOALS


SNAPSHOT = Path(__file__).resolve().parents[1] / "data" / "piscc" / "mindefensa.json"


def _parse_date(value):
    if not value:
        return None
    for pattern in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), pattern).date()
        except ValueError:
            pass
    return None


def _source_item(key, label, previous, current, cutoff, source):
    difference = current - previous
    variation = ((difference / previous) * 100) if previous else None
    weeks = max(1, min(52, ((cutoff - date(cutoff.year, 1, 1)).days // 7) + 1))
    projection = round((current / weeks) * 52)
    goal = GOALS[key]
    status = "favorable" if projection <= goal else ("critico" if difference > 0 else "alerta")
    variation_text = "Sin base comparable" if variation is None else f"{variation:+.1f} %".replace(".", ",")
    return {
        "id": key,
        "indicador": label,
        "countPrev": previous,
        "countBase": current,
        "diferenciaAbs": difference,
        "variacionPct": variation,
        "variacionStr": variation_text,
        "proyeccionAnual": projection,
        "status": status,
        "observacionTecnica": f"Corte independiente: {cutoff.isoformat()}. Proyección lineal ≈{projection}; meta {goal}.",
        "fuenteNombre": source,
        "fechaCorte": cutoff.isoformat(),
    }


def load_mindefensa(cutoff):
    if not SNAPSHOT.exists():
        return {}, ["MinDefensa no tiene un corte local disponible."]
    payload = json.loads(SNAPSHOT.read_text(encoding="utf-8-sig"))
    aliases = {
        "secuestro": ("secuestro", "Secuestro", "MinDefensa / Policía Nacional"),
        "extorsion": ("extors", "Extorsión", "MinDefensa / GAULA Policía"),
        "vif": ("intrafamiliar", "Violencia intrafamiliar", "MinDefensa / Policía Nacional"),
    }
    result = {}
    notices = []
    for key, (needle, label, source) in aliases.items():
        row = next((item for item in payload.get("indicadores", []) if needle in str(item.get("delito", "")).lower()), None)
        source_cutoff = _parse_date(row.get("ultimo_registro")) if row else None
        if not row or not source_cutoff or source_cutoff > cutoff:
            notices.append(f"{label}: sin corte verificable anterior o igual a {cutoff.isoformat()}.")
            continue
        result[key] = _source_item(key, label, int(row.get("anterior") or 0), int(row.get("actual") or 0), source_cutoff, source)
    return result, notices


def load_rnmc(db: Session, cutoff):
    """Comportamientos contrarios a la convivencia: comparendos únicos (expedientes) del RNMC.

    Sale de las tablas de Inspecciones, que reciben los reportes del RNMC (comparendos y medidas
    gestionadas). Cada expediente se cuenta una vez, en la fecha de su primer registro (la del
    hecho en el reporte de comparendos).
    """
    first_dates = """
        SELECT e.numero_expediente, MIN(a.fecha_actuacion)::date AS fecha
        FROM inspeccion_expedientes e
        JOIN inspeccion_medidas m ON m.expediente_id = e.id
        JOIN inspeccion_actuaciones a ON a.medida_id = m.id
        GROUP BY e.numero_expediente
    """

    def count(desde, hasta):
        return db.execute(text(f"SELECT COUNT(*) FROM ({first_dates}) t WHERE fecha >= :desde AND fecha <= :hasta"),
                          {"desde": desde, "hasta": hasta}).scalar() or 0

    source_cutoff = db.execute(text(f"SELECT MAX(fecha) FROM ({first_dates}) t WHERE fecha <= :hasta"),
                               {"hasta": cutoff}).scalar()
    if not source_cutoff:
        return None
    current = count(date(source_cutoff.year, 1, 1), source_cutoff)
    previous = count(date(source_cutoff.year - 1, 1, 1), source_cutoff.replace(year=source_cutoff.year - 1))
    return _source_item("convivencia", "Comportamientos Contrarios a la Convivencia", previous, current, source_cutoff, "RNMC / Inspecciones de Policía")


def get_piscc_sources(db: Session, cutoff: date):
    sources, notices = load_mindefensa(cutoff)
    try:
        rnmc = load_rnmc(db, cutoff)
        if rnmc:
            sources["convivencia"] = rnmc
        else:
            notices.append("Convivencia: RNMC no tiene registros hasta el corte solicitado.")
    except Exception:
        notices.append("Convivencia: no fue posible consultar RNMC.")
    return {"sources": sources, "notices": notices, "requested_cutoff": cutoff.isoformat()}
