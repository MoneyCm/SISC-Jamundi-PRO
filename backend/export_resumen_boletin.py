"""Genera exports/resumen_boletin.json para el reporte ejecutivo semanal.

Lee la base local de SISC y produce el contrato esperado por
C:\\Proyectos\\reporte-ejecutivo-semanal\\fuentes\\leer_sisc.py.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from sqlalchemy import func
from sqlalchemy.exc import OperationalError

from db.models_auth import User
from db.models_hechos_seguridad import HechoSeguridad
from db.models_inspecciones import InspeccionActuacion, InspeccionMedida
from db.session import SessionLocal

PROJECT_DIR = BASE_DIR.parent
DEFAULT_OUTPUT = PROJECT_DIR / "exports" / "resumen_boletin.json"

OPEN_STATES = {"ABIERTO", "ABIERTA", "PENDIENTE", "EN PROCESO", "EN_PROCESO", "RATIFICADA", "COBRO COACTIVO"}
CLOSED_STATES = {"CERRADO", "CERRADA", "CUMPLIDA", "CUMPLIDO", "PAGADO", "MEDIDA CERRADA", "NO IMPUESTA", "MEDIDA NO IMPUESTA"}


def parse_date(value: str | None, fallback: date) -> date:
    if not value:
        return fallback
    return datetime.strptime(value, "%Y-%m-%d").date()


def default_period() -> tuple[date, date]:
    end = date.today()
    start = end - timedelta(days=6)
    return start, end


def state_bucket(value: str | None) -> str:
    normalized = str(value or "").strip().upper()
    if normalized in CLOSED_STATES:
        return "cumplida"
    if normalized in OPEN_STATES:
        return "pendiente"
    return "abierta" if normalized else "pendiente"


def generate_summary(start: date, end: date) -> dict:
    db = SessionLocal()
    try:
        hechos = db.query(HechoSeguridad).filter(
            HechoSeguridad.fecha_evento >= start,
            HechoSeguridad.fecha_evento <= end,
        ).all()
        eventos_por_tipo = Counter(h.conducta_estandar or h.conducta_original or "Sin clasificar" for h in hechos)

        actuaciones = db.query(InspeccionActuacion).filter(
            func.date(InspeccionActuacion.fecha_actuacion) >= start,
            func.date(InspeccionActuacion.fecha_actuacion) <= end,
        ).all()

        medidas = db.query(InspeccionMedida).all()
        abiertas = 0
        cerradas = 0
        acciones = []
        for medida in medidas:
            bucket = state_bucket(medida.estado_actual)
            if bucket == "cumplida":
                cerradas += 1
            else:
                abiertas += 1
            if len(acciones) < 50:
                acciones.append({
                    "estado": bucket,
                    "responsable": medida.tipo_seguimiento or "Inspeccion",
                    "foco": medida.nombre_medida,
                    "fecha_inicio": medida.fecha_inicio.isoformat() if medida.fecha_inicio else None,
                    "fecha_fin": medida.fecha_fin.isoformat() if medida.fecha_fin else None,
                })

        usuarios_total = db.query(User).count()
        usuarios_activos = db.query(User).filter(User.is_active.is_(True)).count()

        return {
            "contrato": "boletin_seguimiento.v1",
            "fecha_corte": end.isoformat(),
            "periodo": {"inicio": start.isoformat(), "fin": end.isoformat()},
            "eventos_semana": {
                "total": len(hechos),
                "por_tipo": dict(eventos_por_tipo.most_common()),
            },
            "boletines": {
                "total": len(actuaciones),
                "por_modulo": {"Inspecciones": len(actuaciones)},
            },
            "usuarios": {
                "activos_semana": usuarios_activos,
                "total_registrados": usuarios_total,
                "por_dependencia": {},
            },
            "acciones": acciones,
            "acciones_resumen": {
                "abiertas": abiertas,
                "cerradas": cerradas,
                "focos_con_seguimiento": sum(1 for item in acciones if item.get("foco")),
            },
            "generado_en": datetime.now().isoformat(timespec="seconds"),
            "fuente": "SISC-Jamundi-PRO",
        }
    finally:
        db.close()


def main() -> int:
    start_default, end_default = default_period()
    parser = argparse.ArgumentParser(description="Exporta resumen semanal SISC para el reporte ejecutivo.")
    parser.add_argument("--inicio", help="Fecha inicial YYYY-MM-DD")
    parser.add_argument("--fin", help="Fecha final YYYY-MM-DD")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Ruta de salida JSON")
    args = parser.parse_args()

    start = parse_date(args.inicio, start_default)
    end = parse_date(args.fin, end_default)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    try:
        summary = generate_summary(start, end)
    except OperationalError as exc:
        print("No se pudo conectar a PostgreSQL. Enciende la base de datos local de SISC en el puerto 5432 y vuelve a ejecutar.")
        print(str(exc).split("\n")[0])
        return 2

    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
