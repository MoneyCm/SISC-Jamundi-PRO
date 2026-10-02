"""Archivo de actas: el original se guarda, solo se adjunta el mismo archivo y el listado trae todas las actas."""
import hashlib
from datetime import date

import pytest
from sqlalchemy.orm import Session

from db.models_council import CouncilActFile, CouncilActRead, CouncilActRequest
from db.session import engine
from services import council_commitments_service as svc


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def _acta(db, contenido=b"%PDF-1.4 acta de prueba", estado="CONFIRMADA"):
    fila = CouncilActRead(filename="Acta 99.pdf", sha256=hashlib.sha256(contenido).hexdigest(), instance="CONSEJO_SEGURIDAD",
                          act_number="99", act_date=date(2026, 9, 30), reading={"proposals": [{}, {}]}, status=estado,
                          result={"created": ["CS-2026-900"], "linked": ["CS-2026-001"], "skipped": []}, created_by="prueba")
    db.add(fila)
    db.commit()
    return fila


def test_solo_se_adjunta_el_mismo_archivo(db):
    fila = _acta(db)
    with pytest.raises(ValueError, match="no es el mismo"):
        svc.attach_act_file(db, str(fila.id), b"otro archivo", "otro.pdf", "mospina")
    assert svc.attach_act_file(db, str(fila.id), b"%PDF-1.4 acta de prueba", "Acta 99.pdf", "mospina")["has_file"]
    record, archivo = svc.get_act_file(db, str(fila.id))
    assert archivo.content == b"%PDF-1.4 acta de prueba" and archivo.content_type == "application/pdf"
    assert archivo.uploaded_by == "mospina"


def test_el_archivo_trae_todas_las_actas_con_su_estado(db):
    fila = _acta(db)
    pendiente = _acta(db, b"otra acta", estado="PENDIENTE")
    todas = {a["read_id"]: a for a in svc.act_archive(db)}
    assert todas[str(fila.id)]["commitments"] == 2 and todas[str(fila.id)]["has_file"] is False
    assert todas[str(pendiente.id)]["commitments"] == 2 and todas[str(pendiente.id)]["status"] == "PENDIENTE"


def test_sin_original_avisa(db):
    fila = _acta(db)
    with pytest.raises(LookupError):
        svc.get_act_file(db, str(fila.id))


def test_al_descartar_una_lectura_se_va_su_archivo(db):
    fila = _acta(db, b"lectura pendiente", estado="PENDIENTE")
    svc.save_act_file(db, fila, b"lectura pendiente", "pendiente.pdf", "mospina")
    svc.discard_act_read(db, str(fila.id))
    db.expire_all()
    assert db.query(CouncilActFile).filter(CouncilActFile.read_id == fila.id).count() == 0


def test_actas_faltantes_por_mes(db, monkeypatch):
    monkeypatch.setattr(svc, "ACTAS_ESPERADAS", {"PRUEBA_MENSUAL": {"frecuencia": "mensual", "responsables": "Secretaría técnica"}})
    for dia, nombre in ((date(2026, 1, 20), "Acta 01.pdf"), (date(2026, 3, 18), "Nota de Gemini – reunión (sin acta oficial)")):
        db.add(CouncilActRead(filename=nombre, sha256=hashlib.sha256(nombre.encode()).hexdigest(), instance="PRUEBA_MENSUAL",
                              act_date=dia, reading={}, status="CONFIRMADA", created_by="prueba"))
    db.commit()
    [faltan] = svc.actas_faltantes(db, hoy=date(2026, 5, 10))
    assert faltan["desde"] == "2026-01" and faltan["responsables"] == "Secretaría técnica"
    assert faltan["faltan"] == ["2026-02", "2026-04"]       # mayo aún no termina
    assert faltan["sin_acta_oficial"] == ["2026-03"]


def test_actas_faltantes_por_semana(db, monkeypatch):
    monkeypatch.setattr(svc, "ACTAS_ESPERADAS", {"PRUEBA_SEMANAL": {"frecuencia": "semanal", "responsables": None}})
    for dia in (date(2026, 9, 2), date(2026, 9, 17)):  # semanas del 31-ago y del 14-sep
        nombre = f"Acta {dia}.pdf"
        db.add(CouncilActRead(filename=nombre, sha256=hashlib.sha256(nombre.encode()).hexdigest(), instance="PRUEBA_SEMANAL",
                              act_date=dia, reading={}, status="CONFIRMADA", created_by="prueba"))
    db.commit()
    [faltan] = svc.actas_faltantes(db, hoy=date(2026, 10, 1))
    assert faltan["frecuencia"] == "semanal" and faltan["responsables"] is None
    assert faltan["desde"] == "2026-08-31" and faltan["ultima"] == "2026-09-17"
    assert faltan["faltan"] == ["2026-09-07", "2026-09-21"]  # la semana del 28-sep aún no termina


def _consejo_con_faltantes(db, monkeypatch):
    monkeypatch.setattr(svc, "ACTAS_ESPERADAS", {"PRUEBA_MENSUAL": {"frecuencia": "mensual", "responsables": "Nelson Ortiz"}})
    nombre = "Acta 01.pdf"
    db.add(CouncilActRead(filename=nombre, sha256=hashlib.sha256(nombre.encode()).hexdigest(), instance="PRUEBA_MENSUAL",
                          act_date=date(2026, 1, 20), reading={}, status="CONFIRMADA", created_by="prueba"))
    db.commit()


def test_pedir_actas_que_faltan(db, monkeypatch):
    _consejo_con_faltantes(db, monkeypatch)
    hoy = date(2026, 5, 10)
    assert svc.registrar_solicitud(db, "PRUEBA_MENSUAL", ["2026-02", "2026-03"], date(2026, 4, 1), "Nelson Ortiz",
                                   "por correo", "mospina", hoy=hoy) == {"registradas": 2, "repetidas": 0}
    [item] = svc.actas_faltantes(db, hoy=hoy)
    assert set(item["solicitudes"]) == {"2026-02", "2026-03"}
    assert item["solicitudes"]["2026-02"]["vencida"] is True and item["solicitudes"]["2026-02"]["dias"] == 39
    # pedirla otra vez actualiza la fecha y cuenta la vez
    svc.registrar_solicitud(db, "PRUEBA_MENSUAL", ["2026-02"], date(2026, 5, 5), "Nelson Ortiz", None, "mospina", hoy=hoy)
    [item] = svc.actas_faltantes(db, hoy=hoy)
    assert item["solicitudes"]["2026-02"]["veces"] == 2 and item["solicitudes"]["2026-02"]["vencida"] is False
    assert item["solicitudes"]["2026-02"]["nota"] == "por correo"
    assert svc.quitar_solicitudes(db, "PRUEBA_MENSUAL", ["2026-03"]) == {"quitadas": 1}
    assert set(svc.actas_faltantes(db, hoy=hoy)[0]["solicitudes"]) == {"2026-02"}


def test_no_se_pide_lo_que_no_falta(db, monkeypatch):
    _consejo_con_faltantes(db, monkeypatch)
    hoy = date(2026, 5, 10)
    with pytest.raises(ValueError, match="no están en la lista"):
        svc.registrar_solicitud(db, "PRUEBA_MENSUAL", ["2026-01"], hoy, "Nelson Ortiz", None, "mospina", hoy=hoy)
    with pytest.raises(ValueError, match="futura"):
        svc.registrar_solicitud(db, "PRUEBA_MENSUAL", ["2026-02"], date(2026, 6, 1), "Nelson Ortiz", None, "mospina", hoy=hoy)
    with pytest.raises(ValueError, match="no tiene actas"):
        svc.registrar_solicitud(db, "OTRA", ["2026-02"], hoy, "Nelson Ortiz", None, "mospina", hoy=hoy)
    assert db.query(CouncilActRequest).filter(CouncilActRequest.instance == "PRUEBA_MENSUAL").count() == 0


def test_aviso_de_actas_pedidas_que_no_llegan(db, monkeypatch):
    from services import avisos

    _consejo_con_faltantes(db, monkeypatch)
    hoy = date(2026, 5, 10)
    svc.registrar_solicitud(db, "PRUEBA_MENSUAL", ["2026-02", "2026-03"], date(2026, 4, 1), "Nelson Ortiz", None, "mospina", hoy=hoy)
    [aviso] = avisos._actas(db, hoy)
    assert aviso["titulo"] == "2 actas pedidas hace más de 15 días no han llegado"
    assert "Nelson Ortiz" in aviso["detalle"] and aviso["destino"] == {"page": "actas_archive"}
    assert avisos._actas(db, date(2026, 4, 10)) == []  # todavía dentro del plazo
