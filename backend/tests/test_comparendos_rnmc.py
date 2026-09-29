"""Cada comparendo (expediente) cuenta una vez, en la fecha de su primer registro."""
from datetime import date, datetime

from db.models import SessionLocal
from db.models_inspecciones import InspeccionActuacion, InspeccionExpediente, InspeccionMedida
from services import comparendos_rnmc


def test_expediente_counts_once_at_its_first_date():
    db = SessionLocal()
    try:
        # Año sin datos reales: el conteo parte de cero.
        assert comparendos_rnmc.contar(db, date(2001, 1, 1), date(2001, 12, 31)) == 0
        expediente = InspeccionExpediente(numero_expediente="UNIDAD-RNMC-2001-1", localidad="CENTRO")
        db.add(expediente)
        db.flush()
        for nombre, fechas in (("MULTA GENERAL TIPO 4", [datetime(2001, 3, 1), datetime(2001, 6, 1)]),
                               ("MEDIDA POR DEFINIR", [datetime(2001, 3, 2)])):
            medida = InspeccionMedida(expediente_id=expediente.id, nombre_medida=nombre)
            db.add(medida)
            db.flush()
            for i, fecha in enumerate(fechas):
                db.add(InspeccionActuacion(medida_id=medida.id, fecha_actuacion=fecha, fuente_archivo="reporte.xls",
                                           fingerprint_hash=f"unidad-rnmc-2001-{nombre[:5]}-{i}"))
        db.flush()

        assert comparendos_rnmc.contar(db, date(2001, 1, 1), date(2001, 12, 31)) == 1
        assert comparendos_rnmc.contar(db, date(2001, 3, 1), date(2001, 3, 31)) == 1
        assert comparendos_rnmc.contar(db, date(2001, 6, 1), date(2001, 6, 30)) == 0
        por_medida = dict(comparendos_rnmc.agrupar(db, InspeccionMedida.nombre_medida, date(2001, 1, 1), date(2001, 12, 31)))
        assert por_medida == {"MULTA GENERAL TIPO 4": 1, "MEDIDA POR DEFINIR": 1}
    finally:
        db.rollback()
        db.close()
