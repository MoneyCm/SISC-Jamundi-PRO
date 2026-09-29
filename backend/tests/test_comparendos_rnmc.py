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

        # Visto desde fin de 2001, el último comparendo (1 de marzo) tiene más de 35 días: toca pedir los reportes.
        estado = comparendos_rnmc.estado_carga(db, date(2001, 12, 31))
        assert estado["corte"] == "2001-03-01"
        assert estado["atrasado"] is True
        assert comparendos_rnmc.estado_carga(db, date(2001, 3, 20))["atrasado"] is False
    finally:
        db.rollback()
        db.close()


def test_article_labels_are_plain_spanish():
    assert comparendos_rnmc.numero_articulo("Art. 35 - Comportamientos que afectan las relaciones") == "35"
    assert comparendos_rnmc.etiqueta_articulo("Art. 27 - Comportamientos que ponen en riesgo la vida e integridad") \
        == "Riñas, amenazas y porte de armas o elementos peligrosos"
    # Un artículo sin etiqueta propia usa el texto oficial.
    assert comparendos_rnmc.etiqueta_articulo("Art. 999 - COMPORTAMIENTOS NUEVOS") == "Comportamientos nuevos"


def test_no_compara_con_un_periodo_sin_datos_completos():
    db = SessionLocal()
    try:
        # Solo hay comparendos de enero a mayo de 2002 (dos expedientes).
        for i, fecha in enumerate([datetime(2002, 1, 3), datetime(2002, 5, 28)]):
            expediente = InspeccionExpediente(numero_expediente=f"UNIDAD-RNMC-2002-{i}", localidad="CENTRO")
            db.add(expediente)
            db.flush()
            medida = InspeccionMedida(expediente_id=expediente.id, nombre_medida="MULTA GENERAL TIPO 2")
            db.add(medida)
            db.flush()
            db.add(InspeccionActuacion(medida_id=medida.id, fecha_actuacion=fecha, fuente_archivo="reporte.xls",
                                       fingerprint_hash=f"unidad-rnmc-2002-{i}"))
        db.flush()
        assert comparendos_rnmc.cubre(db, date(2002, 1, 1), date(2002, 5, 31)) is True
        assert comparendos_rnmc.cubre(db, date(2002, 1, 1), date(2002, 12, 31)) is False
    finally:
        db.rollback()
        db.close()
