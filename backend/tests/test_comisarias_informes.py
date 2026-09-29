"""Informes aprobados de las Comisarías: solo APPROVED, el último por Comisaría; los pendientes solo se cuentan."""
from datetime import date

from db.models import SessionLocal
from db.models_institutional import InstitutionalDataBatch, InstitutionalIndicator
from api.comisarias import informes


def test_solo_el_ultimo_aprobado_por_comisaria():
    db = SessionLocal()
    try:
        antes = informes(db, None)
        viejo = InstitutionalDataBatch(program="COMISARIAS", reporting_entity="Comisaria 1", period="2001-01",
                                       cutoff_date=date(2001, 1, 31), validation_status="APPROVED", version=1,
                                       source_reference="prueba", submitted_by="prueba")
        pendiente = InstitutionalDataBatch(program="COMISARIAS", reporting_entity="Comisaria 1", period="2001-02",
                                           cutoff_date=date(2001, 2, 28), validation_status="PENDING", version=1,
                                           source_reference="prueba", submitted_by="prueba")
        db.add_all([viejo, pendiente])
        db.flush()
        db.add(InstitutionalIndicator(batch_id=viejo.id, indicator="Prueba", value=5, unit="casos"))
        db.flush()
        despues = informes(db, None)
        assert despues["pendientes"] == antes["pendientes"] + 1
        # Un aprobado más antiguo no reemplaza al informe vigente de esa Comisaría.
        periodo = lambda datos: next((i["periodo"] for i in datos["informes"] if "Primera" in i["entidad"]), None)
        if periodo(antes):
            assert periodo(despues) == periodo(antes)
        else:
            assert periodo(despues) == "2001-01"
    finally:
        db.rollback()
        db.close()
