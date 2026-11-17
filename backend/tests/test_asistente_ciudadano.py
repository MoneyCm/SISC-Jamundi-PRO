"""Asistente ciudadano del portal: rutas primero, sin cifras por barrio, nada interno y límite de preguntas."""
from datetime import date

import pytest

from services import asistente_ciudadano as c
from services import asistente_secretaria as asesor

HOY = date(2026, 11, 17)


@pytest.fixture(autouse=True)
def sin_base(monkeypatch):
    monkeypatch.setattr(asesor, "detectar_temas", lambda db, texto: {
        "delitos": ["Homicidio"] if "homicid" in asesor.normalizar(texto) else [],
        "entidades": [], "barrios": ["TERRANOVA"] if "terranova" in asesor.normalizar(texto) else [],
        "piscc": ["vif"] if "intrafamiliar" in asesor.normalizar(texto) else []})
    monkeypatch.setattr(asesor, "responder_periodo", lambda db, pregunta, periodo, hoy: {
        "respuesta": f"Hechos {periodo.etiqueta}: {pregunta}", "fuentes": ["Sábana de la Policía al 6 de noviembre de 2026"]})


@pytest.mark.parametrize("pregunta, ruta", [
    ("Mi esposo me pega, ¿qué hago?", "Línea 155"),
    ("Violencia intrafamiliar: ¿qué hago?", "Línea 155"),
    ("Mi hijo está siendo maltratado en el colegio", "Línea 141"),
    ("¿Cómo denuncio un delito?", "línea 122"),
    ("Auxilio, me están robando", "llame ya al 123"),
])
def test_una_situacion_personal_recibe_la_ruta(pregunta, ruta):
    r = c.responder(None, pregunta, [], HOY)
    assert r["tipo"] == "ruta" and ruta in r["respuesta"]


def test_sin_cifras_por_barrio():
    r = c.responder(None, "¿Cuántos hurtos hay en Terranova?", [], HOY)
    assert r["tipo"] == "barrio" and "Mi barrio" in r["respuesta"] and "menos de 3" in r["respuesta"]


def test_nada_del_seguimiento_interno():
    r = c.responder(None, "¿Qué compromisos tiene vencidos la Policía?", [], HOY)
    assert "interno" in r["respuesta"] and r["tipo"] == "ayuda"


def test_cifras_con_el_motor_verificado_y_sin_la_palabra_sabana():
    r = c.responder(None, "¿Cuántos homicidios van en 2026?", [], HOY)
    assert r["tipo"] == "cifras" and "del 1 de enero al 17 de noviembre de 2026" in r["respuesta"]
    assert "Sábana" not in " ".join(r["fuentes"]) and r["respuesta"].endswith("En una emergencia llame al 123.")


def test_sin_fechas_es_lo_corrido_del_anio_y_jamundi_no_es_un_barrio():
    r = c.responder(None, "¿Cómo van los homicidios en Jamundí?", [], HOY)
    assert "del 1 de enero al 17 de noviembre de 2026" in r["respuesta"] and "Jamundí" not in r["respuesta"]


def test_pregunta_de_seguimiento():
    historial = [{"sender": "user", "text": "¿Cuántos homicidios van en 2026?"}, {"sender": "ai", "text": "104"}]
    r = c.responder(None, "¿Y en 2025?", historial, HOY)
    assert "todo 2025" in r["respuesta"] and "homicidios" in r["respuesta"]


def test_violencia_intrafamiliar_con_cifras_de_mindefensa_y_la_ruta(monkeypatch):
    from services import piscc_historico as ph
    monkeypatch.setattr(ph, "cargar", lambda *a, **k: {"ultimo_mes": "2026-09", "series": {"vif": {
        "2025": {str(m): 20 for m in range(1, 13)}, "2026": {str(m): 30 for m in range(1, 10)}}}})
    r = c.responder(None, "¿Cuántos casos de violencia intrafamiliar hay?", [], HOY)
    assert "270 casos de enero a septiembre de 2026" in r["respuesta"] and "180; subió en 90" in r["respuesta"]
    assert "Línea 155" in r["respuesta"]


def test_saludo_recibe_ayuda():
    assert "¿Cuántos homicidios van en 2026?" in c.responder(None, "hola", [], HOY)["respuesta"]


def test_limite_de_preguntas_por_persona(monkeypatch):
    from fastapi import HTTPException
    from types import SimpleNamespace
    from middleware import rate_limit
    monkeypatch.setattr(rate_limit, "_RATE_LIMIT_ASISTENTE", 2)
    pedido = SimpleNamespace(headers={}, client=SimpleNamespace(host="10.9.9.9"))
    rate_limit.rate_limit_asistente(pedido)
    rate_limit.rate_limit_asistente(pedido)
    with pytest.raises(HTTPException) as error:
        rate_limit.rate_limit_asistente(pedido)
    assert error.value.status_code == 429
