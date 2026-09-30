"""Avisos de Inicio: se ordenan por nivel y un aviso que falla no tumba los demás."""
from datetime import date

from db.models import SessionLocal
from services import avisos as modulo


def test_orden_y_fallas_aisladas(monkeypatch):
    def medio(db, hoy):
        return [modulo._aviso("a", "medio", "Medio", "detalle")]

    def alto(db, hoy):
        return [modulo._aviso("b", "alto", "Alto", "detalle")]

    def roto(db, hoy):
        raise RuntimeError("fuente caída")

    monkeypatch.setattr(modulo, "FUENTES", [medio, roto, alto])
    db = SessionLocal()
    try:
        resultado = modulo.avisos(db, date(2026, 9, 29))
    finally:
        db.close()
    assert [a["clave"] for a in resultado["avisos"]] == ["b", "a"]


def test_fecha_en_palabras():
    assert modulo._fecha("2026-09-12") == "12 de septiembre"
