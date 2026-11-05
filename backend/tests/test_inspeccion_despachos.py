"""Cada expediente queda en la inspección que nombran sus anotaciones o en la de quien lo registró."""
from datetime import date, datetime

from db.models import SessionLocal
from db.models_inspecciones import (
    InspeccionActuacion, InspeccionExpediente, InspeccionFinanza, InspeccionFuncionario, InspeccionMedida,
)
from services import inspeccion_despachos as despachos


def test_inspeccion_en_texto():
    assert despachos.inspeccion_en_texto(
        "Resolución 3426 expedida por la Inspección Tercera de Policía de Jamundí") == "TERCERA"
    assert despachos.inspeccion_en_texto("SE REGISTRA EL PAGO - INSPECCION SEGUNDA DE POLICIA") == "SEGUNDA"
    assert despachos.inspeccion_en_texto("PAGO INSPECCION DE POLICIA SEGUNDA DE JAMUNDI") == "SEGUNDA"
    assert despachos.inspeccion_en_texto("el ciudadano se acerca a la primera inspección") == "PRIMERA"
    assert despachos.inspeccion_en_texto("EL CIUDADNO PRESENTA OPOSICION") is None
    assert despachos.inspeccion_en_texto("REMITIDA A LA INSPECCION DE POLICIA JAMUNDI") is None
    assert despachos.inspeccion_en_texto(None) is None


def test_documento_limpio():
    assert despachos.documento_limpio("12345678.0") == "12345678"
    assert despachos.documento_limpio(" 1112223334 ") == "1112223334"
    assert despachos.documento_limpio("nan") is None
    assert despachos.documento_limpio(None) is None


def _expediente(db, numero, actuaciones, finanza=None, estado="MEDIDA RATIFICADA"):
    expediente = InspeccionExpediente(numero_expediente=numero, localidad="CENTRO")
    db.add(expediente)
    db.flush()
    medida = InspeccionMedida(expediente_id=expediente.id, nombre_medida="MULTA GENERAL TIPO 2", estado_actual=estado)
    db.add(medida)
    db.flush()
    for i, (fecha, anotacion, registrador) in enumerate(actuaciones):
        db.add(InspeccionActuacion(medida_id=medida.id, fecha_actuacion=fecha, anotacion=anotacion,
                                   id_registrador=registrador, fuente_archivo="gestionadas.xls",
                                   fingerprint_hash=f"despachos-{numero}-{i}"))
    if finanza:
        db.add(InspeccionFinanza(medida_id=medida.id, valor_pagado=finanza[0], fecha_pago=finanza[1]))
    db.flush()
    return expediente


def test_asignar_y_gestion_por_inspeccion():
    db = SessionLocal()
    try:
        db.add_all([
            InspeccionFuncionario(documento="9000001", nombre="Funcionaria A", inspeccion="SEGUNDA", desde=date(2000, 1, 1)),
            # Trasladado a mitad de año: lo que registró después ya no es de la tercera.
            InspeccionFuncionario(documento="9000002", nombre="Funcionario B", inspeccion="TERCERA",
                                  desde=date(2000, 1, 1), hasta=date(2001, 6, 30)),
        ])
        db.flush()
        por_anotacion = _expediente(db, "DESP-2001-1", [
            (datetime(2001, 3, 1), "Resolución de pago 74, Inspección Tercera de Policía", "9000001"),
            (datetime(2001, 4, 1), "EL CIUDADANO PRESENTA OPOSICION", "9000001"),
        ], finanza=(233454, date(2001, 4, 1)), estado="PAGADO")
        por_funcionario = _expediente(db, "DESP-2001-2", [(datetime(2001, 5, 2), "SOLICITA LIQUIDACION", "9000001.0")])
        trasladado = _expediente(db, "DESP-2001-3", [(datetime(2001, 7, 10), "SOLICITA LIQUIDACION", "9000002")])
        antes_del_traslado = _expediente(db, "DESP-2001-4", [(datetime(2001, 6, 10), "OPOSICION", "9000002")])
        comparendo = _expediente(db, "DESP-2001-5", [(datetime(2001, 2, 1), None, None)], estado="PENDIENTE")

        despachos.asignar(db)

        assert (por_anotacion.inspeccion, por_anotacion.inspeccion_origen) == ("TERCERA", "ANOTACION")
        assert (por_funcionario.inspeccion, por_funcionario.inspeccion_origen) == ("SEGUNDA", "FUNCIONARIO")
        assert trasladado.inspeccion is None
        assert antes_del_traslado.inspeccion == "TERCERA"
        assert comparendo.inspeccion is None

        gestion = despachos.gestion_por_inspeccion(db, 2001)
        filas = {fila["inspeccion"]: fila for fila in gestion["inspecciones"]}
        assert filas["TERCERA"]["expedientes"] == 2
        assert filas["TERCERA"]["actuaciones"] == 3
        assert filas["TERCERA"]["pagadas"] == 1
        assert filas["TERCERA"]["recaudo"] == 233454
        assert filas["SEGUNDA"]["expedientes"] == 1
        assert filas[despachos.SIN_IDENTIFICAR]["expedientes"] == 1  # el trasladado
        # El comparendo pendiente no es gestión de ninguna inspección: va aparte.
        assert gestion["pendientes_sin_repartir"] == 1
        assert [fila["inspeccion"] for fila in gestion["inspecciones"]] == ["SEGUNDA", "TERCERA", despachos.SIN_IDENTIFICAR]
    finally:
        db.rollback()
        db.close()
